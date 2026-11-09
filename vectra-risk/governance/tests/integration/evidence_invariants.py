"""Invariantes de PBT-U4-01 y PBT-U4-07, comprobadas con SQL sobre `transitions`, `model_versions` y `policies`, y sobre la
cadena del doble del registro (nunca con los valores de retorno de las operaciones).
"""

from collections import defaultdict
from typing import Any

from vectra_governance.model_fsm import ACTORS, TRANSITIONS, Actor
from vectra_contracts.catalog import Role

Snapshot = dict[str, Any]
LIVE = ("activo", "congelado")


def _is_freeze(r: dict[str, Any]) -> bool:
    return (
        r["entity_type"] == "model_version"
        and r["kind"] == "cambio_estado"
        and r["from_state"] == "activo"
        and r["to_state"] == "congelado"
    )


def _entities(snap: Snapshot) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in snap["transitions"]:
        out[(r["entity_type"], r["entity_id"])].append(r)
    return out


def check_pbt07(snap: Snapshot) -> None:
    rows = snap["transitions"]
    chain = snap["chain"]
    by_key = {w.key: w for w in chain}
    assert len(by_key) == len(chain), "dos eventos con la misma llave"
    key_to_n = {str(r["idempotency_key"]): (r["entity_type"], r["entity_id"], r["transition_number"]) for r in rows}
    assert set(by_key) <= set(key_to_n), "un evento en la cadena sin transicion"
    # nunca dos eventos para el mismo numero de transicion de una entidad
    seen: dict[tuple[str, str, int], str] = {}
    for w in chain:
        slot = key_to_n[w.key]
        assert slot not in seen, f"dos eventos para {slot}"
        seen[slot] = w.key

    # 1. ninguna transicion distinta de `freeze` cambia el estado sin un `registry_entry_id` y su evento
    for r in rows:
        if r["status"] == "confirmada":
            assert r["registry_entry_id"] is not None, f"confirmada sin ack: {r['transition_id']}"
            assert str(r["idempotency_key"]) in by_key, "confirmada sin su evento en la cadena"
            assert by_key[str(r["idempotency_key"])].seq == int(r["registry_entry_id"])

    entities = _entities(snap)
    for (etype, eid), erows in entities.items():
        # 2. el estado es el que dicen las transiciones con evidencia (+ el `freeze`, que aplica antes del ack)
        applied = [
            r
            for r in erows
            if r["kind"] == "cambio_estado"
            and (r["status"] == "confirmada" or (_is_freeze(r) and r["status"] == "pendiente_registro"))
        ]
        current = (snap["models"] if etype == "model_version" else snap["policies"]).get(eid)
        if applied:
            expected = max(applied, key=lambda r: r["transition_number"])["to_state"]
            assert current is not None and current["state"] == expected, (etype, eid, current and current["state"], expected)
        else:
            assert current is None, f"{etype} {eid} existe sin ninguna transicion confirmada"

        # 3. los eventos de una entidad aparecen en la cadena en orden de `n`
        ns = [key_to_n[w.key][2] for w in chain if key_to_n[w.key][:2] == (etype, eid)]
        assert ns == sorted(ns), f"eventos fuera de orden de n en {eid}: {ns}"

        # 4. a lo sumo una pendiente por entidad, salvo `freeze` y compensaciones
        pending = [r for r in erows if r["status"] == "pendiente_registro" and r["kind"] == "cambio_estado" and not _is_freeze(r)]
        assert len(pending) <= 1, f"{len(pending)} pendientes en {eid}"
        if pending:
            others = [r for r in erows if r["status"] == "pendiente_registro" and r is not pending[0]]
            assert all(_is_freeze(r) or r["kind"] == "compensacion" for r in others), f"otra pendiente junto a una en {eid}"

        # 5. nunca una `frozen_resolution` sin su `freeze` antes, ni antes de que el freeze y las compensaciones esten escritos
        for r in erows:
            if r["status"] == "confirmada" and r["kind"] == "cambio_estado" and r["from_state"] == "congelado":
                for q in erows:
                    if q["transition_number"] < r["transition_number"] and (_is_freeze(q) or q["kind"] == "compensacion"):
                        assert q["status"] == "confirmada", f"resolucion de {eid} antes de {q['kind']} {q['status']}"
                assert any(_is_freeze(q) and q["transition_number"] < r["transition_number"] for q in erows)

    for w in chain:
        if w.entry["entry_type"] == "frozen_resolution":
            mine = w.entry["model_version_id"]
            freezes = [x.seq for x in chain if x.entry["entry_type"] == "freeze" and x.entry["model_version_id"] == mine]
            assert freezes and min(freezes) < w.seq, "frozen_resolution sin su freeze antes"

    # 6. una `descartada` nunca aplica estado (ver 2), y las mitades de una unidad van juntas
    units: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r["unit_id"] is not None:
            units[str(r["unit_id"])].append(r)
    for unit in units.values():
        statuses = {r["status"] for r in unit}
        if "confirmada" in statuses:
            assert statuses == {"confirmada"}, f"unidad a medias: {statuses}"
        assert not ({"abandonada"} & statuses and "pendiente_registro" in statuses), f"unidad a medias: {statuses}"

    # 7. compensaciones: nunca abandonadas, sin cambio de estado, y una por cada descartada de modelo
    compensations = [r for r in rows if r["kind"] == "compensacion"]
    for c in compensations:
        assert c["status"] != "abandonada"
        assert c["from_state"] == c["to_state"] and c["entity_type"] == "model_version"
    discarded_keys = {
        c["event_payload"]["entry"]["payload"]["details"]["discarded_idempotency_key"] for c in compensations
    }
    for r in rows:
        if r["status"] == "descartada" and r["entity_type"] == "model_version" and r["kind"] == "cambio_estado":
            assert str(r["idempotency_key"]) in discarded_keys, "descartada sin compensacion"
    for c in compensations:  # la compensacion de un freeze va despues del freeze en la cadena
        dep = c["event_payload"].get("depends_on")
        if dep is not None and str(c["idempotency_key"]) in by_key:
            freeze = next(r for r in rows if str(r["transition_id"]) == dep)
            assert str(freeze["idempotency_key"]) in by_key
            assert by_key[str(freeze["idempotency_key"])].seq < by_key[str(c["idempotency_key"])].seq

    # 8. a lo sumo una version servible y una politica activa
    assert sum(1 for m in snap["models"].values() if m["state"] in LIVE) <= 1
    assert sum(1 for p in snap["policies"].values() if p["state"] == "activa") <= 1


