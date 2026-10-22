import asyncio
from datetime import timedelta

import pytest
from telethon import errors

from conftest import FakeAccount, group
from vabot.ad import RenderedAd
from vabot.publisher import NOT_APPROVED, STOPPED_BY_USER, build_plan, explain_error, run_publication, utcnow

AD = RenderedAd(text_html="<b>Hiring</b>")
GROUPS = [
    group(-1001, "A"),
    group(-1002, "B"),
    group(-1003, "C"),
    group(-1004, "D", text_block="lecture seule"),
]


def test_plan_only_targets_approved_writable_groups():
    plan = build_plan("VA OFM", GROUPS, {-1001, -1003, -1004}, with_photo=False)
    assert [g.title for g in plan.targets] == ["A", "C"]
    assert [(g.title, reason) for g, reason in plan.skipped] == [("B", NOT_APPROVED), ("D", "lecture seule")]


def test_plan_uses_photo_restrictions_for_photo_ads():
    groups = [group(-1001, "A", photo_block="images interdites")]
    assert build_plan("x", groups, {-1001}, with_photo=False).targets
    assert not build_plan("x", groups, {-1001}, with_photo=True).targets


def test_plan_respects_repost_cooldown():
    now = utcnow()
    last_sent = {-1001: now - timedelta(hours=3), -1003: now - timedelta(hours=30)}
    plan = build_plan(
        "x",
        GROUPS[:3],
        {-1001, -1002, -1003},
        with_photo=False,
        last_sent=last_sent,
        cooldown_hours=24,
        now=now,
    )
    assert [g.title for g in plan.targets] == ["B", "C"]
    assert "déjà publié il y a 3 h" in plan.skipped[0][1]
    # Délai désactivé
    assert (
        len(
            build_plan(
                "x", GROUPS[:3], {-1001}, with_photo=False, last_sent=last_sent, cooldown_hours=0
            ).targets
        )
        == 1
    )


async def test_dry_run_sends_nothing():
    account = FakeAccount()
    plan = build_plan("VA OFM", GROUPS, {-1001, -1002}, with_photo=False)
    report = await run_publication(plan, AD, account.send_ad, dry_run=True, delay=0)
    assert account.sent == []
    assert report.dry_run and len(report.sent) == 2 and len(report.skipped) == 2


async def test_real_run_reports_failures_and_continues():
    account = FakeAccount(fail={"peer-1002": errors.ChatWriteForbiddenError(request=None)})
    plan = build_plan("VA OFM", GROUPS, {-1001, -1002, -1003}, with_photo=False)
    progress = []

    async def on_progress(done, total, title):
        progress.append((done, total, title))

    report = await run_publication(plan, AD, account.send_ad, dry_run=False, delay=0, on_progress=on_progress)
    assert [peer for peer, _ in account.sent] == ["peer-1001", "peer-1003"]
    assert [o.title for o in report.sent] == ["A", "C"]
    assert [(o.title, o.reason) for o in report.failed] == [("B", "écriture interdite dans ce groupe")]
    assert [o.title for o in report.skipped] == ["D"]
    assert report.stop_reason is None
    assert progress == [(0, 3, "A"), (1, 3, "B"), (2, 3, "C")]


async def test_long_flood_wait_stops_everything():
    account = FakeAccount(fail={"peer-1001": errors.FloodWaitError(request=None, capture=3600)})
    plan = build_plan("VA OFM", GROUPS[:3], {-1001, -1002, -1003}, with_photo=False)
    report = await run_publication(plan, AD, account.send_ad, dry_run=False, delay=0)
    assert account.sent == []  # aucune tentative de contournement
    assert "FloodWait" in report.stop_reason and "1 h 00" in report.stop_reason
    assert len(report.failed) == 1
    assert [o.title for o in report.skipped] == ["B", "C"]
    assert all("interrompue" in o.reason for o in report.skipped)


async def test_stop_button_interrupts_between_groups():
    account = FakeAccount()
    stop = asyncio.Event()
    plan = build_plan("VA OFM", GROUPS[:3], {-1001, -1002, -1003}, with_photo=False)

    async def send(peer, ad, cache):
        await account.send_ad(peer, ad, cache)
        stop.set()  # l'utilisateur appuie sur « Arrêter » pendant le premier envoi

    report = await run_publication(plan, AD, send, dry_run=False, delay=30, stop_event=stop)
    assert len(account.sent) == 1
    assert report.stop_reason == STOPPED_BY_USER
    assert [o.title for o in report.skipped] == ["B", "C"]


async def test_delay_between_sends(monkeypatch):
    pauses = []

    async def fake_pause(seconds, stop_event):
        pauses.append(seconds)

    monkeypatch.setattr("vabot.publisher._pause", fake_pause)
    account = FakeAccount()
    plan = build_plan("VA OFM", GROUPS[:3], {-1001, -1002, -1003}, with_photo=False)
    await run_publication(plan, AD, account.send_ad, dry_run=False, delay=12)
    assert pauses == [12, 12]  # pas d'attente avant le premier envoi


@pytest.mark.parametrize(
    "exc, fatal, expected",
    [
        (errors.SlowModeWaitError(request=None, capture=90), False, "mode lent"),
        (errors.FloodWaitError(request=None, capture=120), True, "FloodWait"),
        (errors.PeerFloodError(request=None), True, "@SpamBot"),
        (errors.UserBannedInChannelError(request=None), True, "@SpamBot"),
        (errors.AuthKeyUnregisteredError(request=None), True, "login.py"),
        (errors.ChatWriteForbiddenError(request=None), False, "écriture interdite"),
        (errors.ChatSendPhotosForbiddenError(request=None), False, "images interdites"),
        (errors.ChannelPrivateError(request=None), False, "inaccessible"),
        (errors.RPCError(request=None, message="TOPIC_CLOSED", code=400), False, "Général"),
        (errors.RPCError(request=None, message="SOMETHING_NEW", code=400), False, "SOMETHING_NEW"),
        (ConnectionError(), True, "connexion"),
        (ValueError("x"), False, "ValueError"),
    ],
)
def test_explain_error(exc, fatal, expected):
    reason, is_fatal = explain_error(exc)
    assert expected in reason
    assert is_fatal is fatal
