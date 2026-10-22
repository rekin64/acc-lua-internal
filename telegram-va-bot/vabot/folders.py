"""Dossiers Telegram : appartenance d'un groupe à un dossier et droits de publication.

Ces fonctions ne font aucun appel réseau, elles sont donc faciles à tester.
La logique d'appartenance reproduit celle des applications Telegram officielles :
1. un chat épinglé ou explicitement inclus fait toujours partie du dossier ;
2. un chat explicitement exclu n'en fait jamais partie ;
3. sinon les options « exclure muets / lus / archivés » s'appliquent ;
4. enfin le type de chat doit être coché (ici : « Groupes »).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from telethon import utils
from telethon.tl import types


@dataclass(frozen=True)
class FolderRule:
    id: int
    title: str
    include_ids: frozenset[int]
    exclude_ids: frozenset[int] = frozenset()
    groups: bool = False
    exclude_muted: bool = False
    exclude_read: bool = False
    exclude_archived: bool = False
    is_chatlist: bool = False  # dossier partagé (lien d'invitation) : liste explicite uniquement


@dataclass(frozen=True)
class DialogState:
    chat_id: int
    muted: bool = False
    unread: bool = False
    archived: bool = False


def folder_title(title: object) -> str:
    """Le titre est une simple chaîne ou un TextWithEntities selon la version de l'API."""
    if isinstance(title, str):
        return title
    return str(getattr(title, "text", "") or "Sans nom")


def _peer_ids(peers: list | None) -> set[int]:
    ids: set[int] = set()
    for peer in peers or []:
        try:
            ids.add(utils.get_peer_id(peer))
        except (TypeError, ValueError):  # InputPeerSelf, InputPeerEmpty…
            continue
    return ids


def rule_from_filter(dialog_filter: object) -> FolderRule | None:
    """Convertit un filtre Telegram en règle. ``None`` pour « Tous les chats »."""
    if isinstance(dialog_filter, types.DialogFilter):
        return FolderRule(
            id=dialog_filter.id,
            title=folder_title(dialog_filter.title),
            include_ids=frozenset(
                _peer_ids(dialog_filter.pinned_peers) | _peer_ids(dialog_filter.include_peers)
            ),
            exclude_ids=frozenset(_peer_ids(dialog_filter.exclude_peers)),
            groups=bool(dialog_filter.groups),
            exclude_muted=bool(dialog_filter.exclude_muted),
            exclude_read=bool(dialog_filter.exclude_read),
            exclude_archived=bool(dialog_filter.exclude_archived),
        )
    if isinstance(dialog_filter, types.DialogFilterChatlist):
        return FolderRule(
            id=dialog_filter.id,
            title=folder_title(dialog_filter.title),
            include_ids=frozenset(
                _peer_ids(dialog_filter.pinned_peers) | _peer_ids(dialog_filter.include_peers)
            ),
            is_chatlist=True,
        )
    return None


def dialog_in_folder(rule: FolderRule, dialog: DialogState) -> bool:
    """Indique si un groupe fait partie du dossier, selon les règles de Telegram."""
    if dialog.chat_id in rule.include_ids:
        return True
    if rule.is_chatlist or dialog.chat_id in rule.exclude_ids:
        return False
    if rule.exclude_muted and dialog.muted:
        return False
    if rule.exclude_read and not dialog.unread:
        return False
    if rule.exclude_archived and dialog.archived:
        return False
    return rule.groups


def is_muted(notify_settings: object, now: datetime | None = None) -> bool:
    mute_until = getattr(notify_settings, "mute_until", None)
    if not isinstance(mute_until, datetime):
        return False
    return mute_until > (now or datetime.now(timezone.utc))


def _restriction_active(rights: object, now: datetime) -> bool:
    """Une restriction personnelle peut être temporaire (until_date)."""
    until = getattr(rights, "until_date", None)
    if not isinstance(until, datetime) or until.timestamp() <= 0:
        return True  # 0 / absent = permanent
    return until > now


def check_send_rights(entity: object, *, with_photo: bool, now: datetime | None = None) -> str | None:
    """Retourne ``None`` si votre compte peut publier l'annonce, sinon la raison.

    On respecte les restrictions du groupe : rien n'est tenté si Telegram
    indique déjà que la publication est interdite.
    """
    now = now or datetime.now(timezone.utc)

    if isinstance(entity, (types.ChatForbidden, types.ChannelForbidden)):
        return "groupe inaccessible (vous en avez été exclu)"
    if isinstance(entity, types.Channel) and not entity.megagroup:
        return "c'est un canal, pas un groupe"
    if not isinstance(entity, (types.Chat, types.Channel)):
        return "ce n'est pas un groupe"
    if isinstance(entity, types.Chat) and (entity.deactivated or entity.migrated_to):
        return "ancien groupe migré ou désactivé"
    if entity.left:
        return "vous n'êtes pas membre de ce groupe"
    if isinstance(entity, types.Channel) and entity.send_paid_messages_stars:
        return "les messages y sont payants (Stars)"
    if entity.creator or entity.admin_rights:
        return None

    own = getattr(entity, "banned_rights", None)
    if own is not None and _restriction_active(own, now):
        if own.send_messages:
            return "votre compte est restreint dans ce groupe"
        if with_photo and (own.send_media or own.send_photos):
            return "votre compte ne peut pas y envoyer d'images"
        if not with_photo and own.send_plain:
            return "votre compte ne peut pas y envoyer de texte"

    default = entity.default_banned_rights
    if default is not None:
        if default.send_messages:
            return "seuls les administrateurs peuvent écrire"
        if with_photo and (default.send_media or default.send_photos):
            return "les images sont interdites dans ce groupe"
        if not with_photo and default.send_plain:
            return "les messages texte sont interdits dans ce groupe"
    return None