def _actor(raw: dict[str, Any]) -> Actor:
    role = raw.get("role")
    return Actor(raw["kind"], raw["sub"], Role(role) if role else None, raw.get("acr"))


def check_pbt01(snap: Snapshot, retired_seen: set[str]) -> None:
    """PBT-U4-01 (business-logic-model §3) salvo `source_candidate_for` (P-5): la maquina de BR-U4-01 con su oraculo."""
    models = snap["models"]
    assert sum(1 for m in models.values() if m["state"] in LIVE) <= 1  # a lo sumo una activo o congelado
    legal = {(src, dst) for (src, _action), dst in TRANSITIONS.items()}
    for r in snap["transitions"]:
        if r["entity_type"] != "model_version" or r["kind"] != "cambio_estado":
            continue
        actor = r["actor"]
        if actor["sub"] == "bias-monitoring-job":
            assert r["to_state"] == "congelado", "bias produjo un estado distinto de congelado"  # X04
        if r["status"] != "confirmada" and not _is_freeze(r):
            continue
        src = None if r["from_state"] == "-" else r["from_state"]
        assert (src, r["to_state"]) in legal, f"transicion fuera de BR-U4-01: {src}->{r['to_state']}"
        if (src, r["to_state"]) == ("congelado", "activo"):  # congelado -> activo solo con cumplimiento + MFA
            assert actor.get("role") == "cumplimiento" and actor.get("acr") == "mfa", actor
        if (src, r["to_state"]) != ("activo", "inactivo"):  # esa la hace el sistema dentro del `mark_active` de otra version
            actions = [a for (s, a), dst in TRANSITIONS.items() if s == src and dst == r["to_state"]]
            who = _actor(actor)
            assert any(w.matches(who) for a in actions for w in ACTORS[a]), f"actor no permitido: {actor} {actions}"
    for unit in {str(r["unit_id"]) for r in snap["transitions"] if r["unit_id"] is not None}:
        statuses = {r["status"] for r in snap["transitions"] if str(r["unit_id"]) == unit}
        # un freeze con un mark_active pendiente: ninguna otra version pasa a activo por ese mark_active
        if "descartada" in statuses:
            assert "confirmada" not in statuses
    for model_id, model in models.items():  # los estados terminales no cambian
        if model_id in retired_seen:
            assert model["state"] == "retirado"
        if model["state"] == "retirado":
            retired_seen.add(model_id)
