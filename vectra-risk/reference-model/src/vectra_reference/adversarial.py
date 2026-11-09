"""Conjunto adversarial de U5 (BR-U5-16..18).

U05-T02 implementa solo los 18 casos RT-4 (BR-U5-17), porque la calibracion de `confidence` del Paso 4
(BR-U5-13) los necesita. Los pares RT-1 y los paquetes RT-3 (Paso 7) quedan para la tarea del Bloque D.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from typing import Any

from vectra_contracts.models.application import ApplicationIn

from vectra_reference.generate import COP_MAX, load_catalog

N_RT4 = 18
RT4_EXPECTED = {
    "confidence": "below_low_confidence_threshold",
    "recommendation": "revision_requerida",
    "reason": "baja_confianza",
}
# Un solicitante sintetico central (dentro de la envolvente), con identificadores en los rangos reservados.
_TEMPLATE: dict[str, Any] = {
    "document_type": "CC",
    "document_number": "9990000001",
    "birth_date": "1985-03-15",
    "phone": "0000900001",
    "email": "SYN-9000001@example.com",
    "address": "Calle 1 # 1-1 (sintetico)",
    "municipality_code": "05001",
    "department_code": "05",
    "monthly_income": 3_000_000,
    "other_income": 0,
    "employment_type": "asalariado",
    "employment_months": 60,
    "monthly_obligations": 300_000,
    "max_days_past_due_12m": 0,
    "property_value": 250_000_000,
    "requested_amount": 150_000_000,
    "term_months": 240,
    "proposed_rate_ea": "0.1250",
    "property_condition": "usada",
    "channel": "sucursal",
    "broker_id": None,
    "free_text": None,
    "sex": "no_informado",
    "socioeconomic_stratum": "no_informado",
}


class AdversarialError(Exception):
    """Un caso adversarial no es una `ApplicationIn` valida o no esta fuera de la envolvente (BR-U5-17)."""


def _times_p99(envelope: Mapping[str, Any], feature: str, factor: float) -> int:
    p99 = next(item["p99"] for item in envelope["numeric"] if item["name"] == feature)
    return min(COP_MAX, int(p99 * factor))


def _rt4_mutations(envelope: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Las 18 mutaciones del solicitante central: (descripcion, campos que cambian). Orden fijo."""
    big = {
        "monthly_income": _times_p99(envelope, "monthly_income", 50),
        "other_income": _times_p99(envelope, "other_income", 50),
        "monthly_obligations": _times_p99(envelope, "monthly_obligations", 50),
    }
    return [
        ("canal no visto 1", {"channel": "canal_no_visto_1"}),
        ("canal no visto 2", {"channel": "canal_no_visto_2", "employment_type": "independiente"}),
        ("canal no visto 3", {"channel": "agencia_externa"}),
        ("canal no visto 4", {"channel": "CANAL-EXTRANO-4", "property_condition": "nueva"}),
        ("ingreso muy alto", {"monthly_income": big["monthly_income"]}),
        ("ingreso minimo", {"monthly_income": 1}),
        ("otros ingresos muy altos", {"other_income": big["other_income"]}),
        ("obligaciones muy altas", {"monthly_obligations": big["monthly_obligations"]}),
        ("mora maxima", {"max_days_past_due_12m": 365}),
        ("antiguedad maxima", {"employment_months": 720, "max_days_past_due_12m": 365}),
        ("plazo minimo", {"term_months": 12}),
        ("tasa muy alta", {"proposed_rate_ea": "0.9000"}),
        ("tasa muy baja y plazo minimo", {"proposed_rate_ea": "0.0100", "term_months": 12}),
        (
            "prestamo igual al valor con ingreso minimo",
            {"property_value": 900_000_000, "requested_amount": 900_000_000, "monthly_income": 1_300_000},
        ),
        (
            "varias features extremas",
            {**big, "max_days_past_due_12m": 365, "term_months": 12},
        ),
        (
            "canal no visto con ingreso muy alto",
            {"channel": "canal_no_visto_5", "monthly_income": big["monthly_income"]},
        ),
        (
            "todas las numericas extremas",
            {
                **big,
                "max_days_past_due_12m": 365,
                "employment_months": 720,
                "term_months": 12,
                "proposed_rate_ea": "0.9000",
                "property_value": 500_000_000_000,
                "requested_amount": 1_000,
            },
        ),
        ("valor de vivienda extremo", {"property_value": 10**12, "requested_amount": 10**12}),
    ]


def rt4_cases(
    envelope: Mapping[str, Any],
    values_of: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    names: Mapping[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Los 18 casos RT-4 (`RT4-01`..`RT4-18`): `ApplicationIn` validas y fuera de la envolvente.

    `values_of` convierte la solicitud en los valores de las features (`features.row_values`); se inyecta para
    no acoplar este modulo al calculo. Cada caso lleva `expected` (domain-entities §5).
    """
    names = names or load_catalog()
    cases: list[dict[str, Any]] = []
    for n, (description, change) in enumerate(_rt4_mutations(envelope), start=1):
        application = {
            **_TEMPLATE,
            "full_name": f"{names['given_names'][n]} {names['surnames'][n]} {names['surnames'][n + 1]}",
            "document_number": f"999{n:07d}",
            "phone": f"0000{900000 + n:06d}"[-10:],
            "email": f"SYN-{9000000 + n:07d}@example.com",
            **change,
        }
        try:
            ApplicationIn.model_validate(
                {**application, "birth_date": date.fromisoformat(application["birth_date"])}
            )
        except ValueError as exc:
            raise AdversarialError(f"RT4-{n:02d} no es una ApplicationIn valida: {exc}") from exc
        if not outside_envelope(envelope, values_of(application)):
            raise AdversarialError(f"RT4-{n:02d} no esta fuera de la envolvente")
        cases.append(
            {
                "case_id": f"RT4-{n:02d}",
                "scenario": "RT-4",
                "description": description,
                "input": application,
                "expected": dict(RT4_EXPECTED),
            }
        )
    if len(cases) != N_RT4:
        raise AdversarialError(f"se esperaban {N_RT4} casos RT-4 y hay {len(cases)}")
    return cases


def outside_envelope(envelope: Mapping[str, Any], values: Mapping[str, Any]) -> bool:
    """BR-U5-17: al menos una feature fuera de [p1, p99] o una categoria no vista."""
    if any(str(values[name]) not in seen for name, seen in envelope["categories"].items()):
        return True
    return any(not item["p1"] <= float(values[item["name"]]) <= item["p99"] for item in envelope["numeric"])
