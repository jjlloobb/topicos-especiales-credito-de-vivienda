"""BR-U0-90..93."""

import json
import stat
from pathlib import Path

import tomllib

import vectra_common
import vectra_contracts
from tools.version_gate import main as gate
from vectra_contracts.routes import REGISTRY

ROOT = Path(__file__).resolve().parents[3]


def fake_oasdiff(tmp_path: Path, code: int) -> str:
    path = tmp_path / "oasdiff"
    path.write_text(f"#!/bin/sh\necho \"$@\" > {tmp_path}/args\nexit {code}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def args(tool, base="0.1.0", head="0.1.0"):
    return ["--base", "a.yaml", "--head", "b.yaml", "--base-version", base, "--head-version", head, "--oasdiff", tool]


def test_br_u0_90_single_version():
    py = [tomllib.loads((ROOT / f"contracts/python/{p}/pyproject.toml").read_text())["project"]["version"] for p in ("vectra_contracts", "vectra_common")]
    ts = json.loads((ROOT / "contracts/ts/package.json").read_text())["version"]
    assert {*py, ts, vectra_contracts.__version__, vectra_common.__version__} == {"0.1.0"}


def test_br_u0_91_breaking_requires_major(tmp_path):
    tool = fake_oasdiff(tmp_path, 1)
    assert gate(args(tool)) == 1
    assert gate(args(tool, head="1.0.0")) == 0


def test_br_u0_92_invokes_oasdiff_and_propagates(tmp_path):
    tool = fake_oasdiff(tmp_path, 3)
    assert gate(args(tool)) == 3
    assert (tmp_path / "args").read_text().split() == ["breaking", "--fail-on", "ERR", "a.yaml", "b.yaml"]
    assert gate(args(fake_oasdiff(tmp_path, 0))) == 0
    assert gate(args(str(tmp_path / "no-existe"))) == 2


def test_br_u0_93_no_spec_without_contract():
    specs = {p.stem for p in (ROOT / "contracts/openapi").glob("*.yaml")}
    assert specs == set(REGISTRY)
