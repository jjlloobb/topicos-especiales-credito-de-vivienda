"""Backend de eco de kind (U02-T14, CA-4, H1): valido sin clúster. Cada comprobacion falla en una copia mutada."""

import copy
from pathlib import Path

import e2e_echo_checks as ec
import pytest
import yaml

SERVER_TEXT = ec.SERVER.read_text(encoding="utf-8")
DOCS = ec.manifest_docs()


def mutated_server(tmp_path: Path, old: str, new: str):
    assert old in SERVER_TEXT, f"la mutacion no encuentra {old!r}"
    path = tmp_path / "server.py"
    path.write_text(SERVER_TEXT.replace(old, new), encoding="utf-8")
    return ec.load_server(path)


def docs_copy() -> list[dict]:
    return copy.deepcopy(DOCS)


def deployment(docs: list[dict], name: str) -> dict:
    return next(d for d in docs if d["kind"] == "Deployment" and d["metadata"]["name"] == name)


# --- servidor ----------------------------------------------------------------------------------------------


def test_the_echo_returns_idempotency_key_and_test_scenario_byte_for_byte():
    assert ec.server_problems(ec.load_server()) == []


def test_the_echo_returns_the_headers_in_the_body_and_the_size_received():
    reply = ec.roundtrip(ec.load_server(), [("Idempotency-Key", "k-1"), ("x-vectra-azp", "channel")], body=b"abc")
    assert ec.echoed_value(reply, "idempotency-key") == "k-1"
    assert ec.echoed_value(reply, "x-vectra-azp") == "channel"
    assert reply["body_bytes"] == 3 and reply["method"] == "POST"


def test_the_echo_counts_a_body_larger_than_one_read():
    reply = ec.roundtrip(ec.load_server(), [], body=b"y" * 300_000)
    assert reply["body_bytes"] == 300_000


@pytest.mark.parametrize("method", ["GET", "PUT", "PATCH", "DELETE"])
def test_the_echo_answers_every_method(method):
    assert ec.roundtrip(ec.load_server(), [("X-Test-Scenario", "s")], method=method)["method"] == method


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("self.headers.items()", "[(k, v.lower()) for k, v in self.headers.items()]"),
        ("self.headers.items()", "[(k, v) for k, v in self.headers.items() if k.lower() != 'idempotency-key']"),
        ("self.headers.items()", "[(k, v) for k, v in self.headers.items() if k.lower() != 'x-test-scenario']"),
        ("self.headers.items()", "[(k, v) for k, v in self.headers.items() if not k.lower().startswith('x-vectra-')]"),
        ("total += len(chunk)", "total += 0"),
    ],
    ids=["lowercased-values", "drops-idempotency-key", "drops-test-scenario", "drops-x-vectra", "wrong-size"],
)
def test_a_mutated_echo_is_detected(tmp_path, old, new):
    assert ec.server_problems(mutated_server(tmp_path, old, new)) != []


# --- manifiestos -------------------------------------------------------------------------------------------


def test_the_design_values_come_from_flows_and_routes():
    assert ec.design() == {
        "console-spa": {"namespace": "vectra-edge", "sa": "console-spa", "name": "console-spa", "port": 8080},
        "console-bff": {"namespace": "vectra-app", "sa": "console-bff", "name": "console-bff", "port": 8080},
        "case-service": {"namespace": "vectra-app", "sa": "case-service", "name": "case-service", "port": 8080},
        "governance-service": {"namespace": "vectra-app", "sa": "governance-service", "name": "governance-service", "port": 8080},
    }


def test_the_manifests_match_the_design():
    assert ec.structure_problems(DOCS) == []


def test_the_manifests_pass_kubeconform():
    ok, output = ec.kubeconform(DOCS)
    assert ok, output


def test_the_manifests_pass_the_u1_kyverno_policies():
    import keycloak_deploy_checks as kd

    ok, output = kd.kyverno(DOCS)
    assert ok, output


def test_the_manifests_pass_the_u1_rego_policies():
    ok, output = ec.conftest(DOCS)
    assert ok, output


def test_the_dockerfile_pins_the_base_image_and_copies_the_server():
    assert ec.dockerfile_problems(ec.DOCKERFILE.read_text(encoding="utf-8")) == []


def test_the_dockerfile_check_fails_on_a_copy():
    assert ec.dockerfile_problems("FROM python:3.12-slim\nCOPY server.py /\n") != []


