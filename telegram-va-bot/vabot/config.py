"""Chargement et validation de la configuration (fichier .env)."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

PROJECT_DIR = Path(__file__).resolve().parent.parent

# Délai minimal entre deux envois : on reste volontairement prudent.
MIN_SEND_DELAY = 5.0
DEFAULT_SEND_DELAY = 10.0
DEFAULT_COOLDOWN_HOURS = 24.0

_BOT_TOKEN_RE = re.compile(r"^\d+:[A-Za-z0-9_-]{30,}$")


class ConfigError(Exception):
    """Configuration absente ou invalide (message lisible par l'utilisateur)."""


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str
    bot_token: str
    owner_id: int
    data_dir: Path
    phone: str | None = None
    send_delay: float = DEFAULT_SEND_DELAY
    repost_cooldown_hours: float = DEFAULT_COOLDOWN_HOURS
    test_mode: bool = False

    @property
    def session_path(self) -> Path:
        # Telethon ajoute lui-même l'extension « .session ».
        return self.data_dir / "account"

    @property
    def session_file(self) -> Path:
        return self.data_dir / "account.session"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "vabot.sqlite3"

    @property
    def photo_path(self) -> Path:
        return self.data_dir / "ad_photo.jpg"

    def secrets(self) -> list[str]:
        """Valeurs à ne jamais faire apparaître dans les journaux."""
        return [s for s in (self.api_hash, self.bot_token, self.phone) if s]


def _get(env: Mapping[str, str | None], key: str) -> str:
    return (env.get(key) or "").strip()


def _parse_int(env: Mapping[str, str | None], key: str, help_text: str) -> int:
    raw = _get(env, key)
    if not raw:
        raise ConfigError(f"{key} manquant dans .env : {help_text}")
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{key} doit être un nombre entier ({help_text}).") from None


def _parse_float(env: Mapping[str, str | None], key: str, default: float) -> float:
    raw = _get(env, key)
    if not raw:
        return default
    try:
        value = float(raw.replace(",", "."))
    except ValueError:
        raise ConfigError(f"{key} doit être un nombre (valeur actuelle : {raw!r}).") from None
    if value < 0:
        raise ConfigError(f"{key} ne peut pas être négatif.")
    return value


def _parse_bool(env: Mapping[str, str | None], key: str) -> bool:
    return _get(env, key).lower() in {"1", "true", "yes", "oui", "on"}


def parse_config(env: Mapping[str, str | None], *, require_bot: bool = True) -> Config:
    """Construit la configuration à partir d'un dictionnaire de variables.

    ``require_bot=False`` permet au script de connexion de fonctionner
    avant que le bot de contrôle ne soit configuré.
    """
    api_id = _parse_int(env, "API_ID", "obtenez-le sur https://my.telegram.org")
    api_hash = _get(env, "API_HASH")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", api_hash):
        raise ConfigError("API_HASH manquant ou invalide (32 caractères, voir https://my.telegram.org).")

    bot_token = _get(env, "BOT_TOKEN")
    owner_id = 0
    if require_bot:
        if not _BOT_TOKEN_RE.match(bot_token):
            raise ConfigError("BOT_TOKEN manquant ou invalide (jeton fourni par @BotFather).")
        owner_id = _parse_int(env, "OWNER_ID", "votre identifiant Telegram, donné par @userinfobot")
        if owner_id <= 0:
            raise ConfigError("OWNER_ID doit être votre identifiant Telegram (nombre positif).")

    data_dir = Path(_get(env, "DATA_DIR") or "data")
    if not data_dir.is_absolute():
        data_dir = PROJECT_DIR / data_dir

    send_delay = _parse_float(env, "SEND_DELAY_SECONDS", DEFAULT_SEND_DELAY)
    if send_delay < MIN_SEND_DELAY:
        raise ConfigError(
            f"SEND_DELAY_SECONDS doit être d'au moins {MIN_SEND_DELAY:g} secondes "
            "pour respecter les limites de Telegram."
        )

    return Config(
        api_id=api_id,
        api_hash=api_hash,
        bot_token=bot_token,
        owner_id=owner_id,
        data_dir=data_dir,
        phone=_get(env, "PHONE") or None,
        send_delay=send_delay,
        repost_cooldown_hours=_parse_float(env, "REPOST_COOLDOWN_HOURS", DEFAULT_COOLDOWN_HOURS),
        test_mode=_parse_bool(env, "TEST_MODE"),
    )


def load_config(env_file: str | Path | None = None, *, require_bot: bool = True) -> Config:
    """Lit le fichier .env du projet (les variables d'environnement sont prioritaires)."""
    path = Path(env_file) if env_file else PROJECT_DIR / ".env"
    if not path.exists() and not os.environ.get("API_ID"):
        raise ConfigError(f"Fichier {path.name} introuvable. Copiez .env.example en .env puis complétez-le.")
    env: dict[str, str | None] = dict(dotenv_values(path)) if path.exists() else {}
    env.update({k: v for k, v in os.environ.items() if k in _KNOWN_KEYS})
    return parse_config(env, require_bot=require_bot)


_KNOWN_KEYS = {
    "API_ID",
    "API_HASH",
    "BOT_TOKEN",
    "OWNER_ID",
    "PHONE",
    "DATA_DIR",
    "SEND_DELAY_SECONDS",
    "REPOST_COOLDOWN_HOURS",
    "TEST_MODE",
}


def secure_data_dir(path: Path) -> None:
    """Crée le dossier de données, lisible uniquement par l'utilisateur courant."""
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:  # Systèmes de fichiers sans permissions POSIX (Windows…)
        pass


def secure_file(path: Path) -> None:
    """Restreint un fichier sensible (session, base) à l'utilisateur courant."""
    if path.exists():
        try:
            path.chmod(0o600)
        except OSError:
            pass
