from __future__ import annotations

from typing import List

_CATEGORIES = [
    # Classic
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

    # Funny
    "Excuse For Being Late",
    "Bad Superpower",
    "Embarrassing Thing",
    "Pick Up Line",
    "Villain Name",

    # Modern / Tech
    "App",
    "Video Game",
    "Programming Language",
    "AI Tool",
    "Tech Company",

    # Creative / Hard
    "Emotion",
    "Phobia",
    "Historical Event",
    "Mythical Creature",

    # Pop Culture
    "TV Show",
    "Superhero",
    "Disney Character",
    "Cartoon Character",
    "Anime",
    "Villain",

    # Group Chaos
    "Reason To Break Up",
    "Awkward Situation",
    "Something Overrated",
    "Red Flag",
    "Green Flag",
    "Something Illegal",
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
