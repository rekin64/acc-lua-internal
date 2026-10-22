"""Persistance SQLite : réglages, annonce, groupes approuvés et historique.

Aucune donnée sur les membres des groupes n'est stockée : uniquement
l'identifiant et le titre des groupes, et le résultat de chaque envoi.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .ad import Ad
from .config import secure_file
from .publisher import Outcome, Report, utcnow

HISTORY_LIMIT = 200  # nombre de publications conservées

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS groups (
    chat_id        INTEGER PRIMARY KEY,
    title          TEXT    NOT NULL,
    in_folder      INTEGER NOT NULL DEFAULT 0,
    blocked_reason TEXT,
    approved       INTEGER NOT NULL DEFAULT 0,
    updated_at     TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS publications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_title TEXT    NOT NULL,
    dry_run      INTEGER NOT NULL,
    started_at   TEXT    NOT NULL,
    finished_at  TEXT    NOT NULL,
    sent         INTEGER NOT NULL,
    failed       INTEGER NOT NULL,
    skipped      INTEGER NOT NULL,
    stop_reason  TEXT
);
CREATE TABLE IF NOT EXISTS results (
    publication_id INTEGER NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
    chat_id        INTEGER NOT NULL,
    group_title    TEXT    NOT NULL,
    status         TEXT    NOT NULL,
    reason         TEXT,
    at             TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_results_chat ON results(chat_id, status);
"""


