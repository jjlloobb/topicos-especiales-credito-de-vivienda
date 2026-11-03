"""Reglas de P-U2-08 e INF-U2-08 como funciones sobre un directorio, para probarlas tambien sobre copias alteradas.

Los valores (colores, plantillas, imagen base) se leen del diseno, no de constantes.
"""

import hashlib
import json
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_FD = _ROOT / "aidlc-docs" / "construction" / "identity-edge"
NFR_PATTERNS = (_FD / "nfr-design" / "nfr-design-patterns.md").read_text(encoding="utf-8")
INFRASTRUCTURE = (_FD / "infrastructure-design" / "infrastructure-design.md").read_text(encoding="utf-8")

EDGE = _ROOT / "identity-edge"
THEME_DIR = EDGE / "keycloak" / "themes" / "vectra" / "login"
DOCKERFILE = EDGE / "keycloak" / "Dockerfile"


def _subsection(text: str, heading: str) -> str:
    start = text.index(heading)
    rest = text[start + len(heading) :]
    end = re.search(r"^#{1,3} ", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


P_U2_08 = _subsection(NFR_PATTERNS, "### P-U2-08")
INF_U2_08 = _subsection(INFRASTRUCTURE, "### INF-U2-08")


# --- diseno ---------------------------------------------------------------------------------

def design_brand() -> dict[str, str]:
    """primario, acento y fondo de P-U2-08."""
    found = {}
    for role, word in (("primary", "primario"), ("accent", "acento"), ("background", "fondo")):
        m = re.search(rf"{word}[^`\n]*`(#[0-9A-Fa-f]{{6}})`", P_U2_08)
        assert m, f"P-U2-08 no fija el color {word}"
        found[role] = m.group(1).upper()
    return found


def design_contrast_ratios() -> dict[str, float]:
    """Los contrastes que P-U2-08 declara (11,44:1 y 5,18:1)."""
    m = re.search(r"primario ([\d,]+):1 y acento ([\d,]+):1", P_U2_08)
    assert m, "P-U2-08 no declara los contrastes"
    return {"primary": float(m.group(1).replace(",", ".")), "accent": float(m.group(2).replace(",", "."))}


def design_logo_name() -> str:
    m = re.search(r"`(vectra-logo\.svg)`", P_U2_08)
    assert m
    return m.group(1)


def design_templates() -> list[str]:
    """Plantillas cuyas claves exige P-U2-08 (el bullet de la referencia de claves)."""
    bullet = P_U2_08.split("Están traducidas", 1)[1].split("\n- ", 1)[0]
    names = re.findall(r"`([\w-]+\.ftl)`", bullet)
    assert names, "P-U2-08 no lista plantillas"
    return names


def design_image() -> tuple[str, str]:
    """(imagen:etiqueta, digest) de INF-U2-08."""
    m = re.search(r"`(quay\.io/keycloak/keycloak:[\w.]+)@(sha256:[0-9a-f]{64})`", INF_U2_08)
    assert m, "INF-U2-08 no fija la imagen base"
    return m.group(1), m.group(2)


def design_version() -> str:
    """La versión de Keycloak del tag de INF-U2-08 (`26.8.1`)."""
    return design_image()[0].rsplit(":", 1)[1]


def reference_dir() -> Path:
    """`identity-edge/tests/fixtures/keycloak-<versión>/`, con la versión de INF-U2-08 (P-U2-08)."""
    return EDGE / "tests" / "fixtures" / f"keycloak-{design_version()}"


REFERENCE_DIR = reference_dir()


def design_build_options() -> list[str]:
    """Las cuatro opciones de `kc.sh build` de INF-U2-08, en la forma de la linea de comandos."""
    text = INF_U2_08
    opts = []
    m = re.search(r"base de datos `(\w+)`", text)
    assert m
    opts.append(f"--db={m.group(1)}")
    assert "health" in text and "métricas" in text
    opts += ["--health-enabled=true", "--metrics-enabled=true"]
    m = re.search(r"`cache=(\w+)`", text)
    assert m
    opts.append(f"--cache={m.group(1)}")
    return opts


def design_start_args() -> list[str]:
    m = re.search(r"Arranque: `([^`]+)`", INF_U2_08)
    assert m
    return m.group(1).split()


# --- referencia -----------------------------------------------------------------------------

def checksum_mismatches(ref: Path) -> list[str]:
    """Archivos de `SHA256SUMS` cuyo contenido no coincide, o que faltan."""
    bad = []
    for line in (ref / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        path = ref / name.strip().removeprefix("*")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            bad.append(name.strip())
    return bad




_PROP_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "f": "\f"}


def _unescape(text: str) -> str:
    out, i = "", 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt == "u" and re.fullmatch(r"[0-9A-Fa-f]{4}", text[i + 2 : i + 6]):
                out += chr(int(text[i + 2 : i + 6], 16))
                i += 6
                continue
            out += _PROP_ESCAPES.get(nxt, nxt)
            i += 2
            continue
        out += ch
        i += 1
    return out


def parse_properties(text: str) -> dict[str, str]:
    """Sintaxis de `java.util.Properties`: clave hasta el primer `=`, `:` o espacio sin escapar; continuaciones con `\\`."""
    props: dict[str, str] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].lstrip(" \t\f")
        i += 1
        if not line or line[0] in "#!":
            continue
        while (len(line) - len(line.rstrip("\\"))) % 2 == 1 and i < len(lines):
            line = line[:-1] + lines[i].lstrip(" \t\f")
            i += 1
        pos = 0
        while pos < len(line):
            if line[pos] == "\\":
                pos += 2
                continue
            if line[pos] in "=: \t\f":
                break
            pos += 1
        key = line[:pos]
        rest = line[pos:].lstrip(" \t\f")
        if rest[:1] in ("=", ":"):
            rest = rest[1:].lstrip(" \t\f")
        props[_unescape(key)] = _unescape(rest)
    return props


