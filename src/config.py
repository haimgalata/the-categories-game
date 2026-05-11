from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _as_bool(value: str, default: bool) -> bool:
    raw = (value or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _as_int(value: str, default: int) -> int:
    try:
        return int((value or "").strip())
    except (TypeError, ValueError):
        return default


def _as_float(value: str, default: float) -> float:
    try:
        return float((value or "").strip())
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class AppSettings:
    telegram_bot_token: str
    groq_api_key: str
    mongodb_uri: str
    game_round_duration: int
    max_players: int
    enable_duplicate_check: bool
    enable_pinning: bool
    language: str
    llm_fallback_enabled: bool
    confidence_threshold: float


def get_settings() -> AppSettings:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or os.getenv("BOT_TOKEN", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    mongo_uri = os.getenv("MONGODB_URI", "").strip()

    return AppSettings(
        telegram_bot_token=token,
        groq_api_key=groq_key,
        mongodb_uri=mongo_uri,
        game_round_duration=max(5, _as_int(os.getenv("GAME_ROUND_DURATION", "30"), 30)),
        max_players=max(1, _as_int(os.getenv("MAX_PLAYERS", "50"), 50)),
        enable_duplicate_check=_as_bool(os.getenv("ENABLE_DUPLICATE_CHECK", "true"), True),
        enable_pinning=_as_bool(os.getenv("ENABLE_PINNING", "true"), True),
        language=(os.getenv("LANGUAGE", "en").strip().lower() or "en"),
        llm_fallback_enabled=_as_bool(os.getenv("LLM_FALLBACK_ENABLED", "true"), True),
        confidence_threshold=min(1.0, max(0.0, _as_float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"), 0.7))),
    )


def validate_required_env(settings: AppSettings) -> None:
    missing = []
    if not settings.telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN (or BOT_TOKEN)")
    if not settings.groq_api_key:
        missing.append("GROQ_API_KEY")
    if not settings.mongodb_uri:
        missing.append("MONGODB_URI")
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
