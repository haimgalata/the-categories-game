from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time
import uuid


@dataclass
class AnswerDraft:
    user_id: int
    text: str
    ts_ms: int


@dataclass
class Answer:
    game_id: str
    round_id: str
    user_id: int
    username: str
    raw_text: str
    corrected_text: str
    valid: bool
    score: int
    response_ms: int
    letter: str = ""
    category: str = ""


@dataclass
class Round:
    round_id: str
    game_id: str
    round_number: int
    letter: str
    category: str
    started_at_ms: int
    ended_at_ms: Optional[int] = None


@dataclass
class PlayerStats:
    chat_id: int
    user_id: int
    username: str
    total_score: int = 0
    correct_count: int = 0
    answer_count: int = 0
    avg_response_ms: float = 0.0


@dataclass
class GameState:
    chat_id: int
    game_id: str
    current_round: int = 0
    round_active: bool = False
    round_letter: str = ""
    round_category: str = ""
    round_started_ms: int = 0
    answers: Dict[int, AnswerDraft] = field(default_factory=dict)


@dataclass
class ValidationResult:
    valid: bool
    corrected: str
    reason: str
    category_match: bool


@dataclass
class RoundResult:
    game_id: str
    round_number: int
    letter: str
    category: str
    answers: List[AnswerDraft]


def now_ms() -> int:
    """
    Params: none
    Returns: current time in milliseconds.
    Description: Helper for response timing.
    Examples:
        Input: none
        Output: 1700000000123
    """
    return int(time.time() * 1000)


def new_game_state(chat_id: int) -> GameState:
    """
    Params: chat_id (group chat id).
    Returns: GameState object.
    Description: Create a new in-memory game state.
    Examples:
        Input: chat_id=12345
        Output: GameState(chat_id=12345, game_id="...")
    """
    game_id = f"{chat_id}-{uuid.uuid4()}"
    return GameState(chat_id=chat_id, game_id=game_id)


def new_round(game_id: str, round_number: int, letter: str, category: str) -> Round:
    """
    Params: game_id, round_number, letter, category.
    Returns: Round object.
    Description: Create a round record.
    Examples:
        Input: game_id="g1", round_number=1, letter="C", category="City"
        Output: Round(round_id="...", game_id="g1", round_number=1, letter="C", category="City", started_at_ms=...)
    """
    return Round(
        round_id=str(uuid.uuid4()),
        game_id=game_id,
        round_number=round_number,
        letter=letter,
        category=category,
        started_at_ms=now_ms(),
    )


def new_answer(
    game_id: str,
    round_id: str,
    user_id: int,
    raw_text: str,
    corrected_text: str,
    valid: bool,
    score: int,
    response_ms: int,
    username: str = "",
    letter: str = "",
    category: str = "",
) -> Answer:
    """
    Params: game_id, round_id, user_id, raw_text, corrected_text, valid, score, response_ms, username.
    Returns: Answer object.
    Description: Create an answer record.
    Examples:
        Input: game_id="g1", round_id="r1", user_id=7, raw_text="CaiHro", corrected_text="Cairo", valid=True, score=18, response_ms=12000
        Output: Answer(game_id="g1", round_id="r1", user_id=7, raw_text="CaiHro", corrected_text="Cairo", valid=True, score=18, response_ms=12000)
    """
    return Answer(
        game_id=game_id,
        round_id=round_id,
        user_id=user_id,
        username=username,
        raw_text=raw_text,
        corrected_text=corrected_text,
        letter=letter,
        category=category,
        valid=valid,
        score=score,
        response_ms=response_ms,
    )


def new_player_stats(chat_id: int, user_id: int, username: str) -> PlayerStats:
    """
    Params: chat_id, user_id, username.
    Returns: PlayerStats object.
    Description: Initialize player stats.
    Examples:
        Input: chat_id=123, user_id=7, username="guy"
        Output: PlayerStats(chat_id=123, user_id=7, username="guy", total_score=0)
    """
    return PlayerStats(chat_id=chat_id, user_id=user_id, username=username)
