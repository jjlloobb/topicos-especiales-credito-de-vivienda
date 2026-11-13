"""Soporte de las pruebas de la API (Paso 10, U04-T04): la app de `create_governance_app` con PostgreSQL real, tokens firmados con
la llave de prueba de U0, el doble del registro de U3, un doble de la API de Kubernetes que guarda los manifiestos, un doble del
model-store con los paquetes reales de U5 y un doble de bias (F25).

La lectura de vuelta es con SQL sobre `model_versions`, `transitions`, `policies`, `data_sources` y `validation_runs`, y sobre la
cadena del doble del registro; el codigo HTTP solo no basta.
"""

import json
import re
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from evidence_support import (
    START,
    FakeRegistry,
    SimClock,
    freeze_context,
    make_service,
    sql,
)
from governance_pg import Db
from strategies import auth as u0_auth
from vectra_contracts.models.monitoring import (
    AttributeResult,
    InitialDisparity,
    BandResult,
    CellResult,
    CompareSourceRequest,
    DisparityResult,
    PrePostDelta,
    PrePostReport,
)
from vectra_governance.api import ApiConfig, ApiDeps, create_governance_app
from vectra_governance.convergence import ServingConfigCache
from vectra_governance.evidence import Evidence
from vectra_governance.k8s_jobs import KubernetesJobs

BASE = "http://governance"
IMAGE = "registry.test/vectra/model-validation-job:1.0.0"
ATTRIBUTES = ("sexo", "rango_edad", "region", "estrato")


class FakeKubernetes:
    """La API de Kubernetes de `vectra-staging`: guarda el manifiesto de cada Job que recibe y lo devuelve en `GET`."""

    def __init__(self) -> None:
        self.jobs: dict[tuple[str, str], dict[str, Any]] = {}
        self.inference_services: set[str] = set()
        self.fail_create = False
        self.status: dict[str, dict[str, Any]] = {}

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer k8s-token"
        path = request.url.path
        if request.method == "POST" and (m := re.fullmatch(r"/apis/batch/v1/namespaces/([^/]+)/jobs", path)):
            if self.fail_create:
                return httpx.Response(500, json={"message": "boom"})
            manifest = json.loads(request.content)
            key = (m.group(1), manifest["metadata"]["name"])
            if key in self.jobs:
                return httpx.Response(409, json={"reason": "AlreadyExists"})
            self.jobs[key] = manifest
            return httpx.Response(201, json=manifest)
        if m := re.fullmatch(r"/apis/batch/v1/namespaces/([^/]+)/jobs/([^/]+)", path):
            manifest = self.jobs.get((m.group(1), m.group(2)))
            if manifest is None:
                return httpx.Response(404, json={})
            return httpx.Response(200, json={**manifest, "status": self.status.get(m.group(2), {})})
        if m := re.fullmatch(r"/apis/serving.kserve.io/v1beta1/namespaces/([^/]+)/inferenceservices/([^/]+)", path):
            found = m.group(1) == "vectra-staging" and m.group(2) in self.inference_services
            return httpx.Response(200 if found else 404, json={})
        return httpx.Response(404, json={})

    def client(self) -> KubernetesJobs:
        return KubernetesJobs("https://kubernetes.test", lambda: "k8s-token", transport=self.transport())


class FakeModelStore:
    """El model-store (F47): bytes por URI `s3://model-store/<prefijo>/<archivo>`, sacados de carpetas de paquetes de U5."""

    def __init__(self) -> None:
        self.roots: dict[str, Path] = {}
        self.reads: list[str] = []

    def add(self, prefix: str, directory: Path) -> str:
        self.roots[prefix] = directory
        return f"s3://model-store/{prefix}/manifest.json"

    def read(self, uri: str) -> bytes:
        self.reads.append(uri)
        match = re.fullmatch(r"s3://model-store/([^/]+)/(.+)", uri)
        if match is None or match.group(1) not in self.roots:
            raise FileNotFoundError(uri)
        target = self.roots[match.group(1)] / match.group(2)
        if not target.is_file():
            raise FileNotFoundError(uri)
        return target.read_bytes()


