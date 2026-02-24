# Categories Game Bot — Planning (Tech Outline)

This document describes the next stage of the Telegram Categories Game bot.
You can use it as a checklist while you implement code later.

## Goals

- Run a full 5‑round Categories game in a Telegram group.
- Randomly pick a letter (A‑Z) and a category from a list each round.
- Give each player 30 seconds to answer.
- Validate answers with Groq (strict JSON) for correctness, spelling, and category match. 
- Score based on correctness + response time.
- Store correct answers in MongoDB and reject repeats.
- After each round, show a live leaderboard.
- After 5 rounds, ask to continue; if no, show full stats and end.
- Track per‑player stats: correct %, avg response time, etc.

## Tech Stack (Assumed)

- Python
- `python-telegram-bot` (ptb) v21+
- Groq API for validation
- MongoDB for persistence

## Game Flow (High Level)

1. `/start_game` in a group creates a new game session.
2. For each round:
   - Pick a random letter and random category.
   - Open a 30‑second answer window.
   - Collect each user's first answer only.
   - Validate each answer with Groq.
   - Score and store valid answers.
   - Show round scores + total leaderboard.
3. After 5 rounds, ask “Continue?”:
   - Yes → start another set of rounds.
   - No → show final results and statistics.

## Data Model (MongoDB)

Collections (suggested):

- `games`
  - `game_id`, `chat_id`, `status`, `current_round`, `started_at`, `ended_at`
- `rounds`
  - `game_id`, `round_number`, `letter`, `category`, `started_at`, `ended_at`
- `answers`
  - `game_id`, `round_id`, `user_id`, `username`, `raw_text`, `corrected_text`,
    `valid`, `score`, `response_ms`
- `players`
  - `chat_id`, `user_id`, `username`, `total_score`, `correct_count`,
    `answer_count`, `avg_response_ms`

Indexes:

- Unique index on (`game_id`, `round_id`, `user_id`) to prevent multi‑answers.
- Unique index on (`game_id`, `category`, `letter`, `corrected_text`) to block repeats.

## Groq Validation (Strict JSON)

Goal: return a strict JSON object so the bot can parse it reliably.

Example response schema:

```
{
  "valid": true,
  "corrected": "Cairo",
  "reason": "Cairo is a city in Egypt and matches the letter C.",
  "categoryMatch": true
}
```

Rules:

- Must start with the round letter after correction.
- Must match the category (e.g., City vs Country).
- If spelling is close but correct, return `corrected` and `valid=true`.
- If wrong category or not real, return `valid=false`.

## Scoring Model (Suggested)

- Base: +10 for valid.
- Time bonus: +0 to +10 based on how fast they answered.
  - Example: `time_bonus = max(0, 10 - (response_ms / 3000))`
- Total per answer = base + time bonus.
- Invalid or repeated answers score 0.

## Stats to Track

Per player:

- Total score
- Correct %
- Average response time
- Best streak (optional)
- Category accuracy (optional)

## Telegram Commands / Messages

- `/start_game`: Create a new game for the group.
- `/stop_game`: End the game and show final stats.
- `/score`: Show current leaderboard.
- Messages during round: treated as answers.

## Implementation Steps (Checklist)

1. **Game state manager** - Haim
   - Keep in‑memory state per `chat_id`.
   - Track round start time and timer job.
2. **Round selection** - Haim
   - Random letter A‑Z.
   - Random category from a fixed list (config file or DB).
3. **Answer collection** - Haim
   - Accept one answer per user per round.
   - Store timestamp to compute response time.
4. **Groq validation** - Guy
   - Send answer, letter, category.
   - Parse strict JSON response.
5. **Scoring + storage** - Guy
   - Score valid answers.
   - Save to MongoDB and update player stats.
   - Reject repeated answers in this game (or global).
6. **Leaderboard + stats** - Guy
   - After round: show scores + totals.
   - End game: show full stats.
7. **Continue prompt** -Haim
   - After 5 rounds, ask if players want to continue.

## Environment Variables

- `TELEGRAM_BOT_TOKEN`
- `GROQ_API_KEY`
- `MONGODB_URI`

## Suggested Project Files (Example)

Use this as a simple, clean layout. Adjust names if you want.

