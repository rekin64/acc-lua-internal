"""Connexion (une seule fois) de votre compte Telegram personnel.

Usage :
    python login.py            connecter le compte (téléphone, code, mot de passe 2FA)
    python login.py --logout   déconnecter le compte et supprimer la session

Arrêtez le bot (main.py) avant de lancer ce script.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from telethon import utils

from vabot.account import CONNECT_TIMEOUT, create_client
from vabot.config import ConfigError, load_config, secure_data_dir, secure_file
from vabot.login_flow import interactive_login


async def run(logout: bool) -> int:
    try:
        config = load_config(require_bot=False)
    except ConfigError as exc:
        print(f"❌ Configuration : {exc}")
        return 1
    secure_data_dir(config.data_dir)
    client = create_client(config)
    try:
        await asyncio.wait_for(client.connect(), CONNECT_TIMEOUT)
        if logout:
            if await client.is_user_authorized():
                await client.log_out()  # invalide la session côté Telegram et supprime le fichier
            elif config.session_file.exists():
                await client.disconnect()
                config.session_file.unlink()
            print("✅ Compte déconnecté, session supprimée.")
            return 0

        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"✅ Déjà connecté : {_label(me)}. Pour changer de compte : python login.py --logout")
            return 0
        if not await interactive_login(client, config.phone):
            return 1
        me = await client.get_me()
        print(f"\n✅ Compte connecté : {_label(me)}")
        print("Session enregistrée : vous n'aurez plus à vous reconnecter.")
        print("Lancez maintenant le bot : python main.py")
        return 0
    except (OSError, ConnectionError, asyncio.TimeoutError):
        print("❌ Impossible de joindre les serveurs Telegram : vérifiez votre connexion Internet.")
        return 1
    finally:
        if client.is_connected():
            await client.disconnect()
        secure_file(config.session_file)


def _label(me: object) -> str:
    username = getattr(me, "username", None)
    return f"@{username}" if username else utils.get_display_name(me)


def main() -> None:
    parser = argparse.ArgumentParser(description="Connexion de votre compte Telegram personnel.")
    parser.add_argument("--logout", action="store_true", help="déconnecter le compte et supprimer la session")
    args = parser.parse_args()
    try:
        sys.exit(asyncio.run(run(args.logout)))
    except KeyboardInterrupt:
        print("\nConnexion annulée.")
        sys.exit(1)


if __name__ == "__main__":
    main()