# --- mutaciones: cada comprobacion falla en una copia -------------------------------------------------------


def mut_namespace(docs):
    deployment(docs, "case-service")["metadata"]["namespace"] = "vectra-edge"


def mut_sa(docs):
    deployment(docs, "console-bff")["spec"]["template"]["spec"]["serviceAccountName"] = "default"


def mut_pod_label(docs):
    deployment(docs, "governance-service")["spec"]["template"]["metadata"]["labels"]["app.kubernetes.io/name"] = "other"


def mut_port(docs):
    deployment(docs, "console-spa")["spec"]["template"]["spec"]["containers"][0]["ports"][0]["containerPort"] = 9090


def mut_service_port(docs):
    next(d for d in docs if d["kind"] == "Service" and d["metadata"]["name"] == "case-service")["spec"]["ports"][0]["port"] = 80


def mut_registry(docs):
    c = deployment(docs, "console-bff")["spec"]["template"]["spec"]["containers"][0]
    c["image"] = c["image"].replace(ec.REGISTRY, "docker.io/")


def mut_missing_service(docs):
    docs[:] = [d for d in docs if not (d["kind"] == "Service" and d["metadata"]["name"] == "console-bff")]


def mut_criticality(docs):
    del deployment(docs, "case-service")["spec"]["template"]["metadata"]["labels"]["vectra.io/criticality"]


STRUCTURE_MUTATIONS = [mut_namespace, mut_sa, mut_pod_label, mut_port, mut_service_port, mut_registry, mut_missing_service, mut_criticality]


@pytest.mark.parametrize("mutate", STRUCTURE_MUTATIONS, ids=lambda f: f.__name__)
def test_structure_check_fails_on_a_mutated_copy(mutate):
    docs = docs_copy()
    mutate(docs)
    assert ec.structure_problems(docs) != []


def test_kubeconform_fails_on_an_unknown_field():
    docs = docs_copy()
    deployment(docs, "case-service")["spec"]["template"]["spec"]["containers"][0]["bogus"] = True
    ok, _ = ec.kubeconform(docs)
    assert not ok


def test_kubeconform_fails_on_a_kind_without_schema():
    docs = docs_copy()
    docs.append({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "x", "namespace": "vectra-app"}})
    ok, _ = ec.kubeconform(docs)
    assert not ok


def mut_latest(docs):
    c = deployment(docs, "console-bff")["spec"]["template"]["spec"]["containers"][0]
    c["image"] = ec.REGISTRY + "vectra/e2e-echo:latest"


def mut_root(docs):
    deployment(docs, "console-bff")["spec"]["template"]["spec"]["securityContext"]["runAsNonRoot"] = False


def mut_no_resources(docs):
    del deployment(docs, "console-bff")["spec"]["template"]["spec"]["containers"][0]["resources"]


def mut_no_priority(docs):
    del deployment(docs, "console-bff")["spec"]["template"]["spec"]["priorityClassName"]


@pytest.mark.parametrize("mutate", [mut_latest, mut_root, mut_no_resources, mut_no_priority], ids=lambda f: f.__name__)
def test_kyverno_fails_on_a_mutated_copy(mutate):
    import keycloak_deploy_checks as kd

    docs = docs_copy()
    mutate(docs)
    ok, _ = kd.kyverno(docs)
    assert not ok


def mut_no_spread(docs):
    del deployment(docs, "case-service")["spec"]["template"]["spec"]["topologySpreadConstraints"]


def mut_no_pdb(docs):
    docs[:] = [d for d in docs if not (d["kind"] == "PodDisruptionBudget" and d["metadata"]["name"] == "case-service")]


def mut_no_exempt(docs):
    del deployment(docs, "case-service")["metadata"]["annotations"]["vectra.io/hpa-exempt"]


@pytest.mark.parametrize("mutate", [mut_no_spread, mut_no_pdb, mut_no_exempt], ids=lambda f: f.__name__)
def test_rego_fails_on_a_mutated_copy(mutate):
    docs = docs_copy()
    mutate(docs)
    ok, _ = ec.conftest(docs)
    assert not ok


def test_the_manifests_file_is_valid_yaml_with_only_the_four_services():
    names = sorted({d["metadata"]["name"] for d in yaml.safe_load_all(ec.MANIFESTS.read_text(encoding="utf-8")) if d and d["kind"] == "Deployment"})
    assert names == sorted(ec.ECHOED)
