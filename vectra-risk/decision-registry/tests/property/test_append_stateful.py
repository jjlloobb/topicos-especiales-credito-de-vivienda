"""PBT-U3-01: `append` + `verify` como maquina de estados contra un modelo en memoria (Paso 7 del plan de U3; US-401; PBT-06).

Para toda secuencia de comandos (append valido de los 9 tipos de negocio, reintento identico, reintento con otro `occurred_at`,
`correlation_id` o `contract_version` pasados mas de 5 min, reintento con un momento de negocio de mas de 7 dias, reintento con
la misma llave y otro contenido, checkpoint, saltos del reloj de la base), la cadena resultante siempre verifica `integra`, `seq`
es contiguo, los reintentos iguales no agregan filas y los distintos dan 409.

Corre contra PostgreSQL real con standby sincrono (Testcontainers), una base por ejemplo.
`HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_append_stateful.py`.
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import vectra_contracts
from chain_builder import Signer
from cluster_dbs import drop_db, make_db
from entries import BUSINESS_TYPES, CASE, entry_dict, iso, payload_for
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule, run_state_machine_as_test
from registry_cluster import Cluster
from vectra_common.errors import ConflictState
from vectra_contracts.models.registry import RegistryEntryIn
from vectra_registry import append
from vectra_registry.chain import format_timestamp
from vectra_registry.pools import Pools
from vectra_registry.queries import fetch_rows
from vectra_registry.verify import ListSource, verify

pytestmark = pytest.mark.integration

CASES = [CASE, uuid.UUID(int=2), uuid.UUID(int=3)]
texts = st.text(st.characters(codec="utf-8", categories=["L", "N", "P", "S", "Zs"]), max_size=30)
STATEFUL_EXAMPLES = 50
SCORING_FAIL_CLOSED = {"cause": "timeout", "retryable": True, "attempt": 1}


class Held:
    """Lo que el modelo recuerda de una entrada escrita: su llave, el cuerpo enviado y el ack que se dio."""

    def __init__(self, data: dict[str, Any], seq: int, recorded_at: datetime) -> None:
        self.data = data
        self.seq = seq
        self.recorded_at = recorded_at


class RegistryMachine(RuleBasedStateMachine):
    cluster: Cluster
    template: str

    def __init__(self) -> None:
        super().__init__()
        self.cdb = make_db(self.cluster, self.template)
        self.loop = asyncio.new_event_loop()
        self.pools = Pools.build(self.cdb.dsns())
        self.signer = Signer(11)
        self.now = datetime.now(UTC) + timedelta(minutes=1)
        self.skew = timedelta(0)  # cuanto adelanta o atrasa el reloj de la base respecto del reloj del servicio
        self.held: list[Held] = []
        self.checkpoints = 0

    # --- infraestructura ---------------------------------------------------------------------------------------------------

    def run(self, coro: Any) -> Any:
        return self.loop.run_until_complete(coro)

    def append(self, data: dict[str, Any]) -> append.AppendOutcome:
        entry = RegistryEntryIn.model_validate_json(json.dumps(data))
        return self.run(  # type: ignore[no-any-return]
            append.append_entry(self.pools, entry, clock=lambda: self.now, db_clock=lambda: self.now + self.skew)
        )

    def entry(self, entry_type: str, **kwargs: Any) -> dict[str, Any]:
        return entry_dict(entry_type, now=self.now, **kwargs)

    def teardown(self) -> None:
        self.run(self.pools.close())
        self.loop.close()
        drop_db(self.cdb)

    # --- comandos ----------------------------------------------------------------------------------------------------------

    @rule(entry_type=st.sampled_from(BUSINESS_TYPES), case=st.sampled_from(CASES), text=texts, back=st.integers(0, 299))
    def append_valido(self, entry_type: str, case: uuid.UUID, text: str, back: int) -> None:
        occurred = self.now - timedelta(seconds=back)
        payload = payload_for(entry_type, occurred)  # los momentos de negocio no pasan de occurred_at (BR-U0-37)
        if entry_type == "model_event":
            payload["details"] = {"nota": text}
        elif entry_type == "recommendation":
            payload["channel"] = text[:40] or "web"
        elif entry_type == "fail_closed":
            payload = dict(SCORING_FAIL_CLOSED)
        kwargs: dict[str, Any] = {"payload": payload, "occurred_at": occurred}
        if entry_type in ("recommendation", "fail_closed", "human_decision", "explanation_view"):
            kwargs["case_id"] = case
        data = self.entry(entry_type, **kwargs)
        head = self.head_seq()
        outcome = self.append(data)
        assert outcome.created and outcome.ack.seq == head + 1  # seq contiguo
        self.held.append(Held(data, outcome.ack.seq, outcome.ack.recorded_at))

    @precondition(lambda self: self.held)
    @rule(pick=st.integers(0, 10_000))
    def reintento_identico(self, pick: int) -> None:
        held = self.held[pick % len(self.held)]
        before = self.count()
        outcome = self.append(held.data)
        assert not outcome.created and (outcome.ack.seq, outcome.ack.recorded_at) == (held.seq, held.recorded_at)
        assert self.count() == before  # los reintentos iguales no agregan filas

    @precondition(lambda self: self.held)
    @rule(pick=st.integers(0, 10_000), minutes=st.integers(6, 600))
    def reintento_con_otra_traza_pasado_el_plazo(self, pick: int, minutes: int) -> None:
        """Otro `occurred_at`, `correlation_id` y `contract_version`, mas de 5 min despues: el ack original."""
        held = self.held[pick % len(self.held)]
        self.now += timedelta(minutes=minutes)
        retry = {**held.data, "occurred_at": iso(self.now), "correlation_id": uuid.uuid4().hex}
        before, original = self.count(), vectra_contracts.__version__
        vectra_contracts.__version__ = "9.9.9"
        try:
            outcome = self.append(retry)
        finally:
            vectra_contracts.__version__ = original
        assert not outcome.created and outcome.ack.seq == held.seq
        assert self.count() == before

    @precondition(lambda self: self.held)
    @rule(pick=st.integers(0, 10_000), days=st.integers(8, 20))
    def reintento_con_un_momento_de_negocio_de_mas_de_7_dias(self, pick: int, days: int) -> None:
        """La cota de BR-U0-37 solo rige para llaves nuevas: el reenvio de una evidencia ya escrita da su ack original."""
        held = self.held[pick % len(self.held)]
        self.now += timedelta(days=days)
        retry = {**held.data, "occurred_at": iso(self.now), "correlation_id": uuid.uuid4().hex}
        before = self.count()
        outcome = self.append(retry)
        assert not outcome.created and outcome.ack.seq == held.seq and self.count() == before

    @precondition(lambda self: self.held)
    @rule(pick=st.integers(0, 10_000), what=st.sampled_from(["actor", "model_version_id", "payload"]))
    def reintento_con_otro_contenido(self, pick: int, what: str) -> None:
        held = self.held[pick % len(self.held)]
        changed = json.loads(json.dumps(held.data))
        if what == "actor":
            changed["actor"] = {**changed["actor"], "id": changed["actor"]["id"] + "-otro"}
        elif what == "model_version_id":
            changed["model_version_id"] = (changed.get("model_version_id") or "") + "-otro"
        else:
            changed["payload"] = mutate_payload(changed)
        before = self.count()
        with pytest.raises(ConflictState):
            self.append(changed)
        assert self.count() == before  # los distintos dan 409 y no escriben

    @rule(seconds=st.integers(0, 600))
    def avanza_el_reloj(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)

    @rule(seconds=st.integers(-7200, 7200))
    def el_reloj_de_la_base_salta(self, seconds: int) -> None:
        """La base puede ir por delante o por detras del servicio, incluso hacia atras: `recorded_at` no decrece."""
        self.skew = timedelta(seconds=seconds)

    @rule()
    def checkpoint(self) -> None:
        head = self.run(self.fetch())[-1]
        stamp = max(self.now + self.skew, head.recorded_at) + timedelta(seconds=1)
        payload = {
            "checkpoint_seq": head.seq,
            "checkpoint_hash": head.hash.hex(),
            "signature": self.signer.sign(head.seq, head.hash.hex(), format_timestamp(stamp)),
            "key_fingerprint": self.signer.fingerprint,
        }
        data = entry_dict("checkpoint", now=self.now, case_id=None, actor={"kind": "system", "id": "system"}, payload=payload)
        outcome = self.run(
            append.append_entry(
                self.pools, RegistryEntryIn.model_validate_json(json.dumps(data)), clock=lambda: self.now, db_clock=lambda: stamp
            )
        )
        assert outcome.created and outcome.ack.recorded_at == stamp
        self.checkpoints += 1

    # --- invariantes -------------------------------------------------------------------------------------------------------

    async def fetch(self) -> list[Any]:
        async with self.pools.dossier.connection() as conn:
            return await fetch_rows(conn, "ORDER BY seq")

    def head_seq(self) -> int:
        return int(self.cdb.db.query("SELECT max(seq) FROM registry_entries")[0][0])  # type: ignore[call-overload]

    def count(self) -> int:
        return int(self.cdb.db.query("SELECT count(*) FROM registry_entries")[0][0])  # type: ignore[call-overload]

    @invariant()
    def la_cadena_verifica_integra_con_seq_contiguo_y_recorded_at_no_decreciente(self) -> None:
        rows = self.run(self.fetch())
        assert [r.seq for r in rows] == list(range(len(rows)))
        assert all(a.recorded_at <= b.recorded_at for a, b in zip(rows, rows[1:], strict=False))
        report = verify("full", ListSource(rows), public_keys=[self.signer.public])
        assert report.result == "integra", (report.first_inconsistent_seq, report.reason)
        assert len(rows) == 1 + len(self.held) + self.checkpoints  # la genesis, lo escrito y los checkpoints


def mutate_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Un payload distinto pero igual de valido: se cambia un valor del tipo."""
    payload = json.loads(json.dumps(data["payload"]))
    match data["entry_type"]:
        case "model_event":
            payload["details"] = {"nota": "otra"} if payload["details"] != {"nota": "otra"} else {"nota": "distinta"}
        case "policy_event":
            payload["policy_version_id"] += "-otra"
        case "data_source_event":
            payload["source_id"] += "-otra"
        case "freeze":
            payload["freeze_id"] += "-otra"
        case "frozen_resolution":
            payload["justification"] += " Otra."
        case "human_decision":
            payload["recommendation_entry_id"] += "9"
        case "explanation_view":
            payload["recommendation_entry_id"] += "9"
        case "recommendation":
            payload["channel"] = payload["channel"] + "x"
        case _:
            payload["attempt"] += 1
    return payload


def test_pbt_u3_01_la_cadena_siempre_verifica_integra(cluster: Cluster, cluster_template: str) -> None:
    RegistryMachine.cluster, RegistryMachine.template = cluster, cluster_template
    # Cada ejemplo crea y borra una base (con su checkpoint de PostgreSQL) y cada paso espera al standby: 50 ejemplos de hasta 15
    # pasos, no los 500 del perfil `ci` (PBT-U3-02..08 si usan los 500).
    run_state_machine_as_test(
        RegistryMachine, settings=settings(max_examples=min(settings().max_examples, STATEFUL_EXAMPLES), stateful_step_count=15)
    )
