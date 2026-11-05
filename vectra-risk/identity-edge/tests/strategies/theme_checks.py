"""Reglas de P-U2-08 e INF-U2-08 como funciones sobre un directorio, para probarlas tambien sobre copias alteradas.

Los valores (colores, plantillas, imagen base) se leen del diseno, no de constantes.
"""

import hashlib
import html
import json
import re
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
    """Las opciones de `kc.sh build`: las cinco de INF-U2-08 y las dos de metricas de eventos de B10 (P-U2-09)."""
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
    m = re.search(r"`kc\.sh build` lleva además `(--http-relative-path=/\w+)`", text)
    assert m, "INF-U2-08 no fija --http-relative-path"
    opts.append(m.group(1))
    opts += design_event_metric_options()
    return opts


def design_event_metric_options() -> list[str]:
    """B10 de P-U2-09: las dos opciones que activan `keycloak_user_events_total` con `client_id`, en la forma de la linea de comandos."""
    m = re.search(r"`(event-metrics-user-enabled=true)`, con `(event-metrics-user-tags=[\w,]+)`", NFR_PATTERNS)
    assert m, "P-U2-09 (B10) no fija las opciones de las metricas de eventos de usuario"
    return [f"--{m.group(1)}", f"--{m.group(2)}"]


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


CSS_PROPERTIES = {
    "background-color", "color", "content", "display", "width", "height", "margin",
    "background", "outline", "outline-offset",
}  # las que usa vectra.css
CSS_UNITS = {"", "px", "rem", "em", "%"}


def _decode_escapes(text: str) -> str:
    def decode(m: re.Match) -> str:
        if m.group(1):
            return chr(min(int(m.group(1), 16) or 0xFFFD, 0x10FFFF))
        return m.group(2)

    text = re.sub(r"\\\r?\n", "", text)
    return re.sub(r"\\(?:([0-9a-fA-F]{1,6})[ \t\n\r\f]?|(.))", decode, text, flags=re.DOTALL)


def _tokenize_css(css: str) -> tuple[list[tuple[str, list[str]]], list[str], list[str]]:
    """(reglas, cadenas, errores). Las cadenas y los `url()` sin comillas son tokens: dentro de ellos no hay comentarios, llaves ni `;`.

    Cada regla es (preludio, declaraciones) con las cadenas sustituidas por `\\x00S<n>\\x00` y los url sin comillas por `\\x00U<n>\\x00`.
    No admite `@`, `\\` fuera de cadenas, llaves anidadas ni comentarios sin cerrar: lo que no tokeniza limpio es un error.
    """
    rules: list[tuple[str, list[str]]] = []
    strings: list[str] = []
    errors: list[str] = []
    prelude, cur, decls, depth, i, n = "", "", [], 0, 0, len(css)
    while i < n:
        c = css[i]
        if css.startswith("/*", i):
            j = css.find("*/", i + 2)
            if j < 0:
                errors.append("structure: comentario sin cerrar")
                break
            cur += " "
            i = j + 2
        elif c in "\"'":
            j, body = i + 1, ""
            while j < n and css[j] != c:
                if css[j] in "\n\r\f":
                    break
                if css[j] == "\\":
                    body += css[j : j + 2]
                    j += 2
                else:
                    body += css[j]
                    j += 1
            if j >= n or css[j] != c:
                errors.append("structure: cadena sin cerrar")
                break
            strings.append(_decode_escapes(body))
            cur += f"\x00S{len(strings) - 1}\x00"
            i = j + 1
        elif depth == 1 and css[i : i + 4].lower() == "url(" and not re.match(r"\s*[\"']", css[i + 4 :]):
            j = css.find(")", i)
            if j < 0:
                errors.append("structure: url( sin cerrar")
                break
            strings.append(css[i + 4 : j])
            cur += f"\x00U{len(strings) - 1}\x00"
            i = j + 1
        elif c == "\\" or c == "@" or c == "\x00":
            errors.append(f"structure: carácter {c!r} fuera de una cadena")
            break
        elif c == "{":
            if depth:
                errors.append("structure: llave anidada")
                break
            depth, prelude, cur = 1, cur, ""
            i += 1
        elif c == "}":
            if not depth:
                errors.append("structure: llave de cierre sin abrir")
                break
            decls.append(cur)
            rules.append((prelude, decls))
            depth, decls, cur = 0, [], ""
            i += 1
        elif c == ";" and depth:
            decls.append(cur)
            cur = ""
            i += 1
        else:
            cur += c
            i += 1
    else:
        if depth or cur.strip():
            errors.append("structure: el CSS no termina en una regla completa")
    return rules, strings, errors


_PLACEHOLDER = re.compile(r"\x00([SU])(\d+)\x00")