def _to_text(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _from_text(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass(frozen=True)
class Folder:
    id: int
    title: str


@dataclass(frozen=True)
class GroupRow:
    chat_id: int
    title: str
    blocked_reason: str | None
    approved: bool


@dataclass(frozen=True)
class PublicationRow:
    id: int
    folder_title: str
    dry_run: bool
    started_at: datetime
    finished_at: datetime
    sent: int
    failed: int
    skipped: int
    stop_reason: str | None


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(_SCHEMA)
        self.conn.commit()
        if str(path) != ":memory:":
            secure_file(self.path)

    def close(self) -> None:
        self.conn.close()

    # --- Réglages -----------------------------------------------------------

    def get_setting(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str | None) -> None:
        with self.conn:
            if value is None:
                self.conn.execute("DELETE FROM settings WHERE key = ?", (key,))
            else:
                self.conn.execute(
                    "INSERT INTO settings(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, value),
                )

    def get_folder(self) -> Folder | None:
        raw = self.get_setting("folder")
        if not raw:
            return None
        data = json.loads(raw)
        return Folder(id=int(data["id"]), title=str(data["title"]))

    def set_folder(self, folder_id: int, title: str) -> None:
        self.set_setting("folder", json.dumps({"id": folder_id, "title": title}))

    def get_ad(self) -> Ad:
        """Annonce enregistrée, ou le modèle par défaut au premier lancement."""
        raw = self.get_setting("ad")
        if not raw:
            return Ad()
        data = json.loads(raw)
        return Ad(text_html=data.get("text_html") or "", photo_path=data.get("photo_path"))

    def save_ad(self, ad: Ad) -> None:
        self.set_setting("ad", json.dumps(asdict(ad), ensure_ascii=False))

    def get_contact(self) -> str | None:
        return self.get_setting("contact")

    def set_contact(self, username: str | None) -> None:
        self.set_setting("contact", username)

    # --- Groupes ------------------------------------------------------------

    def sync_folder_groups(self, groups: Iterable[tuple[int, str, str | None]]) -> None:
        """Remplace la liste des groupes du dossier courant.

        ``groups`` : (chat_id, titre, raison de blocage ou None).
        Les approbations déjà données sont conservées.
        """
        now = _to_text(utcnow())
        with self.conn:
            self.conn.execute("UPDATE groups SET in_folder = 0")
            self.conn.executemany(
                "INSERT INTO groups(chat_id, title, in_folder, blocked_reason, approved, updated_at) "
                "VALUES(?, ?, 1, ?, 0, ?) "
                "ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title, in_folder = 1, "
                "blocked_reason = excluded.blocked_reason, updated_at = excluded.updated_at",
                [(chat_id, title, reason, now) for chat_id, title, reason in groups],
            )

    def folder_groups(self) -> list[GroupRow]:
        rows = self.conn.execute(
            "SELECT chat_id, title, blocked_reason, approved FROM groups "
            "WHERE in_folder = 1 ORDER BY title COLLATE NOCASE, chat_id"
        ).fetchall()
        return [GroupRow(r["chat_id"], r["title"], r["blocked_reason"], bool(r["approved"])) for r in rows]

    def get_group(self, chat_id: int) -> GroupRow | None:
        r = self.conn.execute(
            "SELECT chat_id, title, blocked_reason, approved FROM groups WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return GroupRow(r["chat_id"], r["title"], r["blocked_reason"], bool(r["approved"])) if r else None

    def set_approved(self, chat_id: int, approved: bool) -> None:
        with self.conn:
            self.conn.execute("UPDATE groups SET approved = ? WHERE chat_id = ?", (int(approved), chat_id))

    def set_all_approved(self, approved: bool) -> None:
        """Coche tous les groupes du dossier où la publication est possible, ou les décoche tous."""
        query = "UPDATE groups SET approved = ? WHERE in_folder = 1"
        if approved:
            query += " AND blocked_reason IS NULL"
        with self.conn:
            self.conn.execute(query, (int(approved),))

    def approved_ids(self) -> set[int]:
        rows = self.conn.execute("SELECT chat_id FROM groups WHERE approved = 1").fetchall()
        return {r["chat_id"] for r in rows}

    # --- Historique ---------------------------------------------------------

    def save_report(self, report: Report) -> int:
        finished = report.finished_at or utcnow()
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO publications(folder_title, dry_run, started_at, finished_at, "
                "sent, failed, skipped, stop_reason) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    report.folder_title,
                    int(report.dry_run),
                    _to_text(report.started_at),
                    _to_text(finished),
                    len(report.sent),
                    len(report.failed),
                    len(report.skipped),
                    report.stop_reason,
                ),
            )
            pub_id = int(cur.lastrowid)
            self.conn.executemany(
                "INSERT INTO results(publication_id, chat_id, group_title, status, reason, at) "
                "VALUES(?, ?, ?, ?, ?, ?)",
                [(pub_id, o.chat_id, o.title, o.status, o.reason, _to_text(o.at)) for o in report.outcomes],
            )
            self.conn.execute(
                "DELETE FROM publications WHERE id NOT IN "
                "(SELECT id FROM publications ORDER BY id DESC LIMIT ?)",
                (HISTORY_LIMIT,),
            )
        return pub_id

    def publications(self, limit: int = 10) -> list[PublicationRow]:
        rows = self.conn.execute("SELECT * FROM publications ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [
            PublicationRow(
                id=r["id"],
                folder_title=r["folder_title"],
                dry_run=bool(r["dry_run"]),
                started_at=_from_text(r["started_at"]),
                finished_at=_from_text(r["finished_at"]),
                sent=r["sent"],
                failed=r["failed"],
                skipped=r["skipped"],
                stop_reason=r["stop_reason"],
            )
            for r in rows
        ]

    def load_report(self, publication_id: int) -> Report | None:
        pub = self.conn.execute("SELECT * FROM publications WHERE id = ?", (publication_id,)).fetchone()
        if pub is None:
            return None
        rows = self.conn.execute(
            "SELECT * FROM results WHERE publication_id = ? ORDER BY rowid", (publication_id,)
        ).fetchall()
        return Report(
            folder_title=pub["folder_title"],
            dry_run=bool(pub["dry_run"]),
            started_at=_from_text(pub["started_at"]),
            finished_at=_from_text(pub["finished_at"]),
            stop_reason=pub["stop_reason"],
            outcomes=[
                Outcome(r["chat_id"], r["group_title"], r["status"], r["reason"], _from_text(r["at"]))
                for r in rows
            ],
        )

    def last_sent_times(self) -> dict[int, datetime]:
        """Date du dernier envoi réel réussi, par groupe (pour le délai entre deux annonces)."""
        rows = self.conn.execute(
            "SELECT r.chat_id, MAX(r.at) AS at FROM results r "
            "JOIN publications p ON p.id = r.publication_id "
            "WHERE p.dry_run = 0 AND r.status = 'sent' GROUP BY r.chat_id"
        ).fetchall()
        return {r["chat_id"]: _from_text(r["at"]) for r in rows}
