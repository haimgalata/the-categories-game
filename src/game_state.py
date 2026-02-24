from __future__ import annotations

from typing import Dict, List

from .models import AnswerDraft, GameState, RoundResult, now_ms, new_game_state

_GAMES: Dict[int, GameState] = {}


# ---------------------------------------
# Core Game Management
# ---------------------------------------

def get_or_create_game(chat_id: int) -> GameState:
    if chat_id not in _GAMES:
        _GAMES[chat_id] = new_game_state(chat_id)
    return _GAMES[chat_id]


def reset_game(chat_id: int) -> None:
    _GAMES.pop(chat_id, None)


def get_game(chat_id: int) -> GameState | None:
    return _GAMES.get(chat_id)


# ---------------------------------------
# Setup helpers
# ---------------------------------------

def configure_game(
    chat_id: int,
    num_players: int,
    round_duration: int,
) -> GameState:
    """Store player count and round duration before starting."""
    game = get_or_create_game(chat_id)
    game.num_players = num_players
    game.round_duration = round_duration
    return game


def get_num_players(chat_id: int) -> int:
    game = _GAMES.get(chat_id)
    if not game:
        return 0
    return game.num_players


def get_round_duration(chat_id: int) -> int:
    game = _GAMES.get(chat_id)
    if not game:
        return 30
    return game.round_duration


# ---------------------------------------
# Round State
# ---------------------------------------

def is_round_active(chat_id: int) -> bool:
    game = _GAMES.get(chat_id)
    return bool(game and game.round_active)


def set_round_prompt(chat_id: int, letter: str, category: str) -> None:
    game = get_or_create_game(chat_id)
    game.current_round += 1
    game.round_active = True
    game.round_letter = letter
    game.round_category = category
    game.round_started_ms = now_ms()
    game.answers.clear()


def record_answer(chat_id: int, user_id: int, text: str, ts_ms: int) -> bool:
    game = _GAMES.get(chat_id)
    if not game or not game.round_active:
        return False

    if user_id in game.answers:
        return False

    game.answers[user_id] = AnswerDraft(
        user_id=user_id,
        text=text,
        ts_ms=ts_ms,
    )
    return True


def get_round_answers(chat_id: int) -> List[AnswerDraft]:
    game = _GAMES.get(chat_id)
    if not game:
        return []
    return list(game.answers.values())


def finalize_round(chat_id: int) -> RoundResult:
    game = get_or_create_game(chat_id)
    game.round_active = False

    return RoundResult(
        game_id=game.game_id,
        round_number=game.current_round,
        letter=game.round_letter,
        category=game.round_category,
        answers=list(game.answers.values()),
    )


# ---------------------------------------
# Scoring
# ---------------------------------------

def add_points(chat_id: int, user_id: int, points: int = 1) -> None:
    game = get_or_create_game(chat_id)
    game.scores[user_id] = game.scores.get(user_id, 0) + points


def get_scores(chat_id: int) -> Dict[int, int]:
    game = _GAMES.get(chat_id)
    if not game:
        return {}
    return game.scores


def is_game_over(chat_id: int) -> bool:
    game = _GAMES.get(chat_id)
    if not game:
        return False
    return game.current_round >= game.max_rounds


def extend_game(chat_id: int) -> None:
    """Allow one more round after the initial max_rounds."""
    game = _GAMES.get(chat_id)
    if game:
        game.max_rounds += 1
