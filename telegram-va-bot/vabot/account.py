"""Accès à votre compte Telegram personnel via Telethon (dossiers, groupes, envoi)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from telethon import TelegramClient, functions, utils

from . import __version__
from .ad import RenderedAd
from .config import Config, secure_file
from .folders import DialogState, FolderRule, check_send_rights, dialog_in_folder, is_muted, rule_from_filter
from .publisher import GroupInfo

log = logging.getLogger(__name__)

# Telethon attend automatiquement les FloodWait courts (≤ 60 s) comme demandé par
# Telegram ; au-delà, l'erreur remonte et la publication s'arrête.
FLOOD_SLEEP_THRESHOLD = 60
CONNECT_TIMEOUT = 45  # secondes, pour ne jamais bloquer le bot si Telegram est injoignable
ARCHIVE_FOLDER_ID = 1


class FolderNotFoundError(Exception):
    """Le dossier n'existe plus dans votre compte Telegram."""


@dataclass(frozen=True)
class FolderInfo:
    id: int
    title: str


def create_client(config: Config) -> TelegramClient:
    client = TelegramClient(
        str(config.session_path),
        config.api_id,
        config.api_hash,
        flood_sleep_threshold=FLOOD_SLEEP_THRESHOLD,
        receive_updates=False,  # on n'écoute pas vos conversations
        device_model="VA Recruitment Bot",
        app_version=__version__,
    )
    # Ne pas conserver sur disque les informations (pseudos, téléphones…) des
    # utilisateurs croisés dans vos discussions : inutile pour publier.
    client.session.save_entities = False
    secure_file(config.session_file)
    return client


class TelegramAccount:
    def __init__(self, client: TelegramClient, session_file: Path | None = None):
        self.client = client
        self._session_file = session_file
        self._me: Any = None

    async def connect(self) -> bool:
        """Se connecte aux serveurs Telegram ; renvoie True si le compte est autorisé."""
        log.info("Connexion à votre compte Telegram…")
        return await self.is_authorized()

    async def _ensure_connected(self) -> bool:
        if self.client.is_connected():
            return True
        try:
            await asyncio.wait_for(self.client.connect(), CONNECT_TIMEOUT)
        except (OSError, ConnectionError, asyncio.TimeoutError) as exc:
            log.error("Connexion aux serveurs Telegram impossible (%s)", type(exc).__name__)
            return False
        if self._session_file is not None:
            secure_file(self._session_file)
        return True

    async def disconnect(self) -> None:
        if self.client.is_connected():
            await self.client.disconnect()

    async def is_authorized(self) -> bool:
        if not await self._ensure_connected():
            return False
        try:
            authorized = await self.client.is_user_authorized()
        except (OSError, ConnectionError):
            return False
        if not authorized:
            self._me = None
        return authorized

    async def _get_me(self) -> Any:
        if self._me is None and await self.is_authorized():
            self._me = await self.client.get_me()
        return self._me

    async def username(self) -> str | None:
        me = await self._get_me()
        return getattr(me, "username", None) if me else None

    async def label(self) -> str | None:
        """« @pseudo » ou le nom du compte ; None si aucun compte n'est connecté."""
        me = await self._get_me()
        if me is None:
            return None
        if me.username:
            return f"@{me.username}"
        return utils.get_display_name(me) or str(me.id)

    async def _folder_rules(self) -> list[FolderRule]:
        result = await self.client(functions.messages.GetDialogFiltersRequest())
        filters = getattr(result, "filters", result)  # selon la version de l'API
        return [rule for rule in map(rule_from_filter, filters) if rule is not None]

    async def list_folders(self) -> list[FolderInfo]:
        return [FolderInfo(rule.id, rule.title) for rule in await self._folder_rules()]

    async def folder_groups(self, folder_id: int) -> list[GroupInfo]:
        """Groupes du dossier, en respectant inclusions, exclusions et options du filtre."""
        rule = next((r for r in await self._folder_rules() if r.id == folder_id), None)
        if rule is None:
            raise FolderNotFoundError(folder_id)

        now = datetime.now(timezone.utc)
        groups: list[GroupInfo] = []
        async for dialog in self.client.iter_dialogs(ignore_migrated=True):
            if not dialog.is_group:
                continue
            state = DialogState(
                chat_id=dialog.id,
                muted=is_muted(dialog.dialog.notify_settings, now),
                unread=dialog.unread_count > 0 or bool(dialog.dialog.unread_mark),
                archived=dialog.folder_id == ARCHIVE_FOLDER_ID,
            )
            if not dialog_in_folder(rule, state):
                continue
            groups.append(
                GroupInfo(
                    chat_id=dialog.id,
                    title=dialog.title or str(dialog.id),
                    text_block=check_send_rights(dialog.entity, with_photo=False, now=now),
                    photo_block=check_send_rights(dialog.entity, with_photo=True, now=now),
                    peer=dialog.input_entity,
                )
            )
        groups.sort(key=lambda g: (g.title.lower(), g.chat_id))
        return groups

    async def send_ad(self, peer: Any, ad: RenderedAd, cache: dict) -> None:
        """Envoie l'annonce depuis votre compte. ``cache`` évite de renvoyer l'image à chaque groupe."""
        if ad.photo_path:
            photo = cache.get("photo")
            message = await self.client.send_file(
                peer, photo or ad.photo_path, caption=ad.text_html, parse_mode="html"
            )
            if photo is None and getattr(message, "photo", None) is not None:
                cache["photo"] = message.photo
        else:
            await self.client.send_message(peer, ad.text_html, parse_mode="html", link_preview=False)
