from unittest.mock import AsyncMock, MagicMock

import pytest

from src.handlers import handle_message, stop_game


def _make_update(*, text: str, chat_type: str = "group") -> MagicMock:
    update = MagicMock()
    message = MagicMock()
    message.text = text
    message.message_id = 101
    message.reply_text = AsyncMock()
    update.effective_message = message
    update.effective_chat.id = 1
    update.effective_chat.type = chat_type
    update.effective_user.id = 10
    update.effective_user.first_name = "Alice"
    return update


@pytest.mark.asyncio
async def test_group_text_start_triggers_game_start(monkeypatch):
    update = _make_update(text="start", chat_type="group")
    context = MagicMock()

    called = False

    async def fake_start_from_message(update_arg, context_arg):
        nonlocal called
        called = True
        assert update_arg is update
        assert context_arg is context

    monkeypatch.setattr("src.handlers._start_game_from_message", fake_start_from_message)

    await handle_message(update, context)

    assert called is True


@pytest.mark.asyncio
async def test_group_round_first_answer_has_no_reply(monkeypatch):
    update = _make_update(text="Cairo", chat_type="group")
    context = MagicMock()

    monkeypatch.setattr("src.handlers.is_countdown_active", lambda _: False)
    monkeypatch.setattr("src.handlers.is_round_active", lambda _: True)
    monkeypatch.setattr("src.handlers.record_answer", lambda **_: True)
    monkeypatch.setattr("src.handlers.get_round_answers", lambda _: [])
    monkeypatch.setattr("src.handlers.get_num_players", lambda _: 5)

    end_round = AsyncMock()
    monkeypatch.setattr("src.handlers.end_round", end_round)

    await handle_message(update, context)

    update.effective_message.reply_text.assert_not_called()
    end_round.assert_not_called()


@pytest.mark.asyncio
async def test_group_round_duplicate_answer_has_no_reply(monkeypatch):
    update = _make_update(text="Cairo", chat_type="group")
    context = MagicMock()

    monkeypatch.setattr("src.handlers.is_countdown_active", lambda _: False)
    monkeypatch.setattr("src.handlers.is_round_active", lambda _: True)
    monkeypatch.setattr("src.handlers.record_answer", lambda **_: False)

    await handle_message(update, context)

    update.effective_message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_private_message_during_countdown_has_no_reply(monkeypatch):
    update = _make_update(text="Cairo", chat_type="private")
    context = MagicMock()

    monkeypatch.setattr("src.handlers.is_countdown_active", lambda _: True)
    monkeypatch.setattr("src.handlers.is_round_active", lambda _: False)

    await handle_message(update, context)

    update.effective_message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_private_message_outside_round_has_no_reply(monkeypatch):
    update = _make_update(text="Cairo", chat_type="private")
    context = MagicMock()

    monkeypatch.setattr("src.handlers.is_countdown_active", lambda _: False)
    monkeypatch.setattr("src.handlers.is_round_active", lambda _: False)

    await handle_message(update, context)

    update.effective_message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_stop_game_resets(monkeypatch):
    update = _make_update(text="anything", chat_type="private")
    context = MagicMock()

    called = False

    def fake_reset(chat_id):
        nonlocal called
        called = True
        assert chat_id == 1

    monkeypatch.setattr("src.handlers.reset_game", fake_reset)

    await stop_game(update, context)

    assert called is True