def reference_keys(ref: Path) -> set[str]:
    keys: set[str] = set()
    for rel in ("base/messages_en.properties", "keycloak.v2/messages_en.properties"):
        keys |= parse_properties((ref / rel).read_text(encoding="utf-8")).keys()
    return keys


_MSG_LITERAL = re.compile(r'msg\("([^"$]+)"')


def required_keys(ref: Path, templates: list[str]) -> set[str]:
    """Claves literales `msg("...")` de las plantillas listadas que existen en la referencia."""
    found: set[str] = set()
    for name in templates:
        found |= set(_MSG_LITERAL.findall((ref / "keycloak.v2" / "templates" / name).read_text(encoding="utf-8")))
    return found & reference_keys(ref)


# --- tema -----------------------------------------------------------------------------------

def theme_files(theme: Path) -> list[Path]:
    return sorted(p for p in theme.rglob("*") if p.is_file())


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


_SCHEME_URL = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s\"'<>)]*")
_RELATIVE_SCHEME_URL = re.compile(r"(?:(?<=[\"'(=\s])|^)//[A-Za-z0-9\[][^\s\"'<>)]*", re.MULTILINE)
_TAG = re.compile(r"<(?!!--)[^<>]*>")
_XMLNS_ATTR = re.compile(r"(?<=\s)xmlns(?::[\w.-]+)?\s*=\s*([\"'])(.*?)\1", re.DOTALL)


def _without_namespace_declarations(text: str) -> str:
    """Quita el valor de los atributos `xmlns` / `xmlns:<prefijo>` de las etiquetas; en ninguna otra posición."""
    comments = [m.span() for m in re.finditer(r"<!--.*?-->", text, re.DOTALL)]
    spans = []
    for tag in _TAG.finditer(text):
        if any(a <= tag.start() < b for a, b in comments):
            continue
        for attr in _XMLNS_ATTR.finditer(tag.group(0)):
            spans.append((tag.start() + attr.start(2), tag.start() + attr.end(2)))
    for a, b in reversed(spans):
        text = text[:a] + text[b:]
    return text


def external_references(theme: Path) -> list[str]:
    """URL con esquema o `//host` en cualquier archivo del tema. Solo el valor de un atributo `xmlns` queda exento."""
    bad = []
    for path in theme_files(theme):
        text = _text(path)
        if path.suffix == ".svg":
            text = _without_namespace_declarations(text)
        for url in _SCHEME_URL.findall(text) + _RELATIVE_SCHEME_URL.findall(text):
            bad.append(f"{path.relative_to(theme)}: {url}")
    return bad


