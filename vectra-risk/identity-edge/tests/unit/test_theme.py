"""Tema `vectra` (U02-T06, Paso 4): P-U2-08. Cada regla tiene su caso que falla sobre una copia del tema."""

import re
import shutil
from pathlib import Path

import pytest
import theme_checks as tc

TEMPLATES = tc.design_templates()


@pytest.fixture
def theme(tmp_path: Path) -> Path:
    copy = tmp_path / "login"
    shutil.copytree(tc.THEME_DIR, copy)
    return copy


@pytest.fixture
def reference(tmp_path: Path) -> Path:
    copy = tmp_path / "ref"
    shutil.copytree(tc.REFERENCE_DIR, copy)
    return copy


def _append(path: Path, text: str) -> None:
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


# --- estructura -------------------------------------------------------------------------------

def test_theme_structure_is_standard():
    props = tc.parse_properties((tc.THEME_DIR / "theme.properties").read_text(encoding="utf-8"))
    assert props["parent"] == "keycloak.v2"
    assert (tc.THEME_DIR / "messages" / "messages_es.properties").is_file()
    assert (tc.THEME_DIR / "resources" / "img" / tc.design_logo_name()).is_file()


# --- sin recursos externos ni JavaScript ------------------------------------------------------

def test_theme_has_no_external_urls():
    assert tc.external_references(tc.THEME_DIR) == []


def test_theme_has_no_script():
    assert tc.script_tags(tc.THEME_DIR) == []


def test_theme_files_are_only_text_without_javascript():
    assert [p.name for p in tc.theme_files(tc.THEME_DIR) if p.suffix in {".js", ".mjs", ".ftl", ".html"}] == []


def test_xmlns_namespace_is_not_an_external_reference(theme):
    logo = theme / "resources" / "img" / "vectra-logo.svg"
    assert 'xmlns="http://www.w3.org/2000/svg"' in logo.read_text(encoding="utf-8")
    assert tc.external_references(theme) == []


def test_url_in_css_is_detected(theme):
    _append(theme / "resources" / "css" / "vectra.css", '\n@import url("https://fonts.example.com/x.css");\n')
    assert any("vectra.css" in r for r in tc.external_references(theme))


def test_url_in_svg_is_detected(theme):
    logo = theme / "resources" / "img" / "vectra-logo.svg"
    logo.write_text(logo.read_text(encoding="utf-8").replace("</svg>", '<a href="https://example.com/"/></svg>'), encoding="utf-8")
    assert any("vectra-logo.svg" in r for r in tc.external_references(theme))


def test_xmlns_does_not_hide_another_url_in_the_same_file(theme):
    logo = theme / "resources" / "img" / "vectra-logo.svg"
    logo.write_text(logo.read_text(encoding="utf-8").replace("</svg>", "<!-- http://www.w3.org/2000/svg --></svg>"), encoding="utf-8")
    assert tc.external_references(theme) == []  # misma URL del espacio de nombres: no es otro origen
    logo.write_text(logo.read_text(encoding="utf-8").replace("</svg>", "<!-- http://evil.example/ --></svg>"), encoding="utf-8")
    assert tc.external_references(theme) != []


def test_script_in_svg_is_detected(theme):
    logo = theme / "resources" / "img" / "vectra-logo.svg"
    logo.write_text(logo.read_text(encoding="utf-8").replace("</svg>", "<script>alert(1)</script></svg>"), encoding="utf-8")
    assert tc.script_tags(theme) == ["resources/img/vectra-logo.svg"]


def test_logo_has_no_image_element():
    text = (tc.THEME_DIR / "resources" / "img" / tc.design_logo_name()).read_text(encoding="utf-8")
    assert not re.search(r"<\s*image\b", text, re.IGNORECASE)
    assert "Vectra" in text


# --- mensajes ---------------------------------------------------------------------------------

def test_messages_es_keys_exist_and_required_ones_are_translated():
    assert tc.message_problems(tc.THEME_DIR, tc.REFERENCE_DIR, TEMPLATES) == []


def test_messages_es_translates_totp_keys():
    es = tc.parse_properties((tc.THEME_DIR / "messages" / "messages_es.properties").read_text(encoding="utf-8"))
    totp = {k for k in tc.required_keys(tc.REFERENCE_DIR, TEMPLATES) if k.startswith("loginTotp")}
    assert totp and totp <= es.keys()


