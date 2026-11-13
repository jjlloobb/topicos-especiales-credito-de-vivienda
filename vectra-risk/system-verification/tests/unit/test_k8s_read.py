"""CA-9: `k8s_read` solo con los cuatro verbos de solo lectura (U12 Paso 5; NFR-U12-43; INF-U12-02, INF-U12-03). El ejecutor es un doble: el `kubectl` real nunca corre."""

import importlib.util
from pathlib import Path

import pytest
from kubectl_double import KubectlDouble, pod

from vectra_verification.clients.k8s_read import K8sError, K8sRead

_spec = importlib.util.spec_from_file_location(
    "kubectl_verbs_detector", Path(__file__).with_name("test_kubectl_verbs.py")
)
assert _spec is not None and _spec.loader is not None
_detector = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_detector)  # el detector de U12-T01, sin copiarlo ni cambiarlo
UNIT = _detector.UNIT
scan_tree = _detector.scan_tree
SRC = UNIT / "src" / "vectra_verification"


def test_k8s_read_is_scanned_and_contains_kubectl_invocations() -> None:
    text = (SRC / "clients" / "k8s_read.py").read_text(encoding="utf-8")
    assert text.count('"kubectl"') >= 4  # el escaneo no pasa en vacio
    assert scan_tree(UNIT) == []
    scanned = {p.name for p in (UNIT / "src").rglob("*.py")}
    assert "k8s_read.py" in scanned


def test_the_class_exposes_only_the_four_read_verbs() -> None:
    assert sorted(n for n in dir(K8sRead) if not n.startswith("_")) == [
        "auth_can_i",
        "get",
        "logs",
        "port_forward",
    ]


def test_commands_are_argument_lists_with_the_literal_verb_and_the_namespace() -> None:
    double = KubectlDouble()
    k8s = K8sRead(double)
    k8s.get("pods", "vectra-app", "app=x")
    k8s.logs("registry-0", "vectra-app", tail=5)
    assert k8s.auth_can_i("get", "pods", "vectra-app") is True
    with k8s.port_forward("vectra-app", "app=x", 8080):
        pass
    verbs = [c[1] if c[1] != "auth" else "auth can-i" for c in double.calls]
    assert verbs == ["get", "get", "logs", "auth can-i", "get", "port-forward"][:0] + [
        "get",
        "logs",
        "auth can-i",
        "get",
        "port-forward",
    ]
    assert all(c[0] == "kubectl" and "-n" in c and "vectra-app" in c for c in double.calls)
    assert all(isinstance(c, tuple) and all(isinstance(a, str) for a in c) for c in double.calls)
    assert "shell=True" not in (SRC / "clients" / "k8s_read.py").read_text(encoding="utf-8").replace(
        "sin `shell=True`", ""
    )


def test_a_failing_read_is_a_clear_error() -> None:
    from vectra_verification.clients.k8s_read import Completed

    double = KubectlDouble()
    double.answers["logs"] = Completed(1, "", "Error from server (NotFound)")
    with pytest.raises(K8sError, match="logs_failed:vectra-app/registry-9"):
        K8sRead(double).logs("registry-9", "vectra-app")
    double.answers["auth"] = Completed(1, "", "boom")
    with pytest.raises(K8sError, match="auth_can_i_failed"):
        K8sRead(double).auth_can_i("get", "pods", "vectra-app")


def test_pod_choice_is_ready_not_deleting_and_forward_goes_to_pod_never_to_svc() -> None:
    double = KubectlDouble(
        [
            pod("a-deleting", deleting=True),
            pod("b-notready", ready=False),
            pod("c-ready"),
            pod("d-pending", phase="Pending"),
        ]
    )
    with K8sRead(double).port_forward("vectra-app", "app=x", 8080) as forward:
        assert forward.pod == "c-ready" and forward.local_port == 41234 and forward.attempts == 1
    (call,) = double.forward_calls
    assert "pod/c-ready" in call and not any(a.startswith("svc/") for a in call) and ":8080" in call
    assert not any(
        a in ("8080", "8081") or a.startswith(("8080:", "8081:")) for a in call
    )  # nunca un puerto local fijo
    get_call = next(c for c in double.calls if c[1] == "get")
    assert "-l" in get_call and "app=x" in get_call


def test_no_ready_pod_is_a_clear_error() -> None:
    with (
        pytest.raises(K8sError, match="no_ready_pod:vectra-app"),
        K8sRead(KubectlDouble([pod("x", ready=False)])).port_forward("vectra-app", "a=b", 80),
    ):
        pass


def test_the_process_dies_on_exit_also_with_an_exception() -> None:
    double = KubectlDouble()
    with pytest.raises(RuntimeError), K8sRead(double).port_forward("vectra-app", "a=b", 80):
        raise RuntimeError("boom")
    assert double.processes[0].terminated


def test_a_forward_that_falls_is_chosen_again_once_and_then_fails_clearly() -> None:
    double = KubectlDouble(
        [pod("r-0"), pod("r-1")], forwards=[None, ["Forwarding from 127.0.0.1:50001 -> 80\n"]]
    )
    with K8sRead(double).port_forward("vectra-app", "a=b", 80) as forward:
        assert forward.pods_used == ("r-0", "r-1") and forward.attempts == 2
    down = KubectlDouble([pod("r-0"), pod("r-1")], forwards=[None, None])
    with (
        pytest.raises(K8sError, match=r"port_forward_failed:vectra-app/pod/r-1:attempts=2"),
        K8sRead(down).port_forward("vectra-app", "a=b", 80),
    ):
        pass
    assert len(down.forward_calls) == 2  # una eleccion y una nueva: ni un reintento mas


def test_the_real_kubectl_is_never_reachable_from_these_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "")  # sin `kubectl` en el PATH: el unico ejecutor posible es el doble
    import shutil

    assert shutil.which("kubectl") is None
    double = KubectlDouble()
    K8sRead(double).get("pods", "vectra-app")
    assert double.calls and all(c[0] == "kubectl" for c in double.calls)
