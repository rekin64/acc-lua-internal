import pytest

from vabot import ad as ad_module
from vabot.ad import Ad


def test_default_template_uses_contact_placeholder():
    rendered = ad_module.render(Ad(), "moncompte")
    assert "📩 DM @moncompte to apply" in rendered.text_html
    assert "{contact}" not in rendered.text_html
    assert "WE'RE HIRING" in rendered.text_html


def test_contact_is_html_escaped():
    rendered = ad_module.render(Ad(text_html="DM {contact}"), "a<b")
    assert rendered.text_html == "DM @a&lt;b"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("@MonCompte", "MonCompte"),
        ("moncompte", "moncompte"),
        ("https://t.me/mon_compte", "mon_compte"),
        (" @abcde ", "abcde"),
        ("@abc", None),  # trop court
        ("@1abcde", None),  # doit commencer par une lettre
        ("deux mots", None),
        ("", None),
    ],
)
def test_normalize_username(raw, expected):
    assert ad_module.normalize_username(raw) == expected


def test_validate_ok():
    assert ad_module.validate(Ad(), "moncompte") == []


def test_validate_empty_and_missing_contact():
    assert "L'annonce est vide." in ad_module.validate(Ad(text_html="<b> </b>"), "moncompte")
    assert any("{contact}" in e for e in ad_module.validate(Ad(), None))


def test_validate_text_and_caption_limits():
    long_text = "x" * 2000
    assert ad_module.validate(Ad(text_html=long_text), "c") == []
    errors = ad_module.validate(Ad(text_html=long_text, photo_path="/tmp/p.jpg"), "c")
    assert any("1024" in e for e in errors)
    assert any("4096" in e for e in ad_module.validate(Ad(text_html="x" * 5000), "c"))


def test_length_counts_like_telegram():
    # Les balises ne comptent pas, un emoji compte pour 2 unités UTF-16.
    assert ad_module.telegram_length("<b>abc</b>") == 3
    assert ad_module.telegram_length("🚀") == 2


def test_contact_warning_and_add_line():
    ad = Ad(text_html="We are hiring")
    assert ad_module.warnings(ad, "moncompte")
    fixed = ad_module.add_contact_line(ad)
    assert fixed.text_html.endswith("📩 DM {contact} to apply")
    assert ad_module.warnings(fixed, "moncompte") == []
    assert ad_module.warnings(Ad(text_html="Contact @MonCompte"), "moncompte") == []
