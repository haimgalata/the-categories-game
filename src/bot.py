from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from .handlers import (
    start,
    stop_game,
    score,
    handle_message,
    show_menu,
    menu_callback,
)

# -------------------------------------------------
# Logging setup
# -------------------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# -------------------------------------------------
# Build Application
# -------------------------------------------------

def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()

    # Ensure JobQueue exists (needed for round timers)
    if app.job_queue is None:
        raise RuntimeError("JobQueue is not initialized properly.")

    return app


# -------------------------------------------------
# Register Handlers
# -------------------------------------------------

def register_handlers(app: Application) -> None:
    # ---- Commands ----
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", show_menu))
    app.add_handler(CommandHandler("stop_game", stop_game))
    app.add_handler(CommandHandler("score", score))

    # ---- Button callbacks ----
    app.add_handler(CallbackQueryHandler(menu_callback))

    # ---- Regular text messages ----
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # ---- Global error handler ----
    app.add_error_handler(error_handler)


# -------------------------------------------------
# Error Handling
# -------------------------------------------------

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling update:", exc_info=context.error)


# -------------------------------------------------
# Run Bot
# -------------------------------------------------

def run_bot(app: Application) -> None:
    print(">>> Starting polling...")
    app.run_polling()
