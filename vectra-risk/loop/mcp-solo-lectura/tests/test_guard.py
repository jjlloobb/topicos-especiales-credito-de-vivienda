"""El servidor no arranca con un kubeconfig que no sea el de `vectra-readonly-agent`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from mcp_doubles import FakeRunner, fake_token, kubeconfig_document, write_kubeconfig

from vectra_mcp_readonly import guard, server
from vectra_mcp_readonly.kubectl import Completed, Kubectl


def admin_document() -> dict[str, Any]:
    """La forma del kubeconfig de administrador de kind: certificado de cliente, sin token."""
    document = kubeconfig_document()
    document["users"] = [
        {"name": "kind-vectra", "user": {"client-certificate-data": "Q0VSVA==", "client-key-data": "S0VZ"}}
    ]
    document["contexts"][0]["context"]["user"] = "kind-vectra"
    return document


def test_the_read_only_kubeconfig_is_accepted(tmp_path: Path) -> None:
    path = write_kubeconfig(tmp_path / "ro", kubeconfig_document())
    assert guard.check_file(path, home=tmp_path) == "kind-vectra"


def _two_contexts() -> dict[str, Any]:
    document = kubeconfig_document()
    document["contexts"].append(
        {"name": "kind-otro", "context": {"cluster": "kind-vectra", "user": "vectra-readonly-agent"}}
    )
    return document


def _two_users() -> dict[str, Any]:
    document = kubeconfig_document()
    document["users"].append({"name": "admin", "user": {"client-certificate-data": "Q0VSVA=="}})
    return document


def _with_user(extra: dict[str, Any]) -> dict[str, Any]:
    document = kubeconfig_document()
    document["users"][0]["user"].update(extra)
    return document


def _token(value: Any) -> dict[str, Any]:
    document = kubeconfig_document()
    document["users"][0]["user"]["token"] = value
    return document


REFUSED = {
    "administrador de kind (certificado de cliente)": admin_document(),
    "otra ServiceAccount": kubeconfig_document(
        subject="system:serviceaccount:argocd:argocd-application-controller"
    ),
    "misma cuenta en otro namespace": kubeconfig_document(
        subject="system:serviceaccount:default:vectra-readonly-agent"
    ),
    "usuario humano": kubeconfig_document(subject="kubernetes-admin"),
    "contexto que no es de kind": kubeconfig_document(context="prod-bank"),
    "dos contextos": _two_contexts(),
    "dos usuarios": _two_users(),
    "token y ademas certificado": _with_user({"client-certificate-data": "Q0VSVA=="}),
    "token y ademas impersonacion": _with_user({"as": "system:admin"}),
    "token y ademas exec": _with_user({"exec": {"command": "sh"}}),
    "token que no es un JWT": _token("abc"),
    "token vacio": _token(""),
    "token con payload ilegible": _token("a.%%%.c"),
    "token sin sub": _token(fake_token("x").split(".")[0] + ".e30.firma"),
    "no es un kubeconfig": {"hola": 1},
    "lista": ["x"],
}


@pytest.mark.parametrize("case", sorted(REFUSED))
def test_any_other_kubeconfig_is_refused(case: str, tmp_path: Path) -> None:
    path = write_kubeconfig(tmp_path / "kc", REFUSED[case])  # type: ignore[arg-type]
    with pytest.raises(guard.StartupRefused):
        guard.check_file(path, home=tmp_path)


def test_refuses_a_missing_file_a_loose_mode_the_admin_path_and_bad_yaml(tmp_path: Path) -> None:
    with pytest.raises(guard.StartupRefused, match="no se pudo leer"):
        guard.check_file(tmp_path / "no-existe", home=tmp_path)
    with pytest.raises(guard.StartupRefused, match="debe ser 600"):
        guard.check_file(
            write_kubeconfig(tmp_path / "abierto", kubeconfig_document(), mode=0o644), home=tmp_path
        )
    (tmp_path / ".kube").mkdir()
    admin_path = write_kubeconfig(tmp_path / ".kube" / "config", kubeconfig_document())
    with pytest.raises(guard.StartupRefused, match="administrador"):
        guard.check_file(admin_path, home=tmp_path)
    link = tmp_path / "enlace"
    link.symlink_to(admin_path)
    with pytest.raises(guard.StartupRefused, match="administrador"):
        guard.check_file(link, home=tmp_path)
    broken = tmp_path / "roto"
    broken.write_text("{: [", encoding="utf-8")
    broken.chmod(0o600)
    with pytest.raises(guard.StartupRefused, match="no se pudo leer"):
        guard.check_file(broken, home=tmp_path)
    with pytest.raises(guard.StartupRefused):
        guard.check_file(tmp_path, home=tmp_path)


def test_the_refusal_never_prints_the_token(tmp_path: Path) -> None:
    document = kubeconfig_document(subject="kubernetes-admin")
    token = document["users"][0]["user"]["token"]
    with pytest.raises(guard.StartupRefused) as caught:
        guard.check_file(write_kubeconfig(tmp_path / "kc", document), home=tmp_path)
    assert token not in str(caught.value) and token.split(".")[1] not in str(caught.value)


def test_the_path_comes_from_its_own_variable_never_from_kubeconfig() -> None:
    assert (
        guard.kubeconfig_path({"KUBECONFIG": "/home/u/.kube/config"}) == Path(guard.DEFAULT_PATH).expanduser()
    )
    assert guard.kubeconfig_path(
        {guard.ENV_VAR: "/run/user/1000/ro", "KUBECONFIG": "/home/u/.kube/config"}
    ) == Path("/run/user/1000/ro")
    assert guard.kubeconfig_path({guard.ENV_VAR: ""}) == Path(guard.DEFAULT_PATH).expanduser()


# --- La identidad viva ---


def _kubectl(runner: FakeRunner) -> Kubectl:
    return Kubectl(runner, Path("/x"), "kind-vectra")


def test_live_check_passes_for_the_read_only_identity_and_asks_every_row() -> None:
    runner = FakeRunner()
    guard.check_live(_kubectl(runner))
    asked = {(c[3], c[4], next((a for a in c if a.startswith("--subresource=")), None)) for c in runner.calls}
    assert asked == {
        ("create", "pods", None),
        ("delete", "pods", None),
        ("patch", "deployments", None),
        ("get", "secrets", None),
        ("list", "secrets", None),
        ("create", "pods", "--subresource=exec"),
        ("impersonate", "users", None),
        ("get", "pods", None),
    }
    assert all(c[:3] == ("kubectl", "auth", "can-i") and "-A" in c for c in runner.calls)


@pytest.mark.parametrize(
    "granted",
    [
        "create pods",
        "delete pods",
        "patch deployments",
        "get secrets",
        "list secrets",
        "create pods/exec",
        "impersonate users",
    ],
)
def test_live_check_refuses_an_identity_that_can_do_any_forbidden_thing(granted: str) -> None:
    with pytest.raises(guard.StartupRefused, match="debe responder no"):
        guard.check_live(_kubectl(FakeRunner(answers={"get pods": "yes", granted: "yes"})))


def test_live_check_refuses_an_identity_that_cannot_read() -> None:
    with pytest.raises(guard.StartupRefused, match="debe responder yes"):
        guard.check_live(_kubectl(FakeRunner(answers={})))


def test_live_check_fails_closed_without_an_answer() -> None:
    class Down(FakeRunner):
        def run(self, args, env):  # type: ignore[no-untyped-def]
            super().run(args, env)
            return Completed(1, "", "The connection to the server 127.0.0.1:1 was refused")

    with pytest.raises(guard.StartupRefused, match="no obtuvo respuesta"):
        guard.check_live(_kubectl(Down()))


def test_a_no_with_a_reason_is_still_a_no() -> None:
    class Reasoned(FakeRunner):
        def run(self, args, env):  # type: ignore[no-untyped-def]
            done = super().run(args, env)
            return (
                Completed(done.returncode, "no - RBAC: sin regla\n", "")
                if done.stdout.startswith("no")
                else done
            )

    guard.check_live(_kubectl(Reasoned()))


# --- `prepare`: lo que corre `main` antes de abrir el transporte ---


def test_prepare_refuses_the_admin_kubeconfig_before_running_anything(tmp_path: Path) -> None:
    path = write_kubeconfig(tmp_path / "admin", admin_document())
    runner = FakeRunner()
    with pytest.raises(guard.StartupRefused):
        server.prepare({guard.ENV_VAR: str(path)}, lambda p, c: Kubectl(runner, p, c))
    assert runner.calls == []


def test_prepare_refuses_a_read_only_looking_file_whose_identity_can_write(tmp_path: Path) -> None:
    path = write_kubeconfig(tmp_path / "ro", kubeconfig_document())
    runner = FakeRunner(answers={"get pods": "yes", "create pods": "yes"})
    with pytest.raises(guard.StartupRefused, match="create pods"):
        server.prepare({guard.ENV_VAR: str(path)}, lambda p, c: Kubectl(runner, p, c))


def test_prepare_returns_a_kubectl_bound_to_that_file_and_context(tmp_path: Path) -> None:
    path = write_kubeconfig(tmp_path / "ro", kubeconfig_document())
    runner = FakeRunner()
    kubectl = server.prepare({guard.ENV_VAR: str(path)}, lambda p, c: Kubectl(runner, p, c))
    kubectl.get("pods", "vectra-app")
    assert (
        f"--kubeconfig={path.resolve()}" in runner.calls[-1] and "--context=kind-vectra" in runner.calls[-1]
    )
