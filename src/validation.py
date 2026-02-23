from __future__ import annotations

import json
import os
from typing import Any, Dict

import requests

from .models import ValidationResult

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"


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


def validate_answer_groq(answer: str, letter: str, category: str) -> ValidationResult:
    """
    Params: answer text, letter, category.
    Returns: ValidationResult with valid/corrected/reason.
    Description: Call Groq and parse response.
    Examples:
        Input: answer="Caihiro", letter="C", category="City"
        Output: ValidationResult(valid=True, corrected="Cairo", reason="...", category_match=True)
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip()
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
    if corrected:
        starts_ok = corrected[0].lower() == letter.strip().lower()
    else:
        starts_ok = False
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
