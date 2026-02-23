from __future__ import annotations

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from .handlers import (
    start_game,
    stop_game,
    score,
    handle_message,
    continue_game_callback,
)


def build_application(token: str) -> Application:
    """
    Create and configure the PTB application.
    """
    app = Application.builder().token(token).build()
    return app


def register_handlers(app: Application) -> None:
    """
    Attach all command and message handlers.
    """

    # Commands
    app.add_handler(CommandHandler("start_game", start_game))
    app.add_handler(CommandHandler("stop_game", stop_game))
    app.add_handler(CommandHandler("score", score))

    # Callback query (for Continue button later)
    app.add_handler(CallbackQueryHandler(continue_game_callback))

    # Regular messages (answers during round)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )


def run_bot(app: Application) -> None:
    """
    Start polling and keep the bot running.
    """
    app.run_polling()
