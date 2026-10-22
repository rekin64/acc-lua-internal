# 🤖 VA Recruitment Manager — bot Telegram de recrutement de VAs

Publiez vos annonces de recrutement de Virtual Assistants (Twitter/X) **depuis votre propre compte
Telegram**, dans les groupes de vos dossiers qui autorisent ces annonces. Toute la gestion se fait
depuis un **bot Telegram privé**, en quelques clics : aucun site web, aucun tableau de bord.

Les candidats vous écrivent directement en message privé, sur votre compte personnel.

```
🤖 VA Recruitment Manager
Compte : @moncompte
Dossier : VA OFM · 18 groupe(s) approuvé(s)

Menu :
[📁 Choisir un dossier]
[📝 Configurer mon annonce]
[🚀 Publier]
[📊 Résultats]
```

---

## Sommaire

1. [Ce que fait (et ne fait pas) le bot](#1-ce-que-fait-et-ne-fait-pas-le-bot)
2. [Créer votre bot de contrôle avec BotFather](#2-créer-votre-bot-de-contrôle-avec-botfather)
3. [Obtenir vos identifiants API Telegram](#3-obtenir-vos-identifiants-api-telegram)
4. [Trouver votre identifiant Telegram (OWNER_ID)](#4-trouver-votre-identifiant-telegram-owner_id)
5. [Installation](#5-installation)
6. [Configuration (.env)](#6-configuration-env)
7. [Connexion de votre compte (une seule fois)](#7-connexion-de-votre-compte-une-seule-fois)
8. [Démarrage](#8-démarrage)
9. [Utilisation au quotidien](#9-utilisation-au-quotidien)
10. [Sécurité](#10-sécurité)
11. [Limites Telegram et bonnes pratiques](#11-limites-telegram-et-bonnes-pratiques)
12. [Erreurs courantes](#12-erreurs-courantes)
13. [Tests](#13-tests)
14. [Organisation des fichiers](#14-organisation-des-fichiers)

---

## 1. Ce que fait (et ne fait pas) le bot

**Il fait :**

- lire vos **vrais dossiers Telegram** (inclusions, exclusions et options « exclure muets / lus /
  archivés » respectées, dossiers partagés compris) ;
- vous laisser **cocher explicitement** les groupes qui acceptent les annonces (sélection mémorisée) ;
- enregistrer votre annonce (texte, image + légende, votre @ de contact), avec aperçu ;
- publier depuis votre compte, **uniquement** dans les groupes approuvés, un groupe à la fois ;
- afficher un récapitulatif (envoyés, échecs avec raisons, groupes ignorés) et garder un historique ;
- proposer un **mode test** qui vérifie tout sans rien publier.

**Il ne fait pas (volontairement) :** pas de site web, pas de multi-comptes, pas de proxy, pas d'IA,
**aucun message privé automatique**, aucun contournement des restrictions des groupes ou des limites
anti-spam de Telegram.

---

## 2. Créer votre bot de contrôle avec BotFather

Le « bot de contrôle » est le bot privé dans lequel vous cliquerez sur les boutons.

1. Dans Telegram, ouvrez **[@BotFather](https://t.me/BotFather)** (compte officiel, badge bleu).
2. Envoyez `/newbot`.
3. Donnez un **nom** (ex. `VA Recruitment Manager`).
4. Donnez un **nom d'utilisateur** se terminant par `bot` (ex. `mon_va_recruit_bot`).
5. BotFather répond avec un **jeton** du type `1234567890:AAH...`. Copiez-le : c'est votre `BOT_TOKEN`.

> ⚠️ Ce jeton donne le contrôle du bot : ne le partagez jamais. En cas de fuite :
> @BotFather → `/revoke`.

Facultatif : `/setdescription` et `/setuserpic` pour personnaliser le bot. Inutile de le rendre
privé : il ignore toute personne autre que vous (voir `OWNER_ID`).

---

## 3. Obtenir vos identifiants API Telegram

Ces identifiants permettent au programme de se connecter à **votre compte personnel**.

1. Allez sur **<https://my.telegram.org>** et connectez-vous avec votre numéro
   (le code arrive dans l'application Telegram).
2. Cliquez sur **API development tools**.
3. Remplissez le formulaire (une seule fois) :
   - *App title* : `VA Recruitment` · *Short name* : `varecruit` · *Platform* : `Desktop`
   - le reste peut rester vide.
4. Notez **App api_id** (un nombre → `API_ID`) et **App api_hash** (32 caractères → `API_HASH`).

> ⚠️ `API_HASH` est confidentiel. Ne le publiez jamais (captures d'écran, GitHub…).

---

## 4. Trouver votre identifiant Telegram (OWNER_ID)

Ouvrez **[@userinfobot](https://t.me/userinfobot)** et envoyez `/start` : il répond avec votre
**Id** (un nombre, ex. `123456789`). C'est votre `OWNER_ID` : seul ce compte pourra utiliser le bot.

---

## 5. Installation

Prérequis : **Python 3.11 ou plus récent** ([python.org/downloads](https://www.python.org/downloads/) ;
sous Windows, cochez « Add Python to PATH » pendant l'installation).

Ouvrez un terminal dans le dossier `telegram-va-bot`, puis :

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

**Windows (PowerShell)**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

> À chaque nouvelle session de terminal, réactivez l'environnement
> (`source .venv/bin/activate` ou `.venv\Scripts\Activate.ps1`) avant de lancer le bot.

---

## 6. Configuration (.env)

Ouvrez le fichier `.env` avec un éditeur de texte et complétez :

| Variable | Obligatoire | Description |
|---|---|---|
| `API_ID` | ✅ | Nombre obtenu sur my.telegram.org |
| `API_HASH` | ✅ | Clé de 32 caractères obtenue sur my.telegram.org |
| `BOT_TOKEN` | ✅ | Jeton donné par @BotFather |
| `OWNER_ID` | ✅ | Votre identifiant Telegram (@userinfobot) |
| `PHONE` | | Votre numéro (`+33612345678`), sinon demandé à la connexion |
| `SEND_DELAY_SECONDS` | | Attente entre deux groupes. Défaut `10`, minimum `5` |
| `REPOST_COOLDOWN_HOURS` | | Délai minimum avant de republier dans un même groupe. Défaut `24`, `0` = aucun |
| `TEST_MODE` | | `true` = rien n'est jamais publié (idéal pour la première prise en main) |
| `DATA_DIR` | | Dossier des données locales. Défaut `data` |

---

## 7. Connexion de votre compte (une seule fois)

```bash
python login.py
```

1. Saisissez votre numéro au format international (`+33612345678`).
2. Telegram vous envoie un code dans l'application : tapez-le (la saisie reste **masquée**).
3. Si la validation en deux étapes est activée, tapez votre mot de passe 2FA (saisie masquée).

La session est enregistrée dans `data/account.session` (fichier lisible uniquement par vous) :
vous n'aurez plus à vous reconnecter. Le code et le mot de passe ne sont **jamais** affichés,
enregistrés ni envoyés via un message Telegram.

> Astuce : si vous lancez directement `python main.py`, la connexion est demandée automatiquement
> la première fois.

Pour déconnecter le compte (changement de compte, sécurité) : `python login.py --logout`.
Vous pouvez aussi fermer la session depuis Telegram : Paramètres → Appareils → « VA Recruitment Bot ».

---

## 8. Démarrage

```bash
python main.py
```

Le terminal affiche `Bot @votre_bot prêt`. Ouvrez votre bot dans Telegram et envoyez **/start**.
Le bot fonctionne tant que ce terminal reste ouvert (`Ctrl+C` pour l'arrêter).

Pour qu'il tourne en permanence, lancez-le sur un ordinateur ou un petit serveur toujours allumé
(par exemple sous Linux : `nohup python main.py > bot.log 2>&1 &`, ou un service systemd).

Commandes du bot : `/start` (menu), `/cancel` (annuler l'action en cours).

---

## 9. Utilisation au quotidien

### 📁 Choisir un dossier

1. Le bot affiche vos dossiers Telegram (ex. « VA OFM »).
2. Choisissez-en un : il compte les groupes du dossier (« 👥 23 groupe(s) identifié(s) »).
3. **Cochez les groupes dont les règles autorisent les annonces** : ✅ approuvé, ⬜ non approuvé,
   🔒 publication impossible (groupe en lecture seule, compte restreint, messages payants…).
4. La sélection est enregistrée automatiquement et conservée pour les prochaines fois.
   Un nouveau groupe ajouté au dossier n'est **jamais** approuvé sans votre accord.

> Créer un dossier dans Telegram : Paramètres → Dossiers de discussion → Créer un dossier.

### 📝 Configurer mon annonce

Au premier lancement, l'annonce d'exemple est déjà prête :

```
🚀 WE'RE HIRING — TWITTER/X VAs

We're recruiting Virtual Assistants for a new project.

💰 Commission-based earnings
🌍 Remote work
📱 Twitter/X tasks

📩 DM {contact} to apply
```

- **✏️ Modifier le texte** : envoyez votre texte (gras, italique et liens conservés).
  Écrivez `{contact}` à l'endroit où votre @ doit apparaître : il est remplacé automatiquement.
- **🖼 Ajouter une image** : envoyez une photo (avec ou sans légende). Légende : 1024 caractères max.
- **📩 Mon @ de contact** : par défaut le @ de votre compte ; modifiable (ex. un compte dédié).
- **👁 Aperçu** : l'annonce exactement comme elle sera publiée.
- **📄 Remplacer par le modèle** : revenir à l'exemple ci-dessus.

### 🚀 Publier

1. Le bot vérifie le dossier sur Telegram (état à jour) et affiche l'**aperçu** de l'annonce.
2. Il liste les groupes qui **recevront** l'annonce et ceux qui seront **ignorés** (avec la raison).
3. Choisissez :
   - **✅ Confirmer et publier** : envoi depuis votre compte, un groupe toutes les 10 s
     (bouton **⏹ Arrêter** disponible pendant l'envoi) ;
   - **🧪 Mode test (sans publier)** : tout est vérifié, **rien n'est publié dans les groupes**, et un
     exemplaire est envoyé dans vos « Messages enregistrés » pour contrôler le rendu ;
   - **❌ Annuler**.

### 📊 Résultats

À la fin, puis à tout moment via « 📊 Résultats » :

```
📊 Publication terminée
📁 Dossier : VA OFM
✅ Messages envoyés : 18
❌ Échecs : 2
⏭️ Groupes ignorés : 5
```

suivi de la liste des groupes concernés, des raisons des échecs et de l'historique des
10 dernières publications. Seuls l'identifiant et le titre des groupes sont conservés :
**aucune donnée sur les membres** n'est stockée.

---

## 10. Sécurité

- **Accès réservé** : le bot ignore silencieusement toute personne autre que `OWNER_ID`, et ne
  répond qu'en conversation privée.
- **Secrets** : `.env`, `data/` et les fichiers `*.session` sont exclus de Git (`.gitignore`).
  Le dossier `data/` et ses fichiers sensibles sont créés avec des droits limités à votre utilisateur.
- **Journaux** : le jeton du bot, l'API hash et le numéro de téléphone sont masqués (`***`) s'ils
  apparaissent ; les codes de connexion et mots de passe ne sont jamais journalisés.
- **Session** : `data/account.session` équivaut à une connexion ouverte à votre compte. Ne la copiez
  pas et ne la partagez jamais. En cas de doute : `python login.py --logout`, ou Telegram →
  Paramètres → Appareils → terminer la session.
- **Données minimales** : la session ne garde pas en cache les informations des utilisateurs
  croisés dans vos discussions ; l'historique ne contient que les groupes et les résultats d'envoi.

---

## 11. Limites Telegram et bonnes pratiques

Le bot est conçu pour **respecter** les règles, jamais pour les contourner :

- un envoi à la fois, avec un **délai fixe** entre deux groupes (`SEND_DELAY_SECONDS`) ;
- **FloodWait** : si Telegram demande d'attendre moins de 60 s, le programme attend comme demandé ;
  au-delà, **la publication s'arrête** et le rapport indique combien de temps patienter ;
- **compte limité pour spam** (`PeerFlood`, restriction des groupes publics) : arrêt immédiat, avec
  un renvoi vers [@SpamBot](https://t.me/SpamBot) pour connaître la situation de votre compte ;
- groupes en lecture seule, images interdites, mode lent, messages payants : **ignorés ou signalés**,
  jamais forcés ;
- un même groupe ne reçoit pas deux annonces en moins de `REPOST_COOLDOWN_HOURS` heures (24 h par
  défaut), ce qui évite aussi les doubles clics ;
- aucun message privé n'est envoyé aux membres : ce sont les candidats qui vous écrivent.

Conseils : n'approuvez que les groupes dont les règles autorisent explicitement le recrutement,
gardez un rythme raisonnable (une annonce par groupe et par jour au plus), et faites un essai en
mode test après chaque modification importante.

---

## 12. Erreurs courantes

| Message | Cause | Que faire |
|---|---|---|
| `Fichier .env introuvable` | `.env` absent | `cp .env.example .env` puis le compléter |
| `API_ID / API_HASH / BOT_TOKEN / OWNER_ID … invalide` | Valeur mal copiée | Revérifier les étapes 2 à 4 |
| `BOT_TOKEN refusé par Telegram` | Jeton erroné ou révoqué | Nouveau jeton via @BotFather |
| `Compte Telegram non connecté` | Session absente ou fermée | Arrêter le bot, `python login.py`, relancer |
| `Code incorrect` / `Code expiré` | Saisie erronée ou trop tardive | Relancer `python login.py` |
| `Connexion aux serveurs Telegram impossible` | Pas d'Internet / pare-feu | Vérifier la connexion, relancer |
| `Aucun dossier trouvé` | Aucun dossier dans le compte | Créer un dossier dans Telegram |
| `limite d'envoi Telegram atteinte (FloodWait)` | Trop d'envois récents | Patienter le temps indiqué |
| `Telegram limite votre compte pour spam` | Compte signalé (PeerFlood) | Consulter @SpamBot, réduire le rythme |
| `écriture interdite dans ce groupe` | Groupe en lecture seule / exclu | Décocher le groupe |
| `images interdites dans ce groupe` | Médias non autorisés | Annonce texte, ou décocher le groupe |
| `mode lent du groupe` | Slow mode actif | Réessayer plus tard |
| `groupe inaccessible` | Groupe privé quitté / exclusion | Retirer le groupe du dossier |
| `session Telegram expirée ou révoquée` | Session fermée depuis un autre appareil | `python login.py` |
| `déjà publié il y a …` | Délai entre deux annonces | Attendre, ou ajuster `REPOST_COOLDOWN_HOURS` |
| `Texte trop long` | > 4096 caractères (texte) ou > 1024 (légende) | Raccourcir l'annonce |

---

## 13. Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Les tests (aucun accès réseau, aucun compte réel) couvrent : la configuration, l'annonce (contact,
limites de longueur), les règles des dossiers Telegram (inclusions, exclusions, options, dossiers
partagés), les droits de publication, la base de données, la publication (groupes approuvés
uniquement, erreurs, FloodWait, arrêt, mode test, délai entre deux annonces), la connexion
(code, 2FA), la couche Telethon et des parcours complets dans le bot (accès réservé au
propriétaire, choix du dossier, sélection des groupes, annonce, publication, résultats).

---

## 14. Organisation des fichiers

```
telegram-va-bot/
├── main.py              # démarre le bot de contrôle
├── login.py             # connexion / déconnexion du compte (une seule fois)
├── requirements.txt     # dépendances
├── requirements-dev.txt # dépendances de test
├── .env.example         # modèle de configuration
├── vabot/
│   ├── config.py        # lecture et validation du .env
│   ├── logs.py          # journaux sans secrets
│   ├── login_flow.py    # téléphone → code → mot de passe 2FA
│   ├── account.py       # votre compte Telegram (Telethon) : dossiers, groupes, envoi
│   ├── folders.py       # règles des dossiers et droits de publication
│   ├── ad.py            # annonce : modèle, contact, aperçu, validation
│   ├── publisher.py     # plan de publication, envoi, erreurs Telegram
│   ├── storage.py       # SQLite : réglages, groupes approuvés, historique
│   ├── bot.py           # bot de contrôle (aiogram) : menus et boutons
│   ├── keyboards.py     # boutons
│   └── texts.py         # textes affichés
├── tests/               # tests automatisés (pytest)
└── data/                # créé au lancement : session, base, image (privé, non versionné)
```