_SCRIPT_ELEMENT = re.compile(r"<\s*(?:[\w.-]+:)?script\b", re.IGNORECASE)
_EVENT_ATTR = re.compile(r"(?<=[\s\"'/])on[a-z]+\s*=", re.IGNORECASE)
_JS_URL = re.compile(r"j\s*a\s*v\s*a\s*s\s*c\s*r\s*i\s*p\s*t\s*:", re.IGNORECASE)


def script_problems(theme: Path) -> list[str]:
    """JavaScript propio: elementos `script` (con cualquier prefijo), atributos `on*`, URL `javascript:` y `scripts=`."""
    bad = []
    for path in theme_files(theme):
        rel = str(path.relative_to(theme))
        text = _text(path)
        if _SCRIPT_ELEMENT.search(text):
            bad.append(f"{rel}: elemento script")
        if any(_EVENT_ATTR.search(tag.group(0)) for tag in _TAG.finditer(text)):
            bad.append(f"{rel}: atributo de evento on*")
        if _JS_URL.search(text):
            bad.append(f"{rel}: URL javascript:")
        if path.name == "theme.properties" and "scripts" in parse_properties(text):
            bad.append(f"{rel}: propiedad scripts")
    return bad


def message_problems(theme: Path, ref: Path, templates: list[str]) -> list[str]:
    """Claves de `messages_es` que no existen en la referencia y claves exigidas sin traducir (ausentes o vacías)."""
    es = parse_properties(_text(theme / "messages" / "messages_es.properties"))
    problems = [f"clave inexistente en la referencia: {k}" for k in sorted(set(es) - reference_keys(ref))]
    problems += [f"sin traducir: {k}" for k in sorted(required_keys(ref, templates) - {k for k, v in es.items() if v.strip()})]
    return problems


# --- marca ----------------------------------------------------------------------------------

_NAMED_COLORS = set(
    """aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown burlywood
    cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray
    darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen
    darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue
    firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew
    hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan
    lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen lightskyblue lightslategray
    lightslategrey lightsteelblue lightyellow lime limegreen linen magenta maroon mediumaquamarine mediumblue
    mediumorchid mediumpurple mediumseagreen mediumslateblue mediumspringgreen mediumturquoise mediumvioletred
    midnightblue mintcream mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid
    palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum powderblue purple
    rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue
    slateblue slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet wheat white
    whitesmoke yellow yellowgreen transparent currentcolor""".split()
)
_COLOR_FUNCTIONS = {"rgb", "rgba", "hsl", "hsla", "hwb", "lab", "lch", "oklab", "oklch", "color", "color-mix", "light-dark", "var"}
_HEX_TOKEN = re.compile(r"#[0-9A-Za-z_-]+")


def _value_problems(value: str, allowed: set[str]) -> list[str]:
    value = re.sub(r"url\([^)]*\)", " ", value)
    value = re.sub(r"\"[^\"]*\"|'[^']*'", " ", value)
    bad = [f"color no permitido: {h}" for h in _HEX_TOKEN.findall(value) if h.upper() not in allowed]
    bad += [f"función de color: {f}()" for f in re.findall(r"([\w-]+)\(", value) if f.lower() in _COLOR_FUNCTIONS]
    bad += [f"color con nombre: {n}" for n in re.findall(r"[A-Za-z][A-Za-z-]*", value) if n.lower() in _NAMED_COLORS]
    return bad


