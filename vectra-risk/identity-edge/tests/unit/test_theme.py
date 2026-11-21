"""Tema `vectra` (U02-T06, Paso 4): P-U2-08. Cada regla tiene su caso que falla sobre una copia del tema."""

import re
import shutil
from pathlib import Path

import pytest
import theme_checks as tc

TEMPLATES = tc.design_templates()
BRAND = tc.design_brand()
DARK = tc.design_brand_dark()
ALLOWED = set(BRAND.values()) | set(DARK.values())
LOGO = "resources/img/vectra-logo.svg"
LOGO_DARK = "resources/img/vectra-logo-dark.svg"
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
    assert len(tc.structure_problems(tmp_path / "no-existe")) == 5


def test_theme_without_its_files_fails_the_structure_rule(theme):
    (theme / LOGO).unlink()
    (theme / LOGO_DARK).unlink()
    (theme / CSS).unlink()
    assert tc.structure_problems(theme) == [f"falta {CSS}", f"falta {LOGO}", f"falta {LOGO_DARK}"]


def test_styles_without_the_parent_stylesheet_fail_the_structure_rule(theme):
    """T17."""
    _replace(theme / "theme.properties", "css/styles.css css/vectra.css", "css/vectra.css")
    assert tc.structure_problems(theme)


def test_own_styles_css_shadowing_the_parent_fails_the_structure_rule(theme):
    (theme / "resources" / "css" / "styles.css").write_text("a { }\n", encoding="utf-8")
    assert tc.structure_problems(theme)


@pytest.mark.parametrize(("old", "new"), [("darkMode=true\n", ""), ("darkMode=true", "darkMode=false"), ("darkMode=true", "darkMode=")])
def test_dark_mode_other_than_the_design_fails_the_structure_rule(theme, old, new):
    """El tema define los dos aspectos y el diseño fija `darkMode=true` de forma explícita: `keycloak.v2` pone la clase oscura según el sistema."""
    assert tc.design_dark_mode() == "true"
    _replace(theme / "theme.properties", old, new)
    assert any("darkMode" in p for p in tc.structure_problems(theme))


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


def test_logo_is_the_console_brand_icon():
    """La casa con marca de verificación de `IconBrand` (consola), a escala 2 y desplazada (4, 4): tejado, muros y marca."""
    icons = (tc.EDGE.parent / "console" / "spa" / "src" / "views" / "shared" / "icons.tsx").read_text(encoding="utf-8")
    brand = icons.split("export function IconBrand", 1)[1].split("export function", 1)[0]
    assert re.findall(r'<path d="([^"]+)"', brand) == ["M3 11.5 12 4l9 7.5", "M5.5 10v9.5h13V10", "m9 14.5 2.2 2.2 3.8-4.2"]
    logo = (tc.THEME_DIR / LOGO).read_text(encoding="utf-8")
    assert re.findall(r'<path d="([^"]+)"', logo) == ["M10 27 L28 12 L46 27", "M15 24 V43 H41 V24", "M22 33 L26.4 37.4 L34 29"]


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
    ('d="M10 27 L28 12 L46 27"', 'd="M10 27" onclick="alert(1)"'),
    ('aria-label="Vectra"', 'aria-label="javascript&#58;alert(1)"'),
    ('aria-label="Vectra"', 'aria-label="&lt;script&gt;alert(1)&lt;/script&gt;"'),
    ('aria-label="Vectra"', 'aria-label="Vectra" href="x"'),
    ('role="img"', 'role="img" style="fill:red"'),
    ('stroke-width="3.5"', 'stroke-width="3.5" filter="url(#f)"'),
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
    assert set(BRAND) == {"primary", "brand", "accent", "background", "page"}
    assert set(DARK) == {"primary", "brand", "link", "accent", "background", "page", "button_text"}
    assert len(set(BRAND.values())) == 5 and len(set(DARK.values())) == 7
    assert ALLOWED == set(BRAND.values()) | set(DARK.values()) and len(ALLOWED) == 12  # ningun color sirve a los dos aspectos


def test_brand_css_uses_exactly_the_design_colors():
    css = (tc.THEME_DIR / CSS).read_text(encoding="utf-8")
    assert tc.css_hex_colors(css) == ALLOWED
    assert [p for p in tc.theme_problems(tc.THEME_DIR, ALLOWED) if ": color:" in p] == []


@pytest.mark.parametrize("surface", tc.SURFACES)
@pytest.mark.parametrize("role", tc.TEXT_ROLES)
def test_brand_contrast_over_background_is_at_least_4_5(role, surface):
    """Cada color con texto, icono o foco, sobre la tarjeta y sobre la página. El texto del botón es el fondo sobre primario y marca: la misma razón."""
    ratio = tc.contrast(BRAND[role], BRAND[surface])
    assert ratio >= 4.5
    assert round(ratio, 2) == tc.design_contrast_ratios()[surface][role]  # el diseno declara el mismo numero


