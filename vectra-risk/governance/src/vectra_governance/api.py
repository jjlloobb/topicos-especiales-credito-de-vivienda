"""Endpoints de `governance-service` (Bloque D, Paso 10; BR-U4-01..08, 10..13, 15, 16, 18, 19; US-201..203, 205, 206, 208, 305, 306).

La app sale de `create_app` de U0 con las 21 rutas del `RouteContract` de `governance-service`
(`vectra_contracts.routes`): la autenticacion, los scopes y roles, el MFA y su `auth_time` <= 15 min (el step-up de
`frozen-resolution`), el limite de cuerpo y los `Problem` los pone la fabrica. Aqui solo estan los handlers: cada uno llama a
las operaciones de `evidence.py` (U04-T03) y no repite su logica.

**Hilos.** La capa de servicio es sincrona (decision de U04-T03): cada handler corre en el hilo del *threadpool*.

**Errores.** `model_fsm.Forbidden` y `ConflictState` (y `policy`, que los reutiliza) se traducen a `vectra_common.errors`
(403 y 409) con el `reason` del catalogo `ProblemReason` de U0 cuando el motivo es uno de ellos (`transition_pending`,
`no_active_version`, `active_version_frozen`); el resto de los motivos internos no sale por la API. `RegistrationRejected` es
`422 validation_error` y no crea la version (BR-U4-06). `EntityNotFound` es 404.

**Decisiones que el diseno no fija** (bitacora de U04-T04): el estado HTTP de cada ruta es el del contrato de U0 (OpenAPI:
`POST /v1/models` responde 200 con la version; `approval`, `activation`, `freeze`, `frozen-resolution`, `decision` y
`source-counts`, 204); el `run_id` del informe F32 de `PUT /v1/models/{id}/validation-report` es la corrida de validacion
`lanzado` de la version; el `inference_service` es `isvc-` + los 8 hex finales del `model_version_id` (`mv-<fecha>-<8 hex>`).
"""

import json
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, ValidationError
from vectra_common.app_factory import Handler, RequestContext, create_app
from vectra_common.authn import Authenticator
from vectra_common.errors import ConflictState, Forbidden, NotFound, ValidationFailed, VectraError
from vectra_contracts.catalog import REASON_ALLOWED_CODE, ProblemCode, ProblemReason, Role
from vectra_contracts.models.api import InvalidParam, Page, Principal
from vectra_contracts.models.governance import (
    ActivationIn,
    DataSourceDecisionIn,
    DataSourceProposal,
    FrozenResolutionIn,
    ModelApprovalIn,
    ModelFilter,
    ModelRegistration,
    ModelVersion,
    ModelVersionDetail,
    PolicyDecisionIn,
    PolicyDraft,
    SourceComparisonIn,
    ValidationReport,
    ValidationRun,
)
from vectra_contracts.models.monitoring import FreezeContext, SourceCountsIn
from vectra_contracts.routes import REGISTRY

from vectra_governance.background import Background
from vectra_governance.clients import PackageStore, SourceComparer
from vectra_governance.convergence import ServingConfigCache
from vectra_governance.evidence import (
    EntityNotFound,
    Evidence,
    NewModel,
    Row,
    data_source_of,
    model_version_of,
    policy_version_of,
)
from vectra_governance.k8s_jobs import JobLauncher, JobSpec, job_manifest
from vectra_governance.model_fsm import Actor
from vectra_governance.model_fsm import ConflictState as FsmConflict
from vectra_governance.model_fsm import Forbidden as FsmForbidden
from vectra_governance.registration import RegistrationRejected, validate_registration

SERVICE: Final = "governance-service"
ISVC_HEX: Final = 8


@dataclass(frozen=True)
class ApiConfig:
    """Lo que el Job de validacion necesita saber (BR-U4-05): imagen, dataset, a donde devolver el informe, el endpoint S3 y la URL
    del token y la audiencia (`aud`) de su aserción. Sin valores por omision: `service.config_from_env` los lee de las variables que pone el chart."""

    validation_image: str
    validation_dataset: str
    callback_url: str
    job_s3_endpoint: str
    job_token_url: str
    assertion_audience: str


@dataclass
class ApiDeps:
    evidence: Evidence
    cache: ServingConfigCache
    store: PackageStore
    jobs: JobLauncher
    comparer: SourceComparer
    config: ApiConfig
    background: Background | None = None


