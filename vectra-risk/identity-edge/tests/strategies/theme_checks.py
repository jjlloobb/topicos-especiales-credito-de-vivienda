"""Reglas de P-U2-08 e INF-U2-08 como funciones sobre un directorio, para probarlas tambien sobre copias alteradas.

Los valores (colores, plantillas, imagen base) se leen del diseno, no de constantes.
"""

import hashlib
import html
import json
import re
import shlex
import xml.etree.ElementTree as ET
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


_USED_LITERAL = re.compile(r"""(?:msg\(\s*|label\s*=\s*)["']([^"'$]+)["']""")
_USED_PREFIX = re.compile(r"""msg\(\s*["']([^"'$]+\.)["']\s*\+""")


def used_keys(ref: Path, templates: list[str]) -> set[str]:
    """Claves que las plantillas usan: `msg("…")`/`msg('…')`, `label="…"` y las de `msg("prefijo." + …)` que hay en la referencia."""
    keys = reference_keys(ref)
    found: set[str] = set()
    for name in templates:
        text = (ref / "keycloak.v2" / "templates" / name).read_text(encoding="utf-8")
        found |= set(_USED_LITERAL.findall(text))
        for prefix in _USED_PREFIX.findall(text):
            found |= {k for k in keys if k.startswith(prefix)}
    return found & keys


# --- tema -----------------------------------------------------------------------------------
# Lista blanca sobre contenido parseado: el SVG con un parser XML, el CSS con los escapes decodificados y los
# `.properties` con sus valores decodificados. Todo problema es una cadena `categoria: detalle`.

ALLOWED_SUFFIXES = {".properties", ".css", ".svg"}
SVG_NS = "http://www.w3.org/2000/svg"
SVG_ELEMENTS = {
    "svg": {"viewBox", "width", "height", "role", "aria-label"},
    "title": set(),
    "path": {"d", "fill", "stroke", "stroke-width", "stroke-linejoin", "stroke-linecap"},
    "text": {"x", "y", "font-family", "font-size", "font-weight", "fill"},
}
SVG_COLOR_ATTRS = {"fill", "stroke"}
CSS_KEYWORDS = {"none", "block", "auto", "center", "contain", "no-repeat", "solid"}  # palabras sin color que usa vectra.css
CSS_FUNCTIONS = {"url"}
_CONTROL = re.compile(r"[\x00-\x20\x7f-\x9f  ​-‏﻿]")


def theme_files(theme: Path) -> list[Path]:
    return sorted(p for p in theme.rglob("*") if p.is_file())


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _javascript_in(value: str) -> list[str]:
    """JavaScript en un texto ya decodificado (también tras decodificar entidades HTML)."""
    bad = []
    for variant in {value, html.unescape(value)}:
        squeezed = _CONTROL.sub("", variant).lower()
        if "<script" in squeezed or "javascript:" in squeezed or "vbscript:" in squeezed:
            bad.append("script: JavaScript embebido")
        if re.search(r"(?<![\w-])on[a-z]+\s*=", variant, re.IGNORECASE):
            bad.append("script: atributo de evento on*")
    return sorted(set(bad))


def _url_problem(url: str) -> str | None:
    """Una URL del tema debe ser una ruta relativa sin esquema, sin `/` ni `\\` inicial y sin caracteres de control."""
    if not re.fullmatch(r"[\w.~][\w.~/-]*", url) or _CONTROL.search(url):
        return f"url: {url!r}"
    return None


def _scheme_urls(value: str) -> list[str]:
    bad = []
    for variant in {value, html.unescape(value)}:
        squeezed = _CONTROL.sub("", variant)
        bad += [f"url: {u}" for u in re.findall(r"[A-Za-z][A-Za-z0-9+.-]*:[/\\]{1,2}[^\s\"'<>)]*", squeezed)]
        bad += [f"url: {u}" for u in re.findall(r"(?<![\w:])[/\\]{2}[\w.\[-][^\s\"'<>)]*", squeezed)]
    return sorted(set(bad))


