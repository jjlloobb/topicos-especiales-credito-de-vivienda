"""Agregador de monitoreo (Paso 12 acotado a la demo; BR-U3-17; business-logic-model §2.5; NFR-U3-24, 42), con PostgreSQL real.

Una prueba por viñeta de aceptacion del plan sobre el agregador. La siembra es cruda (`raw_insert`): el agregador solo lee el `payload`
y las columnas, no la cadena de hashes. `monitoring_freezes` con un `reactivar` es de la proyeccion y ya lo prueba
`test_queries.py::test_br_u3_17_freezes_un_reactivar_deja_resolutions_con_su_recorded_at`.
"""

import asyncio
import threading
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import psycopg
import pytest
from cli_support import LABELS, decision, dsn, raw_insert, rec
from registry_pg import Db
from testcontainers.postgres import PostgresContainer
from vectra_contracts.catalog import Scope
from vectra_contracts.models.monitoring import DayRange, MonitoringQuery, MonitoringRangeRequest
from vectra_registry import aggregator
from vectra_registry.pools import Pools
from vectra_registry.queries import monitoring_daily

pytestmark = pytest.mark.integration

NOW = datetime.now(UTC).replace(microsecond=0)
DAY = NOW - timedelta(days=3)
OTHER = {"sexo": "M", "rango_edad": "66+", "region": "caribe", "estrato": "6", "banda_capacidad_pago": "gt_30"}
INVALID = {"sexo": "F", "rango_edad": "26-35", "region": "marte", "estrato": "3", "banda_capacidad_pago": "lt_20"}


def case(n: int) -> uuid.UUID:
    return uuid.UUID(int=n + 1)


class Agg:
    def __init__(self, pg: PostgresContainer, db: Db) -> None:
        self.pg, self.db = pg, db

    @property
    def dsn(self) -> str:
        return dsn(self.pg, self.db, "registry_aggregator")

    def run(self, **kwargs: Any) -> aggregator.RunReport:
        return aggregator.run(self.dsn, clock=lambda: NOW, **kwargs)

    def daily(self) -> dict[tuple[Any, ...], int]:
        rows = self.db.query('SELECT population, model_version_id, day, attribute, "group", band, result, decision, count FROM monitoring_daily')
        return {tuple(r[:8]): int(r[8]) for r in rows}  # type: ignore[call-overload]

    def cell(self, population: str, version: str, day: datetime, attribute: str, group: str, band: str, result: str, decision: str = "-") -> int:
        return self.daily().get((population, version, day.date(), attribute, group, band, result, decision), 0)

    def totals(self) -> dict[tuple[Any, ...], tuple[int, int]]:
        rows = self.db.query("SELECT population, model_version_id, day, total, invalid FROM monitoring_entry_totals")
        return {tuple(r[:3]): (int(r[3]), int(r[4])) for r in rows}  # type: ignore[call-overload]

    def invalid(self) -> list[tuple[Any, ...]]:
        return [tuple(r) for r in self.db.query("SELECT seq, population, model_version_id, day, reason FROM monitoring_invalid ORDER BY seq")]

    def index(self) -> dict[uuid.UUID, tuple[Any, ...]]:
        rows = self.db.query("SELECT case_id, counted_seq, fixed_by_decision FROM monitoring_case_index")
        return {r[0]: (r[1], r[2]) for r in rows}  # type: ignore[misc]

    def watermark(self) -> int:
        return int(self.db.query("SELECT last_seq FROM monitoring_watermark WHERE id = 1")[0][0])  # type: ignore[call-overload]


@pytest.fixture
def agg(pg: PostgresContainer, db: Db) -> Agg:
    return Agg(pg, db)


def marginals(agg: Agg, version: str, day: datetime, labels: dict[str, str], result: str = "favorable") -> list[int]:
    band = labels["banda_capacidad_pago"]
    return [agg.cell("modelo", version, day, a, labels[a], band, result) for a in ("sexo", "rango_edad", "region", "estrato")]


# --- Lote atomico: la marca de agua avanza en la misma transaccion que los conteos ------------------------------------------


class Boom(Exception):
    pass


def boom_at(batch: int) -> Any:
    seen = {"n": 0}

    def hook() -> None:
        seen["n"] += 1
        if seen["n"] == batch:
            raise Boom

    return hook


def test_la_marca_de_agua_y_los_conteos_se_confirman_o_se_deshacen_juntos(agg: Agg) -> None:
    raw_insert(agg.db, [rec(DAY + timedelta(minutes=i), case(i)) for i in range(3)])
    with pytest.raises(Boom):
        agg.run(before_commit=boom_at(1))
    assert agg.watermark() == 0 and agg.daily() == {} and agg.totals() == {} and agg.index() == {}
    agg.run()
    assert agg.watermark() == 3 and sum(agg.daily().values()) == 12


