"""Connexion interactive de votre compte Telegram (téléphone, code, mot de passe 2FA).

Le code et le mot de passe sont saisis dans le terminal, masqués, et ne sont
jamais affichés, journalisés ni transmis via un message Telegram.
"""

from __future__ import annotations

import getpass
from collections.abc import Callable

from telethon import TelegramClient, errors

from .publisher import format_duration

MAX_ATTEMPTS = 3

Ask = Callable[[str], str]
Say = Callable[[str], None]


async def interactive_login(
    client: TelegramClient,
    phone: str | None = None,
    *,
    ask: Ask = input,
    ask_secret: Ask = getpass.getpass,
    say: Say = print,
) -> bool:
    """Connecte le compte si nécessaire. Renvoie True si le compte est connecté."""
    if not client.is_connected():
        await client.connect()
    if await client.is_user_authorized():
        return True

    say("\n🔐 Connexion de votre compte Telegram (à faire une seule fois).")
    phone = (phone or ask("Numéro de téléphone au format international (ex. +33612345678) : ")).strip()
    phone = phone.replace(" ", "")
    try:
        sent = await client.send_code_request(phone)
    except errors.PhoneNumberInvalidError:
        say("❌ Numéro invalide. Utilisez le format international, ex. +33612345678.")
        return False
    except errors.PhoneNumberBannedError:
        say("❌ Ce numéro est banni par Telegram.")
        return False
    except errors.ApiIdInvalidError:
        say("❌ API_ID ou API_HASH invalide : vérifiez le fichier .env (https://my.telegram.org).")
        return False
    except errors.FloodWaitError as exc:
        say(f"❌ Trop de tentatives. Réessayez dans {format_duration(exc.seconds)}.")
        return False

    say("📨 Telegram vient de vous envoyer un code (dans l'application Telegram ou par SMS).")
    for _ in range(MAX_ATTEMPTS):
        code = "".join(ch for ch in ask_secret("Code reçu (saisie masquée) : ") if ch.isdigit())
        if not code:
            say("Aucun code saisi.")
            continue
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=sent.phone_code_hash)
            return await client.is_user_authorized()
        except errors.SessionPasswordNeededError:
            return await _ask_password(client, ask_secret, say)
        except errors.PhoneCodeInvalidError:
            say("Code incorrect, réessayez.")
        except errors.PhoneCodeExpiredError:
            say("❌ Code expiré. Relancez la connexion pour en recevoir un nouveau.")
            return False
        except errors.PhoneNumberUnoccupiedError:
            say("❌ Aucun compte Telegram n'est associé à ce numéro.")
            return False
        except errors.FloodWaitError as exc:
            say(f"❌ Trop de tentatives. Réessayez dans {format_duration(exc.seconds)}.")
            return False
    say("❌ Trop d'essais incorrects. Relancez la connexion.")
    return False


async def _ask_password(client: TelegramClient, ask_secret: Ask, say: Say) -> bool:
    say("🔑 Votre compte est protégé par la validation en deux étapes.")
    for _ in range(MAX_ATTEMPTS):
        password = ask_secret("Mot de passe 2FA (saisie masquée) : ")
        if not password:
            continue
        try:
            await client.sign_in(password=password)
            return await client.is_user_authorized()
        except errors.PasswordHashInvalidError:
            say("Mot de passe incorrect, réessayez.")
        except errors.FloodWaitError as exc:
            say(f"❌ Trop de tentatives. Réessayez dans {format_duration(exc.seconds)}.")
            return False
    say("❌ Trop d'essais incorrects. Relancez la connexion.")
    return False
