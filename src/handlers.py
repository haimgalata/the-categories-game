from __future__ import annotations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .game_state import (
    is_round_active,
    record_answer,
    reset_game,
    get_scores,
)
from .models import now_ms
from .round_logic import start_round, end_round


# -------------------------------------------------
# Commands
# -------------------------------------------------

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id

    if is_round_active(chat_id):
        await update.message.reply_text(
            "⚠️ A round is already active!"
        )
        return

    await start_round(chat_id, context.application)


async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    reset_game(chat_id)
    await update.message.reply_text(
        "🛑 Game stopped and reset."
    )


async def score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    scores = get_scores(chat_id)

    if not scores:
        await update.message.reply_text("📊 No scores yet.")
        return

    sorted_scores = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    text = "📊 Current Scores:\n\n"

    for user_id, points in sorted_scores:
        user = await context.application.bot.get_chat_member(
            chat_id,
            user_id,
        )
        name = user.user.first_name
        text += f"{name} - {points} pts\n"

    await update.effective_message.reply_text(text)


# -------------------------------------------------
# Message Answers
# -------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        await update.message.reply_text(
            "⚠️ You already answered this round."
        )


# -------------------------------------------------
# Menu UI
# -------------------------------------------------

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("▶️ Start Game", callback_data="start"),
            InlineKeyboardButton("🛑 Stop Game", callback_data="stop"),
        ],
        [
            InlineKeyboardButton("📊 Score", callback_data="score"),
            InlineKeyboardButton("🏁 End Game", callback_data="end"),
        ],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.effective_message.reply_text(
        "🎮 Categories Game Menu:",
        reply_markup=reply_markup,
    )


# -------------------------------------------------
# Button Callbacks
# -------------------------------------------------

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    data = query.data

    # START
    if data == "start":
        if is_round_active(chat_id):
            await query.message.reply_text(
                "⚠️ A round is already active!"
            )
            return

        await start_round(chat_id, context.application)

    # STOP
    elif data == "stop":
        reset_game(chat_id)
        await query.message.reply_text(
            "🛑 Game stopped and reset."
        )

    # SCORE
    elif data == "score":
        scores = get_scores(chat_id)

        if not scores:
            await query.message.reply_text("📊 No scores yet.")
            return

        sorted_scores = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        text = "📊 Current Scores:\n\n"

        for user_id, points in sorted_scores:
            user = await context.application.bot.get_chat_member(
                chat_id,
                user_id,
            )
            name = user.user.first_name
            text += f"{name} - {points} pts\n"

        await query.message.reply_text(text)

    # END
    elif data == "end":
        await end_round(chat_id, context.application)
