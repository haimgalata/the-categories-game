from src.models import PlayerStats
from src.scoring import calc_time_bonus, compute_leaderboard, score_answer, update_player_stats


def test_score_valid_fast() -> None:
    """
    Params: none.
    Returns: None.
    Description: Fast valid answer gets higher score.
    Examples:
        Input: valid=True, response_ms=1000
        Output: score > 15
    """
    assert score_answer(True, 1000) == 19


def test_score_valid_slow() -> None:
    """
    Params: none.
    Returns: None.
    Description: Slow valid answer gets lower score.
    Examples:
        Input: valid=True, response_ms=25000
        Output: score close to 10
    """
    assert score_answer(True, 25000) == 11


def test_score_invalid() -> None:
    """
    Params: none.
    Returns: None.
    Description: Invalid answer scores zero.
    Examples:
        Input: valid=False, response_ms=1000
        Output: 0
    """
    assert score_answer(False, 1000) == 0


def test_time_bonus_floor() -> None:
    """
    Params: none.
    Returns: None.
    Description: Bonus does not go below zero.
    Examples:
        Input: response_ms=60000
        Output: 0
    """
    assert calc_time_bonus(60000) == 0


def test_update_player_stats_accumulates() -> None:
    """
    Params: none.
    Returns: None.
    Description: Stats accumulate totals and avg response time.
    Examples:
        Input: first valid then invalid answer
        Output: total_score=19, correct_count=1, answer_count=2, avg_response_ms=6000
    """
    stats = PlayerStats(chat_id=1, user_id=2, username="u")
    update_player_stats(stats, is_valid=True, response_ms=3000, score=19)
    update_player_stats(stats, is_valid=False, response_ms=9000, score=0)
    assert stats.total_score == 19
    assert stats.correct_count == 1
    assert stats.answer_count == 2
    assert stats.avg_response_ms == 6000


def test_compute_leaderboard_orders_by_score() -> None:
    """
    Params: none.
    Returns: None.
    Description: Leaderboard sorts descending by total score.
    Examples:
        Input: scores [5, 10]
        Output: [10, 5]
    """
    p1 = PlayerStats(chat_id=1, user_id=1, username="a", total_score=5)
    p2 = PlayerStats(chat_id=1, user_id=2, username="b", total_score=10)
    ordered = compute_leaderboard([p1, p2])
    assert [p.user_id for p in ordered] == [2, 1]
