import os
from unittest.mock import Mock, patch

import pytest

from src.models import ValidationResult, ValidatorInput
from src.validation import parse_groq_response, validate_answer_groq, validate_submission


def test_parse_groq_response_ok() -> None:
    """
    Params: none.
    Returns: None.
    Description: parse_groq_response maps JSON fields into ValidationResult.
    Examples:
        Input: valid JSON
        Output: ValidationResult(valid=True, corrected="Cairo")
    """
    text = '{"valid": true, "corrected": "Cairo", "reason": "ok", "categoryMatch": true}'
    result = parse_groq_response(text)
    assert isinstance(result, ValidationResult)
    assert result.valid is True
    assert result.corrected == "Cairo"
    assert result.category_match is True


def test_validate_answer_groq_requires_key() -> None:
    """
    Params: none.
    Returns: None.
    Description: validate_answer_groq raises when GROQ_API_KEY is missing.
    Examples:
        Input: no env key
        Output: RuntimeError
    """
    with patch("src.validation.get_settings") as mocked:
        mocked.return_value = type("S", (), {"groq_api_key": ""})()
        with pytest.raises(RuntimeError):
            validate_answer_groq("Cairo", "C", "City")


def test_validate_answer_groq_letter_mismatch_forces_invalid() -> None:
    """
    Params: none.
    Returns: None.
    Description: If corrected answer starts with wrong letter, valid becomes False.
    Examples:
        Input: corrected="Berlin", letter="C"
        Output: valid=False
    """
    os.environ["GROQ_API_KEY"] = "test-key"
    fake_response = Mock()
    fake_response.raise_for_status = Mock()
    fake_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"valid": true, "corrected": "Berlin", "reason": "ok", "categoryMatch": true}'
                }
            }
        ]
    }
    with patch("src.validation.requests.post", return_value=fake_response):
        result = validate_answer_groq("Berlin", "C", "City")
        assert result.valid is False


def test_validate_answer_groq_category_mismatch_forces_invalid() -> None:
    """
    Params: none.
    Returns: None.
    Description: If categoryMatch is false, valid becomes False.
    Examples:
        Input: categoryMatch=false
        Output: valid=False
    """
    os.environ["GROQ_API_KEY"] = "test-key"
    fake_response = Mock()
    fake_response.raise_for_status = Mock()
    fake_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"valid": true, "corrected": "Chile", "reason": "country", "categoryMatch": false}'
                }
            }
        ]
    }
    with patch("src.validation.requests.post", return_value=fake_response):
        result = validate_answer_groq("Chile", "C", "City")
        assert result.valid is False


def test_validate_answer_groq_valid() -> None:
    """
    Params: none.
    Returns: None.
    Description: Valid answer passes when letter and category match.
    Examples:
        Input: corrected="Cairo", categoryMatch=true
        Output: valid=True
    """
    os.environ["GROQ_API_KEY"] = "test-key"
    fake_response = Mock()
    fake_response.raise_for_status = Mock()
    fake_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"valid": true, "corrected": "Cairo", "reason": "ok", "categoryMatch": true}'
                }
            }
        ]
    }
    with patch("src.validation.requests.post", return_value=fake_response):
        result = validate_answer_groq("Caihiro", "C", "City")
        assert result.valid is True


def test_validate_answer_groq_cahiro_close_to_cairo() -> None:
    """
    Params: none.
    Returns: None.
    Description: Misspelled Cairo should be corrected and accepted for City + C.
    Examples:
        Input: answer="Cahiro", letter="C", category="City"
        Output: valid=True, corrected="Cairo"
    """
    os.environ["GROQ_API_KEY"] = "test-key"
    fake_response = Mock()
    fake_response.raise_for_status = Mock()
    fake_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"valid": true, "corrected": "Cairo", "reason": "spelling corrected", "categoryMatch": true}'
                }
            }
        ]
    }
    with patch("src.validation.requests.post", return_value=fake_response):
        result = validate_answer_groq("Cahiro", "C", "City")
        assert result.valid is True
        assert result.corrected == "Cairo"


def test_validate_answer_groq_chile_country_false() -> None:
    """
    Params: none.
    Returns: None.
    Description: Chile should be rejected for Country + C per game rules.
    Examples:
        Input: answer="Chile", letter="C", category="Country"
        Output: valid=False
    """
    os.environ["GROQ_API_KEY"] = "test-key"
    fake_response = Mock()
    fake_response.raise_for_status = Mock()
    fake_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"valid": false, "corrected": "Chile", "reason": "not accepted", "categoryMatch": true}'
                }
            }
        ]
    }
    with patch("src.validation.requests.post", return_value=fake_response):
        result = validate_answer_groq("Chile", "C", "Country")
        assert result.valid is False


def test_validate_submission_round_closed() -> None:
    payload = ValidatorInput(
        letter="C",
        category="Cities",
        answer="Cairo",
        accepted_answers=[],
        round_active=False,
        time_remaining=0,
        player_name="Alex",
        message_id="123",
        round_id="r1",
    )
    result = validate_submission(payload)
    assert result.valid is False
    assert result.reason == "round_closed"


def test_validate_submission_ignores_the_for_letter() -> None:
    with patch("src.validation.validate_answer_groq") as mocked:
        mocked.return_value = ValidationResult(
            valid=True,
            corrected="The Cairo",
            reason="ok",
            category_match=True,
        )
        payload = ValidatorInput(
            letter="C",
            category="Cities",
            answer="The Cairo",
            accepted_answers=[],
            round_active=True,
            time_remaining=10,
            player_name="Alex",
            message_id="123",
            round_id="r1",
        )
        result = validate_submission(payload)
    assert result.valid is True


def test_validate_submission_duplicate_alias_rejected() -> None:
    payload = ValidatorInput(
        letter="N",
        category="Cities",
        answer="NYC",
        accepted_answers=["New York City"],
        round_active=True,
        time_remaining=10,
        player_name="Alex",
        message_id="123",
        round_id="r1",
    )
    result = validate_submission(payload)
    assert result.valid is False
    assert result.reason == "duplicate"


def test_validate_submission_rejects_on_llm_failure() -> None:
    payload = ValidatorInput(
        letter="C",
        category="Cities",
        answer="Cairo",
        accepted_answers=[],
        round_active=True,
        time_remaining=10,
        player_name="Alex",
        message_id="123",
        round_id="r1",
    )
    with patch("src.validation.validate_answer_groq", side_effect=RuntimeError("timeout")):
        result = validate_submission(payload)
    assert result.valid is False
    assert result.reason == "fallback_validation_failed"
