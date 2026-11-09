"""`serving-config` en memoria y convergencia entre replicas (P-U4-01, P-U4-05; NFR-U4-04, 05, 06, 10; Paso 9).

`GET /v1/serving-config` se responde desde la copia en memoria de la replica: no usa ningun pool (P-U4-04). La copia se
recalcula con tres senales:

1. `LISTEN serving_config`: la transaccion que confirma una transicion termina con `NOTIFY` y la replica recarga al instante;
2. el **sondeo** del `etag` (`SELECT etag FROM serving_config`), que cubre las notificaciones perdidas por una conexion
   caida. Cada vuelta que llega a la base **confirma** la copia (alimenta la edad); si el `etag` cambio, recarga;
3. el temporizador de las 00:00 de Bogota: `normative_current` cambia con la fecha (P-U4-05) y por eso cambia el `etag`.
   Recalcula con los insumos ya cargados, sin tocar la base.

**Edad de la copia** (NFR-U4-04): `vectra_serving_config_age_seconds` son los segundos desde la ultima confirmacion contra la
base. A los 30 s sin confirmar la replica deja de servir y responde 503 (`ServingConfigUnavailable`); tampoco sirve antes de
cargar la copia (readiness: `ready`) ni cuando no hay version servible o politica activa. Con varias replicas en un mismo
proceso (las pruebas), el gauge lo publica la ultima que arranca.

**Decision que el diseno no fija**: el periodo del sondeo es de 0,5 s y no de 1 s. P-U4-01 pide «cada 1 s» y NFR-U4-05 pide
convergencia en <= 1 s con la conexion `LISTEN` cortada: con un periodo de 1 s mas el tiempo de la consulta, el peor caso
pasaria de 1 s. Con 0,5 s el sondeo sigue siendo «al menos cada 1 s» (NFR-U4-04) y la cota se cumple.
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final

import psycopg
from prometheus_client import Gauge
from vectra_common.errors import DependencyUnavailable
from vectra_common.metrics import REGISTRY
from vectra_contracts.models.governance import ModelVersion, PolicyVersion, ServingConfig

from vectra_governance.evidence import Clock, model_version_of, policy_version_of, utc_now
from vectra_governance.policy import bogota_date
from vectra_governance.pools import Pools
from vectra_governance.serving_config import compose

log = logging.getLogger(__name__)

POLL_INTERVAL: Final = 0.5
MAX_AGE: Final = 30.0
MIDNIGHT_CHECK: Final = 1.0
CHANNEL: Final = "serving_config"

SERVING_CONFIG_AGE: Final = Gauge(
    "vectra_serving_config_age_seconds",
    "Segundos desde la ultima confirmacion de la copia de serving-config contra la base (NFR-U4-04)",
    registry=REGISTRY,
)


class ServingConfigUnavailable(DependencyUnavailable):
    """503: la copia no esta cargada, esta vencida (30 s sin confirmar) o no hay configuracion servible.

    `reason`: `not_loaded`, `serving_config_stale` o `no_serving_config` (el Paso 10 lo traduce a `ProblemReason`).
    """

    def __init__(self, detail: str) -> None:
        super().__init__()
        self.detail = detail


@dataclass(frozen=True)
class Inputs:
    """Lo que se leyo de la base: con esto se recalcula la copia sin volver a ella (medianoche de Bogota)."""

    db_etag: str | None
    model: ModelVersion | None
    policy: PolicyVersion | None
    effective_from: datetime | None


def etag_matches(header: str | None, etag: str) -> bool:
    """`If-None-Match` (RFC 9110): una lista de etags, con o sin `W/` y comillas; `*` siempre coincide."""
    if header is None:
        return False
    for part in header.split(","):
        candidate = part.strip()
        if candidate == "*":
            return True
        if candidate.startswith("W/"):
            candidate = candidate[2:]
        if candidate.strip('"') == etag:
            return True
    return False


class ServingConfigCache:
    def __init__(
        self,
        pools: Pools,
        *,
        clock: Clock = utc_now,
        monotonic: Callable[[], float] = time.monotonic,
        poll_interval: float = POLL_INTERVAL,
        midnight_check: float = MIDNIGHT_CHECK,
        max_age: float = MAX_AGE,
    ) -> None:
        self.pools = pools
        self.clock = clock
        self.monotonic = monotonic
        self.poll_interval = poll_interval
        self.midnight_check = midnight_check
        self.max_age = max_age
        self._lock = threading.Lock()
        self._inputs: Inputs | None = None
        self._config: ServingConfig | None = None
        self._day: date | None = None
        self._confirmed_at = monotonic()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._threads: list[threading.Thread] = []
        self.listening = False

    # --- lectura (sin pool) ------------------------------------------------------------------------------------------------

    @property
    def ready(self) -> bool:
        """Readiness (P-U4-01): solo con la copia cargada."""
        with self._lock:
            return self._inputs is not None

    def age_seconds(self) -> float:
        """Segundos desde la ultima confirmacion contra la base (o desde el arranque, si aun no cargo)."""
        return max(0.0, self.monotonic() - self._confirmed_at)

    def current(self) -> ServingConfig:
        with self._lock:
            if self._inputs is None:
                raise ServingConfigUnavailable("not_loaded")
            if self.monotonic() - self._confirmed_at >= self.max_age:
                raise ServingConfigUnavailable("serving_config_stale")
            if self._config is None:
                raise ServingConfigUnavailable("no_serving_config")
            return self._config

    def lookup(self, if_none_match: str | None = None) -> tuple[ServingConfig, bool]:
        """`(config, not_modified)`: con `If-None-Match` igual al `etag` vigente, el Paso 10 responde 304."""
        config = self.current()
        return config, etag_matches(if_none_match, config.etag)

    # --- carga -------------------------------------------------------------------------------------------------------------

    def refresh(self) -> bool:
        """Confirma la copia contra la base y recarga si cambio el `etag` o el dia de Bogota. Devuelve si recargo."""
        now = self.clock()
        with self.pools.background() as conn:
            row = conn.execute("SELECT etag FROM serving_config WHERE id = 1").fetchone()
            conn.rollback()
            if row is None:
                raise DependencyUnavailable()
            with self._lock:
                same = (
                    self._inputs is not None
                    and self._inputs.db_etag == row["etag"]
                    and self._day == bogota_date(now)
                )
            if same:
                self._confirmed_at = self.monotonic()
                return False
            conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ  # una sola foto: fila, modelo y politica
            try:
                with conn.transaction():
                    sc = conn.execute("SELECT * FROM serving_config WHERE id = 1").fetchone()
                    assert sc is not None
                    model = (
                        None
                        if sc["model_version_id"] is None
                        else conn.execute(
                            "SELECT * FROM model_versions WHERE model_version_id = %s", (sc["model_version_id"],)
                        ).fetchone()
                    )
                    policy = (
                        None
                        if sc["policy_version_id"] is None
                        else conn.execute(
                            "SELECT * FROM policies WHERE policy_version_id = %s", (sc["policy_version_id"],)
                        ).fetchone()
                    )
            finally:
                conn.isolation_level = None
        inputs = Inputs(
            db_etag=sc["etag"],
            model=None if model is None else model_version_of(model),
            policy=None if policy is None else policy_version_of(policy),
            effective_from=sc["effective_from"],
        )
        self._install(inputs, now)
        self._confirmed_at = self.monotonic()
        return True

    def _install(self, inputs: Inputs, now: datetime) -> None:
        config = (
            None
            if inputs.model is None or inputs.policy is None or inputs.effective_from is None
            else compose(inputs.model, inputs.policy, inputs.effective_from, now)
        )
        with self._lock:
            self._inputs, self._config, self._day = inputs, config, bogota_date(now)

    def apply_clock(self) -> bool:
        """Temporizador de las 00:00 de Bogota (P-U4-05): recalcula `normative_current` y el `etag` sin tocar la base."""
        now = self.clock()
        with self._lock:
            inputs, day = self._inputs, self._day
        if inputs is None or day == bogota_date(now):
            return False
        self._install(inputs, now)
        return True

    # --- hilos -------------------------------------------------------------------------------------------------------------

    def start(self) -> None:
        """Arranca el sondeo, la escucha y el temporizador. La copia se carga en la primera vuelta (`wait_ready`)."""
        self._stop.clear()
        self._confirmed_at = self.monotonic()
        SERVING_CONFIG_AGE.set_function(self.age_seconds)
        for name, target in (("poll", self._poll_loop), ("listen", self._listen_loop), ("midnight", self._midnight_loop)):
            thread = threading.Thread(target=target, name=f"governance-{name}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def wait_ready(self, timeout: float) -> bool:
        deadline = self.monotonic() + timeout
        while self.monotonic() < deadline:
            if self.ready:
                return True
            time.sleep(0.01)
        return self.ready

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        for thread in self._threads:
            thread.join(timeout=5)
        self._threads.clear()

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.refresh()
            except (psycopg.Error, DependencyUnavailable):
                log.warning("no se pudo confirmar serving-config contra la base; la copia envejece")
            self._wake.wait(self.poll_interval)
            self._wake.clear()

    def _listen_loop(self) -> None:
        backoff = 0.1
        while not self._stop.is_set():
            conn = None
            try:
                conn = self.pools.listen_connection()
                conn.execute(f"LISTEN {CHANNEL}")
                self.listening = True
                self._wake.set()  # lo que llego mientras no escuchaba lo cubre esta recarga
                backoff = 0.1
                while not self._stop.is_set():
                    for _ in conn.notifies(timeout=0.5):
                        self._wake.set()
            except (psycopg.Error, DependencyUnavailable):
                log.warning("se cayo la conexion LISTEN; el sondeo mantiene el limite de 1 s")
            finally:
                self.listening = False
                if conn is not None:
                    try:
                        conn.close()
                    except psycopg.Error:
                        pass
            self._stop.wait(backoff)
            backoff = min(backoff * 2, 5.0)

    def _midnight_loop(self) -> None:
        while not self._stop.wait(self.midnight_check):
            if self.apply_clock():
                log.info("cambio de dia en Bogota: normative_current recalculado")
