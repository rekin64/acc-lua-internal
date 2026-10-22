"""Claviers de boutons du bot de contrôle."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

GROUPS_PER_PAGE = 8
BUTTON_TITLE_MAX = 40

HOME = "menu:home"
FOLDERS = "menu:folders"
AD = "menu:ad"
PUBLISH = "menu:publish"
RESULTS = "menu:results"
NOOP = "noop"


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _short(title: str, limit: int = BUTTON_TITLE_MAX) -> str:
    return title if len(title) <= limit else title[: limit - 1] + "…"


def _markup(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu() -> InlineKeyboardMarkup:
    return _markup(
        [
            [_btn("📁 Choisir un dossier", FOLDERS)],
            [_btn("📝 Configurer mon annonce", AD)],
            [_btn("🚀 Publier", PUBLISH)],
            [_btn("📊 Résultats", RESULTS)],
        ]
    )


def back_home() -> InlineKeyboardMarkup:
    return _markup([[_btn("⬅️ Menu", HOME)]])


def folders(items: Sequence, current_id: int | None) -> InlineKeyboardMarkup:
    rows = [
        [_btn(("✅ " if f.id == current_id else "📁 ") + _short(f.title), f"folder:{f.id}")] for f in items
    ]
    rows.append([_btn("🔄 Actualiser", FOLDERS), _btn("⬅️ Menu", HOME)])
    return _markup(rows)


def page_count(total: int) -> int:
    return max(1, -(-total // GROUPS_PER_PAGE))


def groups(rows: Sequence, page: int) -> InlineKeyboardMarkup:
    pages = page_count(len(rows))
    page = min(max(page, 0), pages - 1)
    start = page * GROUPS_PER_PAGE
    keyboard = []
    for group in rows[start : start + GROUPS_PER_PAGE]:
        if group.approved:
            icon = "✅"
        elif group.blocked_reason:
            icon = "🔒"
        else:
            icon = "⬜"
        keyboard.append([_btn(f"{icon} {_short(group.title)}", f"grp:{group.chat_id}:{page}")])
    if pages > 1:
        keyboard.append(
            [
                _btn("◀️", f"gpage:{page - 1}") if page > 0 else _btn("·", NOOP),
                _btn(f"{page + 1}/{pages}", NOOP),
                _btn("▶️", f"gpage:{page + 1}") if page < pages - 1 else _btn("·", NOOP),
            ]
        )
    if rows:
        keyboard.append([_btn("☑️ Tout cocher", f"gall:{page}"), _btn("⬜ Tout décocher", f"gnone:{page}")])
    keyboard.append([_btn("🚀 Publier", PUBLISH), _btn("⬅️ Menu", HOME)])
    return _markup(keyboard)


def ad_menu(has_photo: bool, show_add_contact: bool) -> InlineKeyboardMarkup:
    rows = [
        [_btn("👁 Aperçu", "ad:preview")],
        [_btn("✏️ Modifier le texte", "ad:text")],
    ]
    if has_photo:
        rows.append([_btn("🖼 Changer l'image", "ad:photo"), _btn("🗑 Retirer l'image", "ad:rmphoto")])
    else:
        rows.append([_btn("🖼 Ajouter une image", "ad:photo")])
    rows.append([_btn("📩 Mon @ de contact", "ad:contact")])
    if show_add_contact:
        rows.append([_btn("➕ Ajouter la ligne « DM @… to apply »", "ad:addcontact")])
    rows.append([_btn("📄 Remplacer par le modèle", "ad:template")])
    rows.append([_btn("🚀 Publier", PUBLISH), _btn("⬅️ Menu", HOME)])
    return _markup(rows)


def cancel(back_to: str = HOME) -> InlineKeyboardMarkup:
    return _markup([[_btn("❌ Annuler", back_to)]])


def contact(account_username: str | None) -> InlineKeyboardMarkup:
    rows = []
    if account_username:
        rows.append([_btn(f"Utiliser mon compte (@{account_username})", "ad:contact_me")])
    rows.append([_btn("❌ Annuler", AD)])
    return _markup(rows)


def publish_confirm(has_targets: bool, test_mode: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_targets:
        if not test_mode:
            rows.append([_btn("✅ Confirmer et publier", "pub:go")])
        rows.append([_btn("🧪 Mode test (sans publier)", "pub:test")])
    else:
        rows.append([_btn("📁 Choisir les groupes", FOLDERS)])
    rows.append([_btn("❌ Annuler", HOME)])
    return _markup(rows)


def publish_blocked() -> InlineKeyboardMarkup:
    return _markup(
        [
            [_btn("📁 Choisir un dossier", FOLDERS), _btn("📝 Mon annonce", AD)],
            [_btn("⬅️ Menu", HOME)],
        ]
    )


def stop() -> InlineKeyboardMarkup:
    return _markup([[_btn("⏹ Arrêter la publication", "pub:stop")]])


def after_report() -> InlineKeyboardMarkup:
    return _markup([[_btn("📊 Résultats", RESULTS), _btn("⬅️ Menu", HOME)]])
