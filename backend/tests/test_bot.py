"""Unit tests for the Telegram bot layer (no network calls)."""
from app.bot import _keyboard
from app.bot import settings as bot_settings
from telegram import InlineKeyboardMarkup


def test_keyboard_has_web_app_button():
    kb = _keyboard()
    assert isinstance(kb, InlineKeyboardMarkup)
    open_btn = kb.inline_keyboard[0][0]
    assert open_btn.web_app.url == bot_settings.MINI_APP_URL


def test_keyboard_has_points_callback():
    points_btn = _keyboard().inline_keyboard[1][0]
    assert points_btn.callback_data == "points"
