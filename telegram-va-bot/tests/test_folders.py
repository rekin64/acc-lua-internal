from datetime import datetime, timedelta, timezone

from telethon.tl import types

from vabot.folders import (
    DialogState,
    FolderRule,
    check_send_rights,
    dialog_in_folder,
    folder_title,
    is_muted,
    rule_from_filter,
)

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
CHANNEL_ID = 1234567890
CHANNEL_MARKED = -1001234567890


# --- Appartenance au dossier ---------------------------------------------------


def test_explicitly_included_group():
    rule = FolderRule(id=1, title="VA OFM", include_ids=frozenset({-1001}))
    assert dialog_in_folder(rule, DialogState(-1001))
    assert not dialog_in_folder(rule, DialogState(-1002))


def test_groups_category_with_exclusions():
    rule = FolderRule(
        id=1, title="Groupes", include_ids=frozenset(), exclude_ids=frozenset({-1002}), groups=True
    )
    assert dialog_in_folder(rule, DialogState(-1001))
    assert not dialog_in_folder(rule, DialogState(-1002))


def test_inclusion_wins_over_flags_and_exclusion_wins_over_category():
    rule = FolderRule(
        id=1,
        title="x",
        include_ids=frozenset({-1001}),
        exclude_ids=frozenset({-1002}),
        groups=True,
        exclude_muted=True,
        exclude_read=True,
        exclude_archived=True,
    )
    # Inclus explicitement : toujours dans le dossier, même muet / lu / archivé.
    assert dialog_in_folder(rule, DialogState(-1001, muted=True, unread=False, archived=True))
    # Par catégorie : les options d'exclusion s'appliquent.
    assert dialog_in_folder(rule, DialogState(-1003, unread=True))
    assert not dialog_in_folder(rule, DialogState(-1003, muted=True, unread=True))
    assert not dialog_in_folder(rule, DialogState(-1003, unread=False))
    assert not dialog_in_folder(rule, DialogState(-1003, unread=True, archived=True))
    assert not dialog_in_folder(rule, DialogState(-1002, unread=True))


def test_chatlist_folder_only_contains_its_list():
    rule = FolderRule(id=2, title="Partagé", include_ids=frozenset({-1001}), groups=True, is_chatlist=True)
    assert dialog_in_folder(rule, DialogState(-1001))
    assert not dialog_in_folder(rule, DialogState(-1002))


def test_rule_from_real_telethon_filter():
    dialog_filter = types.DialogFilter(
        id=5,
        title=types.TextWithEntities(text="VA OFM", entities=[]),
        pinned_peers=[types.InputPeerChannel(CHANNEL_ID, 1)],
        include_peers=[types.InputPeerChat(42)],
        exclude_peers=[types.InputPeerChannel(777, 2)],
        groups=True,
        exclude_muted=True,
    )
    rule = rule_from_filter(dialog_filter)
    assert rule.title == "VA OFM"
    assert rule.include_ids == {CHANNEL_MARKED, -42}
    assert rule.exclude_ids == {-1000000000777}
    assert rule.groups and rule.exclude_muted and not rule.exclude_read
    assert rule_from_filter(types.DialogFilterDefault()) is None


def test_rule_from_shared_folder():
    chatlist = types.DialogFilterChatlist(
        id=9, title="Shared", pinned_peers=[], include_peers=[types.InputPeerChannel(CHANNEL_ID, 1)]
    )
    rule = rule_from_filter(chatlist)
    assert rule.is_chatlist and rule.include_ids == {CHANNEL_MARKED}


def test_folder_title_formats():
    assert folder_title("Simple") == "Simple"
    assert folder_title(types.TextWithEntities(text="Riche", entities=[])) == "Riche"


def test_is_muted():
    assert is_muted(types.PeerNotifySettings(mute_until=NOW + timedelta(days=1)), NOW)
    assert not is_muted(types.PeerNotifySettings(mute_until=NOW - timedelta(days=1)), NOW)
    assert not is_muted(types.PeerNotifySettings(), NOW)


# --- Droits de publication -----------------------------------------------------


def megagroup(**kwargs):
    return types.Channel(
        id=CHANNEL_ID, title="G", photo=types.ChatPhotoEmpty(), date=NOW, megagroup=True, **kwargs
    )


def test_open_group_allows_posting():
    assert check_send_rights(megagroup(), with_photo=False, now=NOW) is None
    assert check_send_rights(megagroup(), with_photo=True, now=NOW) is None


def test_read_only_group():
    entity = megagroup(default_banned_rights=types.ChatBannedRights(until_date=None, send_messages=True))
    assert "administrateurs" in check_send_rights(entity, with_photo=False, now=NOW)


def test_admin_can_post_in_read_only_group():
    entity = megagroup(
        default_banned_rights=types.ChatBannedRights(until_date=None, send_messages=True),
        admin_rights=types.ChatAdminRights(post_messages=True),
    )
    assert check_send_rights(entity, with_photo=False, now=NOW) is None


def test_photos_forbidden_only_blocks_photo_ads():
    entity = megagroup(default_banned_rights=types.ChatBannedRights(until_date=None, send_photos=True))
    assert check_send_rights(entity, with_photo=False, now=NOW) is None
    assert "images" in check_send_rights(entity, with_photo=True, now=NOW)


def test_personal_restriction_and_expiry():
    active = megagroup(
        banned_rights=types.ChatBannedRights(until_date=NOW + timedelta(hours=1), send_messages=True)
    )
    expired = megagroup(
        banned_rights=types.ChatBannedRights(until_date=NOW - timedelta(hours=1), send_messages=True)
    )
    assert "restreint" in check_send_rights(active, with_photo=False, now=NOW)
    assert check_send_rights(expired, with_photo=False, now=NOW) is None


def test_paid_messages_and_channels_are_skipped():
    assert "payants" in check_send_rights(megagroup(send_paid_messages_stars=10), with_photo=False, now=NOW)
    channel = types.Channel(id=1, title="C", photo=types.ChatPhotoEmpty(), date=NOW, broadcast=True)
    assert "canal" in check_send_rights(channel, with_photo=False, now=NOW)


def test_basic_group_states():
    chat = types.Chat(
        id=42, title="Petit groupe", photo=types.ChatPhotoEmpty(), participants_count=10, date=NOW, version=1
    )
    assert check_send_rights(chat, with_photo=False, now=NOW) is None
    migrated = types.Chat(
        id=43,
        title="Ancien",
        photo=types.ChatPhotoEmpty(),
        participants_count=10,
        date=NOW,
        version=1,
        deactivated=True,
    )
    assert "migré" in check_send_rights(migrated, with_photo=False, now=NOW)
    assert "exclu" in check_send_rights(types.ChatForbidden(id=44, title="Banni"), with_photo=False, now=NOW)
