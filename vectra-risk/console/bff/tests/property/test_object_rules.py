"""PBT-U10-02 (Paso 3, CA-6): para todo estado del objeto, la regla acepta <=> la columna «Objeto» de C03 lo permite.

`HYPOTHESIS_PROFILE=ci uv run pytest console/bff/tests/property/test_object_rules.py`.

El oraculo es la tabla `ORACLE`, transcrita de `aidlc-docs/inception/application-design/component-methods.md`,
C03, columna «Objeto», una fila por regla (la cita va en cada fila). No usa la implementacion.
"""

from collections.abc import Callable
from typing import Any, get_args

import pytest
from hypothesis import given
from hypothesis import strategies as st
from vectra_contracts.catalog import CaseState, FinalOutcome
from vectra_contracts.models.governance import DataSource, ModelState, PolicyVersion
from vectra_contracts.routes import REGISTRY

from console_bff import object_rules as o
from console_bff.object_rules import ObjectVerdict

CASE_STATES = list(CaseState)
OUTCOMES = [None, *FinalOutcome]
MODEL_STATES = list(get_args(ModelState))
SOURCE_STATES = list(get_args(DataSource.model_fields["state"].annotation))
POLICY_STATES = list(get_args(PolicyVersion.model_fields["state"].annotation))
TEXTS = st.one_of(st.none(), st.just(""), st.just("   \n"), st.text(max_size=12))

# regla -> (fila de C03, predicado «la columna Objeto lo permite»)
ORACLE: dict[str, tuple[str, Callable[..., bool]]] = {
    # «Casos» fila `record_explanation_view`: «el caso está `listo` o `decidido`»
    "record_explanation_view": ("Casos/record_explanation_view", lambda s: s in ("listo", "decidido")),
    # «Casos» fila `record_decision`: «el caso está `listo` (si no, 409)»
    "record_decision": ("Casos/record_decision", lambda s: s == "listo"),
    # «Casos» fila `create_applicant_summary`: «caso `decidido`, decisión final `desfavorable`»
    "create_applicant_summary": (
        "Casos/create_applicant_summary",
        lambda s, outcome: s == "decidido" and outcome == "desfavorable",
    ),
    # «Casos» fila `retry_case`: «el caso está `no_disponible` y no anonimizado (si no, 409)»
    "retry_case": ("Casos/retry_case", lambda s, anonymized: s == "no_disponible" and not anonymized),
    # «Modelos» fila `start_validation`: «estado `registrado` o `validacion_fallida`»
    "start_validation": ("Modelos/start_validation", lambda s: s in ("registrado", "validacion_fallida")),
    # «Modelos» fila `start_source_comparison`: «fuente `en_evaluacion`; candidata con `source_candidate_for`;
    # existe una versión `activo`»
    "start_source_comparison": (
        "Modelos/start_source_comparison",
        lambda s, ds_id, cand_for, active: s == "en_evaluacion" and cand_for == ds_id and active,
    ),
    # «Modelos» fila `approve_model`: «estado `lista_para_aprobacion`»
    "approve_model": ("Modelos/approve_model", lambda s: s == "lista_para_aprobacion"),
    # «Modelos» fila `resolve_frozen`: «estado `congelado`»
    "resolve_frozen": ("Modelos/resolve_frozen", lambda s: s == "congelado"),
    # «Modelos» fila `retire_model`: «estado `inactivo`, `rechazado` o `validacion_fallida`»
    "retire_model": ("Modelos/retire_model", lambda s: s in ("inactivo", "rechazado", "validacion_fallida")),
    # «Políticas» fila `approve_policy`: «estado `propuesta`; `rechazada` exige `justification`»
    "approve_policy": (
        "Politicas/approve_policy",
        lambda s, decision, j: s == "propuesta" and (decision != "rechazada" or bool(j and j.strip())),
    ),
    # «Fuentes de datos» fila `decide_data_source`: «estado `en_evaluacion` con informe antes/después»
    "decide_data_source": ("Fuentes/decide_data_source", lambda s, report: s == "en_evaluacion" and report),
}