def test_si_falla_el_avance_de_la_marca_tambien_se_deshacen_los_conteos(agg: Agg) -> None:
    """La marca de agua se escribe en la misma transaccion que los conteos: sin eso, repetir el lote contaria dos veces."""
    raw_insert(agg.db, [rec(DAY + timedelta(minutes=i), case(i)) for i in range(3)])
    with agg.db.connect() as conn:
        conn.execute("CREATE FUNCTION no_avanza() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'marca bloqueada'; END $$")
        conn.execute("CREATE TRIGGER no_avanza BEFORE UPDATE ON monitoring_watermark FOR EACH ROW EXECUTE FUNCTION no_avanza()")
    with pytest.raises(psycopg.errors.RaiseException):
        agg.run()
    assert agg.watermark() == 0 and agg.daily() == {} and agg.totals() == {} and agg.index() == {}
    with agg.db.connect() as conn:
        conn.execute("DROP TRIGGER no_avanza ON monitoring_watermark")
    agg.run()
    assert agg.watermark() == 3 and sum(agg.daily().values()) == 12  # contadas una sola vez


def test_matar_el_proceso_entre_lotes_y_reanudar_da_los_mismos_conteos(agg: Agg) -> None:
    raw_insert(agg.db, [rec(DAY + timedelta(minutes=i), case(i), outcome="favorable" if i % 2 else "desfavorable") for i in range(7)])
    with pytest.raises(Boom):
        agg.run(size=2, before_commit=boom_at(3))
    assert agg.watermark() == 4  # dos lotes confirmados; el tercero se deshizo entero
    partial = sum(agg.daily().values())
    assert partial == 4 * 4
    report = agg.run(size=2)
    assert report.reached_head and agg.watermark() == 7
    # Los mismos conteos que una corrida sin cortes (7 casos, 4 marginales cada uno).
    assert sum(agg.daily().values()) == 7 * 4
    assert agg.totals() == {("modelo", "mv-1", DAY.date()): (7, 0)}
    assert agg.run().entries == 0  # repetir no cambia nada
    assert sum(agg.daily().values()) == 28


def test_20000_pendientes_la_misma_corrida_llega_a_la_cabeza(agg: Agg) -> None:
    raw_insert(agg.db, [rec(DAY, uuid.uuid4()) for _ in range(20_000)])
    report = agg.run()
    assert (report.reached_head, report.batches, report.entries) == (True, 4, 20_000)
    assert agg.watermark() == 20_000
    assert agg.cell("modelo", "mv-1", DAY, "sexo", "F", "lt_20", "favorable") == 20_000
    assert agg.totals() == {("modelo", "mv-1", DAY.date()): (20_000, 0)}
    assert report.lag_seconds == 0


def test_el_cronjob_se_corta_a_los_240_s_y_until_head_no(agg: Agg) -> None:
    raw_insert(agg.db, [rec(DAY, uuid.uuid4()) for _ in range(20_000)])
    ticks = iter(range(0, 10**6, 1000))  # cada lectura del reloj avanza 1000 s
    cut = agg.run(monotonic=lambda: float(next(ticks)), size=5000)
    assert (cut.reached_head, cut.batches, agg.watermark()) == (False, 1, 5000)
    assert cut.lag_seconds >= 0
    ticks = iter(range(0, 10**6, 1000))
    rest = agg.run(until_head=True, monotonic=lambda: float(next(ticks)), size=5000)
    assert (rest.reached_head, rest.batches, agg.watermark()) == (True, 3, 20_000)
    assert agg.cell("modelo", "mv-1", DAY, "sexo", "F", "lt_20", "favorable") == 20_000


def test_el_atraso_es_0_en_la_cabeza_y_mayor_que_0_si_no(agg: Agg) -> None:
    raw_insert(agg.db, [rec(DAY, case(i), recorded_at=NOW - timedelta(minutes=45)) for i in range(4)])
    cut = agg.run(size=2, seconds=0)
    assert (cut.reached_head, cut.lag_seconds) == (False, 45 * 60)
    assert agg.run().lag_seconds == 0


# --- Una recomendacion por caso ---------------------------------------------------------------------------------------------


