from aiogram.types import InlineKeyboardMarkup

from conftest import group
from vabot import keyboards as kb
from vabot import texts
from vabot.ad import Ad
from vabot.publisher import FAILED, SENT, SKIPPED, Outcome, Plan, Report
from vabot.storage import GroupRow


def test_main_menu():
    text = texts.main_menu("@moncompte", "VA OFM", 18, test_mode=False)
    assert "VA Recruitment Manager" in text and "Compte : <b>@moncompte</b>" in text
    assert "non connecté" in texts.main_menu(None, None, 0, test_mode=False)
    assert "Mode test actif" in texts.main_menu("@x", None, 0, test_mode=True)


def test_report_matches_expected_layout():
    report = Report(
        folder_title="VA OFM",
        dry_run=False,
        outcomes=[Outcome(-i, f"G{i}", SENT) for i in range(18)]
        + [
            Outcome(-100, "Fermé", FAILED, "écriture interdite dans ce groupe"),
            Outcome(-101, "Lent", FAILED, "mode lent"),
        ]
        + [Outcome(-200 - i, f"S{i}", SKIPPED, "non approuvé") for i in range(5)],
    )
    text = texts.report(report)
    assert "📊 <b>Publication terminée</b>" in text
    assert "📁 Dossier : VA OFM" in text
    assert "✅ Messages envoyés : 18" in text
    assert "❌ Échecs : 2" in text
    assert "⏭️ Groupes ignorés : 5" in text
    assert "• Fermé — écriture interdite dans ce groupe" in text


def test_dry_run_report_says_nothing_was_published():
    report = Report(folder_title="VA OFM", dry_run=True, outcomes=[Outcome(-1, "A", SENT)], saved_copy=True)
    text = texts.report(report)
    assert "rien n'a été publié" in text and "Messages enregistrés" in text


def test_titles_are_escaped():
    report = Report(folder_title="<VA>", dry_run=False, outcomes=[Outcome(-1, "<b>pirate</b>", SENT)])
    text = texts.report(report)
    assert "<b>pirate</b>" not in text and "&lt;b&gt;pirate" in text


def test_publish_summary_truncates_long_lists():
    plan = Plan("VA OFM", targets=[group(-i, f"Groupe {i}") for i in range(1, 60)])
    text = texts.publish_summary(plan, Ad(), delay=10, test_mode=False)
    assert "59 groupe(s) recevront" in text
    assert "… et 34 autre(s)" in text
    assert len(text) < 4096
    empty = texts.publish_summary(Plan("VA OFM"), Ad(), delay=10, test_mode=False)
    assert "Aucun groupe" in empty


def test_split_text_respects_limit_and_lines():
    text = "\n".join(f"ligne {i}" for i in range(1000))
    parts = texts.split_text(text, limit=500)
    assert all(len(p) <= 500 for p in parts)
    assert "\n".join(parts) == text
    assert texts.split_text("court") == ["court"]


def _all_callbacks(markup: InlineKeyboardMarkup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def test_callback_data_fits_telegram_limit():
    rows = [
        GroupRow(-1009999999999 - i, "Un titre de groupe vraiment très très long " * 3, None, bool(i % 2))
        for i in range(30)
    ]
    markups = [kb.main_menu(), kb.groups(rows, 2), kb.ad_menu(True, True), kb.publish_confirm(True, False)]
    for markup in markups:
        for data in _all_callbacks(markup):
            assert 0 < len(data.encode()) <= 64


def test_group_keyboard_icons_and_pages():
    rows = [
        GroupRow(-1, "A", None, True),
        GroupRow(-2, "B", None, False),
        GroupRow(-3, "C", "lecture seule", False),
    ]
    labels = [b.text for row in kb.groups(rows, 0).inline_keyboard for b in row]
    assert "✅ A" in labels and "⬜ B" in labels and "🔒 C" in labels
    many = [GroupRow(-i, f"G{i}", None, False) for i in range(1, 20)]
    assert "2/3" in [b.text for row in kb.groups(many, 1).inline_keyboard for b in row]
