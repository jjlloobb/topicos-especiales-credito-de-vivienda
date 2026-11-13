"""Los clientes salientes del Paso 10, sin red: F25 (`compare_source`) y el manifiesto del Job de K01 (BR-U4-05, P-U4-03)."""

import json

import httpx
import pytest
from vectra_common.errors import DependencyUnavailable
from vectra_contracts.models.governance import PolicyDraft
from vectra_contracts.models.monitoring import CompareSourceRequest
from vectra_governance.clients import HttpSourceComparer
from vectra_governance.k8s_jobs import JobSpec, KubernetesJobs, job_manifest

ATTRIBUTES = ("sexo", "rango_edad", "region", "estrato")
TABLES = [{"attribute": a, "cells": [{"group": "g", "band": "lt_20", "favorable": 1, "total": 2}]} for a in ATTRIBUTES]


def spec(**over: object) -> JobSpec:
    base = {
        "job_name": "validation-1", "mode": "validacion", "run_id": "r1", "model_version_id": "mv-1", "image": "reg/job:1.0.0",
        "manifest_uri": "s3://m", "artifact_uri": "s3://a", "explainer_uri": "s3://e", "dataset_ref": "s3://d", "callback_url": "http://g",
        "s3_endpoint": "http://minio:9000", "token_url": "https://keycloak/token",
        "assertion_audience": "https://issuer.example/realms/vectra",
        "policy": PolicyDraft(cutoff="0.0800", low_confidence_threshold="0.0300", channel_rules=[], normative=[]),
    }
    return JobSpec(**{**base, **over})  # type: ignore[arg-type]


def test_the_manifest_has_ttl_deadline_and_no_retries_in_vectra_staging() -> None:
    manifest = job_manifest(spec())
    assert manifest["metadata"]["namespace"] == "vectra-staging"
    assert {k: manifest["spec"][k] for k in ("ttlSecondsAfterFinished", "activeDeadlineSeconds", "backoffLimit")} == {
        "ttlSecondsAfterFinished": 86400, "activeDeadlineSeconds": 7200, "backoffLimit": 0,
    }
    pod = manifest["spec"]["template"]["spec"]
    assert pod["restartPolicy"] == "Never" and pod["containers"][0]["image"].endswith(":1.0.0")


def test_the_mode_fields_must_be_coherent_like_the_validation_runs_check() -> None:
    with pytest.raises(ValueError, match="mode_fields_incoherent"):
        job_manifest(spec(mode="source_comparison"))
    with pytest.raises(ValueError, match="mode_fields_incoherent"):
        job_manifest(spec(source_id="ds-1", baseline_version_id="mv-0"))
    ok = job_manifest(spec(mode="source_comparison", source_id="ds-1", baseline_version_id="mv-0"))
    assert ok["metadata"]["labels"]["vectra.io/mode"] == "source-comparison"


@pytest.mark.parametrize("status", [200, 201, 409])
def test_the_launcher_accepts_created_and_already_existing(status: int) -> None:
    KubernetesJobs("http://k8s", lambda: "t", transport=httpx.MockTransport(lambda _: httpx.Response(status, json={}))).create(job_manifest(spec()))


@pytest.mark.parametrize("status", [401, 403, 422, 500])
def test_the_launcher_fails_closed_on_any_other_answer_or_a_timeout(status: int) -> None:
    client = KubernetesJobs("http://k8s", lambda: "t", transport=httpx.MockTransport(lambda _: httpx.Response(status, json={})))
    with pytest.raises(DependencyUnavailable):
        client.create(job_manifest(spec()))

    def boom(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lento")

    with pytest.raises(DependencyUnavailable):
        KubernetesJobs("http://k8s", lambda: "t", transport=httpx.MockTransport(boom)).get("j")


def test_f25_posts_the_count_tables_with_a_token_and_fails_closed() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(503, json={})

    request = CompareSourceRequest.model_validate({"source_id": "ds-1", "pre": TABLES, "post": TABLES})
    with pytest.raises(DependencyUnavailable):
        HttpSourceComparer("http://bias", lambda: "tok", transport=httpx.MockTransport(handle)).compare_source(request)
    assert seen[0].url.path == "/v1/source-comparisons" and seen[0].headers["authorization"] == "Bearer tok"
    assert json.loads(seen[0].content)["source_id"] == "ds-1"
