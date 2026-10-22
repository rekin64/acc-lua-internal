"""Textes affichés par le bot de contrôle (format HTML de Telegram)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from html import escape as esc

from . import ad as ad_module
from .ad import CONTACT_PLACEHOLDER, Ad
from .publisher import Plan, Report, format_duration

MESSAGE_LIMIT = 4000  # un peu sous la limite Telegram de 4096 caractères
SUMMARY_MAX_ITEMS = 25

NOT_CONNECTED = (
    "❌ <b>Compte Telegram non connecté.</b>\n"
    "Sur l'ordinateur où le bot est installé, arrêtez-le puis lancez "
    "<code>python login.py</code>, et redémarrez-le avec <code>python main.py</code>."
)

NO_FOLDERS = (
    "📁 <b>Aucun dossier trouvé dans votre compte.</b>\n\n"
    "Dans Telegram : Paramètres → Dossiers de discussion → Créer un dossier, "
    "ajoutez-y vos groupes, puis revenez ici."
)

LOADING_FOLDERS = "⏳ Récupération de vos dossiers Telegram…"
LOADING_GROUPS = "⏳ Analyse des groupes du dossier… (quelques secondes)"
CHECKING_GROUPS = "⏳ Vérification des groupes avant publication…"
PREVIEW_INTRO = "👇 Aperçu de l'annonce et liste des groupes :"
PREPARING = "⏳ Préparation de la publication…"
CANCELLED = "Action annulée."
USE_MENU = "Utilisez les boutons ci-dessous, ou /start pour ouvrir le menu."
ALREADY_RUNNING = "⏳ Une publication est déjà en cours. Attendez la fin ou arrêtez-la."

AD_TEXT_PROMPT = (
    "✏️ <b>Envoyez maintenant le texte de votre annonce.</b>\n\n"
    "• La mise en forme (gras, italique, liens) est conservée.\n"
    f"• Écrivez <code>{CONTACT_PLACEHOLDER}</code> là où votre @ doit apparaître.\n"
    "• Vous pouvez aussi envoyer une image avec une légende.\n\n"
    "Votre texte actuel est juste en dessous : copiez-le, modifiez-le et renvoyez-le.\n"
    "/cancel pour annuler."
)
AD_PHOTO_PROMPT = (
    "🖼 <b>Envoyez l'image de votre annonce</b> (en tant que photo, pas en fichier).\n\n"
    "• Avec une légende : elle remplace le texte actuel.\n"
    "• Sans légende : le texte actuel devient la légende (1024 caractères maximum).\n\n"
    "/cancel pour annuler."
)
AD_WRONG_CONTENT = "Envoyez un texte, ou une image en tant que photo (pas en fichier)."
CONTACT_INVALID = "❌ Ce n'est pas un nom d'utilisateur valide. Exemple : <code>@moncompte</code>"


def _local(dt: datetime) -> str:
    return dt.astimezone().strftime("%d/%m/%Y %H:%M")


def _bullets(items: Sequence[str], limit: int | None = None) -> list[str]:
    shown = items if limit is None else items[:limit]
    lines = [f"• {item}" for item in shown]
    if limit is not None and len(items) > limit:
        lines.append(f"• … et {len(items) - limit} autre(s)")
    return lines


def main_menu(account_label: str | None, folder_title: str | None, approved: int, test_mode: bool) -> str:
    lines = ["🤖 <b>VA Recruitment Manager</b>", ""]
    if account_label:
        lines.append(f"Compte : <b>{esc(account_label)}</b>")
    else:
        lines.append("Compte : ❌ <b>non connecté</b> (lancez <code>python login.py</code>)")
    if folder_title:
        lines.append(f"Dossier : <b>{esc(folder_title)}</b> · {approved} groupe(s) approuvé(s)")
    else:
        lines.append("Dossier : aucun pour l'instant")
    if test_mode:
        lines.append("🧪 <b>Mode test actif</b> (TEST_MODE=true) : rien ne sera publié.")
    lines += ["", "Menu :"]
    return "\n".join(lines)


def folders(current_title: str | None) -> str:
    lines = ["📁 <b>Vos dossiers Telegram</b>", ""]
    if current_title:
        lines.append(f"Dossier actuel : <b>{esc(current_title)}</b>")
    lines.append("Choisissez le dossier qui contient les groupes où publier :")
    return "\n".join(lines)


def groups_page(folder_title: str, total: int, approved: int, blocked: int) -> str:
    lines = [
        f"📁 <b>{esc(folder_title)}</b>",
        f"👥 <b>{total}</b> groupe(s) identifié(s) · ✅ {approved} approuvé(s)",
    ]
    if blocked:
        lines[-1] += f" · 🔒 {blocked} sans droit d'écriture"
    if total == 0:
        lines += ["", "Ce dossier ne contient aucun groupe. Ajoutez-en dans Telegram puis réessayez."]
        return "\n".join(lines)
    lines += [
        "",
        "Cochez uniquement les groupes dont les règles <b>autorisent</b> les annonces de recrutement.",
        "✅ approuvé · ⬜ non approuvé · 🔒 publication impossible",
        "Votre sélection est enregistrée automatiquement.",
    ]
    return "\n".join(lines)


def ad_menu(ad: Ad, contact: str | None) -> str:
    rendered = ad_module.render(ad, contact)
    limit = ad_module.CAPTION_LIMIT if ad.has_photo else ad_module.TEXT_LIMIT
    lines = [
        "📝 <b>Votre annonce</b>",
        "",
        f"Format : {'🖼 image + légende' if ad.has_photo else '📝 texte'}",
        f"Contact : {'@' + esc(contact) if contact else '⚠️ aucun'}",
        f"Longueur : {ad_module.telegram_length(rendered.text_html)}/{limit} caractères",
    ]
    problems = [f"❌ {esc(e)}" for e in ad_module.validate(ad, contact)]
    problems += [f"⚠️ {esc(w)}" for w in ad_module.warnings(ad, contact)]
    if problems:
        lines += [""] + problems
    lines += ["", "Utilisez « 👁 Aperçu » pour voir l'annonce exactement comme elle sera publiée."]
    return "\n".join(lines)


def ad_saved(ad: Ad, contact: str | None) -> str:
    return "✅ <b>Annonce enregistrée.</b> Aperçu ci-dessus.\n\n" + ad_menu(ad, contact)


def contact_prompt(current: str | None) -> str:
    now = f"@{esc(current)}" if current else "aucun"
    return (
        "📩 <b>Envoyez le @ qui recevra les candidatures</b> (ex. <code>@moncompte</code>).\n"
        f"Actuellement : {now}\n\n"
        f"Il remplace <code>{CONTACT_PLACEHOLDER}</code> dans votre annonce.\n/cancel pour annuler."
    )


def contact_saved(username: str | None) -> str:
    if username:
        return f"✅ Contact enregistré : @{esc(username)}"
    return "✅ Le @ de votre compte sera utilisé comme contact."


def errors_list(title: str, problems: Sequence[str]) -> str:
    return "\n".join([title, ""] + _bullets([esc(p) for p in problems]))


def publish_summary(plan: Plan, ad: Ad, *, delay: float, test_mode: bool) -> str:
    lines = [
        "🚀 <b>Publication</b>",
        f"📁 Dossier : <b>{esc(plan.folder_title)}</b>",
        f"📝 Annonce : {'image + légende' if ad.has_photo else 'texte'} (aperçu ci-dessus)",
        "",
    ]
    if plan.targets:
        lines.append(f"✅ <b>{len(plan.targets)} groupe(s) recevront l'annonce :</b>")
        lines += _bullets([esc(g.title) for g in plan.targets], SUMMARY_MAX_ITEMS)
    else:
        lines.append("⚠️ <b>Aucun groupe ne peut recevoir l'annonce.</b>")
        lines.append("Approuvez des groupes via « 📁 Choisir un dossier ».")
    if plan.skipped:
        lines += ["", f"⏭️ <b>{len(plan.skipped)} groupe(s) ignoré(s) :</b>"]
        lines += _bullets(
            [f"{esc(g.title)} — {esc(reason)}" for g, reason in plan.skipped], SUMMARY_MAX_ITEMS
        )
    if plan.targets:
        duration = format_duration(max(0, len(plan.targets) - 1) * delay)
        lines += [
            "",
            f"⏱ Durée estimée : {duration} (un envoi toutes les {delay:g} s, limites Telegram respectées).",
            "🧪 Le mode test vérifie tout et vous envoie un exemplaire dans « Messages enregistrés », "
            "sans rien publier dans les groupes.",
        ]
        if test_mode:
            lines += ["", "🧪 <b>Mode test actif</b> (TEST_MODE=true) : rien ne sera publié."]
        else:
            lines += ["", "Confirmez-vous la publication depuis votre compte ?"]
    return "\n".join(lines)


def progress(done: int, total: int, current: str, delay: float) -> str:
    return (
        f"⏳ <b>Publication en cours…</b> {done}/{total}\n"
        f"➡️ {esc(current)}\n\n"
        f"Un envoi toutes les {delay:g} s pour respecter les limites de Telegram.\n"
        "Vous pouvez arrêter à tout moment."
    )


def report(rep: Report) -> str:
    if rep.dry_run:
        title = "🧪 <b>Mode test terminé — rien n'a été publié</b>"
        sent_label = "✅ Groupes qui recevraient l'annonce"
    elif rep.stop_reason:
        title = "⚠️ <b>Publication interrompue</b>"
        sent_label = "✅ Messages envoyés"
    else:
        title = "📊 <b>Publication terminée</b>"
        sent_label = "✅ Messages envoyés"
    lines = [
        title,
        f"📁 Dossier : {esc(rep.folder_title)}",
        f"{sent_label} : {len(rep.sent)}",
        f"❌ Échecs : {len(rep.failed)}",
        f"⏭️ Groupes ignorés : {len(rep.skipped)}",
        f"🕒 {_local(rep.started_at)}",
    ]
    if rep.stop_reason:
        lines += ["", f"⛔ <b>Arrêt :</b> {esc(rep.stop_reason)}"]
    if rep.saved_copy:
        lines += [
            "",
            "📨 Un exemplaire a été envoyé dans vos « Messages enregistrés » pour vérifier le rendu.",
        ]
    if rep.sent:
        lines += ["", f"<b>{sent_label} :</b>"] + _bullets([esc(o.title) for o in rep.sent])
    if rep.failed:
        lines += ["", "<b>❌ Échecs :</b>"] + _bullets(
            [f"{esc(o.title)} — {esc(o.reason or 'erreur inconnue')}" for o in rep.failed]
        )
    if rep.skipped:
        lines += ["", "<b>⏭️ Ignorés :</b>"] + _bullets(
            [f"{esc(o.title)} — {esc(o.reason or '')}" for o in rep.skipped]
        )
    return "\n".join(lines)


def history(rows: Sequence) -> str:
    lines = ["🗂 <b>Historique</b>"]
    for row in rows:
        counts = (
            f"🧪 test · {row.sent} groupe(s)"
            if row.dry_run
            else f"✅ {row.sent} · ❌ {row.failed} · ⏭️ {row.skipped}"
        )
        stop = " · ⚠️ interrompue" if row.stop_reason and not row.dry_run else ""
        lines.append(f"• {_local(row.started_at)} — {esc(row.folder_title)} — {counts}{stop}")
    return "\n".join(lines)


NO_RESULTS = "📊 <b>Résultats</b>\n\nAucune publication pour l'instant. Lancez-en une avec « 🚀 Publier »."


def split_text(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    """Découpe un long texte en plusieurs messages, sur des fins de ligne."""
    parts: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:  # ligne exceptionnellement longue
            if current:
                parts.append(current)
                current = ""
            parts.append(line[:limit])
            line = line[limit:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            parts.append(current)
            current = line
        else:
            current = candidate
    if current or not parts:
        parts.append(current)
    return parts