def svg_problems(text: str, allowed: set[str]) -> list[str]:
    """SVG parseado con `xml.etree`: solo los elementos y atributos del logo; `fill`/`stroke` solo los colores de la marca o `none`."""
    if re.search(r"<!DOCTYPE|<!ENTITY|<\?(?!xml\s)", text, re.IGNORECASE):
        return ["structure: DOCTYPE, entidad o instrucción de proceso"]
    try:
        root = ET.fromstring(text)  # noqa: S314 - sin DOCTYPE, ya rechazado arriba
    except ET.ParseError as exc:
        return [f"structure: SVG mal formado: {exc}"]
    bad = []
    for el in root.iter():
        if not isinstance(el.tag, str) or not el.tag.startswith("{" + SVG_NS + "}"):
            bad.append(f"structure: elemento fuera del espacio de nombres SVG: {el.tag!r}")
            continue
        name = el.tag.split("}", 1)[1]
        if name not in SVG_ELEMENTS:
            bad.append(f"structure: elemento no permitido: {name}")
            continue
        for attr, value in el.attrib.items():
            if attr not in SVG_ELEMENTS[name]:
                bad.append(f"structure: atributo no permitido en {name}: {attr}")
                continue
            bad += _javascript_in(value) + _scheme_urls(value)
            if attr in SVG_COLOR_ATTRS and value.strip().upper() not in allowed | {"NONE"}:
                bad.append(f"color: {attr}={value!r}")
            if re.search(r"url\s*\(", value, re.IGNORECASE):
                bad.append(f"url: {attr}={value!r}")
        content = (el.text or "") + "".join(c.tail or "" for c in el)
        if name in {"title", "text"} and not re.fullmatch(r"[\w ]*", content):
            bad.append(f"structure: contenido no permitido en {name}")
        if name not in {"title", "text"} and content.strip():
            bad.append(f"structure: texto dentro de {name}")
    return sorted(set(bad))


