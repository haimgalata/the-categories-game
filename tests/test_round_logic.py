# tests/test_round_logic.py

import string
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models import AnswerDraft, RoundResult
from src.round_logic import end_round, pick_category, pick_letter, show_final_scores, start_round


def test_pick_letter_returns_single_uppercase_letter():
    letter = pick_letter()

    assert isinstance(letter, str)
    assert len(letter) == 1
    assert letter in string.ascii_uppercase


def test_pick_letter_randomness():
    letters = {pick_letter() for _ in range(100)}
    assert len(letters) > 1  # should not always return same letter


def test_pick_category_valid_list():
    categories = ["City", "Country"]
    result = pick_category(categories)

    assert result in categories


def test_pick_category_empty_list():
    with pytest.raises(ValueError):
        pick_category([])


@pytest.mark.asyncio
async def test_end_round_group_summary_contains_status_rows(monkeypatch):
    chat_id = 777
    result = RoundResult(
        game_id="g1",
        round_number=1,
        letter="C",
        category="City",
        answers=[
            AnswerDraft(user_id=1, player_name="Alice", text="Cairo", ts_ms=1, message_id="11"),
            AnswerDraft(user_id=2, player_name="Bob", text="123", ts_ms=2, message_id="12"),
            AnswerDraft(user_id=3, player_name="Cara", text="Cairo", ts_ms=3, message_id="13"),
            AnswerDraft(user_id=4, player_name="Dan", text="Chicago", ts_ms=4, message_id="14"),
        ],
    )
    game = SimpleNamespace(
        game_id="g1",
        is_group_mode=True,
        round_id="r1",
        round_started_ms=0,
    )
    round_obj = SimpleNamespace(round_id="r1", ended_at_ms=0)

    monkeypatch.setattr("src.round_logic.is_round_active", lambda _: True)
    monkeypatch.setattr("src.round_logic._cancel_round_jobs", lambda *_: None)
    monkeypatch.setattr("src.round_logic.finalize_round", lambda _: result)
    monkeypatch.setattr("src.round_logic.get_or_create_game", lambda _: game)
    monkeypatch.setattr("src.round_logic.get_game", lambda _: game)
    monkeypatch.setattr("src.round_logic.new_round", lambda **_: round_obj)
    monkeypatch.setattr("src.round_logic.save_round", lambda *_: None)
    monkeypatch.setattr("src.round_logic._try_save_answer", lambda *_, **__: None)
    monkeypatch.setattr("src.round_logic.add_points", lambda *_, **__: None)
    monkeypatch.setattr("src.round_logic.is_game_over", lambda _: True)

    def fake_validate_submission(payload):
        if payload.answer == "123":
            return SimpleNamespace(
                valid=False,
                corrected_answer="123",
                reason="not_english",
                message="invalid",
                ui_actions=SimpleNamespace(reply_to_message_id=payload.message_id),
            )
        return SimpleNamespace(
            valid=True,
            corrected_answer=payload.answer,
            reason="ok",
            message="ok",
            ui_actions=SimpleNamespace(reply_to_message_id=payload.message_id),
        )

    monkeypatch.setattr("src.round_logic.validate_submission", fake_validate_submission)
    monkeypatch.setattr(
        "src.round_logic.has_answer_been_used",
        lambda game_id, letter, category, answer: answer == "Cairo" and game_id == "g1" and letter == "C" and category == "City",
    )

    show_final_scores_mock = AsyncMock()
    monkeypatch.setattr("src.round_logic.show_final_scores", show_final_scores_mock)

    app = MagicMock()
    app.bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=999))

    await end_round(chat_id, app)

    summary_text = app.bot.send_message.await_args.kwargs["text"]
    assert "📊 Round 1 Results" in summary_text
    assert "Alice — Cairo — ❌ Duplicate" in summary_text
    assert "Bob — 123 — ❌ Invalid" in summary_text
    assert "Cara — Cairo — ❌ Duplicate" in summary_text
    assert "Dan — Chicago — ✅ Accepted" in summary_text
    show_final_scores_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_show_final_scores_renders_ranked_totals(monkeypatch):
    chat_id = 9
    monkeypatch.setattr("src.round_logic.get_scores", lambda _: {30: 20, 10: 50})
    monkeypatch.setattr("src.round_logic.reset_game", lambda _: None)

    app = MagicMock()
    app.bot.get_chat_member = AsyncMock(
        side_effect=[
            SimpleNamespace(user=SimpleNamespace(first_name="TopPlayer")),
            SimpleNamespace(user=SimpleNamespace(first_name="RunnerUp")),
        ]
    )
    app.bot.send_message = AsyncMock()

    await show_final_scores(chat_id, app)

    text = app.bot.send_message.await_args.args[1]
    assert "🏁 Final Results" in text
    assert "1. TopPlayer - 50 pts" in text
    assert "2. RunnerUp - 20 pts" in text


