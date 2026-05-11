from __future__ import annotations

import json
import re
from typing import Any, Dict

import requests

from .config import get_settings
from .models import ValidationResult, ValidatorInput, ValidatorOutput, ValidatorUiActions

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"

_ENTITY_ALIASES = {
    "nyc": "newyorkcity",
    "newyork": "newyorkcity",
    "la": "losangeles",
    "usa": "unitedstates",
    "uk": "unitedkingdom",
    "uae": "unitedarabemirates",
}


def build_groq_prompt(answer: str, letter: str, category: str) -> str:
    """
    Params: answer text, letter, category.
    Returns: Prompt string.
    Description: Build a strict JSON prompt for Groq.
    Examples:
        Input: answer="Caihiro", letter="C", category="City"
        Output: "Return strict JSON only: {...}"
    """
    return (
        "You are validating a Categories game answer. "
        "Return STRICT JSON only with keys: valid, corrected, reason, categoryMatch. "
        "Rules: "
        "1) Correct spelling if close. "
        "2) valid=true only if the corrected answer is real, matches the category, "
        "and starts with the given letter. "
        "3) categoryMatch=true only if the corrected answer fits the category. "
        f'Letter: "{letter}". Category: "{category}". Answer: "{answer}".'
    )


def _canonicalize_entity(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", text.strip().lower())
    return _ENTITY_ALIASES.get(normalized, normalized)


def canonicalize_answer(text: str) -> str:
    """
    Params: answer text.
    Returns: canonical normalized text.
    Description: Build canonical identity for duplicate checks.
    """
    return _canonicalize_entity(text)


def _starts_with_letter(answer: str, letter: str) -> bool:
    candidate = answer.strip()
    if candidate.lower().startswith("the "):
        candidate = candidate[4:].strip()
    if not candidate:
        return False
    return candidate[0].lower() == letter.strip().lower()


def _is_probably_english(text: str) -> bool:
    if not text.strip():
        return False
    if re.search(r"[^\x00-\x7F]", text):
        return False
    return bool(re.search(r"[A-Za-z]", text))


def _build_message(valid: bool, uncertain: bool, reason: str, player_name: str, corrected: str) -> str:
    if valid and uncertain:
        return f"⚠️ Hmm, {player_name}, that might count... we'll allow {corrected}!"
    if valid:
        return f"✅ Nice one, {player_name}! {corrected} is in 🎉"
    if reason == "round_closed":
        return "⏱️ Too late! This round is already closed."
    if reason == "duplicate":
        return "❌ Already taken! Someone beat you to that one."
    if reason == "wrong_letter":
        return "❌ Oops! That does not start with the right letter."
    if reason == "not_english":
        return "❌ English answers only for this game."
    return "❌ That doesn't match the category"


def validate_submission(payload: ValidatorInput) -> ValidatorOutput:
    """
    Params: validator input contract.
    Returns: validator output contract.
    Description: Deterministic-first validator with Groq fallback.
    """
    settings = get_settings()
    raw_answer = payload.answer.strip()
    corrected = raw_answer.title()
    ui_actions = ValidatorUiActions(
        reply_to_message_id=payload.message_id,
        pin_round=bool(settings.enable_pinning and payload.round_active and payload.time_remaining > 0),
        highlight=False,
        ignore_if_round_inactive=True,
    )
    if not payload.round_active or payload.time_remaining <= 0:
        return ValidatorOutput(
            valid=False,
            corrected_answer=corrected,
            reason="round_closed",
            message=_build_message(False, False, "round_closed", payload.player_name, corrected),
            uncertain=False,
            ui_actions=ui_actions,
        )

    if settings.language == "en" and not _is_probably_english(raw_answer):
        return ValidatorOutput(
            valid=False,
            corrected_answer=corrected,
            reason="not_english",
            message=_build_message(False, False, "not_english", payload.player_name, corrected),
            uncertain=False,
            ui_actions=ui_actions,
        )

    if not _starts_with_letter(raw_answer, payload.letter):
        return ValidatorOutput(
            valid=False,
            corrected_answer=corrected,
            reason="wrong_letter",
            message=_build_message(False, False, "wrong_letter", payload.player_name, corrected),
            uncertain=False,
            ui_actions=ui_actions,
        )

    answer_key = canonicalize_answer(raw_answer)
    used_keys = {canonicalize_answer(value) for value in payload.accepted_answers}
    if settings.enable_duplicate_check and answer_key and answer_key in used_keys:
        return ValidatorOutput(
            valid=False,
            corrected_answer=corrected,
            reason="duplicate",
            message=_build_message(False, False, "duplicate", payload.player_name, corrected),
            uncertain=False,
            ui_actions=ui_actions,
        )

    deterministic_confidence = 0.0
    if deterministic_confidence >= settings.confidence_threshold:
        return ValidatorOutput(
            valid=True,
            corrected_answer=corrected,
            reason="Accepted by deterministic checks",
            message=_build_message(True, True, "uncertain", payload.player_name, corrected),
            uncertain=True,
            ui_actions=ValidatorUiActions(
                reply_to_message_id=payload.message_id,
                pin_round=bool(settings.enable_pinning),
                highlight=False,
                ignore_if_round_inactive=True,
            ),
        )

    if not settings.llm_fallback_enabled:
        return ValidatorOutput(
            valid=False,
            corrected_answer=corrected,
            reason="llm_fallback_disabled",
            message="❌ Could not verify this answer right now.",
            uncertain=False,
            ui_actions=ui_actions,
        )

    try:
        llm_result = validate_answer_groq(raw_answer, payload.letter, payload.category)
    except Exception:
        llm_result = ValidationResult(
            valid=False,
            corrected=corrected,
            reason="fallback_validation_failed",
            category_match=False,
        )
        return ValidatorOutput(
            valid=False,
            corrected_answer=corrected,
            reason=llm_result.reason,
            message="❌ That doesn't match the category",
            uncertain=False,
            ui_actions=ValidatorUiActions(
                reply_to_message_id=payload.message_id,
                pin_round=bool(settings.enable_pinning),
                highlight=False,
                ignore_if_round_inactive=True,
            ),
        )

    corrected = (llm_result.corrected or corrected).strip()
    uncertain = bool(llm_result.valid and (not llm_result.category_match or "maybe" in llm_result.reason.lower()))
    valid = bool(llm_result.valid)
    if settings.enable_duplicate_check and valid and canonicalize_answer(corrected) in used_keys:
        return ValidatorOutput(
            valid=False,
            corrected_answer=corrected,
            reason="duplicate",
            message=_build_message(False, False, "duplicate", payload.player_name, corrected),
            uncertain=False,
            ui_actions=ui_actions,
        )
    if not valid:
        return ValidatorOutput(
            valid=False,
            corrected_answer=corrected,
            reason=llm_result.reason or "category_mismatch",
            message="❌ That doesn't match the category",
            uncertain=False,
            ui_actions=ui_actions,
        )
    return ValidatorOutput(
        valid=True,
        corrected_answer=corrected,
        reason=llm_result.reason or "Accepted",
        message=_build_message(True, uncertain, "ok", payload.player_name, corrected),
        uncertain=uncertain,
        ui_actions=ValidatorUiActions(
            reply_to_message_id=payload.message_id,
            pin_round=bool(settings.enable_pinning),
            highlight=not uncertain,
            ignore_if_round_inactive=True,
        ),
    )


def validate_answer_groq(answer: str, letter: str, category: str) -> ValidationResult:
    """
    Params: answer text, letter, category.
    Returns: ValidationResult with valid/corrected/reason.
    Description: Call Groq and parse response.
    Examples:
        Input: answer="Caihiro", letter="C", category="City"
        Output: ValidationResult(valid=True, corrected="Cairo", reason="...", category_match=True)
    """
    api_key = get_settings().groq_api_key
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY environment variable.")

    prompt = build_groq_prompt(answer, letter, category)
    payload: Dict[str, Any] = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Return strict JSON only. Do not add extra text.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 200,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    content = (
        data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    )
    if not content:
        raise RuntimeError("Groq response missing content.")
    result = parse_groq_response(content)

    corrected = result.corrected.strip()
    starts_ok = _starts_with_letter(corrected, letter)
    if not starts_ok or not result.category_match:
        result = ValidationResult(
            valid=False,
            corrected=result.corrected,
            reason=result.reason,
            category_match=result.category_match,
        )
    return result


def parse_groq_response(text: str) -> ValidationResult:
    """
    Params: raw Groq response text.
    Returns: ValidationResult.
    Description: Parse and validate the strict JSON response.
    Examples:
        Input: text='{\"valid\": true, \"corrected\": \"Cairo\", \"reason\": \"...\", \"categoryMatch\": true}'
        Output: ValidationResult(valid=True, corrected="Cairo", reason="...", category_match=True)
    """
    data = json.loads(text)
    return ValidationResult(
        valid=bool(data.get("valid")),
        corrected=str(data.get("corrected", "")),
        reason=str(data.get("reason", "")),
        category_match=bool(data.get("categoryMatch")),
    )
