"""Tema `vectra` (U02-T06, Paso 4): P-U2-08. Cada regla tiene su caso que falla sobre una copia del tema."""

import re
import shutil
from pathlib import Path

import pytest
import theme_checks as tc

TEMPLATES = tc.design_templates()
BRAND = tc.design_brand()
ALLOWED = set(BRAND.values())
LOGO = "resources/img/vectra-logo.svg"
CSS = "resources/css/vectra.css"
ES = "messages/messages_es.properties"


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


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} no esta en {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# --- estructura -------------------------------------------------------------------------------

def test_theme_exists_and_structure_is_standard():
    assert tc.THEME_DIR.is_dir() and tc.theme_files(tc.THEME_DIR)
    props = tc.parse_properties((tc.THEME_DIR / "theme.properties").read_text(encoding="utf-8"))
    assert props["parent"] == "keycloak.v2"
    assert (tc.THEME_DIR / ES).is_file()
    assert (tc.THEME_DIR / "resources" / "img" / tc.design_logo_name()).is_file()


def test_theme_missing_directory_fails_the_checks(tmp_path):
    missing = tmp_path / "no-existe"
    assert tc.theme_files(missing) == []  # las pruebas de abajo exigen que no este vacio


# --- sin recursos externos ni JavaScript ------------------------------------------------------

def test_theme_has_no_external_urls():
    assert tc.theme_files(tc.THEME_DIR)
    assert tc.external_references(tc.THEME_DIR) == []


def test_theme_has_no_script():
    assert tc.theme_files(tc.THEME_DIR)
    assert tc.script_problems(tc.THEME_DIR) == []


def test_theme_files_are_only_text_without_javascript():
    files = tc.theme_files(tc.THEME_DIR)
    assert files
    assert [p.name for p in files if p.suffix in {".js", ".mjs", ".ftl", ".html"}] == []


def test_xmlns_namespace_is_not_an_external_reference(theme):
    assert 'xmlns="http://www.w3.org/2000/svg"' in (theme / LOGO).read_text(encoding="utf-8")
    assert tc.external_references(theme) == []


def test_xmlns_with_prefix_is_a_namespace_only_in_its_position(theme):
    _replace(theme / LOGO, "</svg>", '<g xmlns:x="http://www.w3.org/1999/xlink"/></svg>')
    assert tc.external_references(theme) == []


URL_MUTATIONS = {
    "T01 import sin esquema": (CSS, '\n@import url("//cdn.example.com/x.css");\n'),
    "T02 url() sin esquema": (CSS, "\n.x { background: url(//cdn.example.com/a.png); }\n"),
    "T07 url() sin comillas": (CSS, "\n.x { background: url(https://cdn.example.com/a.png); }\n"),
    "CSS https": (CSS, '\n@import url("https://fonts.example.com/x.css");\n'),
    "T03 xmlns:e de otra URL y href igual": (
        LOGO, '<use xmlns:e="https://evil.example/x.svg" href="https://evil.example/x.svg"/></svg>'),
    "T05 xmlns en comentario CSS": (CSS, '\n/* xmlns="https://evil.example/f.css" */\n@import url("https://evil.example/f.css");\n'),
    "T06 atributo que termina en xmlns": (LOGO, '<g data-notxmlns="https://evil.example/"/></svg>'),
    "X04b URL del espacio de nombres usada como href": (LOGO, '<use xlink:href="http://www.w3.org/2000/svg"/></svg>'),
    "SVG href": (LOGO, '<a href="https://example.com/"/></svg>'),
    "href sin esquema": (LOGO, '<use href="//evil.example/x.svg#a"/></svg>'),
    "otro esquema": (CSS, '\n@import url("ftp://evil.example/x.css");\n'),
    "comentario SVG con URL": (LOGO, "<!-- http://evil.example/ --></svg>"),
}


@pytest.mark.parametrize("name", URL_MUTATIONS)
def test_external_url_mutations_are_detected(theme, name):
    rel, snippet = URL_MUTATIONS[name]
    path = theme / rel
    if rel == LOGO:
        _replace(path, "</svg>", snippet)
    else:
        _append(path, snippet)
    assert tc.external_references(theme), name


SCRIPT_MUTATIONS = {
    "<script>": "<script>alert(1)</script></svg>",
    "T09 script con prefijo": '<s:script xmlns:s="http://www.w3.org/2000/svg">alert(1)</s:script></svg>',
    "T08 onload": '<g onload="alert(1)"/></svg>',
    "onclick con comillas simples": "<g onclick='alert(1)'/></svg>",
    "T10 javascript:": '<a href="javascript:alert(1)"/></svg>',
    "javascript: con espacios": '<a href="java script:alert(1)"/></svg>',
}


@pytest.mark.parametrize("name", SCRIPT_MUTATIONS)
def test_script_mutations_are_detected(theme, name):
    _replace(theme / LOGO, "</svg>", SCRIPT_MUTATIONS[name])
    assert tc.script_problems(theme), name


def test_scripts_property_is_detected(theme):
    """T11."""
    _append(theme / "theme.properties", "scripts=js/v.txt\n")
    (theme / "resources" / "js").mkdir()
    (theme / "resources" / "js" / "v.txt").write_text("alert(1)\n", encoding="utf-8")
    assert tc.script_problems(theme) == ["theme.properties: propiedad scripts"]


def test_logo_has_no_image_element():
    text = (tc.THEME_DIR / "resources" / "img" / tc.design_logo_name()).read_text(encoding="utf-8")
    assert not re.search(r"<\s*image\b", text, re.IGNORECASE)
    assert "Vectra" in text


# --- mensajes ---------------------------------------------------------------------------------

def test_messages_es_keys_exist_and_required_ones_are_translated():
    assert tc.message_problems(tc.THEME_DIR, tc.REFERENCE_DIR, TEMPLATES) == []


def test_messages_es_translates_totp_keys():
    es = tc.parse_properties((tc.THEME_DIR / ES).read_text(encoding="utf-8"))
    totp = {k for k in tc.required_keys(tc.REFERENCE_DIR, TEMPLATES) if k.startswith("loginTotp")}
    assert totp and totp <= es.keys()


def test_messages_es_has_only_keys_used_by_the_listed_templates():
    es = tc.parse_properties((tc.THEME_DIR / ES).read_text(encoding="utf-8"))
    used = set()
    for name in TEMPLATES:
        text = (tc.REFERENCE_DIR / "keycloak.v2" / "templates" / name).read_text(encoding="utf-8")
        used |= set(re.findall(r"""(?:msg\(|label=|")["']?([\w.-]+)""", text))
    assert "doClickHere" not in es
    assert not (es.keys() - used - {"loginTotp.totp", "loginTotp.hotp"})


@pytest.mark.parametrize("line", [
    "claveInventadaVectra=hola", "claveInventadaVectra: hola", "claveInventadaVectra hola",
    "  claveInventadaVectra   =   hola", "claveInventadaVectra",
])
def test_invented_key_in_any_properties_syntax_is_detected(theme, line):
    """T12 y T13."""
    _append(theme / ES, "\n" + line + "\n")
    assert tc.message_problems(theme, tc.REFERENCE_DIR, TEMPLATES) == ["clave inexistente en la referencia: claveInventadaVectra"]


def test_untranslated_totp_key_is_detected(theme):
    lines = [ln for ln in (theme / ES).read_text(encoding="utf-8").splitlines() if not ln.startswith("loginTotpStep3=")]
    (theme / ES).write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert tc.message_problems(theme, tc.REFERENCE_DIR, TEMPLATES) == ["sin traducir: loginTotpStep3"]


@pytest.mark.parametrize("line", ["doLogIn=", "doLogIn ", "doLogIn:", "doLogIn =   ", "doLogIn=\\\n"])
def test_empty_translation_counts_as_untranslated(theme, line):
    """X05."""
    path = theme / ES
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.startswith("doLogIn=")]
    path.write_text("\n".join(lines) + "\n" + line + "\n", encoding="utf-8")
    assert "sin traducir: doLogIn" in tc.message_problems(theme, tc.REFERENCE_DIR, TEMPLATES)