# --- Errores -----------------------------------------------------------------------------------------------------------------


def problem_reason(reason: str) -> ProblemReason | None:
    """El `reason` de la API: solo los del catalogo de U0 para `conflict_state` (los demas motivos son internos)."""
    try:
        known = ProblemReason(reason)
    except ValueError:
        return None
    return known if REASON_ALLOWED_CODE[known] is ProblemCode.CONFLICT_STATE else None


@contextmanager
def translated() -> Iterator[None]:
    """`model_fsm`/`policy`/`evidence` -> `vectra_common.errors` (403, 404, 409, 422)."""
    try:
        yield
    except FsmForbidden as error:
        raise Forbidden() from error
    except FsmConflict as error:
        raise ConflictState(problem_reason(error.reason)) from error
    except EntityNotFound as error:
        raise NotFound() from error
    except RegistrationRejected as error:
        raise _invalid("package", error.reason) from error


def _invalid(name: str, reason_code: str) -> ValidationFailed:
    return ValidationFailed(invalid_params=[InvalidParam(name=name, reason_code=reason_code)])


def actor_of(principal: Principal, role: Role | None = None) -> Actor:
    """El `Actor` de `model_fsm`: la persona con su rol y `acr`, o el servicio con su cliente (`azp`)."""
    if principal.kind == "service":
        return Actor("service", principal.client_id or principal.subject)
    chosen = role if role in principal.roles else next(iter(sorted(principal.roles, key=lambda r: r.value)), None)
    return Actor("user", principal.subject, chosen, principal.acr)


def _json(body: Any, status: int = 200, headers: dict[str, str] | None = None) -> Response:
    return Response(json.dumps(body, ensure_ascii=False), status_code=status, media_type="application/json", headers=headers)