def _css_unescape(css: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    css = re.sub(r"\\\r?\n", "", css)

    def decode(m: re.Match) -> str:
        if m.group(1):
            return chr(min(int(m.group(1), 16) or 0xFFFD, 0x10FFFF))
        return m.group(2)

    return re.sub(r"\\(?:([0-9a-fA-F]{1,6})[ \t\n\r\f]?|(.))", decode, css, flags=re.DOTALL)


def css_problems(css: str, allowed: set[str]) -> list[str]:
    """CSS con los escapes decodificados: URL relativas, y en cada declaración solo los hex de la marca, números y palabras de lista cerrada."""
    text = _css_unescape(css)
    bad = []
    for rule in re.findall(r"@[\w-]+", text):
        if rule.lower() != "@media":
            bad.append(f"structure: regla {rule}")
    for url in re.findall(r"url\(\s*(?:\"([^\"]*)\"|'([^']*)'|([^)\"']*))\s*\)", text, re.IGNORECASE):
        found = "".join(url).strip()
        problem = _url_problem(found) if found else "url: vacia"
        if problem:
            bad.append(problem)
    bad += _javascript_in(text)
    for body in re.findall(r"\{([^{}]*)\}", text):
        for decl in body.split(";"):
            prop, sep, value = decl.partition(":")
            if not sep:
                continue
            value = re.sub(r"url\([^)]*\)", " ", value, flags=re.IGNORECASE)
            value = re.sub(r"\"[^\"]*\"|'[^']*'", " ", value)
            for hexa in re.findall(r"#[\w-]+", value):
                if hexa.upper() not in allowed:
                    bad.append(f"color: {hexa}")
            value = re.sub(r"#[\w-]+", " ", value)
            for fn in re.findall(r"([A-Za-z_-][\w-]*)\(", value):
                bad.append(f"color: función {fn}()")
            value = re.sub(r"[-+]?(?:\d+\.?\d*|\.\d+)[A-Za-z%]*", " ", value)
            for word in re.findall(r"[A-Za-z_-][\w-]*", value):
                if word.lower() not in CSS_KEYWORDS and f"color: función {word}()" not in bad:
                    bad.append(f"color: palabra no permitida en {prop.strip()}: {word}")
    return sorted(set(bad))


def properties_problems(text: str) -> list[str]:
    """Valores ya decodificados de un `.properties`: sin JavaScript ni URL de otro origen."""
    bad = []
    for key, value in parse_properties(text).items():
        bad += _javascript_in(value) + _scheme_urls(value)
        if key == "scripts":
            bad.append("script: propiedad scripts")
    return sorted(set(bad))


def theme_problems(theme: Path, allowed: set[str]) -> list[str]:
    """Todas las reglas del tema sobre contenido parseado. Cada problema: `<archivo>: <categoria>: <detalle>`."""
    bad = []
    for path in theme_files(theme):
        rel = path.relative_to(theme)
        if path.suffix not in ALLOWED_SUFFIXES:
            bad.append(f"{rel}: structure: tipo de archivo no permitido")
            continue
        text = _text(path)
        found = (
            svg_problems(text, allowed) if path.suffix == ".svg"
            else css_problems(text, allowed) if path.suffix == ".css"
            else properties_problems(text)
        )
        bad += [f"{rel}: {p}" for p in found]
    return bad


def structure_problems(theme: Path) -> list[str]:
    """El tema estándar: `theme.properties` con el padre, `messages_es`, el CSS y el logo; `styles` conserva el del padre."""
    bad = [f"falta {rel}" for rel in ("theme.properties", "messages/messages_es.properties",
                                      "resources/css/vectra.css", f"resources/img/{design_logo_name()}")
           if not (theme / rel).is_file()]
    if not (theme / "theme.properties").is_file():
        return bad
    props = parse_properties(_text(theme / "theme.properties"))
    if props.get("parent") != "keycloak.v2":
        bad.append("parent no es keycloak.v2")
    if props.get("styles", "").split() != ["css/styles.css", "css/vectra.css"]:
        bad.append("styles no conserva css/styles.css del padre y agrega css/vectra.css")
    if (theme / "resources" / "css" / "styles.css").exists():
        bad.append("resources/css/styles.css tapa la hoja del padre")
    return bad


def _of(theme: Path, allowed: set[str], category: str) -> list[str]:
    return [p for p in theme_problems(theme, allowed) if f": {category}:" in p]


def message_problems(theme: Path, ref: Path, templates: list[str]) -> list[str]:
    """Claves de `messages_es` que no existen en la referencia y claves exigidas sin traducir (ausentes o vacías)."""
    es = parse_properties(_text(theme / "messages" / "messages_es.properties"))
    problems = [f"clave inexistente en la referencia: {k}" for k in sorted(set(es) - reference_keys(ref))]
    problems += [f"sin traducir: {k}" for k in sorted(required_keys(ref, templates) - {k for k, v in es.items() if v.strip()})]
    problems += [f"clave que ninguna plantilla usa: {k}" for k in sorted(set(es) & reference_keys(ref) - used_keys(ref, templates))]
    return problems


# --- marca ----------------------------------------------------------------------------------

def css_hex_colors(css: str) -> set[str]:
    return {h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}\b", _css_unescape(css))}


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
_SEPARATORS = {"&&", ";", "||", "|", "&"}


def _instructions(text: str) -> list[tuple[str, str]]:
    """(INSTRUCCIÓN en mayúsculas, resto) con continuaciones de línea; los comentarios se descartan."""
    logical, current = [], ""
    for raw in text.splitlines():
        line = raw.strip()
        if not current and (not line or line.startswith("#")):
            continue
        if current and line.startswith("#"):
            continue
        if line.endswith("\\"):
            current += line[:-1] + " "
            continue
        logical.append((current + line).strip())
        current = ""
    if current.strip():
        logical.append(current.strip())
    out = []
    for line in logical:
        head, _, rest = line.partition(" ")
        out.append((head.upper(), rest.strip()))
    return out


def _argv(rest: str) -> list[str]:
    """Argumentos de una instrucción, en forma exec (JSON) o shell."""
    if rest.startswith("["):
        try:
            parsed = json.loads(rest)
            if isinstance(parsed, list) and all(isinstance(a, str) for a in parsed):
                return parsed
        except json.JSONDecodeError:
            pass
    lexer = shlex.shlex(rest, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return rest.split()


def _kc_invocations(argv: list[str]) -> list[list[str]]:
    """Argumentos que siguen a cada `kc.sh` de la línea de comandos."""
    commands, current = [], []
    for token in argv:
        if token in _SEPARATORS:
            commands.append(current)
            current = []
        else:
            current.append(token)
    commands.append(current)
    found = []
    for command in commands:
        for i, token in enumerate(command):
            if token.rsplit("/", 1)[-1] == "kc.sh":
                found.append(command[i + 1 :])
    return found


def dockerfile_problems(text: str, image: str, digest: str, options: list[str], start: list[str]) -> list[str]:
    """Incumplimientos del Dockerfile frente a INF-U2-08 (y `USER 1000` por el escaneo de U1)."""
    problems = []
    steps = _instructions(text)
    froms = [_argv(rest) for kw, rest in steps if kw == "FROM"]
    if len(froms) != 1 or [a for a in froms[0] if not a.startswith("--")][:1] != [f"{image}@{digest}"]:
        problems.append(f"debe haber un único FROM y ser la imagen exacta con su digest: {froms}")
    copies = [[a for a in _argv(rest) if not a.startswith("--")] for kw, rest in steps if kw == "COPY"]
    if ["themes/vectra", THEME_TARGET] not in copies:
        problems.append(f"el tema no se copia a {THEME_TARGET}: {copies}")
    builds = []
    for kw, rest in steps:
        if kw in {"RUN", "CMD", "ENTRYPOINT", "ONBUILD", "HEALTHCHECK"}:
            builds += [args for args in _kc_invocations(_argv(rest)) if "build" in args]
    if len(builds) != 1:
        problems.append(f"debe haber una única invocación de kc.sh build, hay {len(builds)}")
    else:
        for option in options:
            name = option.split("=", 1)[0]
            same = [g for g in builds[0] if g == name or g.startswith(name + "=")]
            if same != [option]:
                problems.append(f"kc.sh build debe llevar {option} una sola vez: {same}")
    assigned: list[tuple[str, str]] = []
    for kw, rest in steps:
        argv = _argv(rest)
        for token in argv:
            m = re.fullmatch(r"(KC_[A-Z_]+)=(.*)", token, re.DOTALL)
            if m:
                assigned.append((m.group(1), m.group(2)))
        if kw in {"ENV", "ARG"} and len(argv) >= 2 and "=" not in argv[0]:
            assigned.append((argv[0], " ".join(argv[1:])))
    for option in options:
        name, value = option.lstrip("-").split("=", 1)
        env = "KC_" + name.upper().replace("-", "_")
        problems += [f"{env}={v} contradice {option}" for k, v in assigned if k == env and v.strip("\"'") != value]
    users = [(i, _argv(rest)) for i, (kw, rest) in enumerate(steps) if kw == "USER"]
    entry = [i for i, (kw, _) in enumerate(steps) if kw == "ENTRYPOINT"]
    if not users or any(a != ["1000"] for _, a in users) or (entry and users[-1][0] > entry[-1]):
        problems.append("falta `USER 1000` antes del arranque, o hay otro USER")
    cmd = [_argv(rest) for kw, rest in steps if kw == "CMD"]
    entrypoint = [_argv(rest) for kw, rest in steps if kw == "ENTRYPOINT"]
    if not cmd or cmd[-1] != start or not entrypoint or entrypoint[-1][:1] == [] or entrypoint[-1][0].rsplit("/", 1)[-1] != "kc.sh":
        problems.append(f"el arranque no es `{' '.join(start)}` con kc.sh: {cmd} {entrypoint}")
    return problems
