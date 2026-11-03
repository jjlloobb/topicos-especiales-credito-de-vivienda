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
    assert tc.theme_files(tc.THEME_DIR)
    assert tc.structure_problems(tc.THEME_DIR) == []


def test_theme_missing_directory_fails_the_structure_rule(tmp_path):
    assert len(tc.structure_problems(tmp_path / "no-existe")) == 4


def test_theme_without_its_files_fails_the_structure_rule(theme):
    (theme / LOGO).unlink()
    (theme / CSS).unlink()
    assert tc.structure_problems(theme) == [f"falta {CSS}", f"falta {LOGO}"]


def test_styles_without_the_parent_stylesheet_fail_the_structure_rule(theme):
    """T17."""
    _replace(theme / "theme.properties", "css/styles.css css/vectra.css", "css/vectra.css")
    assert tc.structure_problems(theme)


def test_own_styles_css_shadowing_the_parent_fails_the_structure_rule(theme):
    (theme / "resources" / "css" / "styles.css").write_text("a { }\n", encoding="utf-8")
    assert tc.structure_problems(theme)


def test_other_parent_fails_the_structure_rule(theme):
    _replace(theme / "theme.properties", "parent=keycloak.v2", "parent=base")
    assert tc.structure_problems(theme)


# --- sin recursos externos ni JavaScript: lista blanca sobre contenido parseado ----------------

def test_theme_is_clean_under_the_whitelist():
    assert tc.theme_files(tc.THEME_DIR)
    assert tc.theme_problems(tc.THEME_DIR, ALLOWED) == []


def test_theme_has_only_whitelisted_file_types():
    files = tc.theme_files(tc.THEME_DIR)
    assert files and {p.suffix for p in files} <= tc.ALLOWED_SUFFIXES


def test_unlisted_file_type_is_detected(theme):
    (theme / "resources" / "js").mkdir()
    (theme / "resources" / "js" / "v.js").write_text("alert(1)\n", encoding="utf-8")
    (theme / "templates").mkdir()
    (theme / "templates" / "login.ftl").write_text("<#-- -->\n", encoding="utf-8")
    assert len([p for p in tc.theme_problems(theme, ALLOWED) if "tipo de archivo" in p]) == 2


def test_logo_has_no_image_element_and_says_vectra():
    text = (tc.THEME_DIR / LOGO).read_text(encoding="utf-8")
    assert not re.search(r"<\s*image\b", text, re.IGNORECASE)
    assert "Vectra" in text


def _svg(theme: Path, snippet: str) -> None:
    _replace(theme / LOGO, "</svg>", snippet + "</svg>")


SVG_MUTATIONS = {
    # URL de otro origen o con trucos (N01-N06, N11, T03, T05-T06, X04b)
    "N01 use href /\\host": '<use href="/\\evil.example/x.svg#a"/>',
    "N02 href https:\\\\host": '<use href="https:\\\\evil.example/x.svg"/>',
    "N03 href http:/host": '<use href="http:/evil.example/x.svg"/>',
    "N06 entidad tab": '<use href="/&#9;/evil.example/x.svg"/>',
    "N11 xmlns falso": '<use data-x=" xmlns=\'" href="https://evil.example/x.svg#a" z="\'"/>',
    "T03 xmlns:e y href": '<use xmlns:e="https://evil.example/x.svg" href="https://evil.example/x.svg"/>',
    "T06 atributo que termina en xmlns": '<g data-notxmlns="https://evil.example/"/>',
    "X04b namespace como href": '<use xlink:href="http://www.w3.org/2000/svg"/>',
    "SVG href": '<a href="https://example.com/"/>',
    "href sin esquema": '<use href="//evil.example/x.svg#a"/>',
    "image": '<image href="logo.png"/>',
    # JavaScript (T08-T10, N12-N14, N18)
    "script": "<script>alert(1)</script>",
    "T09 script con prefijo": '<s:script xmlns:s="http://www.w3.org/2000/svg">alert(1)</s:script>',
    "SCRIPT en mayusculas": "<SCRIPT>alert(1)</SCRIPT>",
    "T08 onload": '<g onload="alert(1)"/>',
    "T10 javascript:": '<a href="javascript:alert(1)"/>',
    "N12 entidad en javascript": '<a href="&#106;avascript:alert(1)"/>',
    "N13 javascript&#58;": '<a href="javascript&#58;alert(1)"/>',
    "N14 foreignObject iframe srcdoc": '<foreignObject><iframe srcdoc="&lt;script&gt;alert(1)&lt;/script&gt;"/></foreignObject>',
    "N18 set": '<set attributeName="onclick" to="alert(1)"/>',
    "script en CDATA": "<g><![CDATA[<script>alert(1)</script>]]></g>",
    "style element": "<style>text{fill:red}</style>",
    # entidades y estructura
    "DOCTYPE con entidad": None,
    "instruccion de proceso": None,
}


