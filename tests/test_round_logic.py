# tests/test_round_logic.py

import string
import pytest

from src.round_logic import pick_letter, pick_category


def test_pick_letter_returns_single_uppercase_letter():
    letter = pick_letter()

    assert isinstance(letter, str)
    assert len(letter) == 1
    assert letter in string.ascii_uppercase


def test_pick_letter_randomness():
    letters = {pick_letter() for _ in range(100)}
    assert len(letters) > 1  # should not always return same letter


def test_pick_category_valid_list():
    categories = ["City", "Country"]
    result = pick_category(categories)

    assert result in categories


def test_pick_category_empty_list():
    with pytest.raises(ValueError):
        pick_category([])
