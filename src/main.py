from __future__ import annotations

import os
from dotenv import load_dotenv

from .bot import build_application, register_handlers, run_bot


def get_settings() -> dict:
    """
    Params: none.
    Returns: A dict with TELEGRAM_BOT_TOKEN, GROQ_API_KEY, MONGODB_URI.
    Description: Read environment variables and validate required values.
    """

    # Load .env file if exists
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
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return {
        "TELEGRAM_BOT_TOKEN": token,
        "GROQ_API_KEY": groq_key,
        "MONGODB_URI": mongo_uri,
    }


def main() -> None:
    """
    Params: none.
    Returns: None.
    Description: Load config, build the bot application, and start polling.
    """

    settings = get_settings()

    app = build_application(settings["TELEGRAM_BOT_TOKEN"])
    register_handlers(app)

    run_bot(app)


if __name__ == "__main__":
    main()