def _canonical(document: Any) -> bytes:
    """El JSON canonico de U5 (`vectra_reference.package.dump_json`): claves ordenadas, indent 2, UTF-8 y salto final."""
    return (json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError as error:
        raise NotFound() from error


# --- Lecturas ----------------------------------------------------------------------------------------------------------------


class Reads:
    """Lecturas de la API por el pool `read` (listados, informes; P-U4-04)."""

    def __init__(self, evidence: Evidence) -> None:
        self.evidence = evidence

    def one(self, statement: str, *params: object) -> Row | None:
        with self.evidence.pools.read() as conn:
            row = conn.execute(statement, params).fetchone()
            conn.rollback()
        return None if row is None else dict(row)

    def many(self, statement: str, *params: object) -> list[Row]:
        with self.evidence.pools.read() as conn:
            rows = conn.execute(statement, params).fetchall()
            conn.rollback()
        return [dict(r) for r in rows]

    def model(self, model_id: str) -> Row:
        row = self.one("SELECT * FROM model_versions WHERE model_version_id = %s", model_id)
        if row is None:
            raise NotFound()
        return row

    def policy(self, policy_id: str) -> Row:
        row = self.one("SELECT * FROM policies WHERE policy_version_id = %s", policy_id)
        if row is None:
            raise NotFound()
        return row

    def source(self, source_id: str) -> Row:
        row = self.one("SELECT * FROM data_sources WHERE ds_id = %s", source_id)
        if row is None:
            raise NotFound()
        return row

    def run(self, run_id: str) -> ValidationRun:
        row = self.one("SELECT * FROM validation_runs WHERE run_id = %s", run_id)
        if row is None:
            raise NotFound()
        return run_of(row)


def run_of(row: Row) -> ValidationRun:
    return ValidationRun.model_validate_json(
        json.dumps(
            {k: row[k] for k in ValidationRun.model_fields if k in row},
            default=lambda v: str(v) if isinstance(v, uuid.UUID) else v.isoformat() if isinstance(v, datetime) else v,
        )
    )


# --- Handlers ----------------------------------------------------------------------------------------------------------------


def isvc_name(model_version_id: str) -> str:
    """`isvc-<8 hex>` (U6): los 8 hex finales de `mv-<fecha>-<8 hex>`."""
    return f"isvc-{model_version_id[-ISVC_HEX:]}"


def build_handlers(deps: ApiDeps) -> dict[tuple[str, str], Handler]:
    evidence, reads, cache, jobs = deps.evidence, Reads(deps.evidence), deps.cache, deps.jobs

    def sync(fn: Callable[[RequestContext], BaseModel | Response | None]) -> Handler:
        async def handler(ctx: RequestContext) -> BaseModel | Response | None:
            def call() -> BaseModel | Response | None:
                with translated():
                    return fn(ctx)

            return await run_in_threadpool(call)

        return handler

    def auth_time(ctx: RequestContext) -> datetime | None:
        return ctx.principal.auth_time

    def read_package(registration: ModelRegistration) -> tuple[bytes, dict[str, bytes]]:
        """BR-U4-06 punto 2: los **bytes** del manifiesto y de cada archivo que lista (F47). Nunca se interpretan como modelo."""
        try:
            manifest = deps.store.read(registration.manifest_uri)
        except FileNotFoundError as error:
            raise _invalid("manifest_uri", "manifest_not_found") from error
        try:
            names = [e["name"] for e in json.loads(manifest)["files"]]
        except (ValueError, KeyError, TypeError):
            return manifest, {}  # `validate_registration` lo rechaza como `manifest_unreadable`
        base = registration.manifest_uri.rsplit("/", 1)[0]
        files: dict[str, bytes] = {}
        for name in names:
            if not isinstance(name, str) or "/" in name or name in ("", ".", ".."):
                continue  # un nombre que sale de la carpeta del paquete no se lee: queda `file_bytes_missing`
            try:
                files[name] = deps.store.read(f"{base}/{name}")
            except FileNotFoundError:
                continue
        return manifest, files

    def check_declared_sources(registration: ModelRegistration) -> None:
        """BR-U4-13: una version que declara una fuente no aprobada es 422, salvo la candidata de la fuente `en_evaluacion`."""
        candidate_for = registration.source_candidate_for
        for source_id in {*registration.data_sources, *([candidate_for] if candidate_for else [])}:
            source = reads.one("SELECT state FROM data_sources WHERE ds_id = %s", source_id)
            if source is None:
                raise _invalid("data_sources", "source_unknown")
            if source["state"] == "aprobada" and source_id != candidate_for:
                continue
            if source_id == candidate_for and source["state"] == "en_evaluacion":
                continue
            raise _invalid("data_sources", "source_not_approved")

    # --- modelos ---

    def register_model(ctx: RequestContext) -> BaseModel:
        body = ctx.body
        assert isinstance(body, ModelRegistration)  # noqa: S101
        manifest, files = read_package(body)
        verified = validate_registration(
            artifact_format=body.artifact_format,
            manifest_sha256=body.manifest_sha256,
            artifact_sha256=body.artifact_sha256,
            explainer_sha256=body.explainer_sha256,
            manifest=manifest,
            files=files,
        )
        check_declared_sources(body)
        evidence.register(
            actor_of(ctx.principal, Role.INGENIERO_RIESGO),
            NewModel(
                model_version_id=verified.model_version_id,
                registration=body,
                inference_service=isvc_name(verified.model_version_id),
                feature_dictionary_version=verified.feature_dictionary_version,
                feature_dictionary=verified.feature_dictionary,
                feature_spec=verified.feature_spec,
            ),
            auth_time=auth_time(ctx),
        )
        return model_version_of(reads.model(verified.model_version_id))

    def list_models(ctx: RequestContext) -> BaseModel:
        query = ctx.query
        assert isinstance(query, ModelFilter)  # noqa: S101
        where, params = ("WHERE state = ANY(%s)", [list(query.state)]) if query.state else ("", [])
        total = reads.one(f"SELECT count(*) AS n FROM model_versions {where}", *params)  # noqa: S608
        rows = reads.many(
            f"SELECT * FROM model_versions {where} ORDER BY created_at DESC, model_version_id "  # noqa: S608
            "LIMIT %s OFFSET %s",
            *params,
            query.page_size,
            (query.page - 1) * query.page_size,
        )
        return Page[ModelVersion](
            items=[model_version_of(r) for r in rows],
            page=query.page,
            total=0 if total is None else int(total["n"]),
        )

    def get_model(ctx: RequestContext) -> BaseModel:
        row = reads.model(ctx.path_params["id"])
        report = reads.one(
            "SELECT report FROM validation_runs WHERE model_version_id = %s AND mode = 'validacion' "
            "AND state = 'informe_recibido' AND report IS NOT NULL ORDER BY finished_at DESC LIMIT 1",
            row["model_version_id"],
        )
        return ModelVersionDetail(
            **model_version_of(row).model_dump(),
            validation_report=None if report is None else ValidationReport.model_validate(report["report"]),
        )

    def launch(spec: JobSpec, on_failure: Callable[[], object]) -> None:
        try:
            jobs.create(job_manifest(spec))
        except VectraError:
            on_failure()  # sin Job no hay informe: la corrida se cierra `fallido` y se responde 503
            raise

    def active_policy() -> PolicyDraft:
        """La politica `activa` que el Job usa para el `outcome` de BR-U7-04/05; sin ella no hay con que medir: 409 y sin corrida."""
        row = reads.one("SELECT * FROM policies WHERE state = 'activa'")
        if row is None:
            raise ConflictState()
        return PolicyDraft.model_validate(policy_version_of(row).model_dump(include=set(PolicyDraft.model_fields)))

    def spec_for(model: Row, run_id: str, job_name: str, policy: PolicyDraft, **extra: str) -> JobSpec:
        return JobSpec(
            job_name=job_name,
            mode="source_comparison" if extra else "validacion",
            run_id=run_id,
            model_version_id=model["model_version_id"],
            image=deps.config.validation_image,
            manifest_uri=model["manifest_uri"],
            artifact_uri=model["artifact_uri"],
            explainer_uri=model["explainer_uri"],
            dataset_ref=deps.config.validation_dataset,
            callback_url=deps.config.callback_url,
            s3_endpoint=deps.config.job_s3_endpoint,
            token_url=deps.config.job_token_url,
            assertion_audience=deps.config.assertion_audience,
            policy=policy,
            source_id=extra.get("source_id"),
            baseline_version_id=extra.get("baseline_version_id"),
        )

    def start_validation(ctx: RequestContext) -> BaseModel:
        model_id = ctx.path_params["id"]
        model = reads.model(model_id)
        actor = actor_of(ctx.principal, Role.INGENIERO_RIESGO)
        policy = active_policy()
        run_id = str(uuid.uuid4())
        job_name = f"validation-{run_id[:13]}"
        begin = evidence.retry_validation if model["state"] == "validacion_fallida" else evidence.start_validation
        begin(actor, model_id, job_name=job_name, run_id=run_id, auth_time=auth_time(ctx))
        launch(
            spec_for(model, run_id, job_name, policy),
            lambda: evidence.fail_validation(model_id, run_id, "launch_failed", run_state="fallido"),
        )
        return reads.run(run_id)

    def receive_report(ctx: RequestContext) -> None:
        body = ctx.body
        assert isinstance(body, ValidationReport)  # noqa: S101
        model_id = ctx.path_params["id"]
        reads.model(model_id)
        run = reads.one(
            "SELECT run_id FROM validation_runs WHERE model_version_id = %s AND mode = 'validacion' AND state = 'lanzado' "
            "ORDER BY started_at DESC LIMIT 1",
            model_id,
        )
        if run is None:
            raise ConflictState()
        evidence.receive_report(actor_of(ctx.principal), model_id, str(run["run_id"]), body)

    def decide_model(ctx: RequestContext) -> None:
        body = ctx.body
        assert isinstance(body, ModelApprovalIn)  # noqa: S101
        model_id = ctx.path_params["id"]
        reads.model(model_id)
        actor = actor_of(ctx.principal, Role.CRO)
        if body.decision == "aprobado":
            evidence.approve(actor, model_id, auth_time=auth_time(ctx))
            return
        if not (body.justification and body.justification.strip()):
            raise _invalid("justification", "justification_required")
        evidence.reject(actor, model_id, body.justification, auth_time=auth_time(ctx))

    def activate(ctx: RequestContext) -> None:
        body = ctx.body
        assert isinstance(body, ActivationIn)  # noqa: S101
        model_id = ctx.path_params["id"]
        reads.model(model_id)
        evidence.mark_active(
            actor_of(ctx.principal, Role.INGENIERO_RIESGO), model_id, auth_time=auth_time(ctx), evidence=body.evidence
        )

    def retire(ctx: RequestContext) -> BaseModel:
        model_id = ctx.path_params["id"]
        reads.model(model_id)
        evidence.retire(actor_of(ctx.principal, Role.CRO), model_id, auth_time=auth_time(ctx))
        return model_version_of(reads.model(model_id))

    def freeze(ctx: RequestContext) -> None:
        body = ctx.body
        assert isinstance(body, FreezeContext)  # noqa: S101
        model_id = ctx.path_params["id"]
        reads.model(model_id)
        # BR-U4-04: solo la identidad `bias-monitoring-job` (el scope `governance:freeze` ya lo pidio el contrato).
        evidence.freeze(actor_of(ctx.principal), model_id, body)

    def frozen_resolution(ctx: RequestContext) -> None:
        body = ctx.body
        assert isinstance(body, FrozenResolutionIn)  # noqa: S101
        model_id = ctx.path_params["id"]
        reads.model(model_id)
        # BR-U4-03: `cumplimiento` + MFA + `auth_time` <= 15 min (contrato: rol, `mfa`, `mfa_max_age = 900`). El
        # `SET LOCAL vectra.frozen_resolution` lo fija `evidence` al confirmar (TX2), despues de este chequeo.
        evidence.frozen_resolution(
            actor_of(ctx.principal, Role.CUMPLIMIENTO), model_id, body.action, body.justification, auth_time=auth_time(ctx)
        )

    def get_dictionary(ctx: RequestContext) -> Response:
        row = reads.one("SELECT feature_dictionary FROM model_versions WHERE model_version_id = %s", ctx.path_params["id"])
        if row is None:
            raise NotFound()
        return Response(_canonical(row["feature_dictionary"]), media_type="application/json")

    def get_feature_spec(ctx: RequestContext) -> Response:
        """BR-U4-19: el `feature_spec.json` verificado de la version, inmutable (mismos bytes que el paquete canonico de U5)."""
        row = reads.one("SELECT feature_spec FROM model_versions WHERE model_version_id = %s", ctx.path_params["id"])
        if row is None:
            raise NotFound()
        return Response(_canonical(row["feature_spec"]), media_type="application/json")

    def serving_config(ctx: RequestContext) -> Response:
        config, not_modified = cache.lookup(ctx.request.headers.get("if-none-match"))
        headers = {"ETag": f'"{config.etag}"'}
        if not_modified:
            return Response(status_code=304, headers=headers)
        return Response(
            config.model_dump_json(exclude_none=True), media_type="application/json", headers=headers
        )

    # --- politicas ---

    def list_policies(ctx: RequestContext) -> Response:
        rows = reads.many("SELECT * FROM policies ORDER BY created_at DESC, policy_version_id")
        return _json([policy_version_of(r).model_dump(mode="json", exclude_none=True) for r in rows])

    def propose_policy(ctx: RequestContext) -> BaseModel:
        body = ctx.body
        assert isinstance(body, PolicyDraft)  # noqa: S101
        policy_id = f"pol-{uuid.uuid4().hex[:12]}"
        evidence.propose_policy(actor_of(ctx.principal, Role.CRO), policy_id, body, auth_time=auth_time(ctx))
        return policy_version_of(reads.policy(policy_id))

    def decide_policy(ctx: RequestContext) -> None:
        body = ctx.body
        assert isinstance(body, PolicyDecisionIn)  # noqa: S101
        policy_id = ctx.path_params["id"]
        reads.policy(policy_id)
        actor = actor_of(ctx.principal, Role.CRO)
        if body.decision == "aprobada":
            evidence.approve_policy(actor, policy_id, auth_time=auth_time(ctx))
        else:
            evidence.reject_policy(actor, policy_id, body.justification or "", auth_time=auth_time(ctx))

    # --- fuentes de datos (US-306, Q-6) ---

    def list_sources(ctx: RequestContext) -> Response:
        rows = reads.many("SELECT * FROM data_sources ORDER BY created_at DESC, ds_id")
        return _json([data_source_of(r).model_dump(mode="json", exclude_none=True) for r in rows])

    def propose_source(ctx: RequestContext) -> BaseModel:
        body = ctx.body
        assert isinstance(body, DataSourceProposal)  # noqa: S101
        source_id = f"ds-{uuid.uuid4().hex[:12]}"
        evidence.propose_source(actor_of(ctx.principal, Role.INGENIERO_RIESGO), source_id, body, auth_time=auth_time(ctx))
        return data_source_of(reads.source(source_id))

    def decide_source(ctx: RequestContext) -> None:
        body = ctx.body
        assert isinstance(body, DataSourceDecisionIn)  # noqa: S101
        evidence.decide_source(
            actor_of(ctx.principal, Role.CUMPLIMIENTO),
            ctx.path_params["id"],
            body.decision,
            body.justification,
            auth_time=auth_time(ctx),
        )

    def start_source_comparison(ctx: RequestContext) -> BaseModel:
        """BR-U4-13 punto 2: las condiciones (409) y despues el Job en modo `source_comparison` (solo desde esta ruta)."""
        body = ctx.body
        assert isinstance(body, SourceComparisonIn)  # noqa: S101
        source_id = ctx.path_params["id"]
        actor = actor_of(ctx.principal, Role.INGENIERO_RIESGO)
        candidate, baseline = evidence.comparison_models(actor, source_id, body.candidate_version_id)
        for model in (candidate, baseline):  # INF-U4-05: los dos `InferenceService` de staging
            if not jobs.inference_service_exists(model["inference_service"]):
                raise ConflictState()
        policy = active_policy()
        run_id = str(uuid.uuid4())
        job_name = f"source-comparison-{run_id[:13]}"
        evidence.open_comparison(actor, source_id, body.candidate_version_id, run_id=run_id, job_name=job_name)
        launch(
            spec_for(candidate, run_id, job_name, policy, source_id=source_id, baseline_version_id=baseline["model_version_id"]),
            lambda: evidence.close_run(run_id, "fallido"),
        )
        return reads.run(run_id)

    def source_counts(ctx: RequestContext) -> None:
        """F32 `source-counts` y F25 `compare_source`: guarda las tablas de conteo y el `PrePostReport` de la fuente."""
        body = ctx.body
        assert isinstance(body, SourceCountsIn)  # noqa: S101
        run_id = _uuid(ctx.path_params["run_id"])
        run = evidence.open_source_counts_run(run_id)
        try:
            request = evidence.compare_request(run, body)
        except ValidationError as error:
            raise _invalid("pre", "attributes_must_be_the_four_without_repeat") from error
        report = deps.comparer.compare_source(request)
        evidence.save_source_counts(run_id, body, report)

    return {
        ("POST", "/v1/models"): sync(register_model),
        ("POST", "/v1/models/{id}/validations"): sync(start_validation),
        ("POST", "/v1/data-sources/{id}/comparisons"): sync(start_source_comparison),
        ("PUT", "/v1/validation-runs/{run_id}/source-counts"): sync(source_counts),
        ("PUT", "/v1/models/{id}/validation-report"): sync(receive_report),
        ("POST", "/v1/models/{id}/approval"): sync(decide_model),
        ("POST", "/v1/models/{id}/retirement"): sync(retire),
        ("GET", "/v1/models"): sync(list_models),
        ("GET", "/v1/models/{id}"): sync(get_model),
        ("POST", "/v1/models/{id}/activation"): sync(activate),
        ("POST", "/v1/models/{id}/freeze"): sync(freeze),
        ("POST", "/v1/models/{id}/frozen-resolution"): sync(frozen_resolution),
        ("GET", "/v1/serving-config"): sync(serving_config),
        ("GET", "/v1/models/{id}/feature-spec"): sync(get_feature_spec),
        ("GET", "/v1/models/{id}/feature-dictionary"): sync(get_dictionary),
        ("GET", "/v1/policies"): sync(list_policies),
        ("POST", "/v1/policies"): sync(propose_policy),
        ("POST", "/v1/policies/{id}/approval"): sync(decide_policy),
        ("GET", "/v1/data-sources"): sync(list_sources),
        ("POST", "/v1/data-sources"): sync(propose_source),
        ("POST", "/v1/data-sources/{id}/decision"): sync(decide_source),
    }


def create_governance_app(deps: ApiDeps, *, authenticator: Authenticator | None = None) -> FastAPI:
    """La app del servicio (puerto 8080); `app.state.ops_app` es el de 8081, con `/readyz` = copia de `serving-config` cargada."""
    app = create_app(
        SERVICE,
        REGISTRY[SERVICE],
        build_handlers(deps),
        authenticator=authenticator,
        readiness=lambda: deps.cache.ready,
        clock=deps.evidence.clock,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        deps.cache.start()
        if deps.background is not None:
            deps.background.start()
        try:
            yield
        finally:
            if deps.background is not None:
                deps.background.stop()
            deps.cache.stop()
            deps.evidence.pools.close()
            close = getattr(deps.store, "close", None)
            if close is not None:
                close()  # el cliente S3 (F47) cierra su pool de conexiones

    app.router.lifespan_context = lifespan
    return app


__all__ = ["SERVICE", "ApiConfig", "ApiDeps", "Reads", "actor_of", "create_governance_app", "isvc_name", "translated"]
