from __future__ import annotations

from typing import List

from src.models import PlayerStats


def _safe_response_ms(response_ms: int) -> int:
    """
    Params: response time in ms.
    Returns: non-negative response time.
    Description: Clamp negative response times to zero.
    Examples:
        Input: response_ms=-5
        Output: 0
    """
    return max(0, int(response_ms))


def calc_time_bonus(response_ms: int) -> int:
    """
    Params: response time in ms.
    Returns: integer bonus score.
    Description: Compute time bonus based on speed.
    Examples:
        Input: response_ms=1000
        Output: 9
        Input: response_ms=30000
        Output: 0
    """
    safe_ms = _safe_response_ms(response_ms)
    return max(0, int(10 - (safe_ms / 3000)))


def score_answer(valid: bool, response_ms: int) -> int:
    """
    Params: validity, response time in ms.
    Returns: total score for the answer.
    Description: Apply base points plus time bonus.
    Examples:
        Input: valid=True, response_ms=3000
        Output: 19
        Input: valid=False, response_ms=1000
        Output: 0
    """
    if not valid:
        return 0
    return 10 + calc_time_bonus(response_ms)


def update_player_stats(
    stats: PlayerStats, is_valid: bool, response_ms: int, score: int
) -> PlayerStats:
    """
    Params: stats object and latest answer data.
    Returns: updated stats object.
    Description: Increment totals and averages.
    Examples:
        Input: stats.total_score=10, is_valid=True, response_ms=3000, score=19
        Output: stats.total_score=29, stats.answer_count=1
    """
    safe_ms = _safe_response_ms(response_ms)
    stats.total_score += score
    stats.answer_count += 1
    if is_valid:
        stats.correct_count += 1
    # running average
    prev_total = stats.avg_response_ms * (stats.answer_count - 1)
    stats.avg_response_ms = (prev_total + safe_ms) / stats.answer_count
    return stats


def compute_leaderboard(players: List[PlayerStats]) -> List[PlayerStats]:
    """
    Params: list of player stats.
    Returns: players sorted by total score.
    Description: Build leaderboard order.
    Examples:
        Input: [PlayerStats(total_score=5), PlayerStats(total_score=10)]
        Output: [PlayerStats(total_score=10), PlayerStats(total_score=5)]
    """
    return sorted(players, key=lambda p: p.total_score, reverse=True)
