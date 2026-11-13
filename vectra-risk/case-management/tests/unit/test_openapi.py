"""Paso 22 (BR-U8-20; P-7 = a): `tools/check_openapi.py`. El OpenAPI exportado coincide con el de la app y con el contrato de U0, y el script termina en 1, sin
escribir nada, cuando difiere. `create_app` registra las rutas con `include_in_schema=False`: el «OpenAPI de la app» es `spec_for` de U0 sobre las rutas que sirve."""

import hashlib
import importlib.util
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from core_banking_mock.app import build_app as build_mock
from fastapi import FastAPI
from vectra_case.app import build_app as build_case

ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / "case-management"
DOCS = CASE / "docs" / "openapi"


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("check_openapi", CASE / "tools" / "check_openapi.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECK = _load()


def apps() -> dict[str, FastAPI]:
    return {"case-service": build_case(), "core-banking-mock": build_mock()}


def snapshot(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob("*"))}


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    target = tmp_path / "openapi"
    shutil.copytree(DOCS, target)
    return target


def test_the_versioned_export_is_the_one_of_the_apps_and_of_the_u0_contract() -> None:
    assert CHECK.main([], apps()) == 0
    assert len(CHECK.served(build_case())) == 9 and len(CHECK.served(build_mock())) == 2
    for service in CHECK.SERVICES:
        # exportado == lo que sirve la app == `contracts/openapi/<servicio>.yaml`, byte a byte (el contrato lo genera `spec_for` sobre REGISTRY)
        assert (DOCS / f"{service}.yaml").read_bytes().rstrip(b"\n") == (
            ROOT / "contracts" / "openapi" / f"{service}.yaml"
        ).read_bytes().rstrip(b"\n")


def test_the_exported_file_edited_by_hand_ends_in_1_and_writes_nothing(
    docs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = docs / "case-service.yaml"
    document = yaml.safe_load(target.read_text(encoding="utf-8"))
    del document["paths"]["/v1/cases/{id}/retry"]
    target.write_text(yaml.safe_dump(document, sort_keys=True, allow_unicode=True), encoding="utf-8")
    before = snapshot(docs)
    assert CHECK.main(["--docs", str(docs)], apps()) == 1
    assert "difiere del OpenAPI de la app" in capsys.readouterr().out
    assert snapshot(docs) == before


def test_a_missing_exported_file_ends_in_1_and_writes_nothing(docs: Path) -> None:
    (docs / "core-banking-mock.yaml").unlink()
    before = snapshot(docs)
    assert CHECK.main(["--docs", str(docs)], apps()) == 1
    assert snapshot(docs) == before and not (docs / "core-banking-mock.yaml").exists()


def test_an_app_missing_a_route_of_the_contract_ends_in_1(
    docs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = build_case()
    app.router.routes[:] = [
        r for r in app.router.routes if getattr(r, "path", "") != "/v1/cases/{id}/decision"
    ]
    before = snapshot(docs)
    assert CHECK.main(["--docs", str(docs)], {**apps(), "case-service": app}) == 1
    out = capsys.readouterr().out
    assert "la app no sirve POST /v1/cases/{id}/decision, que es del contrato" in out
    assert snapshot(docs) == before


def test_an_app_serving_a_route_the_contract_does_not_have_ends_in_1(
    docs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    app = build_mock()

    async def extra() -> dict[str, str]:
        return {}

    app.add_api_route("/v1/credits/{id}/close", extra, methods=["PUT"], include_in_schema=False)
    before = snapshot(docs)
    assert CHECK.main(["--docs", str(docs)], {**apps(), "core-banking-mock": app}) == 1
    assert "la app sirve PUT /v1/credits/{id}/close, que el contrato no tiene" in capsys.readouterr().out
    assert snapshot(docs) == before


def test_write_regenerates_the_export_and_it_is_the_only_mode_that_writes(tmp_path: Path) -> None:
    target = tmp_path / "nuevo"
    assert CHECK.main(["--docs", str(target)], apps()) == 1 and not target.exists()
    assert CHECK.main(["--write", "--docs", str(target)], apps()) == 0
    assert snapshot(target) == snapshot(DOCS)
    assert CHECK.main(["--docs", str(target)], apps()) == 0
