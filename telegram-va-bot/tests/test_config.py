import logging

import pytest

from conftest import API_HASH, BOT_TOKEN
from vabot.config import ConfigError, parse_config
from vabot.logs import REDACTED, RedactingFilter

BASE = {"API_ID": "12345", "API_HASH": API_HASH, "BOT_TOKEN": BOT_TOKEN, "OWNER_ID": "42"}


def test_valid_config_with_defaults():
    config = parse_config(BASE)
    assert config.api_id == 12345
    assert config.owner_id == 42
    assert config.send_delay == 10
    assert config.repost_cooldown_hours == 24
    assert config.test_mode is False
    assert config.session_file.name == "account.session"


@pytest.mark.parametrize(
    "override, message",
    [
        ({"API_ID": ""}, "API_ID"),
        ({"API_ID": "abc"}, "API_ID"),
        ({"API_HASH": "court"}, "API_HASH"),
        ({"BOT_TOKEN": "pas-un-jeton"}, "BOT_TOKEN"),
        ({"OWNER_ID": ""}, "OWNER_ID"),
        ({"SEND_DELAY_SECONDS": "1"}, "SEND_DELAY_SECONDS"),
        ({"REPOST_COOLDOWN_HOURS": "-3"}, "REPOST_COOLDOWN_HOURS"),
    ],
)
def test_invalid_values_are_explained(override, message):
    with pytest.raises(ConfigError, match=message):
        parse_config({**BASE, **override})


def test_login_does_not_need_the_bot():
    config = parse_config({"API_ID": "1", "API_HASH": API_HASH}, require_bot=False)
    assert config.bot_token == ""


def test_options():
    config = parse_config(
        {**BASE, "TEST_MODE": "true", "SEND_DELAY_SECONDS": "12,5", "REPOST_COOLDOWN_HOURS": "0"}
    )
    assert config.test_mode is True
    assert config.send_delay == 12.5
    assert config.repost_cooldown_hours == 0


def test_secrets_are_redacted_from_logs():
    record = logging.LogRecord(
        "x", logging.INFO, __file__, 1, "token=%s hash=%s", (BOT_TOKEN, API_HASH), None
    )
    RedactingFilter([BOT_TOKEN, API_HASH]).filter(record)
    assert BOT_TOKEN not in record.getMessage()
    assert API_HASH not in record.getMessage()
    assert REDACTED in record.getMessage()
