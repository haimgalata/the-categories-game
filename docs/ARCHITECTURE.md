# Architecture — The Categories Game

This document describes the system design, data model, validation pipeline, and module responsibilities for the bot.

---

## High-Level Flow

```
Telegram Group
      │
      ▼
  Bot Handler  ──── /menu ────▶  Setup Conversation
  (handlers.py)                  (player count, round duration)
      │
      │  round starts
      ▼
  Round Logic  ──── picks letter + category
  (round_logic.py)
      │
      │  player messages → answers collected
      ▼
  Validation Pipeline
  (validation.py)
      ├── Deterministic check (letter match, category match)
      │       │
      │       ├── confidence >= threshold ──▶ accept / reject
      │       └── confidence < threshold  ──▶ Groq LLM fallback
      │
      └── Groq API (strict JSON response)
              │
              ▼
          Scorer  ──── position-based points ──▶  MongoDB  ──▶  Leaderboard message
          (round_logic.py)                       (storage.py)
```

---

## Module Responsibilities

| Module | Responsibility |
|---|---|
| `src/main.py` | Entry point — loads `AppSettings`, validates required env vars, connects to MongoDB, starts the bot |
| `src/config.py` | Typed `AppSettings` dataclass; reads and coerces all environment variables with safe defaults |
| `src/bot.py` | Builds the `python-telegram-bot` `Application`; registers all handlers |
| `src/handlers.py` | Telegram command and callback handlers: `/menu`, `/stop_game`, `/score`, setup conversation flow |
| `src/round_logic.py` | Full round lifecycle: pick letter/category, announce, collect answers, run validation, score, persist, post leaderboard |
| `src/game_state.py` | In-memory `GameState` registry keyed by `chat_id`; tracks active round, collected answers, player list |
| `src/validation.py` | Hybrid validation pipeline: deterministic pre-checks → Groq LLM fallback; returns `ValidationResult` |
| `src/scoring.py` | Position-based scoring: 1st correct = 10 pts, descending to 2 pts for 5th+ |
| `src/storage.py` | MongoDB CRUD: save games, rounds, answers; upsert player stats; enforce duplicate-answer uniqueness |
| `src/models.py` | Dataclasses: `GameState`, `Answer`, `Round`, `PlayerStats`; shared `now_ms()` helper |
| `src/categories.py` | Static category list; `load_categories()` and `normalize_category()` |

---

## Data Model (MongoDB)

### `games`
```
game_id       string   — unique identifier
chat_id       int      — Telegram group chat
status        string   — "active" | "finished"
current_round int
started_at    int      — epoch ms
ended_at      int      — epoch ms (null while active)
```

### `rounds`
```
game_id       string
round_number  int
letter        string   — single uppercase letter
category      string
started_at    int
ended_at      int
```

### `answers`
```
game_id       string
round_id      string
user_id       int
username      string
raw_text      string   — exactly as typed
corrected_text string  — normalized by Groq (may equal raw_text)
valid         bool
score         int
response_ms   int      — time from round start to answer
```

### `players`
```
chat_id        int
user_id        int
username       string
total_score    int
correct_count  int
answer_count   int
avg_response_ms float
```

**Key indexes:**
- Unique on `(game_id, round_id, user_id)` — one answer per player per round
- Unique on `(game_id, category, letter, corrected_text)` — no duplicate answers within a game

---

## Validation Pipeline

Answers go through a two-stage pipeline designed to minimize unnecessary LLM calls:

**Stage 1 — Deterministic checks**
1. Strip and normalize the input
2. Check the first character matches the round letter (case-insensitive)
3. Apply a simple category heuristic (word-list or regex match where possible)
4. If confidence ≥ `CONFIDENCE_THRESHOLD` (default `0.7`): accept or reject immediately

**Stage 2 — Groq LLM fallback** (only when stage 1 is uncertain)

Request schema sent to Groq:
```
Given:
  - Answer: "<text>"
  - Required letter: "<letter>"
  - Category: "<category>"

Respond in strict JSON only:
{
  "valid": true | false,
  "corrected": "<corrected spelling>",
  "reason": "<one sentence>",
  "categoryMatch": true | false
}
```

Rules enforced by the prompt:
- `corrected` must start with the required letter after correction
- `valid` is `false` if the answer does not belong to the category
- Minor spelling variants are accepted (`"Caihro"` → `"Cairo"`, `valid: true`)

---

## Scoring

| Position | Points |
|:---:|:---:|
| 1st correct | 10 |
| 2nd correct | 8 |
| 3rd correct | 6 |
| 4th correct | 4 |
| 5th+ correct | 2 |
| Invalid / duplicate / wrong letter | 0 |

Position is determined by the order in which valid answers arrive during the round.

---

## Game Lifecycle

```
/menu
  └─▶ show_menu (inline keyboard)
        └─▶ "Start Game" button
              └─▶ ask_player_count  (ConversationHandler state 0)
                    └─▶ ask_round_duration  (ConversationHandler state 1)
                          └─▶ start_game_confirmed
                                └─▶  [5-second countdown]
                                       └─▶ Round 1
                                              │
                                     [round timer expires OR all players answered]
                                              │
                                              ▼
                                         end_round
                                              │
                                    validate + score + persist
                                              │
                                     post leaderboard message
                                              │
                                   [if round_number % 5 == 0]
                                              │
                                    "Continue?" inline keyboard
                                         Yes │ No
                                             │
                                       next round / finish
```

---

## Environment Variables

See [`.env.example`](../.env.example) for a complete template. Required variables:

| Variable | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` / `BOT_TOKEN` | Telegram bot authentication |
| `GROQ_API_KEY` | LLM validation fallback |
| `MONGODB_URI` | Atlas connection string |

Optional tuning variables (`GAME_ROUND_DURATION`, `MAX_PLAYERS`, `CONFIDENCE_THRESHOLD`, etc.) are documented in the example file and defaulted safely in `src/config.py`.

---

## Running Tests

```bash
pytest
```

Test files mirror the source modules under `tests/`. Each test file covers the public interface of its corresponding `src/` module using mocks for external services (Telegram API, Groq, MongoDB).
