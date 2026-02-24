from __future__ import annotations

import logging
import random
import uuid
from typing import List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes

from .categories import load_categories
from .game_state import (
    finalize_round,
    set_round_prompt,
    is_round_active,
    is_game_over,
    add_points,
    get_scores,
    reset_game,
    get_or_create_game,
    get_round_duration,
)
from .models import RoundResult, new_answer, new_round, now_ms
from .scoring import score_by_position
from .storage import save_answer, save_round, has_answer_been_used, upsert_player_stats
from .validation import validate_answer_groq

logger = logging.getLogger(__name__)

LEADERBOARD_TOP_N = 5


def pick_letter() -> str:
    return random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def pick_category(categories: List[str]) -> str:
    if not categories:
        raise ValueError("categories list is empty")
    return random.choice(categories)


# -------------------------------------------------
# Start / schedule / cancel
# -------------------------------------------------

async def start_round(chat_id: int, app: Application) -> None:
    if is_round_active(chat_id):
        return

    _cancel_existing_job(chat_id, app)

    letter = pick_letter()
    category = pick_category(load_categories())

    set_round_prompt(chat_id, letter, category)

    duration = get_round_duration(chat_id)

    await app.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🎯 Round started!\n\n"
            f"Letter: {letter}\n"
            f"Category: {category}\n\n"
            f"You have {duration} seconds!"
        ),
    )

    schedule_round_end(chat_id, app, duration)


def schedule_round_end(chat_id: int, app: Application, seconds: int):
    return app.job_queue.run_once(
        _end_round_job,
        when=seconds,
        data={"chat_id": chat_id},
        name=f"round_end_{chat_id}",
    )


def _cancel_existing_job(chat_id: int, app: Application):
    job_name = f"round_end_{chat_id}"
    jobs = app.job_queue.get_jobs_by_name(job_name)
    for job in jobs:
        job.schedule_removal()


async def _end_round_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    await end_round(chat_id, context.application)


# -------------------------------------------------
# End round — validate, score, persist
# -------------------------------------------------

async def end_round(chat_id: int, app: Application) -> None:
    if not is_round_active(chat_id):
        return

    _cancel_existing_job(chat_id, app)

    result: RoundResult = finalize_round(chat_id)
    game = get_or_create_game(chat_id)

    await app.bot.send_message(
        chat_id=chat_id,
        text=(
            f"⏰ Time's up!\n\n"
            f"Round {result.round_number} finished.\n"
            f"Answers received: {len(result.answers)}"
        ),
    )

    # --- Create round record and save ---
    round_obj = new_round(
        game_id=result.game_id,
        round_number=result.round_number,
        letter=result.letter,
        category=result.category,
    )
    round_obj.ended_at_ms = now_ms()
    try:
        save_round(round_obj)
    except Exception as exc:
        logger.error("Failed to save round: %s", exc)

    # --- Sort answers by response time (fastest first) ---
    sorted_answers = sorted(result.answers, key=lambda d: d.ts_ms)

    # --- Validate, check duplicates, score by position ---
    # Process one-by-one so each valid answer is saved to DB immediately,
    # allowing has_answer_been_used to catch within-round duplicates.
    valid_position = 0

    for draft in sorted_answers:
        try:
            validation = validate_answer_groq(
                draft.text,
                result.letter,
                result.category,
            )
        except Exception as exc:
            logger.error("Groq validation failed for '%s': %s", draft.text, exc)
            _try_save_answer(
                game, round_obj, draft, valid=False, score=0,
                corrected=draft.text, letter=result.letter, category=result.category,
            )
            continue

        corrected = validation.corrected or draft.text

        if not validation.valid:
            _try_save_answer(
                game, round_obj, draft, valid=False, score=0,
                corrected=corrected, letter=result.letter, category=result.category,
            )
            continue

        # Check duplicate in DB (catches both cross-round AND within-round dupes)
        try:
            if has_answer_been_used(game.game_id, result.letter, result.category, corrected):
                await app.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ \"{corrected}\" was already used this game!",
                )
                _try_save_answer(
                    game, round_obj, draft, valid=False, score=0,
                    corrected=corrected, letter=result.letter, category=result.category,
                )
                continue
        except Exception as exc:
            logger.error("DB duplicate check failed: %s", exc)

        # Valid and unique — score by position and save to DB immediately
        points = score_by_position(valid_position)
        add_points(chat_id, draft.user_id, points)
        _try_save_answer(
            game, round_obj, draft, valid=True, score=points,
            corrected=corrected, letter=result.letter, category=result.category,
        )
        valid_position += 1

    # --- Show leaderboard after each round ---
    await _send_leaderboard(chat_id, app, top_n=LEADERBOARD_TOP_N)

    # --- Game flow: continue or ask ---
    if is_game_over(chat_id):
        await _ask_continue_or_finish(chat_id, app)
    else:
        await start_round(chat_id, app)


def _try_save_answer(game, round_obj, draft, *, valid, score, corrected, letter, category):
    """Best-effort save an answer to MongoDB."""
    try:
        answer = new_answer(
            game_id=game.game_id,
            round_id=round_obj.round_id,
            user_id=draft.user_id,
            raw_text=draft.text,
            corrected_text=corrected,
            valid=valid,
            score=score,
            response_ms=int(draft.ts_ms - game.round_started_ms),
            username="",
            letter=letter,
            category=category,
        )
        save_answer(answer)
    except Exception as exc:
        logger.error("Failed to save answer: %s", exc)


# -------------------------------------------------
# Continue or finish
# -------------------------------------------------

async def _ask_continue_or_finish(chat_id: int, app: Application):
    keyboard = [
        [
            InlineKeyboardButton("▶️ One more round", callback_data="continue_game"),
            InlineKeyboardButton("🏁 Finish game", callback_data="finish_game"),
        ]
    ]
    await app.bot.send_message(
        chat_id=chat_id,
        text="🎮 5 rounds completed! Do you want to continue or finish?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# -------------------------------------------------
# Final scores
# -------------------------------------------------

async def show_final_scores(chat_id: int, app: Application):
    scores = get_scores(chat_id)

    if not scores:
        text = "🏁 Game Over!\nNo points scored."
    else:
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        text = "🏁 Game Over!\n\n📊 Final Scores:\n\n"

        medals = ["🥇", "🥈", "🥉"]

        for i, (user_id, points) in enumerate(sorted_scores):
            try:
                user = await app.bot.get_chat_member(chat_id, user_id)
                name = user.user.first_name
            except Exception:
                name = str(user_id)
            medal = medals[i] if i < 3 else "•"
            text += f"{medal} {name} - {points} pts\n"

    await app.bot.send_message(chat_id, text)
    reset_game(chat_id)


# -------------------------------------------------
# Leaderboard
# -------------------------------------------------

async def _send_leaderboard(chat_id: int, app: Application, top_n: int = 5):
    scores = get_scores(chat_id)

    if not scores:
        await app.bot.send_message(chat_id, "📊 Leaderboard: No scores yet.")
        return

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    if top_n:
        sorted_scores = sorted_scores[:top_n]

    text = "📊 Leaderboard:\n\n"
    for user_id, points in sorted_scores:
        try:
            user = await app.bot.get_chat_member(chat_id, user_id)
            name = user.user.first_name
        except Exception:
            name = str(user_id)
        text += f"{name} - {points} pts\n"

    await app.bot.send_message(chat_id, text)