def test_restar_relee_las_etiquetas_de_registry_entries_por_counted_seq(agg: Agg) -> None:
    columns = [r[0] for r in agg.db.query("SELECT column_name FROM information_schema.columns WHERE table_name = 'monitoring_case_index' ORDER BY ordinal_position")]
    assert columns == ["case_id", "counted_seq", "evaluated_at", "fixed_by_decision"]
    first, second = raw_insert(agg.db, [rec(DAY, case(1)), rec(DAY + timedelta(hours=1), case(1), labels=OTHER, outcome="desfavorable")])
    agg.run(size=1)  # cada una en su lote: para restar la primera hay que releerla
    assert marginals(agg, "mv-1", DAY, LABELS) == [0, 0, 0, 0]
    assert marginals(agg, "mv-1", DAY, OTHER, "desfavorable") == [1, 1, 1, 1]
    assert agg.index() == {case(1): (second, False)}
    assert agg.totals() == {("modelo", "mv-1", DAY.date()): (2, 0)}
    assert first < second


def test_una_recomendacion_mas_vieja_que_la_contada_no_cambia_nada(agg: Agg) -> None:
    raw_insert(agg.db, [rec(DAY + timedelta(hours=2), case(1)), rec(DAY, case(1), labels=OTHER)])
    agg.run()
    assert marginals(agg, "mv-1", DAY, LABELS) == [1, 1, 1, 1]
    assert marginals(agg, "mv-1", DAY, OTHER) == [0, 0, 0, 0]


def test_empate_de_evaluated_at_gana_el_mayor_seq(agg: Agg) -> None:
    _, second = raw_insert(agg.db, [rec(DAY, case(1)), rec(DAY, case(1), labels=OTHER)])
    agg.run(size=1)
    assert agg.index() == {case(1): (second, False)}
    assert marginals(agg, "mv-1", DAY, OTHER) == [1, 1, 1, 1]


def test_una_recomendacion_invalida_nunca_reemplaza_a_la_contada(agg: Agg) -> None:
    good, bad = raw_insert(agg.db, [rec(DAY, case(1)), rec(DAY + timedelta(hours=1), case(1), labels=INVALID)])
    agg.run()
    assert agg.index() == {case(1): (good, False)}
    assert agg.totals() == {("modelo", "mv-1", DAY.date()): (2, 1)}
    assert [r[0] for r in agg.invalid()] == [bad]
    assert sum(agg.daily().values()) == 4


def test_una_entrada_con_region_fuera_del_catalogo_cuenta_como_invalida_con_su_seq(agg: Agg) -> None:
    (seq,) = raw_insert(agg.db, [rec(DAY, case(1), labels=INVALID)])
    agg.run()
    assert agg.daily() == {} and agg.index() == {}
    assert agg.totals() == {("modelo", "mv-1", DAY.date()): (1, 1)}
    assert agg.invalid() == [(seq, "modelo", "mv-1", DAY.date(), "etiquetas_invalidas")]


# --- Decisiones humanas -----------------------------------------------------------------------------------------------------


def test_una_decision_suma_en_humana_con_las_etiquetas_de_la_referenciada_y_fija_el_caso(agg: Agg) -> None:
    (ref,) = raw_insert(agg.db, [rec(DAY, case(1))])
    _decide(agg, ref, DAY + timedelta(hours=1), case(1))
    (late,) = raw_insert(agg.db, [rec(DAY + timedelta(hours=2), case(1), labels=OTHER)])
    agg.run(size=1)
    day = DAY + timedelta(hours=1)
    assert agg.cell("humana", "mv-1", day, "sexo", "F", "lt_20", "favorable", "sigue") == 1
    assert agg.index() == {case(1): (ref, True)}
    assert marginals(agg, "mv-1", DAY, OTHER) == [0, 0, 0, 0]  # la posterior a la decision no cambia nada
    assert agg.totals()[("humana", "mv-1", day.date())] == (1, 0)
    assert late == ref + 2


def _decide(agg: Agg, ref: int, at: datetime, c: uuid.UUID, **kwargs: Any) -> int:
    return raw_insert(agg.db, [decision(at, c, ref, **kwargs)])[0]


def test_una_decision_que_referencia_una_recomendacion_anterior_resta_la_mas_reciente_y_suma_la_referenciada(agg: Agg) -> None:
    old, new = raw_insert(agg.db, [rec(DAY, case(1)), rec(DAY + timedelta(hours=1), case(1), labels=OTHER)])
    agg.run()
    assert agg.index() == {case(1): (new, False)}
    _decide(agg, old, DAY + timedelta(hours=2), case(1))
    agg.run()
    assert agg.index() == {case(1): (old, True)}
    assert marginals(agg, "mv-1", DAY, OTHER) == [0, 0, 0, 0]
    assert marginals(agg, "mv-1", DAY, LABELS) == [1, 1, 1, 1]
    assert agg.cell("humana", "mv-1", DAY + timedelta(hours=2), "region", "andina", "lt_20", "favorable", "sigue") == 1