@pytest.mark.parametrize("name", SVG_MUTATIONS)
def test_svg_mutations_are_detected(theme, name):
    snippet = SVG_MUTATIONS[name]
    if name == "DOCTYPE con entidad":
        path = theme / LOGO
        path.write_text('<!DOCTYPE svg [<!ENTITY e "x">]>\n' + path.read_text(encoding="utf-8"), encoding="utf-8")
    elif name == "instruccion de proceso":
        path = theme / LOGO
        path.write_text('<?xml-stylesheet href="https://evil.example/s.css"?>\n' + path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        _svg(theme, snippet)
    assert tc.theme_problems(theme, ALLOWED), name


SVG_ATTRIBUTE_MUTATIONS = [
    ('d="M6 10 L24 46 L42 10"', 'd="M6 10" onclick="alert(1)"'),
    ('aria-label="Vectra"', 'aria-label="javascript&#58;alert(1)"'),
    ('aria-label="Vectra"', 'aria-label="&lt;script&gt;alert(1)&lt;/script&gt;"'),
    ('aria-label="Vectra"', 'aria-label="Vectra" href="x"'),
    ('role="img"', 'role="img" style="fill:red"'),
    ('stroke-width="7"', 'stroke-width="7" filter="url(#f)"'),
    ('width="220"', 'width="https://evil.example/"'),
]


@pytest.mark.parametrize(("old", "new"), SVG_ATTRIBUTE_MUTATIONS)
def test_svg_attribute_mutations_are_detected(theme, old, new):
    _replace(theme / LOGO, old, new)
    assert tc.theme_problems(theme, ALLOWED)


def test_malformed_svg_is_detected(theme):
    _replace(theme / LOGO, "</svg>", "")
    assert any("mal formado" in p for p in tc.theme_problems(theme, ALLOWED))


def test_xmlns_declarations_are_not_attributes_to_whitelist(theme):
    _replace(theme / LOGO, 'xmlns="http://www.w3.org/2000/svg"', 'xmlns="http://www.w3.org/2000/svg" xmlns:x="http://www.w3.org/1999/xlink"')
    assert tc.theme_problems(theme, ALLOWED) == []


CSS_URL_MUTATIONS = {
    "T01 import sin esquema": '@import url("//cdn.example.com/x.css");',
    "import de cadena": '@import "x.css";',
    "T02 url sin esquema": ".x { background: url(//cdn.example.com/a.png); }",
    "T07 url sin comillas": ".x { background: url(https://cdn.example.com/a.png); }",
    "https": '.x { background: url("https://fonts.example.com/x.png"); }',
    "N04b barra y contrabarra": '.x { background: url("/\\\\evil.example/a.png"); }',
    "esquema con contrabarra": '.x { background: url("https:\\\\\\\\evil.example/a.png"); }',
    "N03 esquema con una barra": ".x { background: url(http:/evil.example/a.png); }",
    "barra inicial": '.x { background: url("/a.png"); }',
    "escape de la barra": '.x { background: url("\\2f \\2f evil.example/a.png"); }',
    "escape de url": ".x { background: u\\72l(//evil.example/a.png); }",
    "caracter de control": '.x { background: url("a\tb//c"); }',
    "url vacia": ".x { background: url(); }",
    "image-set": '.x { background: image-set("a.png" 1x); }',
    "ftp": '.x { background: url("ftp://evil.example/a.png"); }',
    "namespace": '@namespace url("http://evil.example/");',
    "font-face": '@font-face { font-family: x; src: url("https://evil.example/f.woff"); }',
    "javascript en url": '.x { background: url("javascript:alert(1)"); }',
}


@pytest.mark.parametrize("name", CSS_URL_MUTATIONS)
def test_css_url_mutations_are_detected(theme, name):
    _append(theme / CSS, "\n" + CSS_URL_MUTATIONS[name].replace("\\t", "\t") + "\n")
    assert tc.theme_problems(theme, ALLOWED), name


def test_css_relative_url_is_accepted(theme):
    _append(theme / CSS, '\n.x { background: url("../img/vectra-logo.svg"); }\n')
    assert tc.theme_problems(theme, ALLOWED) == []


def test_css_escape_outside_a_string_does_not_tokenize_cleanly(theme):
    _append(theme / CSS, "\n.x { background: url(\\2e\\2e/img/vectra-logo.svg); }\n")
    assert tc.theme_problems(theme, ALLOWED)


def test_css_escape_inside_a_string_url_is_decoded(theme):
    _append(theme / CSS, '\n.x { background: url("\\2e\\2e/img/vectra-logo.svg"); }\n')
    assert tc.theme_problems(theme, ALLOWED) == []
    _append(theme / CSS, '\n.x { background: url("\\2f \\2f evil.example/a.png"); }\n')
    assert tc.theme_problems(theme, ALLOWED)


def test_css_script_is_detected(theme):
    _append(theme / CSS, '\n.x { content: "<script>alert(1)</script>"; }\n')
    assert any("script:" in p for p in tc.theme_problems(theme, ALLOWED))


@pytest.mark.parametrize("line", [
    "loginTitleHtml=<script>alert(1)</script>",
    "loginTitleHtml=java\\u0073cript:alert(1)",
    "loginTitleHtml=&#106;avascript:alert(1)",
    "loginTitleHtml=JAVA\\tSCRIPT:alert(1)",
    "loginTitleHtml=<img src=x onerror=alert(1)>",
    "loginTitleHtml=<a href=\"https://evil.example/\">x</a>",
    "loginTitleHtml=<a href=\"//evil.example/\">x</a>",
    "loginTitleHtml=&lt;SCRIPT&gt;x&lt;/SCRIPT&gt;",
])
def test_messages_es_mutations_are_detected(theme, line):
    """N15."""
    _append(theme / ES, "\n" + line + "\n")
    assert tc.theme_problems(theme, ALLOWED), line


def test_scripts_property_is_detected(theme):
    """T11."""
    _append(theme / "theme.properties", "scripts=js/v.txt\n")
    (theme / "resources" / "js").mkdir()
    (theme / "resources" / "js" / "v.txt").write_text("alert(1)\n", encoding="utf-8")
    assert any("propiedad scripts" in p for p in tc.theme_problems(theme, ALLOWED))


# --- mensajes ---------------------------------------------------------------------------------

def test_messages_es_keys_exist_and_required_ones_are_translated():
    assert tc.message_problems(tc.THEME_DIR, tc.REFERENCE_DIR, TEMPLATES) == []


def test_messages_es_translates_totp_keys():
    es = tc.parse_properties((tc.THEME_DIR / ES).read_text(encoding="utf-8"))
    totp = {k for k in tc.required_keys(tc.REFERENCE_DIR, TEMPLATES) if k.startswith("loginTotp")}
    assert totp and totp <= es.keys()


def test_messages_es_has_only_keys_used_by_the_listed_templates():
    es = tc.parse_properties((tc.THEME_DIR / ES).read_text(encoding="utf-8"))
    used = tc.used_keys(tc.REFERENCE_DIR, TEMPLATES)
    assert {"doSubmit", "doCancel", "showPassword", "hidePassword", "loginTotp.totp", "loginTotp.hotp"} <= used  # label=, msg('..'), msg("loginTotp." + ...)
    assert es.keys() <= used
    assert "doClickHere" not in es


def test_messages_es_key_no_template_uses_is_detected(theme):
    _append(theme / ES, "\ndoClickHere=Haga clic aquí\n")
    assert tc.message_problems(theme, tc.REFERENCE_DIR, TEMPLATES) == ["clave que ninguna plantilla usa: doClickHere"]


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


def test_brand_colors_come_from_the_design():
    assert ALLOWED == set(BRAND.values()) and len(ALLOWED) == 3


def test_brand_css_uses_exactly_the_design_colors():
    css = (tc.THEME_DIR / CSS).read_text(encoding="utf-8")
    assert tc.css_hex_colors(css) == ALLOWED
    assert [p for p in tc.theme_problems(tc.THEME_DIR, ALLOWED) if ": color:" in p] == []


@pytest.mark.parametrize("role", ["primary", "accent"])
def test_brand_contrast_over_background_is_at_least_4_5(role):
    ratio = tc.contrast(BRAND[role], BRAND["background"])
    assert ratio >= 4.5
    assert round(ratio, 2) == tc.design_contrast_ratios()[role]  # el diseno declara el mismo numero


def test_brand_low_contrast_color_is_detected():
    assert tc.contrast("#FFFF00", "#FFFFFF") < 4.5


CSS_COLOR_MUTATIONS = [
    "color: #123456;", "color: #fff;", "color: #0B3D5C80;", "color: rgb(1, 2, 3);", "color: red;",
    "color: RED;", "color: darkred;", "color: rebeccapurple;", "color: var(--pf-v5-global--danger-color--100);",
    "background: hsl(10 20% 30%);", "border: 1px solid transparent;", "color: currentColor;",
    "--x: color-mix(in srgb, #0B3D5C, #C2410C);", "color: light-dark(#0B3D5C, #FFFFFF);",
    "color: CanvasText;", "background: Highlight;", "color: r\\65 d;", "color: \\72 ed;", "color: inherit;",
    "color: initial;", "color: unset;", "color: revert;", "color: revert-layer;", "color: ButtonFace;",
    "color: #0B3D5C !important;", "color: LinkText;",
]


@pytest.mark.parametrize("decl", CSS_COLOR_MUTATIONS)
def test_brand_css_other_colors_are_detected(theme, decl):
    """T14, T15, T16, N27, N27b, N28."""
    _append(theme / CSS, f"\n.x {{ {decl} }}\n")
    problems = tc.theme_problems(theme, ALLOWED)
    assert problems, decl
    if "\\" not in decl:  # un escape fuera de una cadena ni siquiera tokeniza
        assert [p for p in problems if ": color:" in p], decl


def test_brand_css_lowercase_hex_of_the_brand_is_the_same_color(theme):
    _append(theme / CSS, "\n.x { color: #0b3d5c; }\n")
    assert tc.theme_problems(theme, ALLOWED) == []


SVG_COLOR_MUTATIONS = [
    ('fill="#0B3D5C"', 'fill="red"'),            # T20
    ('fill="#0B3D5C"', 'fill="darkred"'),
    ('fill="#0B3D5C"', 'fill="CanvasText"'),     # N30
    ('fill="#0B3D5C"', 'fill="inherit"'),
    ('fill="#0B3D5C"', 'fill="currentColor"'),
    ('fill="#0B3D5C"', 'fill="#abc"'),
    ('fill="#0B3D5C"', 'fill="&#35;FF0000"'),
    ('fill="#0B3D5C"', 'fill="rgb(1,2,3)"'),
    ('fill="#0B3D5C"', 'fill="var(--x)"'),
    ('stroke="#C2410C"', 'stroke="#C2410D"'),
    ('fill="none"', 'fill="transparent"'),
]


@pytest.mark.parametrize(("old", "new"), SVG_COLOR_MUTATIONS)
def test_brand_logo_other_colors_are_detected(theme, old, new):
    _replace(theme / LOGO, old, new)
    assert [p for p in tc.theme_problems(theme, ALLOWED) if ": color:" in p]


CSS_CLASS_MUTATIONS = {
    "C1 comentario dentro de cadenas": '.x { content: "/*"; color: red; content: "*/"; }',
    "C2 llave dentro de cadena": '.x { content: "}"; color: red; }',
    "C3 URL externa tras cadenas": '.x { content: "/*"; background: url(https://evil.example/a.png); content: "*/"; }',
    "C4 opacity": ".pf-v5-c-button.pf-m-primary { opacity: 0.2; }",
    "punto y coma en cadena": '.x { content: ";"; color: red; }',
    "cadena con comillas simples": ".x { content: '/*'; color: red; content: '*/'; }",
    "cadena no vacia": '.x { content: "hola"; }',
    "cadena sin cerrar": '.x { content: "abc; }',
    "comentario sin cerrar": ".x { color: #0B3D5C; } /* x",
    "llave sin cerrar": ".x { color: #0B3D5C;",
    "llave de mas": ".x { color: #0B3D5C; } }",
    "llave anidada": ".x { .y { color: #0B3D5C; } }",
    "media": "@media print { .x { color: #0B3D5C; } }",
    "filter": ".x { filter: invert(1); }",
    "visibility": ".x { visibility: hidden; }",
    "mix-blend-mode": ".x { mix-blend-mode: difference; }",
    "propiedad en mayusculas": ".x { OPACITY: 0.2; }",
    "cadena vacia en un selector": 'a[x=""] { color: #0B3D5C; }',
    "cadena no vacia en un selector": 'a[x="y"] { color: #0B3D5C; }',
    "unidad rara": ".x { width: 10vw; }",
    "signo de exclamacion": ".x { color: #0B3D5C !important; }",
    "comentario que oculta ; en la declaracion": ".x { color: /* a */ red; }",
}


@pytest.mark.parametrize("name", CSS_CLASS_MUTATIONS)
def test_css_class_mutations_are_detected(theme, name):
    css = CSS_CLASS_MUTATIONS[name]
    if name == "cadena vacia en un selector":
        assert tc.theme_problems(theme, ALLOWED) == []
        _append(theme / CSS, "\n" + css + "\n")
        assert tc.theme_problems(theme, ALLOWED) == []  # la unica cadena admitida es la vacia
        return
    _append(theme / CSS, "\n" + css + "\n")
    assert tc.theme_problems(theme, ALLOWED), name


def test_css_comment_inside_a_string_is_not_a_comment():
    rules, strings, errors = tc._tokenize_css('.x { content: "/*"; color: red; content: "*/"; }')
    assert errors == [] and strings == ["/*", "*/"] and len(rules[0][1]) == 4


def test_css_property_whitelist_is_what_vectra_css_uses():
    rules, _, errors = tc._tokenize_css((tc.THEME_DIR / CSS).read_text(encoding="utf-8"))
    used = {d.partition(":")[0].strip() for _, decls in rules for d in decls if d.strip()}
    assert errors == [] and used == tc.CSS_PROPERTIES