def test_brand_design_declares_a_contrast_for_every_text_color_and_surface():
    assert tc.design_contrast_ratios().keys() == set(tc.SURFACES)
    assert all(ratios.keys() == set(tc.TEXT_ROLES) for ratios in tc.design_contrast_ratios().values())


def _color_rules() -> tuple[list[tuple[str, dict[str, str]]], list[tuple[str, dict[str, str]]]]:
    """(reglas del aspecto claro, reglas del oscuro): cada una es (selectores, {propiedad: valor en mayúsculas})."""
    rules, _, errors = tc._tokenize_css((tc.THEME_DIR / CSS).read_text(encoding="utf-8"))
    assert errors == []
    light, dark = [], []
    for prelude, decls in rules:
        selectors = [sel.strip() for sel in prelude.split(",")]
        is_dark = [sel.startswith("." + tc.DARK_CLASS) for sel in selectors]
        assert all(is_dark) or not any(is_dark), f"regla que mezcla los dos aspectos: {prelude!r}"
        props = {d.partition(":")[0].strip(): d.partition(":")[2].strip().upper() for d in decls if d.strip()}
        (dark if all(is_dark) else light).append((prelude, props))
    return light, dark


def _hex_in(props: dict[str, str]) -> set[str]:
    return {h for value in props.values() for h in re.findall(r"#[0-9A-F]{6}\b", value)}


def test_brand_each_look_uses_only_its_own_colors():
    """Las reglas sin la clase oscura solo llevan colores del aspecto claro; las que empiezan por ella, solo del oscuro. Y cada aspecto usa todos los suyos."""
    light, dark = _color_rules()
    assert set().union(*(_hex_in(p) for _, p in light)) == set(BRAND.values())
    assert set().union(*(_hex_in(p) for _, p in dark)) == set(DARK.values())


def test_brand_every_light_color_rule_has_its_dark_pair():
    """Sin consultas de medios, el oscuro se sostiene regla por regla: toda regla clara que fija un color tiene la misma regla bajo la clase oscura, con las mismas propiedades de color."""
    light, dark = _color_rules()
    dark_by_selector: dict[str, set[str]] = {}
    for prelude, props in dark:
        for sel in prelude.split(","):
            dark_by_selector.setdefault(re.sub(r"\s+", " ", sel.strip()), set()).update(k for k, v in props.items() if "#" in v)
    for prelude, props in light:
        colored = {k for k, v in props.items() if "#" in v}
        if not colored:
            continue
        for sel in (re.sub(r"\s+", " ", x.strip()) for x in prelude.split(",")):
            if sel in {"html", ":root"}:
                pair = "." + tc.DARK_CLASS
            elif sel == ".login-pf body":
                pair = f".{tc.DARK_CLASS}.login-pf body"
            else:
                pair = f".{tc.DARK_CLASS} {sel}"
            assert colored <= dark_by_selector.get(pair, set()), f"{sel}: falta {pair} con {sorted(colored)}"


def test_brand_button_text_is_the_background_color_over_primary_and_brand():
    """El botón principal: texto `#FFFFFF` sobre el primario y, al pasar el cursor o con foco, sobre la marca. En oscuro, texto `#0B2318` sobre el primario y sobre el enlace."""
    light, dark = _color_rules()

    def pairs(rules):
        return {(p["background-color"], p["color"]) for prelude, p in rules if "pf-m-primary" in prelude}

    assert pairs(light) == {(BRAND["primary"], BRAND["background"]), (BRAND["brand"], BRAND["background"])}
    assert pairs(dark) == {(DARK[bg], DARK["button_text"]) for bg in tc.DARK_BUTTON_BACKGROUNDS}
    assert all(tc.contrast(bg, fg) >= 4.5 for bg, fg in pairs(light) | pairs(dark))


def test_brand_accent_is_only_for_warnings():
    """El ámbar no es color de enlaces, botones ni foco: solo de los avisos (`pf-m-warning`), en los dos aspectos."""
    light, dark = _color_rules()
    for rules, accent in ((light, BRAND["accent"]), (dark, DARK["accent"])):
        with_accent = [prelude for prelude, props in rules if accent in _hex_in(props)]
        assert with_accent and all("pf-m-warning" in sel for prelude in with_accent for sel in prelude.split(","))


@pytest.mark.parametrize("surface", tc.SURFACES)
@pytest.mark.parametrize("role", tc.DARK_TEXT_ROLES)
def test_brand_dark_contrast_over_background_is_at_least_4_5(role, surface):
    ratio = tc.contrast(DARK[role], DARK[surface])
    assert ratio >= 4.5
    assert round(ratio, 2) == tc.design_contrast_ratios_dark()[surface][role]  # el diseno declara el mismo numero


@pytest.mark.parametrize("background", tc.DARK_BUTTON_BACKGROUNDS)
def test_brand_dark_button_text_contrast_is_at_least_4_5(background):
    ratio = tc.contrast(DARK["button_text"], DARK[background])
    assert ratio >= 4.5
    assert round(ratio, 2) == tc.design_contrast_ratios_dark()["button"][background]


