"""Reglas de P-U2-08 e INF-U2-08 como funciones sobre un directorio, para probarlas tambien sobre copias alteradas.

Los valores (colores, plantillas, imagen base) se leen del diseno, no de constantes.
"""

import hashlib
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_FD = _ROOT / "aidlc-docs" / "construction" / "identity-edge"
NFR_PATTERNS = (_FD / "nfr-design" / "nfr-design-patterns.md").read_text(encoding="utf-8")
INFRASTRUCTURE = (_FD / "infrastructure-design" / "infrastructure-design.md").read_text(encoding="utf-8")

EDGE = _ROOT / "identity-edge"
THEME_DIR = EDGE / "keycloak" / "themes" / "vectra" / "login"
DOCKERFILE = EDGE / "keycloak" / "Dockerfile"
REFERENCE_DIR = EDGE / "tests" / "fixtures" / "keycloak-26.8.1"


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


def parse_properties(text: str) -> dict[str, str]:
    props: dict[str, str] = {}
    logical = ""
    for raw in text.splitlines():
        line = raw.strip() if not logical else raw.lstrip()
        if not logical and (not line or line[0] in "#!"):
            continue
        if line.endswith("\\") and not line.endswith("\\\\"):
            logical += line[:-1]
            continue
        logical += line
        m = re.match(r"([^=:\s]+)\s*[=:]\s*(.*)$", logical)
        if m:
            props[m.group(1)] = m.group(2)
        logical = ""
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


_URL = re.compile(r"https?://[^\s\"'<>)]+", re.IGNORECASE)
_XMLNS = re.compile(r'xmlns(?::\w+)?\s*=\s*["\']\s*(https?://[^"\']*)["\']', re.IGNORECASE)
_SCRIPT = re.compile(r"<\s*script\b", re.IGNORECASE)


def external_references(theme: Path) -> list[str]:
    """URL `http(s)://` de cualquier archivo del tema, salvo los URI de espacio de nombres XML (`xmlns`)."""
    bad = []
    for path in theme_files(theme):
        text = path.read_text(encoding="utf-8")
        namespaces = {m.group(1) for m in _XMLNS.finditer(text)}
        for url in _URL.findall(text):
            if url not in namespaces:
                bad.append(f"{path.relative_to(theme)}: {url}")
    return bad


def script_tags(theme: Path) -> list[str]:
    return [str(p.relative_to(theme)) for p in theme_files(theme) if _SCRIPT.search(p.read_text(encoding="utf-8"))]


def message_problems(theme: Path, ref: Path, templates: list[str]) -> list[str]:
    """Claves de `messages_es` que no existen en la referencia y claves exigidas sin traducir."""
    es = parse_properties((theme / "messages" / "messages_es.properties").read_text(encoding="utf-8"))
    problems = [f"clave inexistente en la referencia: {k}" for k in sorted(set(es) - reference_keys(ref))]
    problems += [f"sin traducir: {k}" for k in sorted(required_keys(ref, templates) - {k for k, v in es.items() if v.strip()})]
    return problems


# --- marca ----------------------------------------------------------------------------------

_HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
_COLOR_FN = re.compile(r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(", re.IGNORECASE)
_NAMED = re.compile(
    r"\b(?:white|black|red|green|blue|yellow|orange|purple|pink|gray|grey|silver|navy|teal|maroon|brown|cyan|magenta|"
    r"lime|olive|aqua|fuchsia|gold|indigo|violet|crimson|coral|salmon|tan|beige|ivory)\b",
    re.IGNORECASE,
)


def css_colors(css: str) -> tuple[set[str], list[str]]:
    """(hex en mayusculas, otras formas de color) de las declaraciones y variables del CSS, sin comentarios."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    css = re.sub(r"url\([^)]*\)", "", css)
    css = re.sub(r"\"[^\"]*\"|'[^']*'", "", css)
    hexes = {h.upper() for h in _HEX.findall(css)}
    others = _COLOR_FN.findall(css)
    for decl in re.findall(r":([^;{}]+)", css):
        others += _NAMED.findall(decl)
    return hexes, others


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

def dockerfile_problems(text: str, image: str, digest: str, options: list[str], start: list[str]) -> list[str]:
    """Incumplimientos del Dockerfile frente a INF-U2-08."""
    problems = []
    flat = re.sub(r"\\\n", " ", text)
    flat = re.sub(r"[ \t]+", " ", flat)
    froms = re.findall(r"^FROM (\S+)", flat, re.MULTILINE)
    if froms != [f"{image}@{digest}"]:
        problems.append(f"FROM no es la imagen exacta con su digest: {froms}")
    if not re.search(r"^COPY (?:--\S+ )*themes/vectra \S*/themes/vectra\s*$", flat, re.MULTILINE):
        problems.append("el tema no se copia")
    build = re.search(r"^RUN (?:\S*/)?kc\.sh build ?(.*)$", flat, re.MULTILINE)
    if not build:
        problems.append("falta `kc.sh build`")
    else:
        given = build.group(1).split()
        problems += [f"falta {o} en kc.sh build" for o in options if o not in given]
    cmd = re.search(r"^CMD (\[.*\])\s*$", flat, re.MULTILINE)
    import json

    args = json.loads(cmd.group(1)) if cmd else []
    if args != start or not re.search(r'^ENTRYPOINT \["(?:\S*/)?kc\.sh"\]', flat, re.MULTILINE):
        problems.append(f"el arranque no es `{' '.join(start)}` con kc.sh: {args}")
    return problems
