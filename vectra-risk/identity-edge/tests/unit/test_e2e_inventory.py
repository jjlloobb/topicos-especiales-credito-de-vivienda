"""Inventario de las pruebas e2e de U2 (U02-T14, CA-3): cada viñeta del Paso 13 del plan tiene su prueba.

Cada id de prueba se asocia a un fragmento literal del texto del Paso 13. La colección se corre como subproceso
(`pytest --collect-only`, sin variables de entorno de clúster).
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "aidlc-docs" / "construction" / "plans" / "identity-edge-code-generation-plan.md"
E2E = ROOT / "identity-edge" / "tests" / "e2e"
TESTS = ROOT / "identity-edge" / "tests"
# Anclados al inicio de línea; aceptan `[ ]` o `[x]` y, tras el título, el sufijo que se agrega al cerrar el paso.
STEP = re.compile(r"^- \[[ x]\] \*\*Paso 13 — Especificación de las pruebas de extremo a extremo\*\*", re.MULTILINE)
NEXT_STEP = re.compile(r"^- \[[ x]\] \*\*Paso 14", re.MULTILINE)

# fragmento literal del plan -> ids de prueba (nombre de la funcion, sin parametros)
INVENTORY: dict[str, list[str]] = {
    "aprobador sin TOTP → no obtiene token": ["test_approver_without_totp_gets_no_token"],
    "step-up sin SPA: flujo OIDC con `acr_values=mfa` y TOTP hasta el token con `acr = mfa`": ["test_stepup_without_spa_reaches_acr_mfa"],
    "5 fallos → bloqueo, con el evento con `userId` y sin `username`": [
        "test_five_failures_lock_the_user",
        "test_lockout_event_has_user_id_and_no_username",
    ],
    "refresh reusado → sesión revocada": ["test_reused_refresh_token_revokes_the_session"],
    "cabeceras (CSP, HSTS, `nosniff`, `DENY`, `Referrer-Policy`)": ["test_spa_and_api_security_headers", "test_auth_and_grafana_security_headers"],
    "la CSP de `spa` y `api` incluye `require-trusted-types-for 'script'` y `trusted-types 'none'`": ["test_csp_requires_trusted_types"],
    "429 con `Retry-After`": ["test_rate_limit_returns_429_with_retry_after"],
    "cuerpo mayor que el límite → 413 `payload_too_large`": ["test_body_over_the_limit_returns_413_payload_too_large"],
    "`/auth/admin` → 404": ["test_auth_admin_is_not_routed"],
    "token de otro servicio → 401": ["test_token_of_another_service_is_rejected_with_403"],
    "`X-Forwarded-For` falso no cambia la IP registrada": [
        "test_forged_x_forwarded_for_does_not_change_the_logged_ip",
        "test_forged_x_forwarded_for_does_not_change_the_auth_counter",
    ],
    "cabecera interna `x-vectra-sub` inyectada → sin efecto": ["test_injected_x_vectra_sub_has_no_effect"],
    "backend de eco: `Idempotency-Key` (en `/api/intake/**` y `/api/console/**`) y `X-Test-Scenario` (en `/api/intake/**`) llegan intactas": [
        "test_echo_idempotency_key_arrives_intact",
        "test_echo_x_test_scenario_arrives_intact",
    ],
    "ninguna `x-vectra-*` entrante llega": ["test_echo_no_incoming_x_vectra_header_arrives"],
    "accesibilidad del login": [
        "test_login_page_has_no_serious_accessibility_violations",
        "test_totp_page_has_no_serious_accessibility_violations",
        "test_password_change_page_has_no_serious_accessibility_violations",
        "test_theme_loads_no_resource_from_another_origin",
    ],
    "PBT-U2-08: modelo de estados de la fuerza bruta contra el Keycloak de kind": ["test_pbt_u2_08_bruteforce_state_machine"],
}


def step_13_block(text: str) -> str:
    """El bloque del Paso 13: desde su línea hasta el inicio del Paso 14, sin depender del checkbox ni del sufijo."""
    start = STEP.search(text)
    assert start, "el Paso 13 no está en el plan"
    end = NEXT_STEP.search(text, start.end())
    assert end, "el Paso 14 no está en el plan después del Paso 13"
    return text[start.start() : end.start()]


def plan_bullets(text: str | None = None) -> list[str]:
    """Las viñetas de nivel 3 de la lista «Playwright» del Paso 13 y la de PBT-U2-08 (nivel 2); sin la nota H1-H9."""
    block = step_13_block(PLAN.read_text(encoding="utf-8") if text is None else text)
    lines = block.splitlines()
    bullets: list[str] = []
    in_playwright = False
    for line in lines[1:]:
        if line.startswith("  - Playwright"):
            in_playwright = True
        elif line.startswith("  - PBT-U2-08"):
            in_playwright = False
            bullets.append(line.strip()[2:])
        elif line.startswith("  - "):
            in_playwright = False
        elif in_playwright and line.startswith("    - "):
            bullets.append(line.strip()[2:])
    return bullets


def collected_ids(directory: Path, tests_dir: Path = TESTS) -> set[str]:
    """Nombres de las funciones de prueba que `pytest --collect-only` lista en `directory`, sin variables de clúster."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("VECTRA_E2E_", "SYNTH_"))}
    env["VECTRA_E2E_TESTS_DIR"] = str(tests_dir)
    run = subprocess.run(  # noqa: S603 - el interprete del propio entorno
        [sys.executable, "-m", "pytest", str(directory), "--collect-only", "-q", "-p", "no:cacheprovider"],
        capture_output=True, text=True, check=False, env=env, cwd=ROOT,
    )  # fmt: skip
    assert run.returncode == 0, run.stdout + run.stderr
    return {m.group(1) for line in run.stdout.splitlines() if (m := re.match(r"^\S+?::(?:\w+::)*(\w+)(?:\[.*\])?$", line))}


