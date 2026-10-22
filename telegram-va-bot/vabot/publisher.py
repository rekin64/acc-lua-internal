"""Préparation (plan) et exécution d'une publication dans les groupes approuvés."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from telethon import errors

from .ad import RenderedAd

SENT = "sent"
FAILED = "failed"
SKIPPED = "skipped"

NOT_APPROVED = "non approuvé"
STOPPED_BY_USER = "publication arrêtée à votre demande"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min" + (f" {sec:02d} s" if sec else "")
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d}"


@dataclass(frozen=True)
class GroupInfo:
    """Groupe d'un dossier, tel que vu par votre compte."""

    chat_id: int
    title: str
    text_block: str | None = None  # raison pour laquelle un texte ne peut pas y être publié
    photo_block: str | None = None  # idem pour une image
    peer: Any = None  # InputPeer Telethon, jamais stocké en base

    def block_reason(self, with_photo: bool) -> str | None:
        return self.photo_block if with_photo else self.text_block


@dataclass
class Plan:
    folder_title: str
    targets: list[GroupInfo] = field(default_factory=list)
    skipped: list[tuple[GroupInfo, str]] = field(default_factory=list)


@dataclass
class Outcome:
    chat_id: int
    title: str
    status: str  # SENT / FAILED / SKIPPED
    reason: str | None = None
    at: datetime = field(default_factory=utcnow)


@dataclass
class Report:
    folder_title: str
    dry_run: bool
    started_at: datetime = field(default_factory=utcnow)
    finished_at: datetime | None = None
    outcomes: list[Outcome] = field(default_factory=list)
    stop_reason: str | None = None
    saved_copy: bool = False  # mode test : exemplaire envoyé dans « Messages enregistrés »

    def _with(self, status: str) -> list[Outcome]:
        return [o for o in self.outcomes if o.status == status]

    @property
    def sent(self) -> list[Outcome]:
        return self._with(SENT)

    @property
    def failed(self) -> list[Outcome]:
        return self._with(FAILED)

    @property
    def skipped(self) -> list[Outcome]:
        return self._with(SKIPPED)


def build_plan(
    folder_title: str,
    groups: Iterable[GroupInfo],
    approved: set[int],
    *,
    with_photo: bool,
    last_sent: dict[int, datetime] | None = None,
    cooldown_hours: float = 0,
    now: datetime | None = None,
) -> Plan:
    """Sépare les groupes qui recevront l'annonce de ceux qui seront ignorés.

    Seuls les groupes explicitement approuvés, où la publication est permise
    et où rien n'a été publié récemment, reçoivent l'annonce.
    """
    now = now or utcnow()
    last_sent = last_sent or {}
    cooldown = timedelta(hours=cooldown_hours)
    plan = Plan(folder_title=folder_title)
    for group in groups:
        blocked = group.block_reason(with_photo)
        if blocked:  # raison la plus utile à afficher, même pour un groupe non approuvé
            plan.skipped.append((group, blocked))
            continue
        if group.chat_id not in approved:
            plan.skipped.append((group, NOT_APPROVED))
            continue
        previous = last_sent.get(group.chat_id)
        if cooldown and previous and now - previous < cooldown:
            ago = format_duration((now - previous).total_seconds())
            plan.skipped.append(
                (group, f"déjà publié il y a {ago} (minimum {cooldown_hours:g} h entre deux annonces)")
            )
            continue
        plan.targets.append(group)
    return plan


