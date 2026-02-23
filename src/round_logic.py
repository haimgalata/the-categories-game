from __future__ import annotations

import random
from typing import List

from telegram.ext import Application, ContextTypes

from .categories import load_categories
from .game_state import (
    finalize_round,
    set_round_prompt,
    is_round_active,
)
from .models import RoundResult


ROUND_DURATION_SECONDS = 30


# -------------------------
# Selection helpers
# -------------------------

def pick_letter() -> str:
    return random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def pick_category(categories: List[str]) -> str:
    if not categories:
        raise ValueError("categories list is empty")
    return random.choice(categories)


# -------------------------
# Round lifecycle
# -------------------------

async def start_round(chat_id: int, app: Application) -> None:
    """
    Start a new round safely.
    """

    # Prevent double round
    if is_round_active(chat_id):
        return

    # Cancel any leftover scheduled job
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
    """
    Schedule round ending using PTB JobQueue.
    """

    return app.job_queue.run_once(
        _end_round_job,
        when=seconds,
        data={"chat_id": chat_id},
        name=f"round_end_{chat_id}",
    )


def _cancel_existing_job(chat_id: int, app: Application) -> None:
    """
    Cancel previously scheduled round-end job (if exists).
    """
    job_name = f"round_end_{chat_id}"
    current_jobs = app.job_queue.get_jobs_by_name(job_name)

    for job in current_jobs:
        job.schedule_removal()


async def _end_round_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Internal JobQueue callback.
    """
    chat_id = context.job.data["chat_id"]
    await end_round(chat_id, context.application)


async def end_round(chat_id: int, app: Application) -> None:
    """
    Safely end the round.
    """

    # If no active round — ignore
    if not is_round_active(chat_id):
        return

    result: RoundResult = finalize_round(chat_id)

    await app.bot.send_message(
        chat_id=chat_id,
        text=(
            f"⏰ Time's up!\n\n"
            f"Round {result.round_number} finished.\n"
            f"Letter: {result.letter}\n"
            f"Category: {result.category}\n"
            f"Answers received: {len(result.answers)}"
        ),
    )

    # Future integration point:
    # - validation
    # - scoring
    # - leaderboard