def test_properties_parser_follows_java_syntax():
    parsed = tc.parse_properties("# c\n! c\na=1\nb:2\nc 3\n  d =  4\ne\nf=x\\\n   y\ng=\\u00e1\nh\\=i=5\n")
    assert parsed == {"a": "1", "b": "2", "c": "3", "d": "4", "e": "", "f": "xy", "g": "á", "h=i": "5"}


# --- referencia -------------------------------------------------------------------------------

def test_reference_directory_follows_the_design_version():
    assert tc.reference_dir().name == f"keycloak-{tc.design_version()}"
    assert tc.reference_dir().is_dir()


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
    assert {"doLogIn", "loginTotpTitle", "updatePasswordTitle", "loginOtpOneTime"} <= keys
    assert "languages" not in keys  # esta clave literal no existe en la referencia


def test_reference_templates_come_from_the_design():
    assert TEMPLATES
    for name in TEMPLATES:
        assert (tc.REFERENCE_DIR / "keycloak.v2" / "templates" / name).is_file()


def test_reference_new_template_key_becomes_required(reference):
    _append(reference / "keycloak.v2" / "templates" / "login.ftl", '\n${msg("doSubmit")}\n')
    assert "doSubmit" in tc.required_keys(reference, TEMPLATES)


# --- marca ------------------------------------------------------------------------------------

