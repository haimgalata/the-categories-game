import pytest
from unittest.mock import AsyncMock, MagicMock

from src.handlers import (
    handle_message,
    start_game,
    stop_game,
)


# ------------------------
# handle_message
# ------------------------

@pytest.mark.asyncio
async def test_handle_message_no_active_round(monkeypatch):
    update = MagicMock()
    context = MagicMock()

    update.effective_chat.id = 1
    update.effective_user.id = 10
    update.message.text = "Cairo"
    update.message.reply_text = AsyncMock()

    monkeypatch.setattr("src.handlers.is_round_active", lambda chat_id: False)

    await handle_message(update, context)

    update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_handle_message_duplicate(monkeypatch):
    update = MagicMock()
    context = MagicMock()

    update.effective_chat.id = 1
    update.effective_user.id = 10
    update.message.text = "Cairo"
    update.message.reply_text = AsyncMock()

    monkeypatch.setattr("src.handlers.is_round_active", lambda chat_id: True)
    monkeypatch.setattr("src.handlers.record_answer", lambda *args, **kwargs: False)

    await handle_message(update, context)

    update.message.reply_text.assert_called_once()


# ------------------------
# start_game
# ------------------------

@pytest.mark.asyncio
async def test_start_game_calls_start_round(monkeypatch):
    update = MagicMock()
    context = MagicMock()

    update.effective_chat.id = 1
    update.message.reply_text = AsyncMock()

    monkeypatch.setattr("src.handlers.is_round_active", lambda chat_id: False)

    called = False

    async def fake_start_round(chat_id, app):
        nonlocal called
        called = True

    monkeypatch.setattr("src.handlers.start_round", fake_start_round)

    await start_game(update, context)

    assert called


# ------------------------
# stop_game
# ------------------------

@pytest.mark.asyncio
async def test_stop_game_resets(monkeypatch):
    update = MagicMock()
    context = MagicMock()

    update.effective_chat.id = 1
    update.message.reply_text = AsyncMock()

    called = False

    def fake_reset(chat_id):
        nonlocal called
        called = True

    monkeypatch.setattr("src.handlers.reset_game", fake_reset)

    await stop_game(update, context)

    assert called