def problems(plan_text_bullets: list[str], collected: set[str]) -> list[str]:
    found: list[str] = []
    for fragment, ids in INVENTORY.items():
        if not any(fragment in bullet for bullet in plan_text_bullets):
            found.append(f"el fragmento ya no está en el plan: {fragment!r}")
        for test_id in ids:
            if test_id not in collected:
                found.append(f"el id {test_id} no aparece en la colección")
    for bullet in plan_text_bullets:
        if not any(fragment in bullet for fragment in INVENTORY):
            found.append(f"viñeta sin id: {bullet[:70]!r}")
    return found


@pytest.fixture(scope="module")
def collection() -> set[str]:
    return collected_ids(E2E)


def test_the_plan_has_the_bullets_the_inventory_covers():
    bullets = plan_bullets()
    # 11 viñetas de la lista Playwright + PBT-U2-08
    assert len(bullets) == 12, bullets


def test_every_bullet_of_step_13_has_a_test(collection):
    assert problems(plan_bullets(), collection) == []


@pytest.mark.parametrize("step_13_mark", ["[ ]", "[x]"])
@pytest.mark.parametrize("suffix", ["", " (U02-T14)"])
@pytest.mark.parametrize("step_14_mark", ["[ ]", "[x]"])
def test_block_location_does_not_depend_on_checkbox_state(step_13_mark, suffix, step_14_mark):
    body = "\n  - cuerpo del paso\n    - viñeta\n"
    title = "Especificación de las pruebas de extremo a extremo"
    text = f"- [x] **Paso 12 — Otro**\n- {step_13_mark} **Paso 13 — {title}**{suffix}{body}- {step_14_mark} **Paso 14 — Carga**\n  - otro\n"
    assert step_13_block(text) == f"- {step_13_mark} **Paso 13 — {title}**{suffix}{body}"


def test_every_id_is_unique_across_the_inventory():
    ids = [i for ids in INVENTORY.values() for i in ids]
    assert len(ids) == len(set(ids))


def test_a_fragment_missing_from_the_plan_is_detected(collection):
    bullets = [b.replace("refresh reusado", "refresh repetido") for b in plan_bullets()]
    found = problems(bullets, collection)
    assert any("refresh reusado" in p for p in found)
    assert any(p.startswith("viñeta sin id") for p in found)


def test_a_bullet_without_an_id_is_detected(collection):
    assert any(p.startswith("viñeta sin id") for p in problems([*plan_bullets(), "una viñeta nueva del plan"], collection))


def test_an_e2e_test_removed_in_a_copy_is_detected(tmp_path):
    copy = tmp_path / "e2e"
    shutil.copytree(E2E, copy, ignore=shutil.ignore_patterns("__pycache__"))
    source = copy / "test_e2e_sessions.py"
    text = source.read_text(encoding="utf-8")
    assert "def test_reused_refresh_token_revokes_the_session" in text
    source.write_text(text.replace("def test_reused_refresh_token_revokes_the_session", "def helper_reused_refresh_token_revokes_the_session"), encoding="utf-8")
    found = problems(plan_bullets(), collected_ids(copy))
    assert found == ["el id test_reused_refresh_token_revokes_the_session no aparece en la colección"]
