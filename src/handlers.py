from __future__ import annotations

import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from .game_state import (
    is_round_active,
    record_answer,
    reset_game,
    get_scores,
    get_round_answers,
    get_num_players,
    configure_game,
    extend_game,
)
from .models import now_ms
from .round_logic import start_round, end_round, show_final_scores

# ConversationHandler states
ASK_PLAYERS, ASK_DURATION = range(2)


# -------------------------------------------------
# Setup conversation: /startgame -> ask players -> ask duration -> go
# -------------------------------------------------

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id

    if is_round_active(chat_id):
        await update.message.reply_text("⚠️ A round is already active!")
        return ConversationHandler.END

    await update.message.reply_text("👥 How many players are playing? (send a number)")
    return ASK_PLAYERS


async def start_game_from_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for the 'Start Game' menu button."""
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id

    if is_round_active(chat_id):
        await query.message.reply_text("⚠️ A round is already active!")
        return ConversationHandler.END

    await query.message.reply_text("👥 How many players are playing? (send a number)")
    return ASK_PLAYERS


async def receive_players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or int(text) < 1:
        await update.message.reply_text("❌ Please send a valid number (1 or more).")
        return ASK_PLAYERS

    context.chat_data["num_players"] = int(text)
    await update.message.reply_text("⏱️ How many seconds per round? (send a number)")
    return ASK_DURATION


async def receive_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or int(text) < 5:
        await update.message.reply_text("❌ Please send a valid number (at least 5 seconds).")
        return ASK_DURATION

    chat_id = update.effective_chat.id
    num_players = context.chat_data.get("num_players", 2)
    duration = int(text)

    configure_game(chat_id, num_players=num_players, round_duration=duration)

    await update.message.reply_text(
        f"✅ Game configured!\n"
        f"Players: {num_players}\n"
        f"Round duration: {duration}s\n\n"
        f"Starting first round in 5 seconds... Get ready! 🎮"
    )

    await asyncio.sleep(5)
    await start_round(chat_id, context.application)
    return ConversationHandler.END


async def cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("🛑 Game setup cancelled.")
    return ConversationHandler.END


def build_setup_conversation() -> ConversationHandler:
    """Build the ConversationHandler for game setup."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("startgame", start_game),
            CallbackQueryHandler(start_game_from_menu, pattern="^start$"),
        ],
        states={
            ASK_PLAYERS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_players),
            ],
            ASK_DURATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_duration),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_setup)],
        per_chat=True,
        per_user=False,
    )


# -------------------------------------------------
# Commands
# -------------------------------------------------

async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    reset_game(chat_id)
    await update.message.reply_text("🛑 Game stopped and reset.")


async def score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    scores = get_scores(chat_id)

    if not scores:
        await update.message.reply_text("📊 No scores yet.")
        return

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    text = "📊 Current Scores:\n\n"
    for user_id, points in sorted_scores:
        try:
            user = await context.application.bot.get_chat_member(chat_id, user_id)
            name = user.user.first_name
        except Exception:
            name = str(user_id)
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
        await update.message.reply_text("⚠️ You already answered this round.")
        return

    # End early if all declared players have answered
    num_players = get_num_players(chat_id)
    if num_players > 0 and len(get_round_answers(chat_id)) >= num_players:
        await end_round(chat_id, context.application)


# -------------------------------------------------
# Menu UI
# -------------------------------------------------

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("▶️ Start Game", callback_data="start")],
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

    # STOP
    if data == "stop":
        reset_game(chat_id)
        await query.message.reply_text("🛑 Game stopped and reset.")

    # SCORE
    elif data == "score":
        scores = get_scores(chat_id)

        if not scores:
            await query.message.reply_text("📊 No scores yet.")
            return

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        text = "📊 Current Scores:\n\n"

        for user_id, points in sorted_scores:
            try:
                user = await context.application.bot.get_chat_member(chat_id, user_id)
                name = user.user.first_name
            except Exception:
                name = str(user_id)
            text += f"{name} - {points} pts\n"

        await query.message.reply_text(text)

    # END GAME
    elif data == "end":
        if is_round_active(chat_id):
            await end_round(chat_id, context.application)
        await show_final_scores(chat_id, context.application)

    # CONTINUE after 5 rounds
    elif data == "continue_game":
        extend_game(chat_id)
        await start_round(chat_id, context.application)

    # FINISH after 5 rounds
    elif data == "finish_game":
        await show_final_scores(chat_id, context.application)
