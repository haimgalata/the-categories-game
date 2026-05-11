from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .game_state import (
    get_num_players,
    get_or_create_game,
    get_round_duration,
    get_round_answers,
    get_scores,
    is_countdown_active,
    is_round_active,
    record_answer,
    reset_game,
    set_group_mode,
)
from .models import now_ms
from .round_logic import end_round, show_final_scores, start_round

logger = logging.getLogger(__name__)


def _is_group_chat(update: Update) -> bool:
    chat = update.effective_chat
    if chat is None:
        return False
    return chat.type in {"group", "supergroup"}


def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Start Game 🎮", callback_data="start_game")],
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "🎮 Welcome to Categories!\nPress Start Game to begin.",
        reply_markup=_main_keyboard(),
    )


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "🎮 Categories Game Menu",
        reply_markup=_main_keyboard(),
    )


async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    reset_game(chat_id)
    await update.effective_message.reply_text("🛑 Game stopped and reset.")


async def score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    scores = get_scores(chat_id)
    if not scores:
        await update.effective_message.reply_text("📊 No scores yet.")
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or not message.text:
        return
    text = message.text.strip()
    if not text:
        return

    chat_id = update.effective_chat.id
    is_group = _is_group_chat(update)
    if is_group and text.lower() == "start":
        await _start_game_from_message(update, context)
        return

    if is_countdown_active(chat_id):
        return
    if not is_round_active(chat_id):
        return

    user = update.effective_user
    accepted = record_answer(
        chat_id=chat_id,
        user_id=user.id,
        player_name=user.first_name or "Player",
        text=text,
        ts_ms=now_ms(),
        message_id=str(message.message_id),
    )
    if not accepted:
        return

    # If everyone in chat has sent one answer, close early.
    target_answers = max(2 if is_group else 1, get_num_players(chat_id))
    if len(get_round_answers(chat_id)) >= target_answers:
        await end_round(chat_id, context.application)


async def _start_game_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None:
        return
    await _start_game(
        chat_id=chat.id,
        chat_type=chat.type,
        send_message=message.reply_text,
        app=context.application,
    )


async def _start_game(
    *,
    chat_id: int,
    chat_type: str,
    send_message,
    app,
) -> None:
    if is_round_active(chat_id) or is_countdown_active(chat_id):
        return
    game = get_or_create_game(chat_id)
    set_group_mode(chat_id, chat_type in {"group", "supergroup"})
    round_duration = get_round_duration(chat_id)
    intro_text = (
        "🎮 New Game Started!\n\n"
        f"You will play {game.max_rounds} rounds.\n"
        f"⏱️ Each round: {round_duration} seconds\n"
        "Get ready!"
    )
    start_message = await send_message(f"{intro_text}\n\n⏳ Starting in 5...")
    await start_round(
        chat_id,
        app,
        countdown_message_id=start_message.message_id,
        countdown_prefix="⏳ Starting in",
        intro_text=intro_text,
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    data = query.data
    logger.info("Callback received chat_id=%s data=%s", chat_id, data)

    if data == "start_game":
        await _start_game(
            chat_id=chat_id,
            chat_type=query.message.chat.type,
            send_message=query.message.reply_text,
            app=context.application,
        )
        return

    if data == "next_round":
        if is_round_active(chat_id) or is_countdown_active(chat_id):
            await query.message.reply_text("⚠️ Finish the current round first.")
            return
        await start_round(chat_id, context.application)
        return

    if data == "finish_game":
        if is_countdown_active(chat_id):
            await query.message.reply_text("⚠️ Finish the current round first.")
            return
        if is_round_active(chat_id):
            await end_round(chat_id, context.application)
            return
        await show_final_scores(chat_id, context.application)