@pytest.mark.asyncio
async def test_start_round_group_sends_static_message_without_edits(monkeypatch):
    chat_id = 123
    game = SimpleNamespace(current_round=0, max_rounds=5, round_letter="", round_category="", pinned_message_id=0)

    monkeypatch.setattr("src.round_logic.is_round_active", lambda _: False)
    monkeypatch.setattr("src.round_logic._cancel_round_jobs", lambda *_: None)
    monkeypatch.setattr("src.round_logic.pick_letter", lambda: "B")
    monkeypatch.setattr("src.round_logic.pick_category", lambda _: "City")
    monkeypatch.setattr("src.round_logic.load_categories", lambda: ["City"])
    monkeypatch.setattr("src.round_logic.get_round_duration", lambda _: 30)
    monkeypatch.setattr("src.round_logic.get_settings", lambda: SimpleNamespace(enable_pinning=False))
    monkeypatch.setattr("src.round_logic.set_round_message_id", lambda *_: None)
    monkeypatch.setattr("src.round_logic.set_countdown_active", lambda *_: None)
    monkeypatch.setattr("src.round_logic._schedule_round_end", lambda *_: None)
    monkeypatch.setattr("src.round_logic._schedule_round_tick", lambda *_: None)

    def fake_set_round_prompt(_, letter, category):
        game.current_round = 1
        game.round_letter = letter
        game.round_category = category

    monkeypatch.setattr("src.round_logic.set_round_prompt", fake_set_round_prompt)
    monkeypatch.setattr("src.round_logic.get_game", lambda _: game)

    app = MagicMock()
    app.bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=5))
    app.bot.edit_message_text = AsyncMock()

    await start_round(chat_id, app)

    app.bot.send_message.assert_awaited_once()
    sent_text = app.bot.send_message.await_args.kwargs["text"]
    assert "🎮 Round 1/5" in sent_text
    assert "🔠 Letter: B" in sent_text
    assert "📚 Category: City" in sent_text
    assert "⏱️ Time left: 30s" in sent_text
    assert "🟩" in sent_text
    app.bot.edit_message_text.assert_not_awaited()


def test_segmented_timer_bar_clamps_to_bounds():
    from src.round_logic import _build_segmented_timer_bar

    assert _build_segmented_timer_bar(time_left=10, total_time=10) == "🟩 🟩 🟩 🟩 🟩 🟩 🟩 🟩 🟩 🟩"
    assert _build_segmented_timer_bar(time_left=0, total_time=10) == "⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜"
    assert _build_segmented_timer_bar(time_left=-5, total_time=10) == "⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜"


