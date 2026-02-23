
# The Categories Game Telegram Bot

Telegram bot that plays The Categories Game.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Create your local env file:
   - Copy `env.example` to `.env` and fill in values.
4. Run the bot (adjust the entry file name as needed):
   - `python main.py`

## API Keys

Put your API keys in `.env` at the project root (never commit this file).

Example:

```
TELEGRAM_BOT_TOKEN=replace_me
LOG_LEVEL=INFO
```

## Branching

- `main`: stable releases
- `dev`: active development
- `test`: staging / test environment

Suggested flow: feature branch -> `dev` -> `test` -> `main`.