def test_una_decision_sobre_una_inexistente_es_no_atribuible_y_unattributable_invalid_es_1(agg: Agg, pg: PostgresContainer) -> None:
    seq = _decide(agg, 99_999, DAY, case(1))
    agg.run()
    assert agg.totals() == {("humana", "-", DAY.date()): (1, 1)}
    assert agg.invalid() == [(seq, "humana", "-", DAY.date(), "no_atribuible")]
    assert agg.daily() == {} and agg.index() == {}
    assert unattributable(pg, agg.db, DAY.date()) == 1


def test_una_decision_sobre_una_entrada_freeze_es_igual_que_inexistente(agg: Agg, pg: PostgresContainer) -> None:
    (freeze,) = raw_insert(agg.db, [{"entry_type": "freeze", "model_version_id": "mv-1", "recorded_at": DAY, "payload": {}}])
    seq = _decide(agg, freeze, DAY, case(1))
    agg.run()
    assert agg.totals() == {("humana", "-", DAY.date()): (1, 1)}
    assert agg.invalid() == [(seq, "humana", "-", DAY.date(), "no_atribuible")]
    assert unattributable(pg, agg.db, DAY.date()) == 1


def test_una_decision_sobre_una_recomendacion_invalida_fija_el_caso_con_counted_seq_null(agg: Agg) -> None:
    good, bad = raw_insert(agg.db, [rec(DAY, case(1)), rec(DAY + timedelta(hours=1), case(1), labels=INVALID)])
    agg.run()
    assert marginals(agg, "mv-1", DAY, LABELS) == [1, 1, 1, 1]
    dec = _decide(agg, bad, DAY + timedelta(hours=2), case(1))
    (later,) = raw_insert(agg.db, [rec(DAY + timedelta(hours=3), case(1), labels=OTHER)])
    agg.run()
    assert agg.index() == {case(1): (None, True)}
    assert marginals(agg, "mv-1", DAY, LABELS) == [0, 0, 0, 0]  # se resto la contada
    assert marginals(agg, "mv-1", DAY, OTHER) == [0, 0, 0, 0]  # la valida posterior no suma en `modelo`
    assert {r[0] for r in agg.invalid()} == {bad, dec}
    assert agg.totals()[("humana", "mv-1", (DAY + timedelta(hours=2)).date())] == (1, 1)
    assert not [k for k in agg.daily() if k[0] == "humana"]
    assert good < bad < dec < later


def test_una_decision_sobre_una_invalida_sin_fila_previa_crea_el_indice_con_el_evaluated_at_de_la_referenciada(agg: Agg) -> None:
    (bad,) = raw_insert(agg.db, [rec(DAY, case(1), labels=INVALID)])
    _decide(agg, bad, DAY + timedelta(hours=1), case(1))
    agg.run()
    (row,) = agg.db.query("SELECT counted_seq, evaluated_at, fixed_by_decision FROM monitoring_case_index")
    assert (row[0], row[1], row[2]) == (None, DAY, True)


# --- Retencion de 180 dias --------------------------------------------------------------------------------------------------


def test_purga_borra_181_dias_y_deja_179_en_las_cuatro_tablas(agg: Agg) -> None:
    old, new = NOW - timedelta(days=181), NOW - timedelta(days=179)
    edge = NOW - timedelta(days=180)
    with agg.db.connect() as conn:
        for day in (old, edge, new):
            conn.execute(
                "INSERT INTO monitoring_daily VALUES ('modelo', 'mv-1', %s, 'sexo', 'F', 'lt_20', 'favorable', '-', 5)", (day.date(),)
            )
            conn.execute("INSERT INTO monitoring_entry_totals VALUES ('modelo', 'mv-1', %s, 5, 1)", (day.date(),))
            conn.execute("INSERT INTO monitoring_invalid VALUES (%s, 'modelo', 'mv-1', %s, 'x')", (day.toordinal(), day.date()))
            conn.execute("INSERT INTO monitoring_case_index VALUES (%s, 1, %s, false)", (uuid.uuid4(), day))
    report = agg.run()
    assert report.purged == 4
    assert {k[2] for k in agg.daily()} == {edge.date(), new.date()}
    assert {k[2] for k in agg.totals()} == {edge.date(), new.date()}
    assert [r[3] for r in agg.invalid()] == [edge.date(), new.date()]
    assert len(agg.db.query("SELECT 1 FROM monitoring_case_index")) == 2