def test_invented_key_in_messages_es_is_detected(theme):
    _append(theme / "messages" / "messages_es.properties", "claveInventadaVectra=hola\n")
    assert tc.message_problems(theme, tc.REFERENCE_DIR, TEMPLATES) == ["clave inexistente en la referencia: claveInventadaVectra"]


def test_untranslated_totp_key_is_detected(theme):
    path = theme / "messages" / "messages_es.properties"
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.startswith("loginTotpStep3=")]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert tc.message_problems(theme, tc.REFERENCE_DIR, TEMPLATES) == ["sin traducir: loginTotpStep3"]


def test_empty_translation_counts_as_untranslated(theme):
    _append(theme / "messages" / "messages_es.properties", "doLogIn=\n")
    assert "sin traducir: doLogIn" in tc.message_problems(theme, tc.REFERENCE_DIR, TEMPLATES)


# --- referencia -------------------------------------------------------------------------------

def test_reference_checksums_match():
    assert tc.checksum_mismatches(tc.REFERENCE_DIR) == []


def test_reference_altered_fixture_is_detected(reference):
    _append(reference / "keycloak.v2" / "templates" / "login.ftl", "\n")
    assert tc.checksum_mismatches(reference) == ["./keycloak.v2/templates/login.ftl"]


def test_reference_missing_fixture_is_detected(reference):
    (reference / "base" / "messages_en.properties").unlink()
    assert tc.checksum_mismatches(reference) == ["./base/messages_en.properties"]


def test_reference_required_keys_come_from_the_templates():
    keys = tc.required_keys(tc.REFERENCE_DIR, TEMPLATES)
    assert {"doLogIn", "loginTotpTitle", "updatePasswordTitle", "loginOtpOneTime", "showPassword"} - keys == {"showPassword"}
    assert "languages" not in keys  # esta clave literal no existe en la referencia


def test_reference_templates_come_from_the_design():
    assert set(TEMPLATES) == {
        "login.ftl", "login-otp.ftl", "login-config-totp.ftl", "login-update-password.ftl",
        "template.ftl", "buttons.ftl", "field.ftl", "password-commons.ftl",
    }
    for name in TEMPLATES:
        assert (tc.REFERENCE_DIR / "keycloak.v2" / "templates" / name).is_file()


def test_reference_new_template_key_becomes_required(reference):
    _append(reference / "keycloak.v2" / "templates" / "login.ftl", '\n${msg("doSubmit")}\n')
    assert "doSubmit" in tc.required_keys(reference, TEMPLATES)


# --- marca ------------------------------------------------------------------------------------

def test_brand_theme_declares_parent_and_own_css():
    props = tc.parse_properties((tc.THEME_DIR / "theme.properties").read_text(encoding="utf-8"))
    assert props["parent"] == "keycloak.v2"
    assert "css/vectra.css" in props["styles"].split()
    assert (tc.THEME_DIR / "resources" / "css" / "vectra.css").is_file()


def test_brand_css_uses_exactly_the_design_colors():
    brand = tc.design_brand()
    hexes, others = tc.css_colors((tc.THEME_DIR / "resources" / "css" / "vectra.css").read_text(encoding="utf-8"))
    assert hexes == set(brand.values()) == {"#0B3D5C", "#C2410C", "#FFFFFF"}
    assert others == []


def test_brand_logo_uses_only_design_colors():
    brand = set(tc.design_brand().values())
    text = (tc.THEME_DIR / "resources" / "img" / tc.design_logo_name()).read_text(encoding="utf-8")
    assert {h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}\b", text)} <= brand


@pytest.mark.parametrize("role", ["primary", "accent"])
def test_brand_contrast_over_background_is_at_least_4_5(role):
    brand = tc.design_brand()
    ratio = tc.contrast(brand[role], brand["background"])
    assert ratio >= 4.5
    assert round(ratio, 2) == tc.design_contrast_ratios()[role]  # el diseno declara el mismo numero


def test_brand_low_contrast_color_is_detected():
    assert tc.contrast("#FFFF00", "#FFFFFF") < 4.5


@pytest.mark.parametrize("extra", ["color: #123456;", "color: rgb(1, 2, 3);", "color: red;", "background: hsl(10 20% 30%);"])
def test_brand_other_colors_are_detected(theme, extra):
    css = theme / "resources" / "css" / "vectra.css"
    _append(css, f"\n.x {{ {extra} }}\n")
    hexes, others = tc.css_colors(css.read_text(encoding="utf-8"))
    assert hexes != set(tc.design_brand().values()) or others != []
