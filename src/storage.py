from __future__ import annotations

from typing import Any, Dict

from .config import get_settings
from .models import Answer, GameState, PlayerStats, Round
from .validation import canonicalize_answer

_DB = None


def _normalize_text(text: str) -> str:
    return canonicalize_answer(text)


def _game_doc(game: GameState) -> Dict[str, Any]:
    return {
        "game_id": game.game_id,
        "chat_id": game.chat_id,
        "current_round": game.current_round,
        "round_active": game.round_active,
        "round_letter": game.round_letter,
        "round_category": game.round_category,
        "round_started_ms": game.round_started_ms,
    }


def _round_doc(round_obj: Round) -> Dict[str, Any]:
    return {
        "round_id": round_obj.round_id,
        "game_id": round_obj.game_id,
        "round_number": round_obj.round_number,
        "letter": round_obj.letter,
        "category": round_obj.category,
        "started_at_ms": round_obj.started_at_ms,
        "ended_at_ms": round_obj.ended_at_ms,
    }


def _answer_doc(answer: Answer) -> Dict[str, Any]:
    return {
        "game_id": answer.game_id,
        "round_id": answer.round_id,
        "user_id": answer.user_id,
        "username": answer.username,
        "raw_text": answer.raw_text,
        "corrected_text": answer.corrected_text,
        "corrected_norm": _normalize_text(answer.corrected_text),
        "letter": answer.letter,
        "category": answer.category,
        "valid": answer.valid,
        "score": answer.score,
        "response_ms": answer.response_ms,
    }


def _player_doc(stats: PlayerStats) -> Dict[str, Any]:
    return {
        "chat_id": stats.chat_id,
        "user_id": stats.user_id,
        "username": stats.username,
        "total_score": stats.total_score,
        "correct_count": stats.correct_count,
        "answer_count": stats.answer_count,
        "avg_response_ms": stats.avg_response_ms,
    }


def _require_db() -> Any:
    if _DB is None:
        raise RuntimeError("Database not initialized. Call get_db(uri) first.")
    return _DB

def get_db(uri: str) -> Any:
    """
    Params: MongoDB connection string.
    Returns: Database handle.
    Description: Connect to MongoDB and return a DB object.
    Examples:
        Input: uri="mongodb://localhost:27017"
        Output: <Database>
    """
    from pymongo import MongoClient
    from pymongo.errors import ConfigurationError

    global _DB
    client = MongoClient(uri)
    try:
        db = client.get_default_database()
    except ConfigurationError:
        db = client["categories_game"]
    _DB = db
    return db


def ensure_indexes(db: Any) -> None:
    """
    Params: db handle.
    Returns: None.
    Description: Create required indexes for uniqueness.
    Examples:
        Input: db=<Database>
        Output: None
    """
    answers = db["answers"]
    rounds = db["rounds"]
    # One answer per user per round
    answers.create_index(
        [("game_id", 1), ("round_id", 1), ("user_id", 1)], unique=True
    )
    # Block repeated answers in the same game for same letter+category
    answers.create_index(
        [("game_id", 1), ("letter", 1), ("category", 1), ("corrected_norm", 1)],
        unique=True,
    )
    # Identify rounds uniquely
    rounds.create_index([("game_id", 1), ("round_number", 1)], unique=True)


def save_game(game: GameState) -> None:
    """
    Params: game object.
    Returns: None.
    Description: Insert or update a game record.
    Examples:
        Input: game=GameState(chat_id=1001, game_id="...")
        Output: None
    """
    db = _require_db()
    db["games"].update_one({"game_id": game.game_id}, {"$set": _game_doc(game)}, upsert=True)


def save_round(round_obj: Round) -> None:
    """
    Params: round object.
    Returns: None.
    Description: Insert or update a round record.
    Examples:
        Input: round_obj=Round(game_id="g1", round_number=1, letter="C", category="City", started_at_ms=...)
        Output: None
    """
    db = _require_db()
    db["rounds"].update_one(
        {"round_id": round_obj.round_id}, {"$set": _round_doc(round_obj)}, upsert=True
    )


def save_answer(answer: Answer) -> None:
    """
    Params: answer object.
    Returns: None.
    Description: Insert answer record.
    Examples:
        Input: answer=Answer(game_id="g1", round_id="r1", user_id=7, raw_text="Cairo", corrected_text="Cairo", valid=True, score=18, response_ms=12000)
        Output: None
    """
    db = _require_db()
    db["answers"].insert_one(_answer_doc(answer))


def upsert_player_stats(stats: PlayerStats) -> None:
    """
    Params: stats object.
    Returns: None.
    Description: Update player stats for the chat.
    Examples:
        Input: stats=PlayerStats(chat_id=1001, user_id=7, username="guy")
        Output: None
    """
    db = _require_db()
    db["players"].update_one(
        {"chat_id": stats.chat_id, "user_id": stats.user_id},
        {"$set": _player_doc(stats)},
        upsert=True,
    )


def has_answer_been_used(
    game_id: str, letter: str, category: str, corrected_text: str
) -> bool:
    """
    Params: ids and normalized answer.
    Returns: True if already used.
    Description: Enforce no-repeat rule.
    Examples:
        Input: game_id="g1", letter="C", category="City", corrected_text="Cairo"
        Output: False
    """
    if not get_settings().enable_duplicate_check:
        return False
    db = _require_db()
    normalized = _normalize_text(corrected_text)
    hit = db["answers"].find_one(
        {
            "game_id": game_id,
            "letter": letter,
            "category": category,
            "corrected_norm": normalized,
        }
    )
    return hit is not None
