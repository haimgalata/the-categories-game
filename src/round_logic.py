from __future__ import annotations

import asyncio
import logging
import random
from typing import List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes

from .categories import load_categories
from .config import get_settings
from .game_state import (
    finalize_round,
    get_game,
    set_round_prompt,
    set_round_message_id,
    set_pinned_message_id,
    is_round_active,
    set_countdown_active,
    is_game_over,
    add_points,
    get_scores,
    reset_game,
    get_or_create_game,
    get_round_duration,
    get_time_remaining,
)
from .models import RoundResult, ValidatorInput, new_answer, new_round, now_ms
from .scoring import score_by_position
from .storage import save_answer, save_round, has_answer_been_used
from .validation import validate_submission

logger = logging.getLogger(__name__)

LEADERBOARD_TOP_N = 5
COUNTDOWN_SECONDS = 5
TIMER_SEGMENTS = 10


def pick_letter() -> str:
    return random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def pick_category(categories: List[str]) -> str:
    if not categories:
        raise ValueError("categories list is empty")
    return random.choice(categories)


# -------------------------------------------------
# Start / schedule / cancel
# -------------------------------------------------

async def start_round(
    chat_id: int,
    app: Application,
    *,
    countdown_message_id: int | None = None,
    countdown_prefix: str = "⏳ Starting in",
    intro_text: str = "",
) -> None:
    if is_round_active(chat_id):
        return

    _cancel_round_jobs(chat_id, app)
    if countdown_message_id:
        set_countdown_active(chat_id, True)
        for remaining in range(COUNTDOWN_SECONDS - 1, 0, -1):
            await asyncio.sleep(1)
            if is_round_active(chat_id):
                set_countdown_active(chat_id, False)
                return
            try:
                await app.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=countdown_message_id,
                    text=_format_countdown_text(remaining, prefix=countdown_prefix, intro_text=intro_text),
                )
            except Exception as exc:
                logger.debug("Initial countdown edit skipped: %s", exc)
        set_countdown_active(chat_id, False)
        await _send_round_prompt(chat_id, app)
        return

    set_countdown_active(chat_id, False)
    await _send_round_prompt(chat_id, app)


def _format_countdown_text(remaining: int, *, prefix: str, intro_text: str = "") -> str:
    countdown_line = f"{prefix} {remaining}..."
    if not intro_text:
        return countdown_line
    return f"{intro_text}\n\n{countdown_line}"


async def _send_round_prompt(chat_id: int, app: Application) -> None:
    _cancel_round_jobs(chat_id, app)

    letter = pick_letter()
    category = pick_category(load_categories())
    set_round_prompt(chat_id, letter, category)

    duration = get_round_duration(chat_id)
    current_game = get_game(chat_id)
    round_message = await app.bot.send_message(
        chat_id=chat_id,
        text=_build_round_prompt_text(current_game, duration, duration),
    )
    set_round_message_id(chat_id, round_message.message_id)
    _schedule_round_end(chat_id, app, duration)
    _schedule_round_tick(chat_id, app)

    settings = get_settings()
    if settings.enable_pinning:
        try:
            if current_game and current_game.pinned_message_id:
                await app.bot.unpin_chat_message(chat_id=chat_id, message_id=current_game.pinned_message_id)
            await app.bot.pin_chat_message(chat_id=chat_id, message_id=round_message.message_id, disable_notification=True)
            set_pinned_message_id(chat_id, round_message.message_id)
        except Exception as exc:
            logger.warning("Failed to pin round message: %s", exc)


def _schedule_round_end(chat_id: int, app: Application, seconds: int):
    return app.job_queue.run_once(
        _end_round_job,
        when=seconds,
        data={"chat_id": chat_id},
        name=f"round_end_{chat_id}",
    )


def _schedule_round_tick(chat_id: int, app: Application):
    return app.job_queue.run_repeating(
        _round_tick_job,
        interval=1,
        first=1,
        data={"chat_id": chat_id},
        name=f"round_tick_{chat_id}",
    )


def _cancel_round_jobs(chat_id: int, app: Application):
    for job_name in (
        f"round_end_{chat_id}",
        f"round_tick_{chat_id}",
        f"next_round_countdown_{chat_id}",
        f"next_round_start_{chat_id}",
    ):
        jobs = app.job_queue.get_jobs_by_name(job_name)
        for job in jobs:
            job.schedule_removal()


async def _end_round_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    await end_round(chat_id, context.application)


async def _round_tick_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    if not is_round_active(chat_id):
        context.job.schedule_removal()
        return

    game = get_game(chat_id)
    if not game or not game.round_message_id:
        context.job.schedule_removal()
        return

    total_time = max(1, get_round_duration(chat_id))
    remaining = max(0, min(total_time, get_time_remaining(chat_id)))

    try:
        await context.application.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game.round_message_id,
            text=_build_round_prompt_text(game, total_time, remaining),
        )
    except Exception as exc:
        logger.debug("Round timer edit skipped: %s", exc)

    if remaining <= 0:
        context.job.schedule_removal()
        await end_round(chat_id, context.application)


def _build_round_prompt_text(game, total_time: int, time_left: int) -> str:
    return (
        f"🎮 Round {game.current_round}/{game.max_rounds}\n"
        f"🔠 Letter: {game.round_letter}\n"
        f"📚 Category: {game.round_category}\n"
        f"⏱️ Time left: {time_left}s\n"
        f"{_build_segmented_timer_bar(time_left=time_left, total_time=total_time)}"
    )