def css_color_problems(css: str, allowed: set[str]) -> list[str]:
    """Colores de las declaraciones del CSS que no son uno de `allowed` (hex, nombres, funciones y `var()`)."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    bad = []
    for body in re.findall(r"\{([^{}]*)\}", css):
        for decl in body.split(";"):
            prop, sep, value = decl.partition(":")
            if sep:
                bad += _value_problems(value, allowed)
    return bad


_SVG_COLOR_ATTR = re.compile(r"\b(?:fill|stroke|stop-color|flood-color|lighting-color|color)\s*=\s*([\"'])(.*?)\1", re.DOTALL)


def svg_color_problems(svg: str, allowed: set[str]) -> list[str]:
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.DOTALL)
    bad = [f"color no permitido: {h}" for h in re.findall(r"#[0-9A-Fa-f]{3,8}\b", svg) if h.upper() not in allowed]
    bad += [f"función de color: {f}()" for f in re.findall(r"([\w-]+)\(", svg) if f.lower() in _COLOR_FUNCTIONS]
    for m in _SVG_COLOR_ATTR.finditer(svg):
        bad += [p for p in _value_problems(m.group(2), allowed) if not p.startswith("color no permitido")]
    for m in re.finditer(r"\bstyle\s*=\s*([\"'])(.*?)\1", svg, re.DOTALL):
        bad += css_color_problems("{" + m.group(2) + "}", allowed)
    for m in re.finditer(r"<style\b[^>]*>(.*?)</style>", svg, re.DOTALL | re.IGNORECASE):
        bad += css_color_problems(m.group(1), allowed)
    return bad


def theme_color_problems(theme: Path, allowed: set[str]) -> list[str]:
    bad = []
    for path in theme_files(theme):
        rel = path.relative_to(theme)
        if path.suffix == ".css":
            bad += [f"{rel}: {p}" for p in css_color_problems(_text(path), allowed)]
        elif path.suffix == ".svg":
            bad += [f"{rel}: {p}" for p in svg_color_problems(_text(path), allowed)]
    return bad


def css_hex_colors(css: str) -> set[str]:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    return {h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}\b", css)}


def _lin(c: int) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# --- Dockerfile -----------------------------------------------------------------------------

THEME_TARGET = "/opt/keycloak/themes/vectra"


def dockerfile_problems(text: str, image: str, digest: str, options: list[str], start: list[str]) -> list[str]:
    """Incumplimientos del Dockerfile frente a INF-U2-08 (y `USER` por el escaneo de U1)."""
    problems = []
    flat = re.sub(r"\\\n", " ", text)
    flat = re.sub(r"[ \t]+", " ", flat)
    froms = re.findall(r"^FROM (\S+)", flat, re.MULTILINE)
    if froms != [f"{image}@{digest}"]:
        problems.append(f"FROM no es la imagen exacta con su digest: {froms}")
    copies = re.findall(r"^COPY (?:--\S+ )*(\S+) (\S+)\s*$", flat, re.MULTILINE)
    if ("themes/vectra", THEME_TARGET) not in copies:
        problems.append(f"el tema no se copia a {THEME_TARGET}: {copies}")
    builds = re.findall(r"kc\.sh build\b([^\n&;|]*)", flat)
    if len(builds) != 1:
        problems.append(f"debe haber un único kc.sh build, hay {len(builds)}")
    else:
        given = builds[0].split()
        for option in options:
            name = option.split("=", 1)[0]
            same = [g for g in given if g == name or g.startswith(name + "=")]
            if same != [option]:
                problems.append(f"kc.sh build debe llevar {option} una sola vez: {same}")
    for option in options:
        name, value = option.lstrip("-").split("=", 1)
        env = "KC_" + name.upper().replace("-", "_")
        for found in re.findall(rf"\b{env}(?:=|\s+)(\S+)", flat):
            if found.strip("\"'") != value:
                problems.append(f"{env}={found} contradice {option}")
    cmd = re.search(r"^CMD (\[.*\])\s*$", flat, re.MULTILINE)
    args = json.loads(cmd.group(1)) if cmd else []
    if args != start or not re.search(r'^ENTRYPOINT \["(?:\S*/)?kc\.sh"\]', flat, re.MULTILINE):
        problems.append(f"el arranque no es `{' '.join(start)}` con kc.sh: {args}")
    users = [m for m in re.finditer(r"^USER (\S+)", flat, re.MULTILINE)]
    entry = re.search(r"^ENTRYPOINT", flat, re.MULTILINE)
    if not users or users[-1].group(1) != "1000" or (entry and users[-1].start() > entry.start()):
        problems.append("falta `USER 1000` antes del arranque")
    return problems
