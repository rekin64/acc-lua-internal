from datetime import timedelta

from vabot.ad import DEFAULT_TEMPLATE, Ad
from vabot.publisher import FAILED, SENT, SKIPPED, Outcome, Report, utcnow
from vabot.storage import Database


def test_settings_folder_and_contact(db):
    assert db.get_folder() is None
    db.set_folder(7, "VA OFM")
    assert db.get_folder().title == "VA OFM"
    db.set_contact("moncompte")
    assert db.get_contact() == "moncompte"
    db.set_contact(None)
    assert db.get_contact() is None


def test_ad_defaults_to_template_and_is_saved(db):
    assert db.get_ad().text_html == DEFAULT_TEMPLATE
    db.save_ad(Ad(text_html="<b>Hello</b> 🚀", photo_path="/data/p.jpg"))
    assert db.get_ad() == Ad(text_html="<b>Hello</b> 🚀", photo_path="/data/p.jpg")


def test_group_selection_is_kept_across_refreshes(db):
    db.sync_folder_groups([(-1001, "A", None), (-1002, "B", None), (-1003, "C", "lecture seule")])
    assert [g.title for g in db.folder_groups()] == ["A", "B", "C"]
    assert db.approved_ids() == set()  # rien n'est approuvé par défaut

    db.set_approved(-1001, True)
    # Nouvelle lecture du dossier : B a quitté le dossier, D est apparu, A renommé.
    db.sync_folder_groups([(-1001, "A renommé", None), (-1004, "D", None)])
    rows = {g.chat_id: g for g in db.folder_groups()}
    assert set(rows) == {-1001, -1004}
    assert rows[-1001].approved and rows[-1001].title == "A renommé"
    assert not rows[-1004].approved


def test_select_all_skips_blocked_groups(db):
    db.sync_folder_groups([(-1001, "A", None), (-1002, "B", "lecture seule")])
    db.set_all_approved(True)
    assert db.approved_ids() == {-1001}
    db.set_all_approved(False)
    assert db.approved_ids() == set()


def test_report_history_and_cooldown(db):
    now = utcnow()
    real = Report(
        folder_title="VA OFM",
        dry_run=False,
        started_at=now,
        finished_at=now,
        outcomes=[
            Outcome(-1001, "A", SENT, at=now - timedelta(hours=2)),
            Outcome(-1002, "B", FAILED, "écriture interdite"),
            Outcome(-1003, "C", SKIPPED, "non approuvé"),
        ],
    )
    test = Report(folder_title="VA OFM", dry_run=True, outcomes=[Outcome(-1004, "D", SENT)])
    real_id = db.save_report(real)
    db.save_report(test)

    history = db.publications()
    assert [p.dry_run for p in history] == [True, False]
    assert (history[1].sent, history[1].failed, history[1].skipped) == (1, 1, 1)

    loaded = db.load_report(real_id)
    assert [o.title for o in loaded.failed] == ["B"]
    assert loaded.failed[0].reason == "écriture interdite"

    # Seuls les envois réels comptent pour le délai entre deux annonces.
    assert set(db.last_sent_times()) == {-1001}


def test_database_file_is_private(tmp_path):
    path = tmp_path / "private.sqlite3"
    Database(path).close()
    assert oct(path.stat().st_mode & 0o777) == "0o600"
