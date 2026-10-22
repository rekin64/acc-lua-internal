"""Bot de contrôle (aiogram) : toute la gestion quotidienne se fait depuis Telegram."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from html import escape as esc
from pathlib import Path
from typing import Any

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message, TelegramObject

from . import ad as ad_module
from . import keyboards as kb
from . import texts
from .account import FolderNotFoundError
from .config import Config
from .publisher import explain_error, prepare_plan, run_publication
from .storage import Database

log = logging.getLogger(__name__)


class AdForm(StatesGroup):
    text = State()
    photo = State()
    contact = State()


class OwnerOnlyMiddleware(BaseMiddleware):
    """Ignore silencieusement toute personne autre que OWNER_ID, et tout chat non privé."""

    def __init__(self, owner_id: int):
        self.owner_id = owner_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        chat = data.get("event_chat")
        if user is None or user.id != self.owner_id:
            if user is not None:
                log.warning("Accès refusé à l'utilisateur Telegram %s", user.id)
            return None
        if chat is not None and chat.type != "private":
            return None
        return await handler(event, data)


class PublicationJob:
    """Une seule publication à la fois, arrêtable depuis le bot."""

    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.stop_event: asyncio.Event | None = None

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    def start(self, factory: Callable[[asyncio.Event], Awaitable[None]]) -> None:
        self.stop_event = asyncio.Event()
        self.task = asyncio.create_task(factory(self.stop_event))

    def stop(self) -> bool:
        if not self.running or self.stop_event is None:
            return False
        self.stop_event.set()
        return True

    async def wait(self) -> None:
        if self.task is not None:
            await self.task


# --- Outils d'affichage ------------------------------------------------------------


async def show(cq: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Remplace le message du bouton cliqué (ou envoie un nouveau message si impossible)."""
    message = cq.message
    if isinstance(message, Message) and message.text is not None:
        try:
            await message.edit_text(text, reply_markup=markup)
            return
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc):
                return
    await cq.bot.send_message(cq.from_user.id, text, reply_markup=markup)