def css_problems(css: str, allowed: set[str]) -> list[str]:
    """CSS tokenizado: propiedades de una lista blanca; valores solo con hex de la marca, números, palabras sin color de una lista cerrada, `url()` relativos y la cadena vacía."""
    rules, strings, bad = _tokenize_css(css)
    used_as_url: set[int] = set()
    for prelude, decls in rules:
        for m in _PLACEHOLDER.finditer(prelude):
            if strings[int(m[2])] != "":
                bad.append("structure: cadena no vacía en un selector")
        for decl in decls:
            if not decl.strip():
                continue
            prop, sep, value = decl.partition(":")
            prop = prop.strip().lower()
            if not sep or prop not in CSS_PROPERTIES:
                bad.append(f"structure: propiedad no permitida: {prop or decl.strip()}")
            for m in re.finditer(r"url\(\s*\x00S(\d+)\x00\s*\)|\x00U(\d+)\x00", value, re.IGNORECASE):
                idx = int(m[1] or m[2])
                used_as_url.add(idx)
                url = strings[idx].strip() if m[2] else strings[idx]
                bad += [p for p in (_url_problem(url) if url else "url: vacia",) if p]
            value = re.sub(r"url\(\s*\x00S\d+\x00\s*\)|\x00U\d+\x00", " ", value, flags=re.IGNORECASE)
            for m in _PLACEHOLDER.finditer(value):
                if strings[int(m[2])] != "":
                    bad.append(f"structure: cadena no vacía en {prop}")
            value = _PLACEHOLDER.sub(" ", value)
            for hexa in re.findall(r"#[\w-]+", value):
                if hexa.upper() not in allowed:
                    bad.append(f"color: {hexa}")
            value = re.sub(r"#[\w-]+", " ", value)
            for fn in re.findall(r"([A-Za-z_-][\w-]*)\(", value):
                bad.append(f"color: función {fn}()")
            value = re.sub(r"[A-Za-z_-][\w-]*\(", " ", value)
            for num in re.finditer(r"[-+]?(?:\d+\.?\d*|\.\d+)([A-Za-z%]*)", value):
                if num[1].lower() not in CSS_UNITS:
                    bad.append(f"color: unidad no permitida: {num[0]}")
            value = re.sub(r"[-+]?(?:\d+\.?\d*|\.\d+)[A-Za-z%]*", " ", value)
            for word in re.findall(r"[A-Za-z_-][\w-]*", value):
                if word.lower() not in CSS_KEYWORDS:
                    bad.append(f"color: palabra no permitida en {prop}: {word}")
            leftover = re.sub(r"[A-Za-z_-][\w-]*|[/,\s]", "", value)
            if leftover:
                bad.append(f"color: resto no permitido en {prop}: {leftover!r}")
    for idx, text in enumerate(strings):
        if idx not in used_as_url and text != "" and not any(f"\x00S{idx}\x00" in p or f"\x00U{idx}\x00" in p for p, _ in rules):
            bad.append("structure: cadena no vacía")
    bad += _javascript_in("".join(f"{p}{{{';'.join(d)}}}" for p, d in rules).replace("\x00", " ") + " ".join(strings))
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
    rules, _, _ = _tokenize_css(css)
    return {h.upper() for _, decls in rules for d in decls for h in re.findall(r"#[0-9A-Fa-f]{6}\b", d)}


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
KC = "/opt/keycloak/bin/kc.sh"
_BLANKS = re.compile(r"[ \t\v\f\r]+")


def _instructions(text: str) -> list[list[str]]:
    """Instrucciones normalizadas: sin líneas vacías ni comentarios, con continuaciones unidas, separadas por blancos y con el nombre en mayúsculas."""
    logical, current = [], ""
    for raw in text.split("\n"):
        line = raw.strip(" \t\v\f\r")
        if line.startswith("#") or not line:
            if not current:
                continue
            continue
        if line.endswith("\\"):
            current += line[:-1] + " "
            continue
        logical.append(current + line)
        current = ""
    if current.strip():
        logical.append(current)
    steps = []
    for line in logical:
        tokens = [t for t in _BLANKS.split(line.strip()) if t]
        steps.append([tokens[0].upper(), *tokens[1:]])
    return steps


def dockerfile_problems(text: str, image: str, digest: str, options: list[str], start: list[str]) -> list[str]:
    """Lista blanca exacta: el Dockerfile normalizado es FROM, COPY, RUN kc.sh build, USER 1000, ENTRYPOINT, CMD y nada más."""
    problems = []
    if "<<" in text:
        problems.append("heredoc no permitido")
    for raw in text.split("\n"):
        line = raw.strip()
        if line and not line.startswith("#"):
            break
        if re.match(r"#\s*[A-Za-z]+\s*=", line):
            problems.append(f"directiva de parser no permitida: {line}")
    steps = _instructions(text)
    expected = ["FROM", "COPY", "RUN", "USER", "ENTRYPOINT", "CMD"]
    if [s[0] for s in steps] != expected:
        return problems + [f"las instrucciones deben ser exactamente {expected}: {[s[0] for s in steps]}"]
    by_name = {s[0]: s[1:] for s in steps}
    if by_name["FROM"] != [f"{image}@{digest}"]:
        problems.append(f"FROM no es la imagen exacta con su digest: {by_name['FROM']}")
    if by_name["COPY"] != ["--chown=keycloak:keycloak", "themes/vectra", THEME_TARGET]:
        problems.append(f"el tema no se copia a {THEME_TARGET}: {by_name['COPY']}")
    run = by_name["RUN"]
    if run[:2] != [KC, "build"]:
        problems.append(f"RUN debe ser {KC} build con las opciones del diseño: {run}")
    else:
        args = run[2:]
        for option in options:
            name = option.split("=", 1)[0]
            same = [g for g in args if g == name or g.startswith(name + "=")]
            if same != [option]:
                problems.append(f"kc.sh build debe llevar {option} una sola vez: {same}")
        extra = [g for g in args if g not in options]
        if extra:
            problems.append(f"kc.sh build lleva argumentos de más: {extra}")
    if by_name["USER"] != ["1000"]:
        problems.append(f"USER debe ser 1000: {by_name['USER']}")
    if " ".join(by_name["ENTRYPOINT"]) != json.dumps([KC]):
        problems.append(f"ENTRYPOINT debe ser {json.dumps([KC])}: {by_name['ENTRYPOINT']}")
    if " ".join(by_name["CMD"]) != json.dumps(start):
        problems.append(f"CMD debe ser {json.dumps(start)}: {by_name['CMD']}")
    return problems