def test_una_entrada_mas_vieja_que_la_retencion_no_se_agrega(agg: Agg) -> None:
    raw_insert(agg.db, [rec(NOW - timedelta(days=181, hours=1), case(1)), rec(NOW - timedelta(days=179), case(2))])
    agg.run()
    assert {k[2] for k in agg.daily()} == {(NOW - timedelta(days=179)).date()}
    assert list(agg.index()) == [case(2)]


# --- Concurrencia -----------------------------------------------------------------------------------------------------------


def test_con_el_cronjob_y_el_job_solapados_el_for_update_serializa_los_lotes_y_los_conteos_no_cambian(agg: Agg) -> None:
    raw_insert(agg.db, [rec(DAY, case(i % 500)) for i in range(6000)])
    outcomes: list[aggregator.RunReport | BaseException] = []

    def go(**kwargs: Any) -> None:
        try:
            outcomes.append(agg.run(size=500, **kwargs))
        except BaseException as error:  # noqa: BLE001
            outcomes.append(error)

    threads = [threading.Thread(target=go), threading.Thread(target=go, kwargs={"until_head": True})]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(isinstance(o, aggregator.RunReport) for o in outcomes), outcomes
    assert sum(o.entries for o in outcomes if isinstance(o, aggregator.RunReport)) == 6000  # ninguna entrada se cuenta dos veces
    assert agg.watermark() == 6000
    assert agg.totals() == {("modelo", "mv-1", DAY.date()): (6000, 0)}
    assert agg.cell("modelo", "mv-1", DAY, "sexo", "F", "lt_20", "favorable") == 500  # una por caso
    assert len(agg.index()) == 500


def test_un_reset_con_un_lote_en_curso_espera_el_for_update_y_los_conteos_finales_son_correctos(agg: Agg, pg: PostgresContainer) -> None:
    raw_insert(agg.db, [rec(DAY, case(i)) for i in range(10)])
    inside, release = threading.Event(), threading.Event()
    done: list[Any] = []

    def batch() -> None:
        def hold() -> None:
            inside.set()
            assert release.wait(30)

        done.append(agg.run(before_commit=hold))

    worker = threading.Thread(target=batch)
    worker.start()
    assert inside.wait(30)
    finished = threading.Event()
    resetter = threading.Thread(target=lambda: (aggregator.reset(dsn(pg, agg.db, "registry_migrator"), clock=lambda: NOW), finished.set()))
    resetter.start()
    assert not finished.wait(1.5)  # espera el FOR UPDATE del lote en curso
    release.set()
    worker.join(30)
    resetter.join(30)
    assert finished.is_set()
    # El reset corrio despues del lote: tablas vacias y marca antes de la primera entrada de los ultimos 181 dias.
    assert agg.daily() == {} and agg.index() == {}
    assert agg.watermark() == 0
    agg.run()  # el CronJob reconstruye desde la marca y los conteos finales son los correctos
    assert sum(agg.daily().values()) == 40 and agg.totals() == {("modelo", "mv-1", DAY.date()): (10, 0)}


def test_el_rol_del_agregador_no_escribe_la_cadena_ni_hace_truncate(agg: Agg) -> None:
    with psycopg.connect(agg.dsn) as conn:
        for statement in ("UPDATE registry_entries SET actor_id = 'x'", "DELETE FROM registry_entries", "TRUNCATE monitoring_daily"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(statement)  # type: ignore[arg-type]
            conn.rollback()


def unattributable(pg: PostgresContainer, db: Db, day: date) -> int:
    """`unattributable_invalid` de la proyeccion `monitoring_daily` del servicio (BR-U3-17)."""

    async def ask() -> int:
        pools = Pools.build(
            {
                "append": dsn(pg, db, "registry_app"),
                "dossier": dsn(pg, db, "registry_app"),
                "health": dsn(pg, db, "registry_health"),
                "projections": dsn(pg, db, "registry_verifier"),
            }
        )
        try:
            query = MonitoringQuery(
                ranges=[MonitoringRangeRequest(range_id="r", model_version_id="mv-1", population="modelo", from_day=day, to_day=day)],
                include_versions=False,
                unattributable_range=DayRange(from_day=day, to_day=day),
            )
            window = await monitoring_daily(pools, {Scope.REGISTRY_READ_MONITORING}, query, NOW)
            return window.unattributable_invalid
        finally:
            await pools.close()

    return asyncio.run(ask())

