# tests/test_bot.py

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from telegram.ext import Application
from src.bot import build_application, register_handlers


def test_build_application_returns_application():
    token = "123:TESTTOKEN"
    app = build_application(token)
    assert isinstance(app, Application)


def test_register_handlers_does_not_crash():
    token = "123:TESTTOKEN"
    app = build_application(token)
    register_handlers(app)


def test_handlers_registered():
    token = "123:TESTTOKEN"
    app = build_application(token)
    register_handlers(app)
    assert len(app.handlers) > 0