def test_brand_theme_declares_parent_and_own_css():
    props = tc.parse_properties((tc.THEME_DIR / "theme.properties").read_text(encoding="utf-8"))
    assert props["parent"] == "keycloak.v2"
    assert (tc.THEME_DIR / CSS).is_file()


def test_brand_styles_keep_the_parent_stylesheet():
    """T17: un `styles` en el hijo reemplaza al del padre; `css/styles.css` se resuelve por la cadena hacia keycloak.v2."""
    styles = tc.parse_properties((tc.THEME_DIR / "theme.properties").read_text(encoding="utf-8"))["styles"].split()
    assert styles == ["css/styles.css", "css/vectra.css"]
    assert not (tc.THEME_DIR / "resources" / "css" / "styles.css").exists()  # no tapa al del padre


def test_brand_styles_without_parent_stylesheet_are_detected(theme):
    _replace(theme / "theme.properties", "css/styles.css css/vectra.css", "css/vectra.css")
    styles = tc.parse_properties((theme / "theme.properties").read_text(encoding="utf-8"))["styles"].split()
    assert styles != ["css/styles.css", "css/vectra.css"]


def test_brand_colors_come_from_the_design():
    assert ALLOWED == set(BRAND.values()) and len(ALLOWED) == 3


def test_brand_css_uses_exactly_the_design_colors():
    css = (tc.THEME_DIR / CSS).read_text(encoding="utf-8")
    assert tc.css_hex_colors(css) == ALLOWED
    assert tc.theme_color_problems(tc.THEME_DIR, ALLOWED) == []


@pytest.mark.parametrize("role", ["primary", "accent"])
def test_brand_contrast_over_background_is_at_least_4_5(role):
    ratio = tc.contrast(BRAND[role], BRAND["background"])
    assert ratio >= 4.5
    assert round(ratio, 2) == tc.design_contrast_ratios()[role]  # el diseno declara el mismo numero


def test_brand_low_contrast_color_is_detected():
    assert tc.contrast("#FFFF00", "#FFFFFF") < 4.5


CSS_COLOR_MUTATIONS = [
    "color: #123456;", "color: #fff;", "color: #0B3D5C80;", "color: rgb(1, 2, 3);", "color: red;",
    "color: darkred;", "color: rebeccapurple;", "color: var(--pf-v5-global--danger-color--100);",
    "background: hsl(10 20% 30%);", "border: 1px solid transparent;", "color: currentColor;",
    "--x: color-mix(in srgb, #0B3D5C, #C2410C);", "color: light-dark(#0B3D5C, #FFFFFF);",
]


@pytest.mark.parametrize("decl", CSS_COLOR_MUTATIONS)
def test_brand_css_other_colors_are_detected(theme, decl):
    """T14, T15, T16."""
    _append(theme / CSS, f"\n.x {{ {decl} }}\n")
    assert tc.theme_color_problems(theme, ALLOWED), decl


SVG_COLOR_MUTATIONS = [
    ('fill="#0B3D5C"', 'fill="red"'),            # T20
    ('fill="#0B3D5C"', 'fill="darkred"'),
    ('fill="#0B3D5C"', 'fill="#abc"'),
    ('fill="#0B3D5C"', 'fill="rgb(1,2,3)"'),
    ('fill="#0B3D5C"', 'fill="var(--x)"'),
    ('fill="#0B3D5C"', 'style="fill:blue"'),
    ('stroke="#C2410C"', 'stroke="#C2410D"'),
    ("</svg>", "<style>text{fill:green}</style></svg>"),
]


@pytest.mark.parametrize(("old", "new"), SVG_COLOR_MUTATIONS)
def test_brand_logo_other_colors_are_detected(theme, old, new):
    _replace(theme / LOGO, old, new)
    assert tc.theme_color_problems(theme, ALLOWED)