async def send_long(bot: Bot, chat_id: int, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    parts = texts.split_text(text)
    for index, part in enumerate(parts):
        await bot.send_message(chat_id, part, reply_markup=markup if index == len(parts) - 1 else None)


async def current_contact(db: Database, account: Any) -> str | None:
    """@ de contact choisi, ou à défaut celui de votre compte."""
    return db.get_contact() or await account.username()


async def send_preview(bot: Bot, chat_id: int, ad: ad_module.Ad, contact: str | None) -> None:
    """Envoie l'annonce exactement comme elle sera publiée."""
    rendered = ad_module.render(ad, contact)
    try:
        if ad.photo_path and Path(ad.photo_path).exists():
            await bot.send_photo(chat_id, FSInputFile(ad.photo_path), caption=rendered.text_html)
        else:
            await bot.send_message(chat_id, rendered.text_html)
    except TelegramBadRequest as exc:
        log.info("Aperçu impossible : %s", exc)
        await bot.send_message(
            chat_id, "⚠️ Aperçu impossible : vérifiez la longueur et le contenu de l'annonce."
        )


async def main_menu_text(db: Database, account: Any, config: Config) -> str:
    folder = db.get_folder()
    approved = sum(1 for g in db.folder_groups() if g.approved) if folder else 0
    return texts.main_menu(
        await account.label(), folder.title if folder else None, approved, config.test_mode
    )


async def publish_blockers(db: Database, account: Any) -> list[str]:
    """Raisons empêchant de publier (compte, dossier, annonce)."""
    problems: list[str] = []
    if not await account.is_authorized():
        problems.append("compte Telegram non connecté : lancez « python login.py »")
    if db.get_folder() is None:
        problems.append("aucun dossier choisi : « 📁 Choisir un dossier »")
    ad = db.get_ad()
    problems += ad_module.validate(ad, await current_contact(db, account))
    if ad.photo_path and not Path(ad.photo_path).exists():
        problems.append("l'image de l'annonce est introuvable : renvoyez-la")
    return problems


def describe_failure(exc: BaseException) -> str:
    if isinstance(exc, FolderNotFoundError):
        return "ce dossier n'existe plus dans votre compte : choisissez-en un autre"
    return explain_error(exc)[0]


# --- Menu principal ----------------------------------------------------------------


async def cmd_start(message: Message, state: FSMContext, db: Database, account: Any, config: Config) -> None:
    await state.clear()
    await message.answer(await main_menu_text(db, account, config), reply_markup=kb.main_menu())


async def cmd_cancel(message: Message, state: FSMContext, db: Database, account: Any, config: Config) -> None:
    await state.clear()
    await message.answer(texts.CANCELLED)
    await message.answer(await main_menu_text(db, account, config), reply_markup=kb.main_menu())


async def cb_home(cq: CallbackQuery, state: FSMContext, db: Database, account: Any, config: Config) -> None:
    await state.clear()
    await cq.answer()
    await show(cq, await main_menu_text(db, account, config), kb.main_menu())


async def cb_noop(cq: CallbackQuery) -> None:
    await cq.answer()


async def on_other_message(message: Message) -> None:
    await message.answer(texts.USE_MENU, reply_markup=kb.main_menu())


# --- Dossiers et groupes ---------------------------------------------------------


async def cb_folders(cq: CallbackQuery, db: Database, account: Any) -> None:
    await cq.answer()
    if not await account.is_authorized():
        await show(cq, texts.NOT_CONNECTED, kb.back_home())
        return
    await show(cq, texts.LOADING_FOLDERS)
    try:
        folders = await account.list_folders()
    except Exception as exc:  # noqa: BLE001
        log.warning("Lecture des dossiers impossible : %s", type(exc).__name__)
        await show(cq, f"❌ Impossible de lire vos dossiers : {esc(describe_failure(exc))}", kb.back_home())
        return
    if not folders:
        await show(cq, texts.NO_FOLDERS, kb.folders([], None))
        return
    current = db.get_folder()
    await show(
        cq,
        texts.folders(current.title if current else None),
        kb.folders(folders, current.id if current else None),
    )


async def show_groups(cq: CallbackQuery, db: Database, page: int) -> None:
    folder = db.get_folder()
    if folder is None:
        await show(cq, "Choisissez d'abord un dossier.", kb.back_home())
        return
    rows = db.folder_groups()
    approved = sum(1 for g in rows if g.approved)
    blocked = sum(1 for g in rows if g.blocked_reason)
    await show(cq, texts.groups_page(folder.title, len(rows), approved, blocked), kb.groups(rows, page))


async def cb_folder(cq: CallbackQuery, db: Database, account: Any) -> None:
    folder_id = int(cq.data.split(":", 1)[1])
    await cq.answer()
    await show(cq, texts.LOADING_GROUPS)
    try:
        folder = next((f for f in await account.list_folders() if f.id == folder_id), None)
        if folder is None:
            raise FolderNotFoundError(folder_id)
        groups = await account.folder_groups(folder_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("Lecture du dossier impossible : %s", type(exc).__name__)
        await show(cq, f"❌ Impossible de lire ce dossier : {esc(describe_failure(exc))}", kb.back_home())
        return
    db.set_folder(folder.id, folder.title)
    db.sync_folder_groups((g.chat_id, g.title, g.text_block) for g in groups)
    await show_groups(cq, db, 0)


async def cb_group_toggle(cq: CallbackQuery, db: Database) -> None:
    _, chat_id, page = cq.data.split(":")
    group = db.get_group(int(chat_id))
    if group is None:
        await cq.answer("Groupe introuvable : actualisez le dossier.", show_alert=True)
        return
    if group.blocked_reason and not group.approved:
        await cq.answer(f"🔒 Publication impossible : {group.blocked_reason}", show_alert=True)
        return
    db.set_approved(group.chat_id, not group.approved)
    await cq.answer("✅ Groupe approuvé" if not group.approved else "Groupe retiré")
    await show_groups(cq, db, int(page))


async def cb_group_page(cq: CallbackQuery, db: Database) -> None:
    await cq.answer()
    await show_groups(cq, db, int(cq.data.split(":")[1]))


async def cb_group_all(cq: CallbackQuery, db: Database) -> None:
    action, page = cq.data.split(":")
    approve = action == "gall"
    db.set_all_approved(approve)
    await cq.answer("Groupes cochés" if approve else "Groupes décochés")
    await show_groups(cq, db, int(page))


# --- Annonce -----------------------------------------------------------------------


async def show_ad_menu(
    target: CallbackQuery | Message, db: Database, account: Any, *, saved: bool = False
) -> None:
    ad = db.get_ad()
    contact = await current_contact(db, account)
    text = texts.ad_saved(ad, contact) if saved else texts.ad_menu(ad, contact)
    markup = kb.ad_menu(ad.has_photo, not ad_module.mentions_contact(ad, contact))
    if isinstance(target, CallbackQuery):
        await show(target, text, markup)
    else:
        await target.answer(text, reply_markup=markup)


async def preview_then_menu(
    bot: Bot, chat_id: int, db: Database, account: Any, *, saved: bool = False
) -> None:
    ad = db.get_ad()
    contact = await current_contact(db, account)
    await send_preview(bot, chat_id, ad, contact)
    text = texts.ad_saved(ad, contact) if saved else texts.ad_menu(ad, contact)
    await bot.send_message(
        chat_id, text, reply_markup=kb.ad_menu(ad.has_photo, not ad_module.mentions_contact(ad, contact))
    )


async def cb_ad_menu(cq: CallbackQuery, state: FSMContext, db: Database, account: Any) -> None:
    await state.clear()
    await cq.answer()
    await show_ad_menu(cq, db, account)


async def cb_ad_preview(cq: CallbackQuery, bot: Bot, db: Database, account: Any) -> None:
    await cq.answer()
    await preview_then_menu(bot, cq.from_user.id, db, account)


async def cb_ad_text(cq: CallbackQuery, state: FSMContext, bot: Bot, db: Database) -> None:
    await state.set_state(AdForm.text)
    await cq.answer()
    await show(cq, texts.AD_TEXT_PROMPT, kb.cancel(kb.AD))
    with suppress(TelegramBadRequest):
        await bot.send_message(cq.from_user.id, db.get_ad().text_html)


async def cb_ad_photo(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdForm.photo)
    await cq.answer()
    await show(cq, texts.AD_PHOTO_PROMPT, kb.cancel(kb.AD))


async def cb_ad_remove_photo(cq: CallbackQuery, db: Database, account: Any) -> None:
    ad = db.get_ad()
    if ad.photo_path:
        with suppress(OSError):
            Path(ad.photo_path).unlink()
    db.save_ad(ad.with_photo(None))
    await cq.answer("Image retirée")
    await show_ad_menu(cq, db, account)


async def cb_ad_template(cq: CallbackQuery, bot: Bot, db: Database, account: Any) -> None:
    db.save_ad(db.get_ad().with_text(ad_module.DEFAULT_TEMPLATE))
    await cq.answer("Modèle chargé")
    await preview_then_menu(bot, cq.from_user.id, db, account, saved=True)


async def cb_ad_add_contact(cq: CallbackQuery, bot: Bot, db: Database, account: Any) -> None:
    ad = ad_module.add_contact_line(db.get_ad())
    problems = ad_module.validate(ad, await current_contact(db, account))
    if problems:
        await cq.answer(problems[0], show_alert=True)
        return
    db.save_ad(ad)
    await cq.answer("Ligne de contact ajoutée")
    await preview_then_menu(bot, cq.from_user.id, db, account, saved=True)


async def cb_ad_contact(cq: CallbackQuery, state: FSMContext, db: Database, account: Any) -> None:
    await state.set_state(AdForm.contact)
    await cq.answer()
    await show(
        cq, texts.contact_prompt(await current_contact(db, account)), kb.contact(await account.username())
    )


async def cb_ad_contact_me(cq: CallbackQuery, state: FSMContext, db: Database, account: Any) -> None:
    await state.clear()
    db.set_contact(None)
    await cq.answer(texts.contact_saved(None))
    await show_ad_menu(cq, db, account)


async def _save_ad(message: Message, state: FSMContext, db: Database, account: Any, ad: ad_module.Ad) -> bool:
    problems = ad_module.validate(ad, await current_contact(db, account))
    if problems:
        await message.answer(
            texts.errors_list("❌ <b>Annonce non enregistrée :</b>", problems)
            + "\n\nRenvoyez-la corrigée, ou /cancel."
        )
        return False
    db.save_ad(ad)
    await state.clear()
    await preview_then_menu(message.bot, message.chat.id, db, account, saved=True)
    return True


async def on_ad_text(message: Message, state: FSMContext, db: Database, account: Any) -> None:
    await _save_ad(message, state, db, account, db.get_ad().with_text(message.html_text))


async def on_ad_photo(
    message: Message, state: FSMContext, db: Database, account: Any, config: Config
) -> None:
    current = db.get_ad()
    text_html = message.html_text if message.caption else current.text_html
    temp_path = config.photo_path.with_name("ad_photo.tmp.jpg")
    await message.bot.download(message.photo[-1], destination=temp_path)
    ad = ad_module.Ad(text_html=text_html, photo_path=str(config.photo_path))
    problems = ad_module.validate(ad, await current_contact(db, account))
    if problems:
        temp_path.unlink(missing_ok=True)
        await message.answer(
            texts.errors_list("❌ <b>Image non enregistrée :</b>", problems)
            + "\n\nRaccourcissez le texte, ou /cancel."
        )
        return
    temp_path.replace(config.photo_path)
    await _save_ad(message, state, db, account, ad)


async def on_ad_wrong_content(message: Message) -> None:
    await message.answer(texts.AD_WRONG_CONTENT)


async def on_contact(message: Message, state: FSMContext, db: Database, account: Any) -> None:
    username = ad_module.normalize_username(message.text)
    if username is None:
        await message.answer(texts.CONTACT_INVALID)
        return
    db.set_contact(username)
    await state.clear()
    await message.answer(texts.contact_saved(username))
    await show_ad_menu(message, db, account)


# --- Publication -------------------------------------------------------------------


async def cb_publish(
    cq: CallbackQuery, bot: Bot, db: Database, account: Any, config: Config, job: PublicationJob
) -> None:
    await cq.answer()
    if job.running:
        await show(cq, texts.ALREADY_RUNNING, kb.stop())
        return
    problems = await publish_blockers(db, account)
    if problems:
        await show(
            cq,
            texts.errors_list("🚀 <b>Publication impossible pour l'instant :</b>", problems),
            kb.publish_blocked(),
        )
        return

    await show(cq, texts.CHECKING_GROUPS)
    ad = db.get_ad()
    try:
        plan = await prepare_plan(
            db,
            account,
            folder=db.get_folder(),
            with_photo=ad.has_photo,
            cooldown_hours=config.repost_cooldown_hours,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Préparation impossible : %s", type(exc).__name__)
        await show(
            cq, f"❌ Impossible de vérifier les groupes : {esc(describe_failure(exc))}", kb.publish_blocked()
        )
        return

    await show(cq, texts.PREVIEW_INTRO)
    await send_preview(bot, cq.from_user.id, ad, await current_contact(db, account))
    await send_long(
        bot,
        cq.from_user.id,
        texts.publish_summary(plan, ad, delay=config.send_delay, test_mode=config.test_mode),
        kb.publish_confirm(bool(plan.targets), config.test_mode),
    )


async def cb_publish_start(
    cq: CallbackQuery, bot: Bot, db: Database, account: Any, config: Config, job: PublicationJob
) -> None:
    if job.running:
        await cq.answer("Une publication est déjà en cours.", show_alert=True)
        return
    dry_run = cq.data == "pub:test" or config.test_mode
    await cq.answer("🧪 Mode test lancé" if dry_run else "🚀 Publication lancée")
    if isinstance(cq.message, Message):  # évite un double clic sur « Confirmer »
        with suppress(TelegramBadRequest):
            await cq.message.edit_reply_markup(reply_markup=None)
    chat_id = cq.from_user.id
    status = await bot.send_message(chat_id, texts.PREPARING, reply_markup=None if dry_run else kb.stop())

    async def task(stop_event: asyncio.Event) -> None:
        await run_publication_task(
            bot,
            chat_id,
            status.message_id,
            dry_run=dry_run,
            db=db,
            account=account,
            config=config,
            stop_event=stop_event,
        )

    job.start(task)


async def run_publication_task(
    bot: Bot,
    chat_id: int,
    status_id: int,
    *,
    dry_run: bool,
    db: Database,
    account: Any,
    config: Config,
    stop_event: asyncio.Event,
) -> None:
    async def on_progress(done: int, total: int, title: str) -> None:
        with suppress(TelegramAPIError):  # l'affichage ne doit jamais interrompre la publication
            await bot.edit_message_text(
                texts.progress(done, total, title, config.send_delay),
                chat_id=chat_id,
                message_id=status_id,
                reply_markup=kb.stop(),
            )

    try:
        problems = await publish_blockers(db, account)
        if problems:
            await bot.send_message(
                chat_id,
                texts.errors_list("🚀 <b>Publication impossible :</b>", problems),
                reply_markup=kb.publish_blocked(),
            )
            return
        ad = db.get_ad()
        rendered = ad_module.render(ad, await current_contact(db, account))
        plan = await prepare_plan(
            db,
            account,
            folder=db.get_folder(),
            with_photo=ad.has_photo,
            cooldown_hours=config.repost_cooldown_hours,
        )
        saved_copy = False
        if dry_run:
            try:
                await account.send_ad("me", rendered, {})
                saved_copy = True
            except Exception as exc:  # noqa: BLE001
                log.warning("Envoi de l'exemplaire de test impossible : %s", type(exc).__name__)
        report = await run_publication(
            plan,
            rendered,
            account.send_ad,
            dry_run=dry_run,
            delay=config.send_delay,
            stop_event=stop_event,
            on_progress=on_progress,
        )
        report.saved_copy = saved_copy
        db.save_report(report)
        log.info(
            "Publication terminée (%s) : %d envoyés, %d échecs, %d ignorés",
            "test" if dry_run else "réelle",
            len(report.sent),
            len(report.failed),
            len(report.skipped),
        )
        with suppress(TelegramBadRequest):
            await bot.delete_message(chat_id, status_id)
        await send_long(bot, chat_id, texts.report(report), kb.after_report())
    except Exception as exc:  # noqa: BLE001 - l'utilisateur doit toujours être prévenu
        log.exception("Publication interrompue par une erreur")
        await bot.send_message(
            chat_id, f"❌ Publication impossible : {esc(describe_failure(exc))}", reply_markup=kb.back_home()
        )


async def cb_publish_stop(cq: CallbackQuery, job: PublicationJob) -> None:
    if job.stop():
        await cq.answer("⏹ Arrêt demandé : plus aucun message ne sera envoyé.", show_alert=True)
    else:
        await cq.answer("Aucune publication en cours.")


# --- Résultats ---------------------------------------------------------------------


async def cb_results(cq: CallbackQuery, bot: Bot, db: Database) -> None:
    await cq.answer()
    publications = db.publications(limit=10)
    if not publications:
        await show(cq, texts.NO_RESULTS, kb.back_home())
        return
    last = db.load_report(publications[0].id)
    text = texts.report(last) + "\n\n" + texts.history(publications)
    parts = texts.split_text(text)
    if len(parts) == 1:
        await show(cq, parts[0], kb.after_report())
    else:
        await send_long(bot, cq.from_user.id, text, kb.after_report())


# --- Assemblage --------------------------------------------------------------------


def create_router() -> Router:
    router = Router(name="va-bot")
    msg, cb = router.message, router.callback_query

    msg.register(cmd_start, CommandStart())
    msg.register(cmd_start, Command("menu"))
    msg.register(cmd_cancel, Command("cancel"))

    msg.register(on_ad_photo, AdForm.text, F.photo)
    msg.register(on_ad_photo, AdForm.photo, F.photo)
    msg.register(on_ad_text, AdForm.text, F.text)
    msg.register(on_ad_wrong_content, AdForm.text)
    msg.register(on_ad_wrong_content, AdForm.photo)
    msg.register(on_contact, AdForm.contact, F.text)
    msg.register(on_other_message)

    cb.register(cb_home, F.data == kb.HOME)
    cb.register(cb_noop, F.data == kb.NOOP)
    cb.register(cb_folders, F.data == kb.FOLDERS)
    cb.register(cb_folder, F.data.startswith("folder:"))
    cb.register(cb_group_toggle, F.data.startswith("grp:"))
    cb.register(cb_group_page, F.data.startswith("gpage:"))
    cb.register(cb_group_all, F.data.startswith("gall:") | F.data.startswith("gnone:"))

    cb.register(cb_ad_menu, F.data == kb.AD)
    cb.register(cb_ad_preview, F.data == "ad:preview")
    cb.register(cb_ad_text, F.data == "ad:text")
    cb.register(cb_ad_photo, F.data == "ad:photo")
    cb.register(cb_ad_remove_photo, F.data == "ad:rmphoto")
    cb.register(cb_ad_template, F.data == "ad:template")
    cb.register(cb_ad_add_contact, F.data == "ad:addcontact")
    cb.register(cb_ad_contact, F.data == "ad:contact")
    cb.register(cb_ad_contact_me, F.data == "ad:contact_me")

    cb.register(cb_publish, F.data == kb.PUBLISH)
    cb.register(cb_publish_start, F.data.in_({"pub:go", "pub:test"}))
    cb.register(cb_publish_stop, F.data == "pub:stop")
    cb.register(cb_results, F.data == kb.RESULTS)
    return router


def build_dispatcher(config: Config, db: Database, account: Any) -> Dispatcher:
    dp = Dispatcher(config=config, db=db, account=account, job=PublicationJob())
    dp.update.outer_middleware(OwnerOnlyMiddleware(config.owner_id))
    dp.include_router(create_router())
    return dp
