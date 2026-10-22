"""Démarre le bot de contrôle « VA Recruitment Manager ».

Usage : python main.py
Au premier lancement, la connexion de votre compte Telegram est demandée dans le terminal.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.types import BotCommand

from vabot.account import TelegramAccount, create_client
from vabot.bot import build_dispatcher
from vabot.config import ConfigError, load_config, secure_data_dir
from vabot.login_flow import interactive_login
from vabot.logs import setup_logging
from vabot.storage import Database

log = logging.getLogger("vabot")


async def run() -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"❌ Configuration : {exc}")
        return 1
    setup_logging(config.secrets())
    secure_data_dir(config.data_dir)

    db = Database(config.db_path)
    client = create_client(config)
    account = TelegramAccount(client, config.session_file)
    authorized = await account.connect()
    if not authorized and client.is_connected() and sys.stdin.isatty():
        authorized = await interactive_login(client, config.phone)
    if authorized:
        log.info("Compte Telegram connecté : %s", await account.label())
    else:
        log.warning("Compte Telegram non connecté : lancez « python login.py ». Le bot démarre quand même.")

    bot = Bot(
        config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    dp = build_dispatcher(config, db, account)
    try:
        me = await bot.get_me()
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Ouvrir le menu"),
                BotCommand(command="cancel", description="Annuler l'action en cours"),
            ]
        )
        log.info("Bot @%s prêt. Ouvrez-le dans Telegram et envoyez /start.", me.username)
        if config.test_mode:
            log.info("TEST_MODE actif : aucune annonce ne sera publiée.")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), handle_signals=True)
    except TelegramUnauthorizedError:
        log.error("BOT_TOKEN refusé par Telegram : vérifiez-le auprès de @BotFather.")
        return 1
    except TelegramNetworkError:
        log.error("Impossible de joindre l'API des bots Telegram : vérifiez votre connexion Internet.")
        return 1
    finally:
        await bot.session.close()
        await account.disconnect()
        db.close()
    return 0


def main() -> None:
    try:
        sys.exit(asyncio.run(run()))
    except KeyboardInterrupt:
        print("\nArrêt du bot.")


if __name__ == "__main__":
    main()
