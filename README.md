# The Categories Game — Telegram Bot

A multiplayer **Categories Game** bot for Telegram groups.  
Each round the bot picks a random **letter** and **category** — players race to answer first.  
Answers are validated by AI (Groq) for spelling and correctness, and results are stored in MongoDB.

## Features

- AI-powered answer validation via **Groq** (`openai/gpt-oss-20b`)
- Spelling correction (e.g. "Caihro" → "Cairo" ✅)
- Duplicate answer detection within the same game
- Position-based scoring: 1st correct = 10 pts, 2nd = 8, 3rd = 6, 4th = 4, 5th+ = 2
- Configurable player count and round duration
- Rounds end early when all players have answered
- After 5 rounds: choose to continue or finish
- Leaderboard displayed after every round
- All answers and rounds persisted in **MongoDB Atlas**

## Setup

### 1. Clone & install

```bash
git clone https://github.com/<your-org>/The-Categories-Game.git
cd The-Categories-Game
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Create `.env`

Create a `.env` file in the project root with the following variables:

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groq_api_key
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/categories_game?retryWrites=true&w=majority
```

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Get from [@BotFather](https://t.me/BotFather) on Telegram |
| `GROQ_API_KEY` | Get from [console.groq.com](https://console.groq.com) |
| `MONGODB_URI` | MongoDB Atlas connection string (include `/categories_game` database name) |

### 3. Run the bot

```bash
py -m src.main
```

You should see:

```
Connecting to MongoDB...
MongoDB connected and indexes ensured.
Bot started successfully
>>> Starting polling...
```

## How to Play

1. Add the bot to a Telegram group
2. Send `/menu` → press **Start Game**
3. Bot asks: **How many players?** → send a number
4. Bot asks: **How many seconds per round?** → send a number (min 5)
5. After a 5-second countdown, the first round starts
6. Bot shows a **letter** and a **category** — type your answer in the chat
7. The round ends when all players answer or time runs out
8. Bot validates answers with AI, shows scores, and starts the next round
9. After 5 rounds, choose to **continue** or **finish**

## Scoring

| Position | Points |
|---|---|
| 1st correct answer | 10 |
| 2nd correct answer | 8 |
| 3rd correct answer | 6 |
| 4th correct answer | 4 |
| 5th+ correct answer | 2 |

Invalid answers, wrong category, wrong starting letter, and duplicate answers score **0 points**.

## Project Structure

```
src/
  main.py          — Entry point, loads settings, connects to DB, starts bot
  bot.py           — Telegram application builder and handler registration
  handlers.py      — Command handlers, setup conversation, menu callbacks
  round_logic.py   — Round lifecycle: start, end, validate, score, persist
  game_state.py    — In-memory game state per chat
  validation.py    — Groq API integration for answer validation
  scoring.py       — Position-based scoring and player stats
  storage.py       — MongoDB CRUD operations
  models.py        — Dataclasses (GameState, Answer, Round, etc.)
  categories.py    — Category list

tests/             — Unit tests for each module
```

## Branching

- `main` — stable releases
- `Dev` — active development
- `guy` / `haim` — personal feature branches