def explain_error(exc: BaseException) -> tuple[str, bool]:
    """Traduit une erreur Telegram en (raison lisible, arrêt de la publication ?).

    Les limites de Telegram sont respectées : en cas de FloodWait trop long
    ou de restriction du compte, la publication s'arrête au lieu d'insister.
    """
    if isinstance(exc, errors.SlowModeWaitError):
        return f"mode lent du groupe : prochain message possible dans {format_duration(exc.seconds)}", False
    if isinstance(exc, (errors.FloodWaitError, errors.FloodPremiumWaitError)):
        return (
            f"limite d'envoi Telegram atteinte (FloodWait) : patientez {format_duration(exc.seconds)} "
            "avant de republier",
            True,
        )
    if isinstance(exc, errors.PeerFloodError):
        return "Telegram limite votre compte pour spam : vérifiez auprès de @SpamBot", True
    if isinstance(exc, errors.UserBannedInChannelError):
        return "votre compte ne peut plus écrire dans les groupes publics : vérifiez auprès de @SpamBot", True
    if isinstance(exc, errors.UnauthorizedError):
        return "session Telegram expirée ou révoquée : relancez « python login.py »", True
    if isinstance(exc, ConnectionError):
        return "connexion à Telegram perdue", True

    known: list[tuple[type[BaseException], str]] = [
        (errors.ChatWriteForbiddenError, "écriture interdite dans ce groupe"),
        (errors.ChatSendPhotosForbiddenError, "images interdites dans ce groupe"),
        (errors.ChatSendMediaForbiddenError, "médias interdits dans ce groupe"),
        (errors.ChatSendPlainForbiddenError, "messages texte interdits dans ce groupe"),
        (errors.ChatRestrictedError, "votre compte est restreint dans ce groupe"),
        (errors.ChatGuestSendForbiddenError, "il faut rejoindre le groupe pour y écrire"),
        (errors.ChannelPrivateError, "groupe inaccessible (privé, ou vous en avez été exclu)"),
        (errors.ChatForbiddenError, "accès au groupe refusé"),
        (errors.ChatAdminRequiredError, "droits d'administrateur requis"),
        (errors.MessageTooLongError, "annonce trop longue"),
        (errors.MediaCaptionTooLongError, "légende trop longue (1024 caractères maximum)"),
    ]
    for error_type, reason in known:
        if isinstance(exc, error_type):
            return reason, False

    if isinstance(exc, errors.RPCError):
        code = str(getattr(exc, "message", "") or type(exc).__name__)
        if "TOPIC_CLOSED" in code:
            return "le sujet « Général » du forum est fermé", False
        if "PAYMENT_REQUIRED" in code:
            return "les messages y sont payants (Stars)", False
        return f"erreur Telegram ({code})", False
    return f"erreur inattendue ({type(exc).__name__})", False


SendFunc = Callable[[Any, RenderedAd, dict], Awaitable[Any]]
ProgressFunc = Callable[[int, int, str], Awaitable[None]]


async def _pause(seconds: float, stop_event: asyncio.Event | None) -> None:
    """Attend ``seconds`` secondes, en se réveillant tout de suite si on demande l'arrêt."""
    if seconds <= 0:
        return
    if stop_event is None:
        await asyncio.sleep(seconds)
        return
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass


async def run_publication(
    plan: Plan,
    ad: RenderedAd,
    send: SendFunc,
    *,
    dry_run: bool,
    delay: float,
    stop_event: asyncio.Event | None = None,
    on_progress: ProgressFunc | None = None,
) -> Report:
    """Publie l'annonce dans les groupes du plan, un par un, avec un délai entre chaque envoi.

    En mode test (``dry_run``), rien n'est envoyé : le rapport liste les groupes
    qui auraient reçu l'annonce.
    """
    report = Report(folder_title=plan.folder_title, dry_run=dry_run)
    report.outcomes.extend(Outcome(g.chat_id, g.title, SKIPPED, reason) for g, reason in plan.skipped)
    total = len(plan.targets)
    media_cache: dict = {}  # l'image n'est envoyée sur les serveurs qu'une seule fois

    for index, group in enumerate(plan.targets):
        if dry_run:
            report.outcomes.append(Outcome(group.chat_id, group.title, SENT, "mode test : non envoyé"))
            continue

        if index > 0:
            await _pause(delay, stop_event)
        if stop_event is not None and stop_event.is_set():
            report.stop_reason = STOPPED_BY_USER
            _skip_remaining(report, plan.targets[index:], "non tenté : " + STOPPED_BY_USER)
            break

        if on_progress is not None:
            await on_progress(index, total, group.title)
        try:
            await send(group.peer, ad, media_cache)
        except Exception as exc:  # noqa: BLE001 - toute erreur est rapportée à l'utilisateur
            reason, fatal = explain_error(exc)
            report.outcomes.append(Outcome(group.chat_id, group.title, FAILED, reason))
            if fatal:
                report.stop_reason = reason
                _skip_remaining(report, plan.targets[index + 1 :], "non tenté : publication interrompue")
                break
        else:
            report.outcomes.append(Outcome(group.chat_id, group.title, SENT))

    report.finished_at = utcnow()
    return report


def _skip_remaining(report: Report, groups: Iterable[GroupInfo], reason: str) -> None:
    report.outcomes.extend(Outcome(g.chat_id, g.title, SKIPPED, reason) for g in groups)


async def prepare_plan(
    db: Any, account: Any, *, folder: Any, with_photo: bool, cooldown_hours: float
) -> Plan:
    """Relit le dossier sur Telegram (état à jour) puis construit le plan de publication."""
    groups = await account.folder_groups(folder.id)
    db.sync_folder_groups((g.chat_id, g.title, g.text_block) for g in groups)
    return build_plan(
        folder.title,
        groups,
        db.approved_ids(),
        with_photo=with_photo,
        last_sent=db.last_sent_times(),
        cooldown_hours=cooldown_hours,
    )