```
The-Categories-Game/
  .gitignore
  .editorconfig
  README.md
  requirements.txt
  .env               # local only, never commit
  docs/
    README.md        # this plan
  src/
    __init__.py
    main.py          # bot entrypoint - Haim
    bot.py           # telegram setup, handlers register -Haim
    handlers.py      # commands + message routing -Haim
    game_state.py    # in-memory game state per chat - Guy
    round_logic.py   # round lifecycle + timers - Haim
    validation.py    # Groq validation client - Guy
    scoring.py       # scoring rules - Guy
    storage.py       # MongoDB client + queries - GUY
    models.py        # data models / helpers - Guy
    categories.py    # list of categories - Haim
  tests/
    test_validation.py
    test_scoring.py 
```

## Function Map (src/ and tests/)

Use these as the planned function names, return types, and responsibilities.

### `src/main.py`

`main() -> None`  
Params: none  
Returns: None  
Description: Load config, build the bot application, and start polling.

`get_settings() -> dict`  
Params: none  
Returns: A dict with `TELEGRAM_BOT_TOKEN`, `GROQ_API_KEY`, `MONGODB_URI`.  
Description: Read environment variables and validate required values.

### `src/bot.py`

`build_application(token: str) -> Application`  
Params: `token` (bot token).  
Returns: A `python-telegram-bot` `Application`.  
Description: Create and configure the PTB application.

`register_handlers(app: Application) -> None`  
Params: `app` (Application).  
Returns: None.  
Description: Attach all command and message handlers from `handlers.py`.

`run_bot(app: Application) -> None`  
Params: `app` (Application).  
Returns: None.  
Description: Start polling and keep the bot running.

### `src/handlers.py`

`start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None`  
Params: Telegram update/context.  
Returns: None.  
Description: Create a new game for the group chat and start round 1.

`stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None`  
Params: Telegram update/context.  
Returns: None.  
Description: End the current game and display final stats.

`score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None`  
Params: Telegram update/context.  
Returns: None.  
Description: Show the current leaderboard for the game.

`handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None`  
Params: Telegram update/context.  
Returns: None.  
Description: Treat incoming messages as answers during active rounds.

`continue_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None`  
Params: Telegram update/context.  
Returns: None.  
Description: Handle the continue/stop prompt after 5 rounds.

### `src/game_state.py`

`get_or_create_game(chat_id: int) -> GameState`  
Params: `chat_id` (group chat id).  
Returns: In-memory `GameState`.  
Description: Fetch or initialize a game state for a chat.

`reset_game(chat_id: int) -> None`  
Params: `chat_id`.  
Returns: None.  
Description: Clear game state for a chat.

`is_round_active(chat_id: int) -> bool`  
Params: `chat_id`.  
Returns: True if a round is active.  
Description: Check whether answers should be accepted.

`record_answer(chat_id: int, user_id: int, text: str, ts_ms: int) -> bool`  
Params: chat id, user id, answer text, timestamp in ms.  
Returns: True if accepted, False if duplicate for this round.  
Description: Store the first answer per user per round.

`get_round_answers(chat_id: int) -> list[Answer]`  
Params: `chat_id`.  
Returns: List of `Answer` objects for the round.  
Description: Read collected answers for validation and scoring.

`set_round_prompt(chat_id: int, letter: str, category: str) -> None`  
Params: chat id, letter, category.  
Returns: None.  
Description: Store current round letter/category in state.

`finalize_round(chat_id: int) -> RoundResult`  
Params: `chat_id`.  
Returns: Round summary object.  
Description: End the round and freeze current answers.

### `src/round_logic.py`

`pick_letter() -> str`  
Params: none.  
Returns: A single uppercase letter A-Z.  
Description: Randomly select the round letter.

`pick_category(categories: list[str]) -> str`  
Params: list of category strings.  
Returns: One category.  
Description: Randomly select a category.

`start_round(chat_id: int, app: Application) -> None`  
Params: chat id, PTB application.  
Returns: None.  
Description: Initialize round state and announce prompt.

`schedule_round_end(chat_id: int, app: Application, seconds: int) -> Job`  
Params: chat id, application, seconds.  
Returns: A PTB `Job` object.  
Description: Schedule the round end after 30 seconds.

`end_round(chat_id: int, app: Application) -> None`  
Params: chat id, application.  
Returns: None.  
Description: Close the round, trigger validation, scoring, and leaderboard.

### `src/validation.py`

`build_groq_prompt(answer: str, letter: str, category: str) -> str`  
Params: answer text, letter, category.  
Returns: Prompt string.  
Description: Build a strict JSON prompt for Groq.