ARGS: dict[str, st.SearchStrategy[tuple[Any, ...]]] = {
    "record_explanation_view": st.tuples(st.sampled_from(CASE_STATES)),
    "record_decision": st.tuples(st.sampled_from(CASE_STATES)),
    "create_applicant_summary": st.tuples(st.sampled_from(CASE_STATES), st.sampled_from(OUTCOMES)),
    "retry_case": st.tuples(st.sampled_from(CASE_STATES), st.booleans()),
    "start_validation": st.tuples(st.sampled_from(MODEL_STATES)),
    "start_source_comparison": st.tuples(
        st.sampled_from(SOURCE_STATES),
        st.sampled_from(["ds-1", "ds-2"]),
        st.sampled_from([None, "ds-1", "ds-2"]),
        st.booleans(),
    ),
    "approve_model": st.tuples(st.sampled_from(MODEL_STATES)),
    "resolve_frozen": st.tuples(st.sampled_from(MODEL_STATES)),
    "retire_model": st.tuples(st.sampled_from(MODEL_STATES)),
    "approve_policy": st.tuples(
        st.sampled_from(POLICY_STATES), st.sampled_from(["aprobada", "rechazada"]), TEXTS
    ),
    "decide_data_source": st.tuples(st.sampled_from(SOURCE_STATES), st.booleans()),
}


def test_oracle_has_one_row_per_rule_function() -> None:
    rules = {
        name for name, v in vars(o).items() if callable(v) and getattr(v, "__module__", "") == o.__name__
    }
    rules -= {"ObjectVerdict", "_accept_if"}
    assert rules == set(ORACLE) == set(ARGS)


def test_state_universes_come_from_u0() -> None:
    assert MODEL_STATES[0] == "registrado" and len(MODEL_STATES) == 10
    assert SOURCE_STATES == ["propuesta", "en_evaluacion", "aprobada", "rechazada"]
    assert POLICY_STATES == ["propuesta", "activa", "rechazada", "historica"]
    assert len(CASE_STATES) == 7


@pytest.mark.parametrize("name", sorted(ORACLE))
@given(data=st.data())
def test_rule_accepts_iff_c03_allows(name: str, data: st.DataObject) -> None:
    args = data.draw(ARGS[name])
    _, allowed = ORACLE[name]
    verdict = getattr(o, name)(*args)
    assert (verdict is ObjectVerdict.ACCEPT) == allowed(*args), (name, args)
    # P-U10-01: aceptar, 403 o 409; las reglas de estado dan 409 cuando no aceptan.
    assert verdict in (ObjectVerdict.ACCEPT, ObjectVerdict.CONFLICT)
    assert verdict.status == (200 if allowed(*args) else 409)


def test_every_state_of_every_rule_is_checked_exhaustively() -> None:
    """Complemento de la propiedad: producto completo de los universos finitos."""
    for s in CASE_STATES:
        assert (o.record_decision(s) is ObjectVerdict.ACCEPT) == (s == "listo")
        for outcome in OUTCOMES:
            assert (o.create_applicant_summary(s, outcome) is ObjectVerdict.ACCEPT) == (
                s == "decidido" and outcome == "desfavorable"
            )
        for anonymized in (True, False):
            assert (o.retry_case(s, anonymized) is ObjectVerdict.ACCEPT) == (
                s == "no_disponible" and not anonymized
            )
    for m in MODEL_STATES:
        assert (o.retire_model(m) is ObjectVerdict.ACCEPT) == (
            m in ("inactivo", "rechazado", "validacion_fallida")
        )


def test_verdict_statuses() -> None:
    assert [(v.value, v.status) for v in ObjectVerdict] == [
        ("accept", 200),
        ("forbidden", 403),
        ("conflict", 409),
    ]


def test_object_rules_map_covers_exactly_the_30_bff_routes() -> None:
    """P-3 (a): el mapa `operation_id -> regla | None` tiene las 30 rutas de `RouteContract`, ni mas ni menos."""
    ids = [route.operation_id for route in REGISTRY["console-bff"]]
    assert len(ids) == 30
    assert set(o.OBJECT_RULES) == set(ids)
    assert len(o.OBJECT_RULES) == 30


def test_object_rules_map_binds_each_rule_to_its_c03_route() -> None:
    by_name = {
        "post_api_console_cases_id_explanation-views": "record_explanation_view",
        "post_api_console_cases_id_decision": "record_decision",
        "post_api_console_cases_id_applicant-summary": "create_applicant_summary",
        "post_api_console_cases_id_retry": "retry_case",
        "post_api_console_models_id_validations": "start_validation",
        "post_api_console_data-sources_id_comparisons": "start_source_comparison",
        "post_api_console_models_id_approval": "approve_model",
        "post_api_console_models_id_frozen-resolution": "resolve_frozen",
        "post_api_console_models_id_retirement": "retire_model",
        "post_api_console_policies_id_approval": "approve_policy",
        "post_api_console_data-sources_id_decision": "decide_data_source",
    }
    bound = {op: rule.__name__ for op, rule in o.OBJECT_RULES.items() if rule is not None}
    assert bound == by_name
    assert set(by_name.values()) == set(ORACLE)
