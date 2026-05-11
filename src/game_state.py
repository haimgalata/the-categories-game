from __future__ import annotations

import uuid
from typing import Dict, List

from .config import get_settings
from .models import AnswerDraft, GameState, RoundResult, now_ms, new_game_state

_GAMES: Dict[int, GameState] = {}


# ---------------------------------------
# Core Game Management
# ---------------------------------------

def get_or_create_game(chat_id: int) -> GameState:
    if chat_id not in _GAMES:
        game = new_game_state(chat_id)
        settings = get_settings()
        game.round_duration = settings.game_round_duration
        _GAMES[chat_id] = game
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


def set_group_mode(chat_id: int, is_group_mode: bool) -> None:
    game = get_or_create_game(chat_id)
    game.is_group_mode = is_group_mode


def get_round_duration(chat_id: int) -> int:
    game = _GAMES.get(chat_id)
    if not game:
        return get_settings().game_round_duration
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
    game.round_id = str(uuid.uuid4())
    game.round_letter = letter
    game.round_category = category
    game.round_started_ms = now_ms()
    game.countdown_active = False
    game.answers.clear()


def set_round_message_id(chat_id: int, message_id: int) -> None:
    game = get_or_create_game(chat_id)
    game.round_message_id = message_id


def set_timer_message_id(chat_id: int, message_id: int) -> None:
    game = get_or_create_game(chat_id)
    game.timer_message_id = message_id


def get_timer_message_id(chat_id: int) -> int:
    game = _GAMES.get(chat_id)
    if not game:
        return 0
    return game.timer_message_id


def set_pinned_message_id(chat_id: int, message_id: int) -> None:
    game = get_or_create_game(chat_id)
    game.pinned_message_id = message_id


def is_countdown_active(chat_id: int) -> bool:
    game = _GAMES.get(chat_id)
    return bool(game and game.countdown_active)


def set_countdown_active(chat_id: int, active: bool) -> None:
    game = get_or_create_game(chat_id)
    game.countdown_active = active


def get_time_remaining(chat_id: int) -> int:
    game = _GAMES.get(chat_id)
    if not game or not game.round_active:
        return 0
    elapsed = max(0, (now_ms() - game.round_started_ms) // 1000)
    return max(0, game.round_duration - elapsed)


def record_answer(
    chat_id: int,
    user_id: int,
    player_name: str,
    text: str,
    ts_ms: int,
    message_id: str,
) -> bool:
    game = _GAMES.get(chat_id)
    if not game or not game.round_active:
        return False

    if user_id in game.answers:
        return False

    game.answers[user_id] = AnswerDraft(
        user_id=user_id,
        player_name=player_name,
        text=text,
        ts_ms=ts_ms,
        message_id=message_id,
    )
    game.participant_ids.add(user_id)
    return True


def get_round_answers(chat_id: int) -> List[AnswerDraft]:
    game = _GAMES.get(chat_id)
    if not game:
        return []
    return list(game.answers.values())


def get_round_answer_count(chat_id: int) -> int:
    game = _GAMES.get(chat_id)
    if not game:
        return 0
    return len(game.answers)


def get_participant_count(chat_id: int) -> int:
    game = _GAMES.get(chat_id)
    if not game:
        return 0
    return len(game.participant_ids)


def finalize_round(chat_id: int) -> RoundResult:
    game = get_or_create_game(chat_id)
    game.round_active = False
    game.timer_message_id = 0

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
