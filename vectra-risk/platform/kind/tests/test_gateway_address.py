"""U01-T16: `gateway-address.sh` lee la direccion del gateway, comprueba que responde y compara con lo que resuelve el nombre. Solo lectura; kubectl, curl y getent son falsos."""

import os
import re
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get("GATEWAY_ADDRESS_SCRIPT", HERE / "gateway-address.sh"))

KUBECTL = r"""#!/usr/bin/env bash
echo "kubectl $*" >> "$FAKE_DIR/calls.log"
case "$*" in
  *"get svc api-gateway"*"-n vectra-edge"*|*"get service api-gateway"*"-n vectra-edge"*) printf '%s' "$FAKE_ADDRESS" ;;
  *) echo "kubectl falso: orden inesperada: $*" >&2; exit 9 ;;
esac
"""
CURL = r"""#!/usr/bin/env bash
echo "curl $*" >> "$FAKE_DIR/calls.log"
[ "$FAKE_RESPONDS" = si ] || exit 7
printf '404'
"""
GETENT = r"""#!/usr/bin/env bash
echo "getent $*" >> "$FAKE_DIR/calls.log"
[ -n "$FAKE_RESOLVED" ] && echo "$FAKE_RESOLVED      $2"
exit 0
"""


def run(tmp_path: Path, address: str, responds: bool, resolved: str) -> subprocess.CompletedProcess[str]:
    fake = tmp_path / "bin"
    fake.mkdir(exist_ok=True)
    for name, body in (("kubectl", KUBECTL), ("curl", CURL), ("getent", GETENT)):
        (fake / name).write_text(body, encoding="utf-8")
        (fake / name).chmod(0o755)
    env = {"PATH": f"{fake}:/usr/bin:/bin", "FAKE_DIR": str(tmp_path), "FAKE_ADDRESS": address, "FAKE_RESPONDS": "si" if responds else "no", "FAKE_RESOLVED": resolved}
    return subprocess.run([str(SCRIPT)], env=env, capture_output=True, text=True, timeout=30, check=False)


def calls(tmp_path: Path) -> list[str]:
    return (tmp_path / "calls.log").read_text(encoding="utf-8").splitlines()


def test_gateway_address_matches_and_responds(tmp_path: Path):
    result = run(tmp_path, "172.18.0.2", responds=True, resolved="172.18.0.2")
    assert result.returncode == 0, result.stdout + result.stderr
    log = calls(tmp_path)
    assert any(line.startswith("curl") and "--resolve vectra.localtest.me:443:172.18.0.2" in line for line in log)
    assert "/etc/hosts" not in result.stdout + result.stderr or "no hace falta" in (result.stdout + result.stderr).lower()


def test_gateway_address_differs_and_says_which_hosts_line_is_missing(tmp_path: Path):
    result = run(tmp_path, "172.18.0.2", responds=True, resolved="127.0.0.1")
    assert result.returncode != 0
    assert "172.18.0.2 vectra.localtest.me" in result.stdout + result.stderr
    assert "/etc/hosts" in result.stdout + result.stderr


def test_gateway_address_service_without_an_external_address(tmp_path: Path):
    result = run(tmp_path, "", responds=False, resolved="127.0.0.1")
    assert result.returncode != 0
    assert "cloud-provider-kind" in result.stdout + result.stderr
    assert not [line for line in calls(tmp_path) if line.startswith("curl")]  # sin direccion no hay a quien llamar


def test_gateway_address_that_does_not_respond_fails_even_if_it_matches(tmp_path: Path):
    result = run(tmp_path, "172.18.0.2", responds=False, resolved="172.18.0.2")
    assert result.returncode != 0
    assert "no responde" in result.stdout + result.stderr


def test_gateway_address_reads_only_and_sends_no_credentials(tmp_path: Path):
    run(tmp_path, "172.18.0.2", responds=True, resolved="127.0.0.1")
    for line in calls(tmp_path):
        if line.startswith("kubectl"):
            assert re.search(r"\bget\b", line) and not re.search(r"\b(apply|delete|patch|annotate|create|edit|replace|scale)\b", line)
        if line.startswith("curl"):
            assert not re.search(r"(^| )(-u|--user|-H|--header|-d|--data\S*|-X|--request|-K|--config)( |$)", line)


def test_gateway_address_does_not_write_the_hosts_file():
    text = SCRIPT.read_text(encoding="utf-8")
    assert not re.search(r">>? *\S*/etc/hosts|\btee\b|\bsudo\b", text)


def test_gateway_address_refuses_a_context_that_is_not_kind(tmp_path: Path):
    (tmp_path / "kubectl").write_text(f'#!/bin/sh\ntouch "{tmp_path}/llamado"\n', encoding="utf-8")
    (tmp_path / "kubectl").chmod(0o755)
    result = subprocess.run([str(SCRIPT)], env={"PATH": f"{tmp_path}:/usr/bin:/bin", "VECTRA_KIND_CONTEXT": "produccion"}, capture_output=True, text=True, check=False)
    assert result.returncode == 2 and not (tmp_path / "llamado").exists()


@pytest.mark.parametrize("address", ["172.18.0.2"])
def test_gateway_address_uses_the_kind_context(tmp_path: Path, address: str):
    run(tmp_path, address, responds=True, resolved=address)
    assert all("--context kind-vectra" in line for line in calls(tmp_path) if line.startswith("kubectl"))
