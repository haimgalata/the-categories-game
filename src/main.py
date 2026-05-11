from __future__ import annotations

from .bot import build_application, register_handlers, run_bot
from .config import get_settings, validate_required_env
from .storage import get_db, ensure_indexes


def main() -> None:
    settings = get_settings()
    validate_required_env(settings)

    # ---------------------------
    # Initialize MongoDB
    # ---------------------------
    print("Connecting to MongoDB...")
    db = get_db(settings.mongodb_uri)
    ensure_indexes(db)
    print("MongoDB connected and indexes ensured.")

    # ---------------------------
    # Initialize Telegram bot
    # ---------------------------
    app = build_application(settings.telegram_bot_token)
    register_handlers(app)

    print("Bot started successfully")
    run_bot(app)


if __name__ == "__main__":
    main()
