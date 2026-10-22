"""Journalisation sans fuite de secrets."""

from __future__ import annotations

import logging
from collections.abc import Iterable

REDACTED = "***"


class RedactingFilter(logging.Filter):
    """Masque les secrets connus (jeton du bot, API hash, téléphone) dans les journaux."""

    def __init__(self, secrets: Iterable[str]):
        super().__init__()
        self._secrets = [s for s in secrets if s and len(s) >= 6]

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True
        message = record.getMessage()
        redacted = message
        for secret in self._secrets:
            redacted = redacted.replace(secret, REDACTED)
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True


def setup_logging(secrets: Iterable[str] = (), level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s : %(message)s"))
    handler.addFilter(RedactingFilter(secrets))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # Bibliothèques trop bavardes : on ne garde que les avertissements.
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