`validate_answer_groq(answer: str, letter: str, category: str) -> ValidationResult`  
Params: answer text, letter, category.  
Returns: ValidationResult with valid/corrected/reason.  
Description: Call Groq and parse response

`parse_groq_response(text: str) -> ValidationResult`  
Params: raw Groq response text.  
Returns: ValidationResult.  
Description: Parse and validate the strict JSON response.

### `src/scoring.py`

`calc_time_bonus(response_ms: int) -> int`  
Params: response time in ms.  
Returns: integer bonus score.  
Description: Compute time bonus based on speed.

`score_answer(valid: bool, response_ms: int) -> int`  
Params: validity, response time in ms.  
Returns: total score for the answer.  
Description: Apply base points plus time bonus.

`update_player_stats(stats: PlayerStats, is_valid: bool, response_ms: int, score: int) -> PlayerStats`  
Params: stats object and latest answer data.  
Returns: updated stats object.  
Description: Increment totals and averages.

`compute_leaderboard(players: list[PlayerStats]) -> list[PlayerStats]`  
Params: list of player stats.  
Returns: players sorted by total score.  
Description: Build leaderboard order.

### `src/storage.py`

`get_db(uri: str) -> Database`  
Params: MongoDB connection string.  
Returns: Database handle.  
Description: Connect to MongoDB and return a DB object.

`ensure_indexes(db: Database) -> None`  
Params: db handle.  
Returns: None.  
Description: Create required indexes for uniqueness.

`save_game(game: Game) -> None`  
Params: game object.  
Returns: None.  
Description: Insert or update a game record.

`save_round(round_obj: Round) -> None`  
Params: round object.  
Returns: None.  
Description: Insert or update a round record.

`save_answer(answer: Answer) -> None`  
Params: answer object.  
Returns: None.  
Description: Insert answer record.

`upsert_player_stats(stats: PlayerStats) -> None`  
Params: stats object.  
Returns: None.  
Description: Update player stats for the chat.

`has_answer_been_used(game_id: str, letter: str, category: str, corrected_text: str) -> bool`  
Params: ids and normalized answer.  
Returns: True if already used.  
Description: Enforce no-repeat rule.

### `src/models.py`

`now_ms() -> int`  
Params: none.  
Returns: current time in milliseconds.  
Description: Helper for response timing.

`new_game_state(chat_id: int) -> GameState`  
Params: chat id.  
Returns: GameState object.  
Description: Create a new in-memory game state.

`new_round(game_id: str, round_number: int, letter: str, category: str) -> Round`  
Params: ids and round data.  
Returns: Round object.  
Description: Create a round record.

`new_answer(game_id: str, round_id: str, user_id: int, raw_text: str, corrected_text: str, valid: bool, score: int, response_ms: int) -> Answer`  
Params: ids, answer data, score, response time.  
Returns: Answer object.  
Description: Create an answer record.

`new_player_stats(chat_id: int, user_id: int, username: str) -> PlayerStats`  
Params: ids and username.  
Returns: PlayerStats object.  
Description: Initialize player stats.

### `src/categories.py`

`load_categories() -> list[str]`  
Params: none.  
Returns: list of categories.  
Description: Provide the base category list (static or from file).

`normalize_category(name: str) -> str`  
Params: category name.  
Returns: normalized category string.  
Description: Normalize category comparisons.

### `tests/test_validation.py`

`test_valid_city_cairo() -> None`  
Params: none.  
Returns: None.  
Description: Accept a valid city with correct letter.

`test_invalid_city_country() -> None`  
Params: none.  
Returns: None.  
Description: Reject a country when category is city.

`test_correction_applied() -> None`  
Params: none.  
Returns: None.  
Description: Accept a misspelling corrected by Groq.

### `tests/test_scoring.py`

`test_score_valid_fast() -> None`  
Params: none.  
Returns: None.  
Description: Fast valid answer gets higher score.

`test_score_valid_slow() -> None`  
Params: none.  
Returns: None.  
Description: Slow valid answer gets lower score.

`test_score_invalid() -> None`  
Params: none.  
Returns: None.  
Description: Invalid answer scores zero.

`test_time_bonus_floor() -> None`  
Params: none.  
Returns: None.  
Description: Bonus does not go below zero.

Notes:

- Keep `.env` local only.
- If you don’t want `src/`, you can put the Python files at project root.
