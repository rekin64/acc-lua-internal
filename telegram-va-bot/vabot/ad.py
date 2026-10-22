"""Annonce de recrutement : modèle, contact, rendu et validation."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, replace

from telethon.extensions import html as tl_html

CONTACT_PLACEHOLDER = "{contact}"
TEXT_LIMIT = 4096  # limite Telegram pour un message texte
CAPTION_LIMIT = 1024  # limite Telegram pour la légende d'une image

DEFAULT_TEMPLATE = (
    "🚀 <b>WE'RE HIRING — TWITTER/X VAs</b>\n"
    "\n"
    "We're recruiting Virtual Assistants for a new project.\n"
    "\n"
    "💰 Commission-based earnings\n"
    "🌍 Remote work\n"
    "📱 Twitter/X tasks\n"
    "\n"
    "📩 DM {contact} to apply"
)

CONTACT_LINE = "📩 DM {contact} to apply"

_USERNAME_RE = re.compile(r"^@?([A-Za-z][A-Za-z0-9_]{3,31})$")


@dataclass(frozen=True)
class Ad:
    text_html: str = DEFAULT_TEMPLATE
    photo_path: str | None = None  # image locale (data/ad_photo.jpg), facultative

    @property
    def has_photo(self) -> bool:
        return bool(self.photo_path)

    def with_text(self, text_html: str) -> Ad:
        return replace(self, text_html=text_html)

    def with_photo(self, path: str | None) -> Ad:
        return replace(self, photo_path=path)


@dataclass(frozen=True)
class RenderedAd:
    """Annonce prête à être envoyée (contact remplacé)."""

    text_html: str
    photo_path: str | None = None


def normalize_username(raw: str | None) -> str | None:
    """« @MonCompte », « MonCompte » ou « t.me/MonCompte » → « MonCompte »."""
    if not raw:
        return None
    value = raw.strip()
    for prefix in ("https://", "http://"):
        if value.lower().startswith(prefix):
            value = value[len(prefix) :]
    if value.lower().startswith("t.me/"):
        value = value[5:]
    match = _USERNAME_RE.match(value.strip("/"))
    return match.group(1) if match else None


def render(ad: Ad, contact: str | None) -> RenderedAd:
    text = ad.text_html
    if contact:
        text = text.replace(CONTACT_PLACEHOLDER, "@" + html.escape(contact))
    return RenderedAd(text_html=text.strip(), photo_path=ad.photo_path)


def plain_text(text_html: str) -> str:
    """Texte tel qu'il apparaîtra dans Telegram (balises retirées)."""
    text, _entities = tl_html.parse(text_html)
    return text


def telegram_length(text_html: str) -> int:
    """Longueur comptée comme Telegram (unités UTF-16, un emoji compte double)."""
    return len(plain_text(text_html).encode("utf-16-le")) // 2


def mentions_contact(ad: Ad, contact: str | None) -> bool:
    if CONTACT_PLACEHOLDER in ad.text_html:
        return True
    return bool(contact) and f"@{contact}".lower() in ad.text_html.lower()


def validate(ad: Ad, contact: str | None) -> list[str]:
    """Erreurs bloquantes empêchant la publication."""
    errors: list[str] = []
    if not plain_text(ad.text_html).strip():
        errors.append("L'annonce est vide.")
    if CONTACT_PLACEHOLDER in ad.text_html and not contact:
        errors.append(
            "L'annonce contient {contact} mais aucun @ de contact n'est défini "
            "(ajoutez un nom d'utilisateur à votre compte ou utilisez « 📩 Contact »)."
        )
    length = telegram_length(render(ad, contact).text_html)
    limit = CAPTION_LIMIT if ad.has_photo else TEXT_LIMIT
    if length > limit:
        kind = "la légende d'une image" if ad.has_photo else "un message"
        errors.append(f"Texte trop long : {length} caractères, maximum {limit} pour {kind}.")
    return errors


def warnings(ad: Ad, contact: str | None) -> list[str]:
    """Points d'attention non bloquants."""
    if not mentions_contact(ad, contact):
        return ["Votre annonce ne mentionne pas votre @ : les candidats ne sauront pas qui contacter."]
    return []


def add_contact_line(ad: Ad) -> Ad:
    return ad.with_text(ad.text_html.rstrip() + "\n\n" + CONTACT_LINE)
