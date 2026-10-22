"""Parcours complets du bot de contrôle, avec une fausse API Bot (aucun accès réseau)."""

from dataclasses import replace
from datetime import datetime
from itertools import count
from types import SimpleNamespace

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.methods import AnswerCallbackQuery, EditMessageText, GetFile, GetMe, SendMessage, SendPhoto
from aiogram.types import CallbackQuery, Chat, File, Message, PhotoSize, Update, User

from conftest import BOT_TOKEN, OWNER_ID, STRANGER_ID
from vabot.bot import build_dispatcher

_ids = count(1000)


class RecordingSession(BaseSession):
    """Enregistre les appels à l'API Bot au lieu de les envoyer à Telegram."""

    def __init__(self):
        super().__init__()
        self.requests = []

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        if isinstance(method, GetMe):
            return User(id=1, is_bot=True, first_name="Bot", username="test_bot")
        if isinstance(method, GetFile):
            return File(file_id=method.file_id, file_unique_id="u", file_path="photos/ad.jpg")
        if isinstance(method, (SendMessage, SendPhoto, EditMessageText)):
            return Message(
                message_id=getattr(method, "message_id", None) or next(_ids),
                date=datetime.now(),
                chat=Chat(id=method.chat_id or OWNER_ID, type="private"),
                text=getattr(method, "text", None),
            )
        return True

    async def stream_content(self, url, headers=None, timeout=30, chunk_size=65536, raise_for_status=True):
        yield b"\xff\xd8fake-jpeg"

    async def close(self):
        pass


def _user(user_id):
    return User(id=user_id, is_bot=False, first_name="Test")


def _message(user_id=OWNER_ID, chat_type="private", **fields):
    return Message(
        message_id=next(_ids),
        date=datetime.now(),
        chat=Chat(id=user_id, type=chat_type),
        from_user=_user(user_id),
        **fields,
    )