@pytest.mark.asyncio
async def test_start_round_uses_single_countdown_message_before_round(monkeypatch):
    chat_id = 456
    monkeypatch.setattr("src.round_logic.is_round_active", lambda _: False)
    monkeypatch.setattr("src.round_logic._cancel_round_jobs", lambda *_: None)
    monkeypatch.setattr("src.round_logic.set_countdown_active", lambda *_: None)
    monkeypatch.setattr("src.round_logic.asyncio.sleep", AsyncMock())

    send_round_prompt = AsyncMock()
    monkeypatch.setattr("src.round_logic._send_round_prompt", send_round_prompt)

    app = MagicMock()
    app.bot.send_message = AsyncMock()
    app.bot.edit_message_text = AsyncMock()

    await start_round(
        chat_id,
        app,
        countdown_message_id=999,
        countdown_prefix="⏳ Starting in",
        intro_text="Intro text",
    )

    app.bot.send_message.assert_not_awaited()
    assert app.bot.edit_message_text.await_count == 4
    assert app.bot.edit_message_text.await_args_list[0].kwargs["message_id"] == 999
    assert "⏳ Starting in 4..." in app.bot.edit_message_text.await_args_list[0].kwargs["text"]
    assert "⏳ Starting in 1..." in app.bot.edit_message_text.await_args_list[-1].kwargs["text"]
    send_round_prompt.assert_awaited_once_with(chat_id, app)


@pytest.mark.asyncio
async def test_end_round_non_final_sends_single_results_with_countdown(monkeypatch):
    chat_id = 555
    result = RoundResult(
        game_id="g2",
        round_number=2,
        letter="M",
        category="Movie",
        answers=[AnswerDraft(user_id=1, player_name="Alice", text="Matrix", ts_ms=1, message_id="9")],
    )
    game = SimpleNamespace(game_id="g2", is_group_mode=True, round_id="r2", round_started_ms=0)
    round_obj = SimpleNamespace(round_id="r2", ended_at_ms=0)

    monkeypatch.setattr("src.round_logic.is_round_active", lambda _: True)
    monkeypatch.setattr("src.round_logic._cancel_round_jobs", lambda *_: None)
    monkeypatch.setattr("src.round_logic.finalize_round", lambda _: result)
    monkeypatch.setattr("src.round_logic.get_or_create_game", lambda _: game)
    monkeypatch.setattr("src.round_logic.get_game", lambda _: game)
    monkeypatch.setattr("src.round_logic.new_round", lambda **_: round_obj)
    monkeypatch.setattr("src.round_logic.save_round", lambda *_: None)
    monkeypatch.setattr("src.round_logic._try_save_answer", lambda *_, **__: None)
    monkeypatch.setattr("src.round_logic.add_points", lambda *_, **__: None)
    monkeypatch.setattr("src.round_logic.has_answer_been_used", lambda *_, **__: False)
    monkeypatch.setattr("src.round_logic.is_game_over", lambda _: False)
    monkeypatch.setattr(
        "src.round_logic.validate_submission",
        lambda payload: SimpleNamespace(
            valid=True,
            corrected_answer=payload.answer,
            reason="ok",
            message="ok",
            ui_actions=SimpleNamespace(reply_to_message_id=payload.message_id),
        ),
    )

    scheduled = {}

    def fake_schedule_next_round_countdown(chat_id_arg, app_arg, *, seconds, message_id, summary_text):
        scheduled["chat_id"] = chat_id_arg
        scheduled["seconds"] = seconds
        scheduled["message_id"] = message_id
        scheduled["summary_text"] = summary_text

    monkeypatch.setattr("src.round_logic._schedule_next_round_countdown", fake_schedule_next_round_countdown)

    app = MagicMock()
    app.bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=321))

    await end_round(chat_id, app)

    app.bot.send_message.assert_awaited_once()
    sent_text = app.bot.send_message.await_args.kwargs["text"]
    assert "📊 Round 2 Results" in sent_text
    assert "Alice — Matrix — ✅ Accepted" in sent_text
    assert "⏳ Next round in 5..." in sent_text
    assert scheduled["chat_id"] == chat_id
    assert scheduled["seconds"] == 5
    assert scheduled["message_id"] == 321
    assert "📊 Round 2 Results" in scheduled["summary_text"]
