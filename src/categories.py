from __future__ import annotations

from typing import List

_CATEGORIES = [
    "City",
    "Country",
    "Food",
    "Animal",
    "Movie",
    "Song",
    "Sports Team",
    "Famous Person",
    "Brand",
    "Car",
]


def load_categories() -> List[str]:
    """
    Provide the base category list.
    """
    # Return a copy to avoid accidental mutation
    return list(_CATEGORIES)


def normalize_category(name: str) -> str:
    """
    Normalize category comparisons.
    """
    if not isinstance(name, str):
        return ""

    # Remove extra spaces and normalize case
    return " ".join(name.strip().lower().split())
