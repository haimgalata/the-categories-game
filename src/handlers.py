from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from .game_state import (
    is_round_active,
    record_answer,
    reset_game,
)
from .models import now_ms
from .round_logic import start_round


# -------------------------
# Commands
# -------------------------

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Start a new game (round 1).
    """

    chat_id = update.effective_chat.id

    if is_round_active(chat_id):
        await update.message.reply_text("⚠️ A round is already active!")
        return

    await start_round(chat_id, context.application)


async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Stop current game and reset state.
    """

    chat_id = update.effective_chat.id

    reset_game(chat_id)

    await update.message.reply_text("🛑 Game stopped and reset.")


async def score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Placeholder for leaderboard (Guy will implement).
    """

    await update.message.reply_text("📊 Leaderboard will be available soon.")


# -------------------------
# Messages (Answers)
# -------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Collect answers during active round.
    """

    chat_id = update.effective_chat.id

    if not is_round_active(chat_id):
        return

    user = update.effective_user
    text = update.message.text.strip()

    accepted = record_answer(
        chat_id=chat_id,
        user_id=user.id,
        text=text,
        ts_ms=now_ms(),
    )

    if not accepted:
        await update.message.reply_text("⚠️ You already answered this round.")
    # אם התקבל — שקט, כדי לא להציף קבוצה


# -------------------------
# Continue Callback (Future)
# -------------------------

async def continue_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Placeholder for continue / stop after 5 rounds.
    """

    query = update.callback_query
    await query.answer()

    await query.edit_message_text("🔄 Continue feature coming soon.")