def registration_body(directory: Path, store: FakeModelStore, prefix: str, **over: Any) -> dict[str, Any]:
    """El `ModelRegistration` de un paquete de U5 (formato `xgboost_json`, como el predictor de referencia)."""
    manifest_uri = store.add(prefix, directory)
    manifest = (directory / "manifest.json").read_bytes()
    listed = {e["name"]: e["sha256"] for e in json.loads(manifest)["files"]}
    import hashlib

    return {
        "artifact_uri": manifest_uri.replace("manifest.json", "predictor.json"),
        "artifact_format": "xgboost_json",
        "artifact_sha256": listed["predictor.json"],
        "explainer_uri": manifest_uri.replace("manifest.json", "explainer.json"),
        "explainer_sha256": listed["explainer.json"],
        "manifest_uri": manifest_uri,
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        **over,
    }


def _result(version: str, groups: int, *, label: str) -> DisparityResult:
    """Un `DisparityResult` con `groups` celdas por atributo (para fabricar informes grandes)."""
    return DisparityResult(
        population="modelo",
        model_version_id=version,
        window_from=START.date(),
        window_to=START.date(),
        attributes=[
            AttributeResult(
                attribute=attribute,  # type: ignore[arg-type]
                cells=[
                    CellResult(group=f"{label}-{attribute}-grupo-{i}", band="lt_20", n=100 + i, rate="0.5000", status="suficiente")
                    for i in range(groups)
                ],
                bands=[BandResult(band="lt_20", difference="0.0100", n_band=groups * 100)],
                aggregate="0.0100",
                population_difference_partial=False,
            )
            for attribute in ATTRIBUTES
        ],
        model_aggregate="0.0100",
    )


def initial_disparity(groups: int) -> InitialDisparity:
    """La `initial_disparity` de un informe de validacion, con `groups` celdas por atributo."""
    return InitialDisparity(attributes=_result("v", groups, label="ini").attributes, model_aggregate="0.0100", n_min=30, threshold_pp="5.0000", rule_met=False)


class FakeBias:
    """`compare_source` de bias (F25): devuelve un `PrePostReport` con `groups` celdas por atributo; guarda las solicitudes."""

    def __init__(self) -> None:
        self.requests: list[CompareSourceRequest] = []
        self.groups = 1
        self.fail = False

    def compare_source(self, request: CompareSourceRequest) -> PrePostReport:
        from vectra_common.errors import DependencyUnavailable

        if self.fail:
            raise DependencyUnavailable()
        self.requests.append(request)
        return PrePostReport(
            source_id=request.source_id,
            pre=_result("pre", self.groups, label="pre"),
            post=_result("post", self.groups, label="post"),
            delta=PrePostDelta(attributes=[], model_aggregate="0.0000"),
            threshold_pp="5.0000",
            n_min=30,
            truncated=False,
            disclaimer="El monitoreo mide disparidad y no certifica ausencia de discriminacion",
        )


def count_tables() -> dict[str, Any]:
    """`SourceCountsIn` valido: las tablas de conteo de los cuatro atributos, antes y despues."""
    table = lambda attribute: {  # noqa: E731
        "attribute": attribute,
        "cells": [{"group": "g", "band": "lt_20", "favorable": 5, "total": 10}],
    }
    return {"pre": [table(a) for a in ATTRIBUTES], "post": [table(a) for a in ATTRIBUTES]}


