"""Politicas HCL versionadas de la boveda (Paso 12 acotado a la demo; P-U3-08; NFR-U3-40, 42).

Solo las identidades de checkpoint y archivo firman (`update` sobre `transit/sign/...`); la API y el agregador no tienen ninguna
capacidad; `registry-verify` solo lee la llave publica. Sin comodines. Se analizan los archivos HCL tal como estan en
`decision-registry/vault-policies/` (la forma de los `path "..." { capabilities = [...] }` es la unica que usan).
"""

import re
import sys
from pathlib import Path

import pytest

POLICIES = Path(__file__).resolve().parents[2] / "vault-policies"
KEY = "registry-checkpoints"
SIGNERS = {"registry-checkpoint", "registry-archive"}
READERS = {"registry-verify"}
NONE = {"decision-registry-service", "registry-aggregator"}
IDENTITIES = SIGNERS | READERS | NONE
BLOCK = re.compile(r'path\s+"([^"]+)"\s*\{(.*?)\}', re.S)
CAPABILITIES = re.compile(r"capabilities\s*=\s*\[(.*?)\]", re.S)


def parse(name: str) -> dict[str, set[str]]:
    """`{ruta: {capacidades}}` de una politica; los comentarios (`#`) no cuentan."""
    text = "\n".join(line.split("#", 1)[0] for line in (POLICIES / f"{name}.hcl").read_text().splitlines())
    paths: dict[str, set[str]] = {}
    for path, body in BLOCK.findall(text):
        match = CAPABILITIES.search(body)
        assert match, f"{name}: {path} sin capabilities"
        paths[path] = set(re.findall(r'"([^"]+)"', match.group(1)))
    return paths


def can_sign(name: str) -> bool:
    return any("/sign/" in path and caps & {"update", "create"} for path, caps in parse(name).items())


def test_hay_una_politica_por_identidad_y_ninguna_otra() -> None:
    assert {p.stem for p in POLICIES.glob("*.hcl")} == IDENTITIES


@pytest.mark.parametrize("name", sorted(SIGNERS))
def test_solo_checkpoint_y_archivo_tienen_sign(name: str) -> None:
    assert parse(name)[f"transit/sign/{KEY}"] == {"update"}
    assert can_sign(name)


@pytest.mark.parametrize("name", sorted(READERS | NONE))
def test_las_demas_identidades_no_firman(name: str) -> None:
    assert not can_sign(name)


@pytest.mark.parametrize("name", sorted(NONE))
def test_la_api_y_el_agregador_no_tienen_ninguna_capacidad(name: str) -> None:
    assert parse(name) == {}


def test_registry_verify_solo_lee_la_llave_publica() -> None:
    assert parse("registry-verify") == {f"transit/keys/{KEY}": {"read"}}


@pytest.mark.parametrize("name", sorted(IDENTITIES))
def test_sin_comodines_ni_capacidades_de_mas(name: str) -> None:
    for path, caps in parse(name).items():
        assert not re.search(r"[*+]", path), f"{name}: comodin en {path}"
        assert path in {f"transit/sign/{KEY}", f"transit/keys/{KEY}"}, f"{name}: ruta fuera de la llave de checkpoints"
        assert caps <= {"update", "read"}, f"{name}: {path} concede {caps - {'update', 'read'}}"


def test_el_parser_ve_un_sign_que_se_cuela(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """El analisis detecta lo que dice detectar: una politica de la API con `sign` se ve como firmante."""
    (tmp_path / "decision-registry-service.hcl").write_text(
        'path "transit/sign/registry-checkpoints" {\n  capabilities = ["update"]\n}\n'
    )
    monkeypatch.setattr(sys.modules[__name__], "POLICIES", tmp_path)
    assert can_sign("decision-registry-service")
