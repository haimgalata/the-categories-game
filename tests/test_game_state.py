from src.game_state import (
    finalize_round,
    get_or_create_game,
    get_round_answers,
    is_round_active,
    record_answer,
    reset_game,
    set_round_prompt,
)


def test_get_or_create_game_returns_same_instance() -> None:
    """
    Params: none.
    Returns: None.
    Description: get_or_create_game returns existing state for same chat_id.
    Examples:
        Input: chat_id=1
        Output: same object instance on second call
    """
    reset_game(1)
    g1 = get_or_create_game(1)
    g2 = get_or_create_game(1)
    assert g1 is g2


def test_set_round_prompt_activates_round() -> None:
    """
    Params: none.
    Returns: None.
    Description: set_round_prompt activates round and sets prompt values.
    Examples:
        Input: chat_id=2, letter="C", category="City"
        Output: round_active=True
    """
    reset_game(2)
    set_round_prompt(2, "C", "City")
    game = get_or_create_game(2)
    assert game.round_active is True
    assert game.round_letter == "C"
    assert game.round_category == "City"


def test_record_answer_accepts_first_only() -> None:
    """
    Params: none.
    Returns: None.
    Description: record_answer accepts first answer per user per round.
    Examples:
        Input: same user twice
        Output: first True, second False
    """
    reset_game(3)
    set_round_prompt(3, "C", "City")
    accepted = record_answer(3, 10, "Alex", "Cairo", 1000, "101")
    rejected = record_answer(3, 10, "Alex", "Cairo", 2000, "102")
    assert accepted is True
    assert rejected is False


def test_record_answer_rejects_when_no_round() -> None:
    """
    Params: none.
    Returns: None.
    Description: record_answer returns False if round is inactive.
    Examples:
        Input: round not started
        Output: False
    """
    reset_game(4)
    assert record_answer(4, 1, "Alex", "Cairo", 1000, "101") is False


def test_get_round_answers_returns_list() -> None:
    """
    Params: none.
    Returns: None.
    Description: get_round_answers returns collected answers.
    Examples:
        Input: two answers
        Output: list length 2
    """
    reset_game(5)
    set_round_prompt(5, "C", "City")
    record_answer(5, 1, "Alex", "Cairo", 1000, "101")
    record_answer(5, 2, "Sam", "Chicago", 1100, "102")
    answers = get_round_answers(5)
    assert len(answers) == 2


def test_finalize_round_ends_round() -> None:
    """
    Params: none.
    Returns: None.
    Description: finalize_round ends round and returns RoundResult.
    Examples:
        Input: active round
        Output: round_active=False and correct prompt values
    """
    reset_game(6)
    set_round_prompt(6, "C", "City")
    record_answer(6, 1, "Alex", "Cairo", 1000, "101")
    result = finalize_round(6)
    game = get_or_create_game(6)
    assert game.round_active is False
    assert result.letter == "C"
    assert result.category == "City"
    assert len(result.answers) == 1
