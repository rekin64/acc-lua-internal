"""Couche Telethon testée avec de vrais objets Telethon et un client simulé (sans réseau)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from telethon import functions, utils
from telethon.tl import types
from telethon.tl.custom import Dialog

from vabot.account import FolderNotFoundError, TelegramAccount, create_client
from vabot.ad import RenderedAd

NOW = datetime.now(timezone.utc)


def megagroup(chat_id, title, **kwargs):
    return types.Channel(
        id=chat_id,
        title=title,
        photo=types.ChatPhotoEmpty(),
        date=NOW,
        megagroup=True,
        access_hash=1,
        **kwargs,
    )


def make_dialog(entity, *, unread=1, muted=False, archived=False):
    raw = types.Dialog(
        peer=utils.get_peer(entity),
        top_message=1,
        read_inbox_max_id=0,
        read_outbox_max_id=0,
        unread_count=unread,
        unread_mentions_count=0,
        unread_reactions_count=0,
        unread_poll_votes_count=0,
        notify_settings=types.PeerNotifySettings(mute_until=NOW + timedelta(days=365) if muted else None),
        folder_id=1 if archived else None,
    )
    return Dialog(None, raw, {utils.get_peer_id(entity): entity}, None)


class FakeTelethonClient:
    def __init__(self, filters, dialogs):
        self.filters = filters
        self.dialogs = dialogs
        self.sent = []

    def is_connected(self):
        return True

    async def is_user_authorized(self):
        return True

    async def __call__(self, request):
        assert isinstance(request, functions.messages.GetDialogFiltersRequest)
        return types.messages.DialogFilters(filters=self.filters)

    def iter_dialogs(self, **kwargs):
        async def generator():
            for dialog in self.dialogs:
                yield dialog

        return generator()

    async def send_file(self, peer, file, caption, parse_mode):
        self.sent.append(("photo", peer, file, caption))
        return SimpleNamespace(photo="UPLOADED_PHOTO")

    async def send_message(self, peer, text, parse_mode, link_preview):
        self.sent.append(("text", peer, text))


@pytest.fixture
def account():
    folder = types.DialogFilter(
        id=3,
        title=types.TextWithEntities(text="VA OFM", entities=[]),
        pinned_peers=[],
        include_peers=[types.InputPeerChannel(101, 1), types.InputPeerChannel(104, 1)],
        exclude_peers=[types.InputPeerChannel(103, 1)],
        groups=True,
        exclude_muted=True,
    )
    read_only_chat = types.Chat(
        id=42,
        title="F basic read-only",
        photo=types.ChatPhotoEmpty(),
        participants_count=5,
        date=NOW,
        version=1,
        default_banned_rights=types.ChatBannedRights(until_date=None, send_messages=True),
    )
    dialogs = [
        make_dialog(megagroup(101, "A included"), unread=0, muted=True),  # inclus : options ignorées
        make_dialog(megagroup(102, "B by category")),
        make_dialog(megagroup(103, "C excluded")),
        make_dialog(
            types.Channel(
                id=104,
                title="D channel",
                photo=types.ChatPhotoEmpty(),
                date=NOW,
                broadcast=True,
                access_hash=1,
            )
        ),
        make_dialog(megagroup(105, "E muted"), muted=True),
        make_dialog(read_only_chat),
        make_dialog(types.User(id=7, first_name="Membre", access_hash=1)),
    ]
    return TelegramAccount(FakeTelethonClient([types.DialogFilterDefault(), folder], dialogs))


async def test_list_folders_skips_all_chats(account):
    folders = await account.list_folders()
    assert [(f.id, f.title) for f in folders] == [(3, "VA OFM")]


async def test_folder_groups_follow_telegram_rules(account):
    groups = await account.folder_groups(3)
    assert [g.title for g in groups] == ["A included", "B by category", "F basic read-only"]
    assert [g.chat_id for g in groups] == [-1000000000101, -1000000000102, -42]
    assert groups[0].text_block is None and groups[0].peer is not None
    assert "administrateurs" in groups[2].text_block


async def test_unknown_folder(account):
    with pytest.raises(FolderNotFoundError):
        await account.folder_groups(99)


async def test_photo_is_uploaded_once(account):
    ad = RenderedAd(text_html="<b>Hiring</b>", photo_path="/data/ad_photo.jpg")
    cache = {}
    await account.send_ad("peer1", ad, cache)
    await account.send_ad("peer2", ad, cache)
    sent = account.client.sent
    assert sent[0][2] == "/data/ad_photo.jpg"
    assert sent[1][2] == "UPLOADED_PHOTO"  # réutilisation de l'image déjà envoyée


async def test_text_ad(account):
    await account.send_ad("peer1", RenderedAd(text_html="Hello"), {})
    assert account.client.sent == [("text", "peer1", "Hello")]


def test_client_does_not_persist_member_data(config):
    client = create_client(config)
    assert client.session.save_entities is False
    assert client.flood_sleep_threshold == 60