def test_brand_dark_design_declares_a_contrast_for_every_text_color_and_surface():
    declared = tc.design_contrast_ratios_dark()
    assert declared.keys() == {*tc.SURFACES, "button"}
    assert all(declared[s].keys() == set(tc.DARK_TEXT_ROLES) for s in tc.SURFACES)
    assert declared["button"].keys() == set(tc.DARK_BUTTON_BACKGROUNDS)


def test_brand_dark_logo_is_the_light_logo_with_the_dark_colors():
    """El logo del aspecto oscuro: las mismas trazas y texto, con la marca y el primario oscuros (un SVG de fondo no hereda `currentColor`)."""
    light = (tc.THEME_DIR / LOGO).read_text(encoding="utf-8")
    dark = (tc.THEME_DIR / LOGO_DARK).read_text(encoding="utf-8")
    assert dark == light.replace(BRAND["brand"], DARK["brand"]).replace(BRAND["primary"], DARK["primary"])
    assert set(re.findall(r"#[0-9A-Fa-f]{6}", dark)) == {DARK["brand"], DARK["primary"]}
    css = (tc.THEME_DIR / CSS).read_text(encoding="utf-8")
    assert f'.{tc.DARK_CLASS} #kc-header-wrapper::before' in css and "vectra-logo-dark.svg" in css


def test_brand_dark_missing_pair_is_detected(theme, monkeypatch):
    """Si se quita una pareja oscura (el título), la regla de las parejas lo detecta."""
    _replace(theme / CSS, f".{tc.DARK_CLASS} #kc-page-title", f".{tc.DARK_CLASS} #kc-otro")
    monkeypatch.setattr(tc, "THEME_DIR", theme)
    with pytest.raises(AssertionError, match="kc-page-title"):
        test_brand_every_light_color_rule_has_its_dark_pair()


def test_brand_low_contrast_color_is_detected():
    assert tc.contrast("#FFFF00", "#FFFFFF") < 4.5


CSS_COLOR_MUTATIONS = [
    "color: #123456;", "color: #fff;", "color: #14633F80;", "color: rgb(1, 2, 3);", "color: red;",
    "color: RED;", "color: darkred;", "color: rebeccapurple;", "color: var(--pf-v5-global--danger-color--100);",
    "background: hsl(10 20% 30%);", "border: 1px solid transparent;", "color: currentColor;",
    "--x: color-mix(in srgb, #14633F, #8A5A00);", "color: light-dark(#14633F, #FFFFFF);",
    "color: CanvasText;", "background: Highlight;", "color: r\\65 d;", "color: \\72 ed;", "color: inherit;",
    "color: initial;", "color: unset;", "color: revert;", "color: revert-layer;", "color: ButtonFace;",
    "color: #14633F !important;", "color: LinkText;",
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
    _append(theme / CSS, "\n.x { color: #14633f; }\n")
    assert tc.theme_problems(theme, ALLOWED) == []


SVG_COLOR_MUTATIONS = [
    ('fill="#0B3B2C"', 'fill="red"'),            # T20
    ('fill="#0B3B2C"', 'fill="darkred"'),
    ('fill="#0B3B2C"', 'fill="CanvasText"'),     # N30
    ('fill="#0B3B2C"', 'fill="inherit"'),
    ('fill="#0B3B2C"', 'fill="currentColor"'),
    ('fill="#0B3B2C"', 'fill="#abc"'),
    ('fill="#0B3B2C"', 'fill="&#35;FF0000"'),
    ('fill="#0B3B2C"', 'fill="rgb(1,2,3)"'),
    ('fill="#0B3B2C"', 'fill="var(--x)"'),
    ('stroke="#0B3B2C"', 'stroke="#0B3B2D"'),
    ('stroke="#14633F"', 'stroke="#14633E"'),
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
    "comentario sin cerrar": ".x { color: #14633F; } /* x",
    "llave sin cerrar": ".x { color: #14633F;",
    "llave de mas": ".x { color: #14633F; } }",
    "llave anidada": ".x { .y { color: #14633F; } }",
    "media": "@media print { .x { color: #14633F; } }",
    "filter": ".x { filter: invert(1); }",
    "visibility": ".x { visibility: hidden; }",
    "mix-blend-mode": ".x { mix-blend-mode: difference; }",
    "propiedad en mayusculas": ".x { OPACITY: 0.2; }",
    "cadena vacia en un selector": 'a[x=""] { color: #14633F; }',
    "cadena no vacia en un selector": 'a[x="y"] { color: #14633F; }',
    "unidad rara": ".x { width: 10vw; }",
    "signo de exclamacion": ".x { color: #14633F !important; }",
    "variable no listada": ":root { --pf-v5-global--danger-color--100: #14633F; }",
    "variable listada con otras mayusculas": ":root { --pf-v5-global--link--color: #14633F; }",
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
