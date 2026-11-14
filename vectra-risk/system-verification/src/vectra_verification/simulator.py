"""Simulador de solicitudes (U12 Paso 6; BR-U12-01, BR-U12-02; NFR-U12-10, NFR-U12-11, NFR-U12-50; PBT-U12-01).

Lee la entrega de U5 (P-5 (a)): `datasets/test.parquet` con `pyarrow` y `adversarial/manifest.json` de la misma carpeta. De cada fila toma las
columnas de `ApplicationIn` y la valida con ese modelo (estricto: se valida desde JSON); `default` y `synthetic_id` no se envian. `generator_version` y `seed` salen del manifiesto,
y se registran el tamaño de `test` y el SHA-256 del Parquet. Escenarios `normal` (`sampler.normal`) y `stratified` (`sampler.stratified`: el volumen es un piso, se envian **todas** las filas
devueltas y el resultado trae las celdas cortas). Los escenarios `rt1` y `rt4` estan diferidos por la demo (enmienda §3 U12, fila «6»): pedirlos es `scenario_deferred`, sin solicitudes.

Envio: `POST /api/intake/v1/intake/applications` con una `Idempotency-Key` nueva por solicitud (UUID4) y `X-Test-Scenario`. Ritmo: `rate` (10/s por omision, 30/s como maximo: el limite sin
rafaga de U2), cumplido con el reloj inyectado de modo que en toda ventana de 1 s haya como mucho `rate` envios. 429 y 503 (P-8 (a)): se reenvia **la misma** solicitud (misma clave, mismo
cuerpo) hasta `MAX_RESENDS` veces y se cuenta; el contenido de una solicitud nunca cambia. `RunReport` sin datos del solicitante ni posiciones de fila; las posiciones enviadas se devuelven aparte.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final

import pyarrow.parquet as pq
from pydantic import ValidationError
from vectra_contracts.labels import derive_monitoring_labels
from vectra_contracts.models.application import ApplicationIn

from vectra_verification import guard, sampler
from vectra_verification.clients._api import ApiError
from vectra_verification.clients.gateway import GatewayClient
from vectra_verification.clock import Clock
from vectra_verification.guard import Environment

SCENARIOS: Final = ("normal", "stratified")
DEFERRED: Final = ("rt1", "rt4")
DEFAULT_RATE: Final = 10.0
MAX_RATE: Final = 30.0  # `intake-channel-simulator` de U2: 30/s sin rafaga
MAX_RESENDS: Final = 3
RESEND_STATUSES: Final = (429, 503)
RELEASE_HINT: Final = "make -C reference-model release"
DELIVERY_FILES: Final = ("datasets/test.parquet", "adversarial/manifest.json")
APPLICATION_COLUMNS: Final = frozenset(ApplicationIn.model_fields)
OPTIONAL_COLUMNS: Final = frozenset(
    {"sex", "socioeconomic_stratum", "broker_id", "free_text"}
)  # con valor por omision en `ApplicationIn`


class SimulatorError(Exception):
    """Un fallo del simulador antes de enviar (o de leer la entrega). El mensaje empieza por un codigo estable y no lleva datos del solicitante."""


@dataclass(frozen=True)
class Population:
    """La particion `test` de U5 leida: una solicitud y una fila de muestreo por posicion, y con que se genero."""

    applications: tuple[ApplicationIn, ...]
    rows: tuple[sampler.Row, ...]
    generator_version: str
    seed: int
    test_rows: int
    parquet_sha256: str


def read_delivery(directory: Path, evaluated_on: datetime) -> Population:
    """Lee la entrega de U5. Una carpeta sin esos archivos es un error claro que dice como generarla."""
    parquet, manifest_file = (directory / name for name in DELIVERY_FILES)
    for path in (parquet, manifest_file):
        if not path.is_file():
            raise SimulatorError(f"u5_delivery_missing:{path.name}: genere la entrega con `{RELEASE_HINT}`")
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        generator_version, seed = str(manifest["generator_version"]), int(manifest["seed"])
    except (ValueError, KeyError, TypeError):
        raise SimulatorError(f"u5_manifest_invalid: regenere la entrega con `{RELEASE_HINT}`") from None
    table = pq.read_table(parquet)
    missing = APPLICATION_COLUMNS - OPTIONAL_COLUMNS - set(table.column_names)
    if missing:
        raise SimulatorError(f"u5_columns_missing:{','.join(sorted(missing))}")
    applications: list[ApplicationIn] = []
    for record in table.to_pylist():
        payload = {
            name: value for name, value in record.items() if name in APPLICATION_COLUMNS
        }  # sin `default` ni `synthetic_id`
        try:
            applications.append(ApplicationIn.model_validate_json(json.dumps(payload)))
        except ValidationError:
            raise SimulatorError(f"u5_row_invalid:{len(applications)}") from None
    on = evaluated_on.date()
    rows = tuple(
        sampler.Row(
            str(i), _groups(labels := derive_monitoring_labels(application, on)), labels.banda_capacidad_pago
        )
        for i, application in enumerate(applications)
    )
    digest = hashlib.sha256(parquet.read_bytes()).hexdigest()
    return Population(tuple(applications), rows, generator_version, seed, len(applications), digest)


def _groups(labels: Any) -> dict[str, str]:
    return {
        "sexo": labels.sexo,
        "rango_edad": labels.rango_edad,
        "region": labels.region,
        "estrato": labels.estrato,
    }


@dataclass(frozen=True)
class RunReport:
    """domain-entities §2 mas lo de la tarea. Sin datos del solicitante: ningun campo de `ApplicationIn` ni la posicion de las filas."""

    scenario: str
    sent: int
    accepted: int
    rejected_by_code: dict[str, int]
    case_ids: tuple[str, ...]
    started_at: datetime
    finished_at: datetime
    generator_version: str
    seed: int
    sampling_seed: int
    rate: float
    run_prefix: str
    test_rows: int
    parquet_sha256: str
    resends: int
    short_cells: tuple[sampler.CellReport, ...] = ()


@dataclass(frozen=True)
class SimulationResult:
    report: RunReport
    sent_positions: tuple[
        int, ...
    ]  # aparte del `RunReport`: U12-T04 detecta con ellas «solicitudes repetidas entre escenarios» (NFR-U12-11)


def pace(clock: Clock, rate: float, last_sent: float | None) -> float:
    """Espera (con el reloj inyectado) hasta `1 / rate` despues del envio anterior; devuelve el instante del envio."""
    interval = 1.0 / rate
    now = clock.monotonic()
    if last_sent is not None and now - last_sent < interval:
        clock.sleep(interval - (now - last_sent))
        now = clock.monotonic()
    return now


class Simulator:
    def __init__(
        self,
        environment: Environment,
        gateway: GatewayClient,
        clock: Clock,
        population: Population,
        run_prefix: str,
    ) -> None:
        self._environment = environment
        self._gateway = gateway
        self._clock = clock
        self._population = population
        self._prefix = run_prefix
        self.keys_used: list[str] = []

    def select(
        self, scenario: str, volume: int, seed: int, min_per_cell: int = sampler.MIN_PER_CELL
    ) -> tuple[tuple[int, ...], tuple[sampler.CellReport, ...]]:
        if scenario in DEFERRED:
            raise SimulatorError(f"scenario_deferred:{scenario}")
        if scenario not in SCENARIOS:
            raise SimulatorError(f"scenario_unknown:{scenario}")
        if scenario == "normal":
            return tuple(int(i) for i in sampler.normal(self._population.rows, volume, seed)), ()
        sample = sampler.stratified(self._population.rows, volume, seed, min_per_cell)
        return tuple(int(i) for i in sample.ids), sample.short

    def run(
        self, scenario: str, volume: int, seed: int, *, rate: float = DEFAULT_RATE, section: str = "decisions"
    ) -> SimulationResult:
        """Envia la muestra. Todo se comprueba **antes** de la primera solicitud: escenario, ritmo, seccion y barrera horaria."""
        if scenario in DEFERRED or scenario not in SCENARIOS:
            self.select(scenario, 0, seed)  # el error claro
        if not 0 < rate <= MAX_RATE:
            raise SimulatorError(f"rate_out_of_range:{rate}>{MAX_RATE}")
        guard.check_section(self._environment, section)
        if section == "decisions":
            guard.check_decisions(self._environment, self._clock.now(), volume, rate)
        positions, short = self.select(scenario, volume, seed)
        started = self._clock.now()
        accepted, resends = 0, 0
        rejected: Counter[str] = Counter()
        case_ids: list[str] = []
        last_sent: float | None = None
        for position in positions:
            key = str(uuid.uuid4())
            self.keys_used.append(key)
            application = self._population.applications[position]
            for attempt in range(MAX_RESENDS + 1):
                last_sent = pace(self._clock, rate, last_sent)
                try:
                    reference = self._gateway.submit_application(application, key)
                except ApiError as error:
                    if error.status in RESEND_STATUSES and attempt < MAX_RESENDS:
                        resends += 1
                        if error.retry_after:
                            self._clock.sleep(error.retry_after)
                        continue
                    rejected[error.code or f"http_{error.status}"] += 1
                else:
                    accepted += 1
                    case_ids.append(str(reference.case_id))
                break
        report = RunReport(
            scenario=scenario,
            sent=len(positions),
            accepted=accepted,
            rejected_by_code=dict(rejected),
            case_ids=tuple(case_ids),
            started_at=started,
            finished_at=self._clock.now(),
            generator_version=self._population.generator_version,
            seed=self._population.seed,
            sampling_seed=seed,
            rate=rate,
            run_prefix=self._prefix,
            test_rows=self._population.test_rows,
            parquet_sha256=self._population.parquet_sha256,
            resends=resends,
            short_cells=short,
        )
        return SimulationResult(report, positions)
