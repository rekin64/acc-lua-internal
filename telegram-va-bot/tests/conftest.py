"""Outils communs aux tests : configuration, base temporaire et faux compte Telegram."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vabot.account import FolderInfo, FolderNotFoundError  # noqa: E402
from vabot.config import parse_config  # noqa: E402
from vabot.publisher import GroupInfo  # noqa: E402
from vabot.storage import Database  # noqa: E402

OWNER_ID = 111
STRANGER_ID = 999
BOT_TOKEN = "123456:" + "A" * 35
API_HASH = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def config(tmp_path):
    return parse_config(
        {
            "API_ID": "12345",
            "API_HASH": API_HASH,
            "BOT_TOKEN": BOT_TOKEN,
            "OWNER_ID": str(OWNER_ID),
            "DATA_DIR": str(tmp_path),
            "SEND_DELAY_SECONDS": "5",
        }
    )


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    yield database
    database.close()


class FakeAccount:
    """Imite TelegramAccount sans aucun accès réseau."""

    def __init__(self, groups=None, *, authorized=True, username="moncompte", fail=None):
        self.folders = [FolderInfo(7, "VA OFM"), FolderInfo(8, "Autres")]
        self.groups = {7: list(groups or [])}
        self.authorized = authorized
        self._username = username
        self.fail = dict(fail or {})  # peer -> exception à lever
        self.sent: list[tuple[object, object]] = []

    async def is_authorized(self):
        return self.authorized

    async def username(self):
        return self._username if self.authorized else None

    async def label(self):
        return f"@{self._username}" if self.authorized else None

    async def list_folders(self):
        return list(self.folders)

    async def folder_groups(self, folder_id):
        if folder_id not in {f.id for f in self.folders}:
            raise FolderNotFoundError(folder_id)
        return list(self.groups.get(folder_id, []))

    async def send_ad(self, peer, ad, cache):
        if peer in self.fail:
            raise self.fail[peer]
        self.sent.append((peer, ad))


def group(
    chat_id: int, title: str, text_block: str | None = None, photo_block: str | None = None
) -> GroupInfo:
    return GroupInfo(
        chat_id=chat_id, title=title, text_block=text_block, photo_block=photo_block, peer=f"peer{chat_id}"
    )


@pytest.fixture
def fake_account():
    return FakeAccount(
        [
            group(-1001, "OFM Jobs"),
            group(-1002, "VA Hiring"),
            group(-1003, "Admins only", text_block="seuls les administrateurs peuvent écrire"),
        ]
    )