class ApiWorld:
    """La app de governance sobre una base de prueba, con sus dobles. `client` habla con ella por ASGI (sin red)."""

    def __init__(self, db: Db, *, replica: str = "a") -> None:
        self.db = db
        self.clock = SimClock()
        self.registry = FakeRegistry(self.clock)
        self.k8s = FakeKubernetes()
        self.store = FakeModelStore()
        self.bias = FakeBias()
        self.svc: Evidence = make_service(db, self.registry, self.clock, replica)
        self.cache = ServingConfigCache(self.svc.pools, clock=self.clock)
        self.deps = ApiDeps(
            evidence=self.svc,
            cache=self.cache,
            store=self.store,
            jobs=self.k8s.client(),
            comparer=self.bias,
            config=ApiConfig(
                validation_image=IMAGE,
                validation_dataset="s3://model-store/validation/dataset.csv",
                callback_url="http://governance-service.vectra-app.svc.cluster.local:8080",
                job_s3_endpoint="http://minio.vectra-data.svc.cluster.local:9000",
                job_token_url="https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/realms/vectra/protocol/openid-connect/token",
                assertion_audience="https://vectra.localtest.me/auth/realms/vectra",
            ),
        )
        self.app = create_governance_app(self.deps, authenticator=u0_auth.authenticator())
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app, raise_app_exceptions=False), base_url=BASE
        )

    # --- tokens (firmados con la llave de prueba de U0; el `auth_time` se mide contra el reloj simulado) ---

    def user(self, role: str, sub: str | None = None, *, mfa: bool = True, age: int = 60, scope: str | None = None) -> dict[str, str]:
        stamp = int(self.clock().timestamp())
        over: dict[str, Any] = {"sub": sub or f"{role}-1", "roles": [role], "acr": "mfa" if mfa else "pwd", "auth_time": stamp - age}
        if scope:
            over["scope"] = scope
        return u0_auth.bearer(**over)

    def service(self, azp: str, scope: str = "") -> dict[str, str]:
        return u0_auth.bearer(sub=f"svc-{azp}", roles=None, acr=None, auth_time=None, scope=scope, azp=azp)

    def refresh(self) -> None:
        """La copia de `serving-config` de esta replica se pone al dia (en produccion lo hacen `LISTEN` y el sondeo)."""
        self.cache.refresh()

    # --- lectura de vuelta ---

    def sql(self, statement: str, *params: object) -> list[dict[str, Any]]:
        return sql(self.svc, statement, *params)

    def state(self, model_id: str) -> str | None:
        rows = self.sql("SELECT state FROM model_versions WHERE model_version_id = %s", model_id)
        return None if not rows else str(rows[0]["state"])

    def count(self, table: str) -> int:
        return int(self.sql(f"SELECT count(*) AS n FROM {table}")[0]["n"])  # noqa: S608

    def chain(self, entity_id: str) -> list[str]:
        return self.registry.names(entity_id)

    def put_source(
        self, ds_id: str, *, state: str = "en_evaluacion", groups: int | None = None, proposed_by: str = "ing-1"
    ) -> None:
        """Una fuente en `state`, con un `pre_post_report` de `groups` celdas por atributo si se pide. El `INSERT` es del
        superusuario de la prueba: es el arreglo del caso, no lo que se prueba."""
        report = None
        if groups is not None:
            bias = FakeBias()
            bias.groups = groups
            report = json.dumps(bias.compare_source(CompareSourceRequest(source_id=ds_id, **count_tables())).model_dump(mode="json"))
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO data_sources (ds_id, name, description, provides_features, owner, proposed_by, state, pre_post_report) "
                "VALUES (%s, %s, 'd', %s, 'datos', %s, %s, %s)",
                (ds_id, f"fuente {ds_id}", ["f1"], proposed_by, state, report),
            )

    def source_events(self, ds_id: str) -> list[dict[str, Any]]:
        """Los `data_source_event` de la fuente en la cadena del doble del registro."""
        return [
            w.entry["payload"]
            for w in self.registry.chain
            if w.entry["entry_type"] == "data_source_event" and w.entry["payload"]["source_id"] == ds_id
        ]

    def advance(self, **delta: float) -> None:
        self.clock.advance(**delta)

    def close(self) -> None:
        self.svc.pools.close()


def wait(condition: Callable[[], bool], timeout: float = 5.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


__all__ = ["ApiWorld", "FakeBias", "FakeKubernetes", "FakeModelStore", "count_tables", "datetime", "freeze_context", "registration_body"]
