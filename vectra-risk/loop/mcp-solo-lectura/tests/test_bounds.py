"""Las salidas se acotan (elementos, largo de cada texto, total) y solo llevan los campos elegidos."""

from __future__ import annotations

import json
from pathlib import Path

from mcp_doubles import FakeRunner

from vectra_mcp_readonly import tools
from vectra_mcp_readonly.kubectl import Completed, K8sError, Kubectl, redact

JWT = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJl"


def _kubectl(items: dict) -> Kubectl:
    return Kubectl(FakeRunner(items), Path("/x"), "kind-vectra")


def _pod(index: int) -> dict:
    return {
        "metadata": {"name": f"pod-{index:04d}", "annotations": {"nota": "ANOTACION-PRIVADA"}},
        "spec": {
            "containers": [{"name": "c", "env": [{"name": "DB_PASSWORD", "value": "VALOR-DE-ENTORNO"}]}]
        },
        "status": {
            "phase": "Running",
            "startTime": "2026-11-20T10:00:00Z",
            "containerStatuses": [
                {
                    "ready": index % 2 == 0,
                    "restartCount": index,
                    "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                }
            ],
        },
    }


def test_items_are_capped_and_the_total_is_reported() -> None:
    result = tools.pods(_kubectl({"pods": [_pod(i) for i in range(500)]}), "vectra-app")
    assert result["total"] == 500 and len(result["items"]) == tools.MAX_ITEMS and result["truncated"] is True
    assert result["items"][0] == {"name": "pod-0499", "phase": "Running", "ready": "0/1", "restarts": 499, "reason": "CrashLoopBackOff", "started": "2026-11-20T10:00:00Z"}  # fmt: skip
    assert len(json.dumps(result, ensure_ascii=False)) <= tools.MAX_CHARS


def test_a_small_answer_is_not_marked_truncated() -> None:
    result = tools.pods(_kubectl({"pods": [_pod(1)]}), "vectra-app")
    assert result["total"] == 1 and result["truncated"] is False


def test_only_the_chosen_fields_leave_the_server() -> None:
    text = json.dumps(tools.pods(_kubectl({"pods": [_pod(1)]}), "vectra-app"))
    assert "VALOR-DE-ENTORNO" not in text and "ANOTACION-PRIVADA" not in text and "DB_PASSWORD" not in text


def test_long_texts_are_clipped_and_the_total_size_is_capped() -> None:
    event = {"type": "Warning", "reason": "R" * 5000, "message": "m" * 100_000, "lastTimestamp": "2026-11-20T10:00:00Z", "involvedObject": {"kind": "Pod", "name": "n" * 9000}}  # fmt: skip
    result = tools.events(_kubectl({"events": [dict(event) for _ in range(400)]}), "vectra-app")
    assert all(
        len(value) <= tools.MAX_FIELD_CHARS
        for item in result["items"]
        for value in item.values()
        if isinstance(value, str)
    )
    assert len(json.dumps(result, ensure_ascii=False)) <= tools.MAX_CHARS
    assert (
        result["total"] == 400 and result["truncated"] is True and 0 < len(result["items"]) < tools.MAX_ITEMS
    )


def test_events_are_newest_first_and_can_be_filtered_to_warnings() -> None:
    rows = [
        {
            "type": "Normal",
            "reason": "Pulled",
            "message": "ok",
            "lastTimestamp": "2026-11-20T10:00:00Z",
            "involvedObject": {"kind": "Pod", "name": "a"},
        },
        {
            "type": "Warning",
            "reason": "BackOff",
            "message": "mal",
            "eventTime": "2026-11-21T10:00:00Z",
            "involvedObject": {"kind": "Pod", "name": "b"},
        },
    ]
    assert [e["reason"] for e in tools.events(_kubectl({"events": rows}), "vectra-app")["items"]] == [
        "BackOff",
        "Pulled",
    ]
    assert [
        e["reason"]
        for e in tools.events(_kubectl({"events": rows}), "vectra-app", only_warnings=True)["items"]
    ] == ["BackOff"]


def test_credentials_in_a_message_are_redacted() -> None:
    event = {
        "type": "Warning",
        "reason": "Failed",
        "message": f"login fallo: password=hunter2 Authorization: Bearer {JWT}",
        "involvedObject": {},
    }
    message = tools.events(_kubectl({"events": [event]}), "vectra-app")["items"][0]["message"]
    assert "hunter2" not in message and JWT not in message and "eyJ" not in message and "<oculto>" in message
    assert redact("sin nada sensible") == "sin nada sensible"


def test_a_kubectl_failure_is_short_and_redacted() -> None:
    class Failing(FakeRunner):
        def run(self, args, env):  # type: ignore[no-untyped-def]
            return Completed(1, "", f"error: token={JWT} " + "x" * 5000)

    try:
        Kubectl(Failing(), Path("/x"), "kind-vectra").get("pods", "vectra-app")
    except K8sError as error:
        assert JWT not in str(error) and len(str(error)) < 300
    else:
        raise AssertionError("debia fallar")


def test_a_response_that_is_not_a_list_is_an_error_not_a_crash() -> None:
    class Odd(FakeRunner):
        def run(self, args, env):  # type: ignore[no-untyped-def]
            return Completed(0, '{"items": "x"}', "")

    try:
        Kubectl(Odd(), Path("/x"), "kind-vectra").get("pods", "vectra-app")
    except K8sError as error:
        assert "get_response_shape" in str(error)
    else:
        raise AssertionError("debia fallar")


def test_argo_applications_puts_the_unhealthy_first_and_shortens_the_revision() -> None:
    apps = [
        {
            "metadata": {"name": "a-sana"},
            "status": {
                "sync": {"status": "Synced", "revision": "0123456789abcdef0123"},
                "health": {"status": "Healthy"},
            },
        },
        {
            "metadata": {"name": "z-rota"},
            "status": {
                "sync": {"status": "OutOfSync"},
                "health": {"status": "Degraded"},
                "operationState": {"phase": "Failed"},
            },
        },
        {"metadata": {"name": "m-nueva"}},
        {
            "metadata": {"name": "b-varias-fuentes"},
            "status": {
                "sync": {"status": "Synced", "revisions": ["fedcba9876543210", "x"]},
                "health": {"status": "Healthy"},
            },
        },
    ]
    result = tools.argo_applications(_kubectl({"applications.argoproj.io": apps}))
    assert [a["name"] for a in result["items"]] == ["m-nueva", "z-rota", "a-sana", "b-varias-fuentes"]
    assert (
        result["items"][2]["revision"] == "0123456789ab" and result["items"][3]["revision"] == "fedcba987654"
    )
    assert result["sync"] == {"Unknown": 1, "OutOfSync": 1, "Synced": 2}


def test_inference_services_and_workloads_project_status() -> None:
    isvc = {"metadata": {"name": "modelo"}, "spec": {"predictor": {"model": {"modelFormat": {"name": "onnx"}, "runtime": "triton", "storageUri": "s3://cubo/privado"}}}, "status": {"url": "http://modelo.vectra-app", "conditions": [{"type": "Ready", "status": "False", "reason": "RevisionFailed"}]}}  # fmt: skip
    result = tools.inference_services(_kubectl({"inferenceservices.serving.kserve.io": [isvc]}), "vectra-app")
    assert result["items"] == [{"name": "modelo", "ready": "False", "reason": "RevisionFailed", "message": None, "url": "http://modelo.vectra-app", "model_format": "onnx", "runtime": "triton"}]  # fmt: skip
    deployments = [
        {
            "metadata": {"name": "api"},
            "spec": {"replicas": 2},
            "status": {"readyReplicas": 1, "updatedReplicas": 2},
        }
    ]
    assert tools.workloads(_kubectl({"deployments.apps": deployments}), "vectra-app")["items"] == [
        {"name": "api", "desired": 2, "ready": 1, "updated": 2}
    ]
    jobs = [{"metadata": {"name": "j"}, "status": {"succeeded": 1}}]
    assert tools.workloads(_kubectl({"jobs.batch": jobs}), "vectra-app", "jobs")["items"] == [
        {"name": "j", "active": 0, "succeeded": 1, "failed": 0}
    ]
    daemons = [{"metadata": {"name": "d"}, "status": {"desiredNumberScheduled": 3, "numberReady": 3}}]
    assert tools.workloads(_kubectl({"daemonsets.apps": daemons}), "vectra-app", "daemonsets")["items"] == [
        {"name": "d", "desired": 3, "ready": 3}
    ]


def test_permissions_reports_the_probes_and_groups_the_rules() -> None:
    result = tools.permissions(_kubectl({}), "vectra-app")
    allowed = {f"{p['verb']} {p['resource']}": p["allowed"] for p in result["probes"]}
    assert allowed == {
        "get pods": True,
        "list applications.argoproj.io": True,
        "list inferenceservices.serving.kserve.io": True,
        "get secrets": False,
        "create pods": False,
        "delete pods": False,
        "patch deployments": False,
        "create pods/exec": False,
    }
    by_verbs = {tuple(item["verbs"]): item for item in result["items"]}
    assert by_verbs[("get", "list", "watch")]["resources"] == ["applications.argoproj.io", "pods", "pods/log"]
    assert (
        by_verbs[("get", "list", "watch")]["read_only"] is True
        and by_verbs[("create",)]["read_only"] is False
    )
    assert by_verbs[("create",)]["resources"] == [
        "selfsubjectaccessreviews.authorization.k8s.io",
        "selfsubjectrulesreviews.authorization.k8s.io",
    ]
    assert by_verbs[("get",)]["resources"] == ["(no recurso) [/healthz]"]
    assert result["identity"] == "system:serviceaccount:argocd:vectra-readonly-agent"
