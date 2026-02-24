from src.models import (
    Answer,
    GameState,
    PlayerStats,
    Round,
    now_ms,
    new_answer,
    new_game_state,
    new_player_stats,
    new_round,
)


def test_now_ms_increases() -> None:
    """
    Params: none.
    Returns: None.
    Description: now_ms should be non-decreasing across calls.
    Examples:
        Input: none
        Output: t2 >= t1
    """
    t1 = now_ms()
    t2 = now_ms()
    assert t2 >= t1


def test_new_game_state_fields() -> None:
    """
    Params: none.
    Returns: None.
    Description: new_game_state populates chat_id and game_id.
    Examples:
        Input: chat_id=123
        Output: GameState(chat_id=123, game_id="123-...")
    """
    game = new_game_state(123)
    assert isinstance(game, GameState)
    assert game.chat_id == 123
    assert game.game_id.startswith("123-")
    assert game.current_round == 0
    assert game.round_active is False


def test_new_round_fields() -> None:
    """
    Params: none.
    Returns: None.
    Description: new_round populates ids, letter, and category.
    Examples:
        Input: game_id="g1", round_number=1, letter="C", category="City"
        Output: Round(round_number=1, letter="C", category="City")
    """
    rnd = new_round("g1", 1, "C", "City")
    assert isinstance(rnd, Round)
    assert rnd.game_id == "g1"
    assert rnd.round_number == 1
    assert rnd.letter == "C"
    assert rnd.category == "City"
    assert rnd.started_at_ms > 0


def test_new_answer_fields() -> None:
    """
    Params: none.
    Returns: None.
    Description: new_answer maps inputs to Answer fields.
    Examples:
        Input: raw_text="CaiHro", corrected_text="Cairo"
        Output: Answer(corrected_text="Cairo")
    """
    ans = new_answer(
        game_id="g1",
        round_id="r1",
        user_id=7,
        raw_text="CaiHro",
        corrected_text="Cairo",
        valid=True,
        score=18,
        response_ms=12000,
        username="u",
    )
    assert isinstance(ans, Answer)
    assert ans.game_id == "g1"
    assert ans.round_id == "r1"
    assert ans.user_id == 7
    assert ans.username == "u"
    assert ans.raw_text == "CaiHro"
    assert ans.corrected_text == "Cairo"
    assert ans.valid is True
    assert ans.score == 18
    assert ans.response_ms == 12000


def test_new_player_stats_defaults() -> None:
    """
    Params: none.
    Returns: None.
    Description: new_player_stats sets initial totals to zero.
    Examples:
        Input: chat_id=1, user_id=2, username="guy"
        Output: PlayerStats(total_score=0, correct_count=0)
    """
    stats = new_player_stats(1, 2, "guy")
    assert isinstance(stats, PlayerStats)
    assert stats.chat_id == 1
    assert stats.user_id == 2
    assert stats.username == "guy"
    assert stats.total_score == 0
    assert stats.correct_count == 0
    assert stats.answer_count == 0
    assert stats.avg_response_ms == 0.0
