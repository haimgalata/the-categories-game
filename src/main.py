from __future__ import annotations

import os
from dotenv import load_dotenv

from .bot import build_application, register_handlers, run_bot
from .storage import get_db, ensure_indexes


def get_settings() -> dict:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    mongo_uri = os.getenv("MONGODB_URI", "").strip()

    missing = []

    if not token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not groq_key:
        missing.append("GROQ_API_KEY")
    if not mongo_uri:
        missing.append("MONGODB_URI")

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return {
        "TELEGRAM_BOT_TOKEN": token,
        "GROQ_API_KEY": groq_key,
        "MONGODB_URI": mongo_uri,
    }


def main() -> None:
    settings = get_settings()

    # ---------------------------
    # Initialize MongoDB
    # ---------------------------
    print("Connecting to MongoDB...")
    db = get_db(settings["MONGODB_URI"])
    ensure_indexes(db)
    print("MongoDB connected and indexes ensured.")

    # ---------------------------
    # Initialize Telegram bot
    # ---------------------------
    app = build_application(settings["TELEGRAM_BOT_TOKEN"])
    register_handlers(app)

    print("Bot started successfully")
    run_bot(app)


if __name__ == "__main__":
    main()
