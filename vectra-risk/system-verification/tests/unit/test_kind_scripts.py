"""Los guiones de lectura de `docs/kind/` contra un `kubectl`, un `free` y un `docker` de mentira (U12-T06, CA-5).

Cada guion corre **de verdad** (el ejecutable de `sh`, con su salida completa) contra `tests/doubles/kind_kubectl_bin.py`: nunca contra el `kubectl` del host ni contra un cluster. Lo que se comprueba es
lo que el revisor encontro en las guias anteriores (`revisiones/U04-T07/ronda-1.md`): un guion que nunca corrio contra nada real perdia la entrada (F-01), los objetivos que se saltaban en silencio con
codigo 0 (F-02), una espera fija con carrera (F-04), las fechas incrustadas (F-05) y una unidad de memoria que solo entendia una forma (`CANDIDATAS.md`, linea 388).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import kind_docs as kd
import kind_kubectl_bin
import pytest
import yaml
from vectra_verification import evidence

KIND = kd.KIND_DOCS
SCRIPTS = ("arranque.sh", "observabilidad.sh", "memoria.sh", "identidad.sh", "estado-final.sh")
ALLOWED_VERBS = {"get", "logs", "port-forward", "auth"}
FREE = "              total        used        free      shared  buff/cache   available\nMem:          15171        8679        1386         592        6045        {available}\nSwap:          4095        1774        2321\n"
DOCKER = "vectra-control-plane 2.1GiB / 14.8GiB 14.2%\nvectra-worker 1.9GiB / 14.8GiB 12.8%\nkind-registry 20MiB / 14.8GiB 0.1%\notro-contenedor 1GiB / 14.8GiB 7%\n"
SECRET = "Zx9-no-debe-aparecer-1234567890"  # noqa: S105
SEED = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"


def pod(name: str, **kw: Any) -> dict[str, Any]:
    ready = kw.get("ready", True)
    waiting = kw.get("waiting")
    state: dict[str, Any] = {"waiting": {"reason": waiting}} if waiting else {"running": {}}
    container: dict[str, Any] = {
        "name": "app",
        "ready": ready and not waiting,
        "restartCount": kw.get("restarts", 0),
        "state": state,
    }
    if "last_exit" in kw:
        container["lastState"] = {
            "terminated": {"exitCode": kw["last_exit"], "reason": kw.get("last_reason", "Completed")}
        }
    return {
        "metadata": {"name": name, "namespace": kw.get("namespace", "vectra-app")},
        "spec": {
            "containers": [
                {
                    "name": "app",
                    "resources": {"requests": {"memory": kw["request"]}} if "request" in kw else {},
                }
            ]
        },
        "status": {"phase": kw.get("phase", "Running"), "containerStatuses": [container]},
    }


def listing(items: list[dict[str, Any]]) -> str:
    return json.dumps({"items": items})


def external_secret(name: str, namespace: str = "vectra-app", reason: str = "SecretSynced") -> dict[str, Any]:
    status = "True" if reason == "SecretSynced" else "False"
    return {
        "metadata": {"name": name, "namespace": namespace},
        "status": {"conditions": [{"type": "Ready", "status": status, "reason": reason}]},
    }


def application(name: str, sync: str = "Synced", health: str = "Healthy") -> dict[str, Any]:
    return {"metadata": {"name": name}, "status": {"sync": {"status": sync}, "health": {"status": health}}}


def healthy_state(**over: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "rules": [
            {
                "match": ["get", "pods", "-n", "vectra-app", "-o", "json"],
                "stdout": listing([pod("case-service-0")]),
            },
            {
                "match": ["get", "pods", "-n", "vectra-edge", "-o", "json"],
                "stdout": listing([pod("envoy-0", namespace="vectra-edge")]),
            },
            {
                "match": ["get", "externalsecret", "-A"],
                "stdout": listing([external_secret("case-service-client")]),
            },
            {
                "match": ["get", "applications.argoproj.io"],
                "stdout": listing([application("case-management"), application("kyverno", sync="OutOfSync")]),
            },
            {
                "match": ["get", "pods", "-n", "linkerd-cni", "-o", "json"],
                "stdout": listing([pod("linkerd-cni-a", namespace="linkerd-cni")]),
            },
        ],
    }
    state.update(over)
    return state


def lay_out(tmp_path: Path) -> Path:
    """Una copia de `docs/kind/` y de `demos/verify/lib.sh` con la misma posicion relativa (`../../demos/verify`): sobre ella se prueban las mutaciones."""
    root = tmp_path / "copy"
    shutil.copytree(KIND, root / "docs" / "kind", ignore=shutil.ignore_patterns("inventario.yaml"))
    (root / "demos" / "verify").mkdir(parents=True)
    shutil.copy(kd.SYSTEM / "demos/verify/lib.sh", root / "demos/verify/lib.sh")
    return root / "docs" / "kind"


def run(
    script: str,
    args: list[str],
    tmp_path: Path,
    state: dict[str, Any],
    *,
    free: str = "",
    docker: str = "",
    env: dict[str, str] | None = None,
    where: Path = KIND,
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    shutil.rmtree(bin_dir, ignore_errors=True)
    variables = kind_kubectl_bin.install(
        bin_dir, state, free_text=free or FREE.format(available=9000), docker_text=docker or DOCKER
    )
    return subprocess.run(
        ["sh", str(where / script), *args],
        env={**os.environ, **variables, "TMPDIR": str(tmp_path), **(env or {})},
        capture_output=True, text=True, timeout=120, check=False,
    )  # fmt: skip


def verbs(tmp_path: Path) -> set[str]:
    found = set()
    for call in kind_kubectl_bin.calls(tmp_path / "bin"):
        args = [a for a in call[1:]]
        if args[:1] == ["--context"]:
            args = args[2:]
        found.add(" ".join(args[:2]) if args[0] == "auth" else args[0])
    return found


# --- lo que se comprueba de todos -------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("script", SCRIPTS)
def test_every_script_exists_is_executable_and_has_no_fixed_wait_or_date(script: str) -> None:
    path = KIND / script
    text = path.read_text(encoding="utf-8")
    assert os.access(path, os.X_OK)
    assert text.startswith("#!/bin/sh")
    assert not re.search(r"\bsleep\b", text), "F-04: nada de esperas fijas en los guiones"
    assert not re.search(r"20\d\d-\d\d-\d\d|\b20\d{6}-\d{4}\b", text), "F-05: sin fechas ni runId incrustados"
    assert "kubectl --context" in text or "open_prom" in text
    assert not re.search(r"port-forward[^\n]*\bsvc/", text), (
        "INF-U12-03: port-forward a un pod, nunca a svc/..."
    )


# --- arranque.sh --------------------------------------------------------------------------------------------------------------------------------------


def test_arranque_on_a_healthy_state_is_0_and_asks_only_for_the_four_verbs(tmp_path: Path) -> None:
    done = run("arranque.sh", ["vectra-app", "vectra-edge"], tmp_path, healthy_state())
    assert done.returncode == 0, done.stdout + done.stderr
    assert "sin hallazgos" in done.stdout
    assert (
        "AVISO Application kyverno: OutOfSync" in done.stdout
    )  # una Application OutOfSync es un aviso, no un fallo
    assert verbs(tmp_path) <= ALLOWED_VERBS


def test_arranque_strict_fails_on_an_outofsync_application(tmp_path: Path) -> None:
    done = run("arranque.sh", ["--estricto", "vectra-app"], tmp_path, healthy_state())
    assert done.returncode == 1 and "FALLA Application kyverno" in done.stdout


@pytest.mark.parametrize(
    ("broken", "needle"),
    [
        (pod("scoring-0", waiting="ImagePullBackOff"), "ImagePullBackOff"),
        (pod("scoring-0", waiting="CreateContainerConfigError"), "CreateContainerConfigError"),
        (pod("worker-0", restarts=4, last_exit=0), "salio con codigo 0 y sin mensaje"),
        (pod("bff-0", restarts=2, last_exit=137, last_reason="OOMKilled"), "OOMKilled"),
        (pod("db-0", phase="Pending", ready=False), "fase Pending"),
        (pod("x-0", ready=False), "contenedores no listos"),
    ],
)
def test_arranque_reports_each_broken_pod_and_exits_non_zero(
    tmp_path: Path, broken: dict[str, Any], needle: str
) -> None:
    state = healthy_state()
    state["rules"][0] = {
        "match": ["get", "pods", "-n", "vectra-app", "-o", "json"],
        "stdout": listing([pod("ok-0"), broken]),
    }
    done = run("arranque.sh", ["vectra-app"], tmp_path, state)
    assert done.returncode == 1, done.stdout + done.stderr
    assert needle in done.stdout and broken["metadata"]["name"] in done.stdout


def test_arranque_reports_an_externalsecret_that_is_not_synced_and_an_unhealthy_application(
    tmp_path: Path,
) -> None:
    state = healthy_state()
    state["rules"][2] = {
        "match": ["get", "externalsecret", "-A"],
        "stdout": listing([external_secret("case-service-client", reason="SecretSyncedError")]),
    }
    assert run("arranque.sh", ["vectra-app"], tmp_path, state).returncode == 1
    state = healthy_state()
    state["rules"][3] = {
        "match": ["get", "applications.argoproj.io"],
        "stdout": listing([application("governance", health="Degraded")]),
    }
    done = run("arranque.sh", ["vectra-app"], tmp_path, state)
    assert done.returncode == 1 and "Application governance: salud Degraded" in done.stdout


def test_arranque_always_reads_linkerd_cni_and_points_to_the_inotify_limit(tmp_path: Path) -> None:
    """F-04 (1): la Application `linkerd-cni` puede verse `Healthy` mientras sus pods fallan por `too many open files`; el guion los lee aunque el operador no pida el namespace."""
    state = healthy_state()
    state["rules"].insert(
        0,
        {
            "match": ["get", "pods", "-n", "linkerd-cni", "-o", "json"],
            "stdout": listing(
                [pod("linkerd-cni-x", namespace="linkerd-cni", restarts=840, waiting="CrashLoopBackOff")]
            ),
        },
    )
    done = run("arranque.sh", ["vectra-app"], tmp_path, state)
    assert done.returncode == 1, done.stdout + done.stderr
    assert "linkerd-cni/linkerd-cni-x [app]: CrashLoopBackOff" in done.stdout and "inotify" in done.stdout
    assert run("arranque.sh", ["vectra-app", "linkerd-cni"], tmp_path, healthy_state()).returncode == 0


@pytest.mark.parametrize("exit_code", [0, 137, 255])
def test_arranque_flags_a_restarted_vault_pod_whatever_its_exit_code(tmp_path: Path, exit_code: int) -> None:
    """F-04 (2): un reinicio de la máquina deja la bóveda (que guarda todo en memoria) vacía y un código de salida cualquiera: el diagnóstico de K-05 la marca por el reinicio, no por el código."""
    state = healthy_state()
    state["rules"].insert(
        0,
        {
            "match": ["get", "pods", "-n", "vault", "-o", "json"],
            "stdout": listing([pod("vault-0", namespace="vault", restarts=1, last_exit=exit_code)]),
        },
    )
    done = run("arranque.sh", ["vault"], tmp_path, state)
    assert done.returncode == 1, done.stdout + done.stderr
    assert "vault/vault-0 [app]: la boveda se reinicio" in done.stdout and "seed-vault.sh" in done.stdout
    state["rules"][0]["stdout"] = listing([pod("vault-0", namespace="vault")])
    assert run("arranque.sh", ["vault"], tmp_path, state).returncode == 0


def arranque_exit_with_kubectl_down(where: Path, tmp_path: Path) -> int:
    state = {"rules": [{"match": ["get"], "stderr": "Unable to connect to the server\n", "rc": 1}]}
    return run("arranque.sh", ["vectra-app"], tmp_path, state, where=where).returncode


def test_arranque_when_kubectl_fails_exits_2_and_says_so_not_0(tmp_path: Path) -> None:
    done = run(
        "arranque.sh",
        ["vectra-app"],
        tmp_path,
        {"rules": [{"match": ["get"], "stderr": "Unable to connect\n", "rc": 1}]},
    )
    assert done.returncode == 2 and "NO SE PUDO LEER" in done.stderr


def test_red_a_script_that_swallows_the_kubectl_error_is_caught(tmp_path: Path) -> None:
    """Rojo de CA-5 (F-02 de U04-T07): un guion que captura el error de `kubectl` y sale con 0 hace fallar `test_arranque_when_kubectl_fails_exits_2_and_says_so_not_0`."""
    where = lay_out(tmp_path)
    mutated = (
        (where / "arranque.sh")
        .read_text(encoding="utf-8")
        .replace('|| cannot_read "no se pudo leer los pods de $NS: $(head -c 200 "$TMP_DIR/err")"', "|| true")
    )
    mutated = mutated.replace(
        '|| cannot_read "no se pudo leer los ExternalSecret: $(head -c 200 "$TMP_DIR/err")"', "|| true"
    )
    mutated = mutated.replace(
        '|| cannot_read "no se pudo leer las Applications: $(head -c 200 "$TMP_DIR/err")"', "|| true"
    )
    assert "|| true" in mutated
    (where / "arranque.sh").write_text(mutated, encoding="utf-8")
    state = {"rules": [{"match": ["get"], "stderr": "Unable to connect\n", "rc": 1}]}
    # el guion roto da 0 con el cluster caido (es lo que la prueba de arriba no deja pasar); el real da 2
    assert run("arranque.sh", ["vectra-app"], tmp_path, state, where=where).returncode != 2
    assert run("arranque.sh", ["vectra-app"], tmp_path, state).returncode == 2


# --- observabilidad.sh -------------------------------------------------------------------------------------------------------------------------------


def rules_group() -> list[dict[str, Any]]:
    alerts = [
        {"name": n, "type": "alerting"}
        for n in ("CoreWriteAttempt", "FailClosedPersistente", "ProductMetricsStale")
    ]
    return [{"name": "vectra-app", "rules": alerts + [{"name": "r", "type": "recording"}]}]


def target(job: str, namespace: str, health: str = "up") -> dict[str, Any]:
    return {
        "labels": {"job": job, "namespace": namespace},
        "health": health,
        "lastError": "" if health == "up" else "connection refused",
    }


PROM_POD = {
    "match": ["get", "pods", "-n", "vectra-observability", "-l", "app.kubernetes.io/name=prometheus"],
    "stdout": "pod/prometheus-0\n",
}


def test_observabilidad_port_forwards_to_one_pod_never_a_service(tmp_path: Path) -> None:
    state = {"rules": [PROM_POD], "prom_rules": rules_group()}
    done = run("observabilidad.sh", ["reglas"], tmp_path, state)
    assert done.returncode == 0, done.stdout + done.stderr
    forwards = [c for c in kind_kubectl_bin.calls(tmp_path / "bin") if "port-forward" in c]
    assert (
        len(forwards) == 1
        and "pod/prometheus-0" in forwards[0]
        and not any(a.startswith("svc/") for a in forwards[0])
    )
    assert verbs(tmp_path) <= ALLOWED_VERBS


def test_observabilidad_reglas_fails_when_an_alert_is_not_loaded(tmp_path: Path) -> None:
    state = {
        "rules": [PROM_POD],
        "prom_rules": [{"name": "g", "rules": [{"name": "CoreWriteAttempt", "type": "alerting"}]}],
    }
    done = run("observabilidad.sh", ["reglas"], tmp_path, state)
    assert done.returncode == 1 and "FALLA la alerta FailClosedPersistente no esta cargada" in done.stdout


def test_observabilidad_targets_needs_the_linkerd_proxy_of_the_mock_up(tmp_path: Path) -> None:
    good = {
        "rules": [PROM_POD],
        "prom_targets": [target("linkerd-proxy", "vectra-mock"), target("case-service", "vectra-app")],
    }
    assert run("observabilidad.sh", ["targets"], tmp_path, good).returncode == 0
    missing = {"rules": [PROM_POD], "prom_targets": [target("case-service", "vectra-app")]}
    done = run("observabilidad.sh", ["targets"], tmp_path, missing)
    assert done.returncode == 1 and "linkerd-proxy de vectra-mock no esta up" in done.stdout
    down = {"rules": [PROM_POD], "prom_targets": [target("linkerd-proxy", "vectra-mock", "down")]}
    assert run("observabilidad.sh", ["targets"], tmp_path, down).returncode == 1


def test_observabilidad_serie_prints_the_real_label_set_and_fails_without_the_series(tmp_path: Path) -> None:
    name = "inbound_http_authz_deny_total"
    labels = {
        "__name__": name,
        "namespace": "vectra-mock",
        "route_name": "core-mock-catch-all",
        "pod": "core-mock-0",
    }
    done = run(
        "observabilidad.sh", ["serie", name], tmp_path, {"rules": [PROM_POD], "prom_series": {name: [labels]}}
    )
    assert (
        done.returncode == 0
        and 'namespace="vectra-mock"' in done.stdout
        and 'route_name="core-mock-catch-all"' in done.stdout
    )
    assert run("observabilidad.sh", ["serie", name], tmp_path, {"rules": [PROM_POD]}).returncode == 1


def test_observabilidad_consulta_prints_series_and_an_empty_result_is_not_an_error(tmp_path: Path) -> None:
    expr = 'ALERTS{alertname="CoreWriteAttempt"}'
    firing = {
        "rules": [PROM_POD],
        "prom_query": {
            expr: [{"metric": {"alertname": "CoreWriteAttempt", "alertstate": "firing"}, "value": [0, "1"]}]
        },
    }
    done = run("observabilidad.sh", ["consulta", expr], tmp_path, firing)
    assert (
        done.returncode == 0 and 'alertstate="firing"' in done.stdout and done.stdout.strip().endswith(" 1")
    )
    empty = run("observabilidad.sh", ["consulta", expr], tmp_path, {"rules": [PROM_POD]})
    assert empty.returncode == 0 and "sin resultados" in empty.stdout


def test_observabilidad_a_dead_port_forward_is_a_clear_error_with_no_silent_retry(tmp_path: Path) -> None:
    done = run("observabilidad.sh", ["reglas"], tmp_path, {"rules": [PROM_POD], "pf_fails": True})
    assert done.returncode == 2 and "el port-forward a Prometheus cayo" in done.stderr
    assert len([c for c in kind_kubectl_bin.calls(tmp_path / "bin") if "port-forward" in c]) == 1


def test_observabilidad_prometheus_down_and_a_bad_use_exit_2(tmp_path: Path) -> None:
    assert (
        run("observabilidad.sh", ["reglas"], tmp_path, {"rules": [PROM_POD], "prom_down": True}).returncode
        == 2
    )
    assert run("observabilidad.sh", [], tmp_path, {}).returncode == 2
    assert run("observabilidad.sh", ["borrar"], tmp_path, {"rules": [PROM_POD]}).returncode == 2


# --- memoria.sh ---------------------------------------------------------------------------------------------------------------------------------------


def mem_state(pods: list[dict[str, Any]], working: dict[str, int]) -> dict[str, Any]:
    result = [
        {"metric": {"namespace": "vectra-app", "pod": name}, "value": [0, str(value)]}
        for name, value in working.items()
    ]
    return {
        "rules": [PROM_POD, {"match": ["get", "pods", "-A", "-o", "json"], "stdout": listing(pods)}],
        "prom_query": {"container_memory_working_set_bytes": result},
    }


def test_memoria_normalizes_ki_mi_gi_and_bytes_and_marks_a_pod_over_its_request(tmp_path: Path) -> None:
    pods = [
        pod("a-0", request="262144Ki"),
        pod("b-0", request="256Mi"),
        pod("c-0", request="1Gi"),
        pod("d-0", request="268435456"),
    ]
    working = {"a-0": 100 * 2**20, "b-0": 300 * 2**20, "c-0": 512 * 2**20, "d-0": 10 * 2**20}
    done = run("memoria.sh", ["despues"], tmp_path, mem_state(pods, working))
    assert done.returncode == 0, done.stdout + done.stderr
    assert "vectra-app/a-0: 100 MiB de trabajo, request 256 MiB" in done.stdout
    assert "vectra-app/b-0: 300 MiB de trabajo, request 256 MiB  SOBRE EL REQUEST" in done.stdout
    assert "vectra-app/c-0: 512 MiB de trabajo, request 1024 MiB" in done.stdout
    assert "vectra-app/d-0: 10 MiB de trabajo, request 256 MiB" in done.stdout
    assert "vectra-control-plane" in done.stdout and "otro-contenedor" not in done.stdout


def test_memoria_gate_antes_needs_8_gib_and_durante_1_5_gib(tmp_path: Path) -> None:
    state = mem_state([pod("a-0", request="128Mi")], {"a-0": 2**20})
    low = FREE.format(available=4000)
    assert run("memoria.sh", ["antes"], tmp_path, state, free=low).returncode == 1
    assert run("memoria.sh", ["durante"], tmp_path, state, free=low).returncode == 0
    assert run("memoria.sh", ["durante"], tmp_path, state, free=FREE.format(available=1000)).returncode == 1
    assert run("memoria.sh", ["antes"], tmp_path, state, free=FREE.format(available=9000)).returncode == 0


def test_memoria_reports_an_oomkilled_pod_and_never_uses_kubectl_top(tmp_path: Path) -> None:
    state = mem_state(
        [pod("a-0", request="128Mi", restarts=1, last_exit=137, last_reason="OOMKilled")], {"a-0": 2**20}
    )
    done = run("memoria.sh", ["despues"], tmp_path, state)
    assert done.returncode == 1 and "OOMKilled: vectra-app/a-0" in done.stdout
    assert "top" not in verbs(tmp_path) and verbs(tmp_path) <= ALLOWED_VERBS


def test_memoria_bad_use_and_unreadable_free_exit_2(tmp_path: Path) -> None:
    assert run("memoria.sh", ["hoy"], tmp_path, {}).returncode == 2
    assert run("memoria.sh", ["antes"], tmp_path, mem_state([], {}), free="Mem: ?\n").returncode == 2


# --- identidad.sh -------------------------------------------------------------------------------------------------------------------------------------

NO_K16 = ("vectra-mock", "vectra-staging", "secrets", "networkpolicies")


def identity_state(**over: Any) -> dict[str, Any]:
    names = {
        f"SYNTH_{u.upper().replace('-', '_')}_{s}": SECRET
        for u in (
            "analista-1",
            "analista-2",
            "ingeniero-1",
            "cro-1",
            "cro-2",
            "cumplimiento-1",
            "cumplimiento-2",
        )
        for s in ("PASSWORD", "TOTP_SEED")
    }
    names["SYNTH_ANALISTA_1_TOTP_SEED"] = SEED
    state: dict[str, Any] = {
        "rules": [
            *[{"match": ["auth", "can-i", word], "stdout": "no\n", "rc": 1} for word in NO_K16],
            {"match": ["auth", "can-i"], "stdout": "yes\n"},
            {"match": ["get", "job", "keycloak-config-cli"], "stdout": "1"},
            {
                "match": ["logs", "job/keycloak-config-cli"],
                "stdout": "INFO Importing file\nWARN Password policy violation: Password was NOT updated\n",
            },
            {"match": ["get", "pods", "-n", "vault"], "stdout": "pod/vault-0\n"},
        ],
        "vault_keys": names,
    }
    state.update(over)
    return state


def test_identidad_all_good_prints_no_secret_and_passes_the_evidence_filter(tmp_path: Path) -> None:
    done = run("identidad.sh", [], tmp_path, identity_state(), env={"VAULT_TOKEN": "root"})
    assert done.returncode == 0, done.stdout + done.stderr
    assert "AVISO el log trae 'Password policy violation" in done.stdout
    assert "identity/synthetic-users: 14 claves (solo nombres)" in done.stdout
    for text in (done.stdout, done.stderr):
        assert SECRET not in text and SEED not in text
        evidence.ensure_clean(text, [SECRET, SEED])
    assert verbs(tmp_path) <= ALLOWED_VERBS | {"auth can-i"}


def test_identidad_uses_the_k16_group_and_the_table_matches_k16(tmp_path: Path) -> None:
    run("identidad.sh", [], tmp_path, identity_state(), env={"VAULT_TOKEN": "root"})
    cans = [c for c in kind_kubectl_bin.calls(tmp_path / "bin") if "can-i" in c]
    assert cans and all(
        "--as-group=vectra-verification-operators" in c and "--as=operador" in c for c in cans
    )
    k16 = {
        (d["metadata"]["namespace"], r, v)
        for d in yaml.safe_load_all(kd.read("platform/rbac/verification-operator/k16.yaml"))
        if d["kind"] == "Role"
        for rule in d["rules"]
        for r in rule["resources"]
        for v in rule["verbs"]
    }
    for line in (KIND / "identidad.sh").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"check (yes|no) (\w+) (\S+) (\S+)", line)
        if not match:
            continue
        expected, verb, resource, namespace = match.groups()
        resource_name = resource.split(".")[0]
        verb_name = "create" if resource == "pods/portforward" else verb
        assert ((namespace, resource_name, verb_name) in k16) == (expected == "yes"), line


def test_identidad_a_k16_mismatch_a_missing_key_and_a_job_that_did_not_finish_fail(tmp_path: Path) -> None:
    wrong = identity_state()
    wrong["rules"].insert(0, {"match": ["auth", "can-i", "get", "jobs"], "stdout": "no\n", "rc": 1})
    done = run("identidad.sh", [], tmp_path, wrong, env={"VAULT_TOKEN": "root"})
    assert done.returncode == 1 and "FALLA K16 get jobs en vectra-app" in done.stdout
    missing = identity_state()
    del missing["vault_keys"]["SYNTH_CUMPLIMIENTO_2_PASSWORD"]
    done = run("identidad.sh", [], tmp_path, missing, env={"VAULT_TOKEN": "root"})
    assert done.returncode == 1 and "FALLA falta la clave SYNTH_CUMPLIMIENTO_2_PASSWORD" in done.stdout
    unfinished = identity_state()
    unfinished["rules"].insert(0, {"match": ["get", "job", "keycloak-config-cli"], "stdout": ""})
    done = run("identidad.sh", [], tmp_path, unfinished, env={"VAULT_TOKEN": "root"})
    assert done.returncode == 1 and "el Job keycloak-config-cli no termino" in done.stdout


def test_identidad_without_a_vault_token_or_with_a_wrong_one_exits_2(tmp_path: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k != "VAULT_TOKEN"}
    done = subprocess.run(
        ["sh", str(KIND / "identidad.sh")],
        env={**env, **kind_kubectl_bin.install(tmp_path / "bin", identity_state())},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert done.returncode == 2 and "falta VAULT_TOKEN" in done.stderr
    assert run("identidad.sh", [], tmp_path, identity_state(), env={"VAULT_TOKEN": "otro"}).returncode == 2


def test_identidad_a_dead_vault_port_forward_is_a_clear_error(tmp_path: Path) -> None:
    done = run("identidad.sh", [], tmp_path, identity_state(pf_fails=True), env={"VAULT_TOKEN": "root"})
    assert done.returncode == 2 and "el port-forward a la boveda cayo" in done.stderr


def test_identidad_waits_for_a_port_forward_that_takes_half_a_second(tmp_path: Path) -> None:
    """F-01: un `kubectl port-forward` real tarda más de 0,2 s en imprimir `Forwarding from`; el sondeo espera (con plazo) y no se rinde en 100 ms."""
    done = run("identidad.sh", [], tmp_path, identity_state(pf_delay=0.5), env={"VAULT_TOKEN": "root"})
    assert done.returncode == 0, done.stdout + done.stderr
    assert "sin hallazgos" in done.stdout


def test_identidad_gives_up_with_2_by_its_deadline_when_the_port_forward_never_opens(tmp_path: Path) -> None:
    started = time.monotonic()
    done = run("identidad.sh", [], tmp_path, identity_state(pf_never=True), env={"VAULT_TOKEN": "root"})
    elapsed = time.monotonic() - started
    assert done.returncode == 2 and "el port-forward a la boveda no abrio" in done.stderr, done.stderr
    assert 5 < elapsed < 60, f"el plazo es de ≈ 10 s, no {elapsed:.1f} s"


# --- estado-final.sh ----------------------------------------------------------------------------------------------------------------------------------

F22_RESOURCES = (
    "allow-f22-explainability-service-to-explainer-egress",
    "allow-f22-to-explainer-ingress",
    "f22-explainer-8080",
    "f22-explainer-8080-mtls",
    "explainer-8080",
)
GOOD_MODELS = json.dumps(
    [{"model_version_id": "mv-ref", "state": "activo"}, {"model_version_id": "mv-proxy", "state": "inactivo"}]
)


def final_state(**over: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "rules": [
            {"match": ["get", "inferenceservices.serving.kserve.io", "vectra-staging"], "stdout": ""},
            {
                "match": ["get", "inferenceservices.serving.kserve.io", "vectra-serving"],
                "stdout": "inferenceservice.serving.kserve.io/isvc-aaaa1111\n",
            },
            *[{"match": ["get", name], "stdout": f"x/{name}\n"} for name in F22_RESOURCES],
            PROM_POD,
        ],
        "prom_query": {
            "vectra_cases_failclosed_persistent": [{"metric": {}, "value": [0, "5"]}],
            "ALERTS": [{"metric": {"alertname": "FailClosedPersistente"}, "value": [0, "1"]}],
        },
    }
    state.update(over)
    return state


def test_estado_final_as_it_was_is_0_and_reports_what_stays(tmp_path: Path) -> None:
    models = tmp_path / "modelos.json"
    models.write_text(GOOD_MODELS, encoding="utf-8")
    done = run("estado-final.sh", ["--modelos", str(models)], tmp_path, final_state())
    assert done.returncode == 0, done.stdout + done.stderr
    assert (
        "como estaba" in done.stdout
        and "fallo persistente (no_disponible de D1) = 5" in done.stdout
        and "alertas en firing = FailClosedPersistente" in done.stdout
    )
    assert verbs(tmp_path) <= ALLOWED_VERBS


def test_estado_final_reads_the_models_from_stdin(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    variables = kind_kubectl_bin.install(
        bin_dir, final_state(), free_text=FREE.format(available=1), docker_text=""
    )
    done = subprocess.run(
        ["sh", str(KIND / "estado-final.sh"), "--modelos", "-"],
        input=GOOD_MODELS,
        env={**os.environ, **variables},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr


@pytest.mark.parametrize(
    ("models", "needle"),
    [
        (
            json.dumps(
                [
                    {"model_version_id": "mv-ref", "state": "activo"},
                    {"model_version_id": "mv-p", "state": "congelado"},
                ]
            ),
            "sigue congelado",
        ),
        (json.dumps([{"model_version_id": "mv-p", "state": "inactivo"}]), "debe haber un solo modelo activo"),
        (
            json.dumps(
                [{"model_version_id": "a", "state": "activo"}, {"model_version_id": "b", "state": "activo"}]
            ),
            "debe haber un solo modelo activo",
        ),
    ],
)
def test_estado_final_a_frozen_or_missing_active_model_fails(
    tmp_path: Path, models: str, needle: str
) -> None:
    file = tmp_path / "m.json"
    file.write_text(models, encoding="utf-8")
    done = run("estado-final.sh", ["--modelos", str(file)], tmp_path, final_state())
    assert done.returncode == 1 and needle in done.stdout


def test_estado_final_staging_leftovers_and_a_missing_f22_resource_fail(tmp_path: Path) -> None:
    file = tmp_path / "m.json"
    file.write_text(GOOD_MODELS, encoding="utf-8")
    left = final_state()
    left["rules"].insert(
        0,
        {
            "match": ["get", "inferenceservices.serving.kserve.io", "vectra-staging"],
            "stdout": "inferenceservice.serving.kserve.io/isvc-proxy\n",
        },
    )
    done = run("estado-final.sh", ["--modelos", str(file)], tmp_path, left)
    assert done.returncode == 1 and "quedan InferenceService en vectra-staging" in done.stdout
    gone = final_state()
    gone["rules"].insert(
        0, {"match": ["get", "server.policy.linkerd.io", "explainer-8080"], "stderr": "NotFound\n", "rc": 1}
    )
    done = run("estado-final.sh", ["--modelos", str(file)], tmp_path, gone)
    assert done.returncode == 1 and "FALLA F22: falta Server explainer-8080" in done.stdout


def test_estado_final_without_models_or_with_garbage_exits_2(tmp_path: Path) -> None:
    assert run("estado-final.sh", [], tmp_path, final_state()).returncode == 2
    junk = tmp_path / "j.json"
    junk.write_text("no es json", encoding="utf-8")
    assert run("estado-final.sh", ["--modelos", str(junk)], tmp_path, final_state()).returncode == 2
    assert (
        run(
            "estado-final.sh", ["--modelos", str(tmp_path / "no-existe.json")], tmp_path, final_state()
        ).returncode
        == 2
    )


@pytest.mark.parametrize("resource", F22_RESOURCES)
def test_estado_final_an_unreadable_f22_resource_is_2_not_a_missing_one(
    tmp_path: Path, resource: str
) -> None:
    """F-05: solo un `NotFound` es «falta» (1); una API caída en cualquiera de las cinco lecturas de F22 es «no se pudo leer» (2)."""
    file = tmp_path / "m.json"
    file.write_text(GOOD_MODELS, encoding="utf-8")
    down = final_state()
    down["rules"].insert(
        0,
        {
            "match": ["get", resource],
            "stderr": "Unable to connect to the server: connection refused\n",
            "rc": 1,
        },
    )
    done = run("estado-final.sh", ["--modelos", str(file)], tmp_path, down)
    assert done.returncode == 2, done.stdout + done.stderr
    assert "NO SE PUDO LEER" in done.stderr and "FALLA F22" not in done.stdout
    gone = final_state()
    gone["rules"].insert(
        0, {"match": ["get", resource], "stderr": "Error from server (NotFound): not found\n", "rc": 1}
    )
    done = run("estado-final.sh", ["--modelos", str(file)], tmp_path, gone)
    assert done.returncode == 1 and "FALLA F22: falta" in done.stdout