def _build_segmented_timer_bar(*, time_left: int, total_time: int, segments: int = TIMER_SEGMENTS) -> str:
    safe_total = max(1, total_time)
    safe_segments = max(1, segments)
    clamped_left = max(0, min(safe_total, time_left))
    filled = int(round((clamped_left / safe_total) * safe_segments))
    filled = max(0, min(safe_segments, filled))
    empty = safe_segments - filled
    return ("🟩 " * filled + "⬜ " * empty).strip()


# -------------------------------------------------
# End round — validate, score, persist
# -------------------------------------------------

async def end_round(chat_id: int, app: Application) -> None:
    if not is_round_active(chat_id):
        return

    _cancel_round_jobs(chat_id, app)

    result: RoundResult = finalize_round(chat_id)
    game = get_or_create_game(chat_id)

    # --- Create round record and save ---
    round_obj = new_round(
        game_id=result.game_id,
        round_number=result.round_number,
        letter=result.letter,
        category=result.category,
    )
    state_game = get_game(chat_id)
    if state_game and state_game.round_id:
        round_obj.round_id = state_game.round_id
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

    accepted_answers: list[str] = []
    round_rows: list[str] = []

    for draft in sorted_answers:
        validation = validate_submission(
            ValidatorInput(
                letter=result.letter,
                category=result.category,
                answer=draft.text,
                accepted_answers=accepted_answers,
                round_active=True,
                time_remaining=1,
                player_name=draft.player_name,
                message_id=draft.message_id,
                round_id=state_game.round_id if state_game else round_obj.round_id,
            )
        )

        corrected = validation.corrected_answer or draft.text

        if not validation.valid:
            _try_save_answer(
                game, round_obj, draft, valid=False, score=0,
                corrected=corrected, letter=result.letter, category=result.category,
            )
            round_rows.append(f"• {draft.player_name} — {corrected} — ❌ Invalid")
            continue

        # Check duplicate in DB (catches both cross-round AND within-round dupes)
        try:
            if has_answer_been_used(game.game_id, result.letter, result.category, corrected):
                _try_save_answer(
                    game, round_obj, draft, valid=False, score=0,
                    corrected=corrected, letter=result.letter, category=result.category,
                )
                round_rows.append(f"• {draft.player_name} — {corrected} — ❌ Duplicate")
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
        accepted_answers.append(corrected)
        round_rows.append(f"• {draft.player_name} — {corrected} — ✅ Accepted")
        valid_position += 1

    # --- Single round summary message ---
    rows_text = "\n".join(round_rows) if round_rows else "No submissions this round."
    summary_text = (
        f"📊 Round {result.round_number} Results\n"
        f"🔠 {result.letter} | 📚 {result.category}\n\n"
        f"{rows_text}"
    )

    if is_game_over(chat_id):
        await app.bot.send_message(chat_id=chat_id, text=summary_text)
        if not game.is_group_mode:
            # Keep private mode behavior with a separate leaderboard call.
            try:
                await _send_leaderboard(chat_id, app, top_n=LEADERBOARD_TOP_N)
            except Exception as exc:
                logger.error("Failed to send leaderboard: %s", exc)
        await show_final_scores(chat_id, app)
    else:
        end_phase_text = f"{summary_text}\n\n⏳ Next round in {COUNTDOWN_SECONDS}..."
        countdown_message = await app.bot.send_message(chat_id=chat_id, text=end_phase_text)
        _schedule_next_round_countdown(
            chat_id,
            app,
            seconds=COUNTDOWN_SECONDS,
            message_id=countdown_message.message_id,
            summary_text=summary_text,
        )


def _schedule_next_round_countdown(
    chat_id: int,
    app: Application,
    *,
    seconds: int,
    message_id: int,
    summary_text: str,
) -> None:
    app.job_queue.run_repeating(
        _next_round_countdown_job,
        interval=1,
        first=1,
        data={
            "chat_id": chat_id,
            "message_id": message_id,
            "summary_text": summary_text,
            "remaining": max(0, seconds),
        },
        name=f"next_round_countdown_{chat_id}",
    )


async def _next_round_countdown_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    message_id = job_data["message_id"]
    summary_text = job_data["summary_text"]
    remaining = max(0, int(job_data.get("remaining", 0)) - 1)
    job_data["remaining"] = remaining

    try:
        await context.application.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"{summary_text}\n\n⏳ Next round in {remaining}...",
        )
    except Exception as exc:
        logger.debug("Next-round countdown edit skipped: %s", exc)

    if remaining > 0:
        return

    context.job.schedule_removal()
    chat_id = context.job.data["chat_id"]
    await start_round(chat_id, context.application)


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

async def show_final_scores(chat_id: int, app: Application):
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Start Game 🎮", callback_data="start_game")]]
    )
    scores = get_scores(chat_id)
    if scores:
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        lines: list[str] = []
        for index, (user_id, points) in enumerate(sorted_scores, start=1):
            try:
                user = await app.bot.get_chat_member(chat_id, user_id)
                name = user.user.first_name
            except Exception:
                name = str(user_id)
            lines.append(f"{index}. {name} - {points} pts")
        ranking_block = "\n".join(lines)
    else:
        ranking_block = "No points were scored."
    final_text = (
        "🏁 Final Results\n\n"
        f"{ranking_block}\n\n"
        "Tap below to start a new game."
    )
    await app.bot.send_message(chat_id, final_text, reply_markup=keyboard)
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


