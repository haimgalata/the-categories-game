from __future__ import annotations

import random
from typing import List

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
)
from .models import RoundResult
from .validation import validate_answer_groq


ROUND_DURATION_SECONDS = 5


def pick_letter() -> str:
    return random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def pick_category(categories: List[str]) -> str:
    if not categories:
        raise ValueError("categories list is empty")
    return random.choice(categories)


async def start_round(chat_id: int, app: Application) -> None:
    if is_round_active(chat_id):
        return

    _cancel_existing_job(chat_id, app)

    letter = pick_letter()
    category = pick_category(load_categories())

    set_round_prompt(chat_id, letter, category)

    await app.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🎯 Round started!\n\n"
            f"Letter: {letter}\n"
            f"Category: {category}\n\n"
            f"You have {ROUND_DURATION_SECONDS} seconds!"
        ),
    )

    schedule_round_end(chat_id, app, ROUND_DURATION_SECONDS)


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


async def end_round(chat_id: int, app: Application) -> None:
    if not is_round_active(chat_id):
        return

    # ❗ חשוב: לבטל טיימר קיים
    _cancel_existing_job(chat_id, app)

    result: RoundResult = finalize_round(chat_id)

    await app.bot.send_message(
        chat_id=chat_id,
        text=(
            f"⏰ Time's up!\n\n"
            f"Round {result.round_number} finished.\n"
            f"Answers received: {len(result.answers)}"
        ),
    )

    # --- Validation + Scoring ---
    for draft in result.answers:
        try:
            validation = validate_answer_groq(
                draft.text,
                result.letter,
                result.category,
            )
        except Exception:
            continue

        if validation.valid:
            add_points(chat_id, draft.user_id, 1)

    # --- Game Flow ---
    if is_game_over(chat_id):
        await _show_final_scores(chat_id, app)
    else:
        await start_round(chat_id, app)


async def _show_final_scores(chat_id: int, app: Application):
    scores = get_scores(chat_id)

    if not scores:
        text = "🏁 Game Over!\nNo points scored."
    else:
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        text = "🏁 Game Over!\n\n📊 Final Scores:\n\n"

        medals = ["🥇", "🥈", "🥉"]

        for i, (user_id, points) in enumerate(sorted_scores):
            user = await app.bot.get_chat_member(chat_id, user_id)
            name = user.user.first_name
            medal = medals[i] if i < 3 else "•"
            text += f"{medal} {name} - {points} pts\n"

    await app.bot.send_message(chat_id, text)
    reset_game(chat_id)