@pytest.fixture
def h(config, db, fake_account):
    session = RecordingSession()
    bot = Bot(BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher(replace(config, send_delay=0), db, fake_account)

    async def send(text=None, user_id=OWNER_ID, chat_type="private", **fields):
        session.requests.clear()
        update = Update(update_id=next(_ids), message=_message(user_id, chat_type, text=text, **fields))
        await dp.feed_update(bot, update)
        return session.requests

    async def click(data, user_id=OWNER_ID):
        session.requests.clear()
        menu = Message(message_id=50, date=datetime.now(), chat=Chat(id=user_id, type="private"), text="menu")
        cq = CallbackQuery(
            id=str(next(_ids)), from_user=_user(user_id), chat_instance="ci", data=data, message=menu
        )
        await dp.feed_update(bot, Update(update_id=next(_ids), callback_query=cq))
        return session.requests

    return SimpleNamespace(send=send, click=click, db=db, account=fake_account, job=dp["job"], config=config)


def texts_of(requests):
    return "\n".join(
        getattr(r, "text", None) or getattr(r, "caption", None) or ""
        for r in requests
        if isinstance(r, (SendMessage, EditMessageText, SendPhoto))
    )


def alerts(requests):
    return [r.text for r in requests if isinstance(r, AnswerCallbackQuery) and r.show_alert]


async def approve_two_groups(h):
    await h.click("folder:7")
    await h.click("grp:-1001:0")
    await h.click("grp:-1002:0")


# --- Accès -------------------------------------------------------------------------


async def test_only_owner_can_use_the_bot(h):
    assert await h.send("/start", user_id=STRANGER_ID) == []
    assert await h.click("menu:publish", user_id=STRANGER_ID) == []
    assert await h.send("/start", chat_type="group") == []


async def test_start_shows_account_and_menu(h):
    requests = await h.send("/start")
    reply = requests[-1]
    assert isinstance(reply, SendMessage)
    assert "VA Recruitment Manager" in reply.text and "@moncompte" in reply.text
    buttons = [b.text for row in reply.reply_markup.inline_keyboard for b in row]
    assert buttons == ["📁 Choisir un dossier", "📝 Configurer mon annonce", "🚀 Publier", "📊 Résultats"]


async def test_not_connected_account(h):
    h.account.authorized = False
    assert "non connecté" in texts_of(await h.send("/start"))
    assert "login.py" in texts_of(await h.click("menu:folders"))


# --- Dossiers et groupes -----------------------------------------------------------


async def test_folder_and_group_selection(h):
    requests = await h.click("menu:folders")
    folder_buttons = [b.text for row in requests[-1].reply_markup.inline_keyboard for b in row]
    assert "📁 VA OFM" in folder_buttons and "📁 Autres" in folder_buttons

    text = texts_of(await h.click("folder:7"))
    assert h.db.get_folder().title == "VA OFM"
    assert "3</b> groupe(s) identifié(s)" in text
    assert h.db.approved_ids() == set()  # sélection explicite obligatoire

    await h.click("grp:-1001:0")
    assert h.db.approved_ids() == {-1001}
    await h.click("grp:-1001:0")
    assert h.db.approved_ids() == set()

    # Groupe en lecture seule : refus expliqué, pas d'approbation possible.
    requests = await h.click("grp:-1003:0")
    assert any("administrateurs" in a for a in alerts(requests))
    assert h.db.approved_ids() == set()

    await h.click("gall:0")
    assert h.db.approved_ids() == {-1001, -1002}


# --- Annonce -----------------------------------------------------------------------


async def test_write_ad_with_contact_placeholder(h):
    await h.click("ad:text")
    requests = await h.send("Hiring VAs! DM {contact}")
    assert h.db.get_ad().text_html == "Hiring VAs! DM {contact}"
    assert "Hiring VAs! DM @moncompte" in texts_of(requests)  # aperçu
    assert "Annonce enregistrée" in texts_of(requests)


async def test_change_contact(h):
    await h.click("ad:contact")
    assert "pas un nom d'utilisateur" in texts_of(await h.send("pas valide !"))
    await h.send("@recrutement_va")
    assert h.db.get_contact() == "recrutement_va"
    assert "DM @recrutement_va to apply" in texts_of(await h.click("ad:preview"))


async def test_add_photo_then_remove(h, config):
    await h.click("ad:photo")
    photo = [
        PhotoSize(file_id="small", file_unique_id="s", width=90, height=90),
        PhotoSize(file_id="big", file_unique_id="b", width=800, height=800),
    ]
    requests = await h.send(photo=photo)
    ad = h.db.get_ad()
    assert ad.photo_path == str(config.photo_path) and config.photo_path.exists()
    assert any(isinstance(r, GetFile) and r.file_id == "big" for r in requests)
    assert any(isinstance(r, SendPhoto) for r in requests)  # aperçu avec l'image

    await h.click("ad:rmphoto")
    assert not h.db.get_ad().has_photo and not config.photo_path.exists()


async def test_too_long_caption_is_refused(h):
    await h.click("ad:text")
    await h.send("x" * 2000 + " {contact}")
    await h.click("ad:photo")
    photo = [PhotoSize(file_id="big", file_unique_id="b", width=800, height=800)]
    assert "1024" in texts_of(await h.send(photo=photo))
    assert not h.db.get_ad().has_photo


# --- Publication -------------------------------------------------------------------


async def test_publish_requires_a_folder(h):
    assert "aucun dossier choisi" in texts_of(await h.click("menu:publish"))


async def test_publish_summary_then_confirmation(h):
    await approve_two_groups(h)
    text = texts_of(await h.click("menu:publish"))
    assert "VA OFM" in text and "2 groupe(s) recevront l'annonce" in text
    assert "Admins only — seuls les administrateurs peuvent écrire" in text
    assert h.account.sent == []  # rien n'est publié avant la confirmation

    requests = await h.click("pub:go")
    await h.job.wait()
    assert [peer for peer, _ in h.account.sent] == ["peer-1001", "peer-1002"]
    assert "@moncompte" in h.account.sent[0][1].text_html

    report = texts_of(requests)  # rapport envoyé à la fin de la tâche de publication
    assert "📊 <b>Publication terminée</b>" in report and "✅ Messages envoyés : 2" in report
    pub = h.db.publications()[0]
    assert (pub.dry_run, pub.sent, pub.failed, pub.skipped) == (False, 2, 0, 1)

    results = texts_of(await h.click("menu:results"))
    assert "Publication terminée" in results and "Messages envoyés : 2" in results
    assert "Historique" in results

    # Republier tout de suite : le délai minimum entre deux annonces protège les groupes.
    await h.click("pub:go")
    await h.job.wait()
    assert len(h.account.sent) == 2


async def test_test_mode_publishes_nothing(h):
    await approve_two_groups(h)
    await h.click("pub:test")
    await h.job.wait()
    assert [peer for peer, _ in h.account.sent] == ["me"]  # exemplaire dans « Messages enregistrés »
    pub = h.db.publications()[0]
    assert pub.dry_run and pub.sent == 2
    assert "rien n'a été publié" in texts_of(await h.click("menu:results"))


async def test_failures_are_reported(h):
    from telethon import errors

    h.account.fail["peer-1002"] = errors.ChatWriteForbiddenError(request=None)
    await approve_two_groups(h)
    await h.click("pub:go")
    await h.job.wait()
    text = texts_of(await h.click("menu:results"))
    assert "Messages envoyés : 1" in text and "Échecs : 1" in text
    assert "VA Hiring — écriture interdite dans ce groupe" in text
