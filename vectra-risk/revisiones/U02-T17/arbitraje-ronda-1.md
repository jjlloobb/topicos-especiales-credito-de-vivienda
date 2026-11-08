# Arbitraje de la ronda 1 — U02-T17

Orquestador, 2026-11-08. Informe: `revisiones/U02-T17/ronda-1.md` (NO-VERDE).

## Regla

Lo que el diff rompe es del diff; lo que ya estaba flojo antes es candidata (`DECISIONES-LOOP.md` §1).

## Decisiones

- **F-01 (NARANJA) — entra en la ronda 2.** La justificación de la bitácora es falsa: el revisor reprodujo el rojo con las entradas restauradas. Quitar entradas de `FIXED_WAVES` debilita CA-3 sin necesidad. Corrección en `platform/tests/test_waves.py`:
  - conservar `valkey: 2` y `keycloak: 3`;
  - renombrar `api-gateway` → `gateway` y `rate-limit` → `ratelimit`, con wave 3;
  - sumar `identity-jobs: 3`, `identity-rules: 4` e `identity-monitors: 4`;
  - rojo en la bitácora: con `keycloak` e `identity-jobs` en wave 4, `test_waves.py` falla;
  - corregir en la bitácora la afirmación falsa.
- **F-02 (NARANJA) — decisión del usuario, 2026-11-08: 5,5 GiB provisional.** `BUDGET_GIB = 5.5` se queda, con un comentario en el literal: «Provisional (decisión del usuario, 2026-11-08, U02-T17): U1 + U2 piden 5,47 GiB. Se revisa con la medición del Paso 16 de U2 (DD-3 y T6 de `aidlc-docs/construction/plans/demo-kind-alcance.md`).» Se anota la candidata en `CANDIDATAS.md`.
- **`CANDIDATAS.md` sí existe** (`vectra-risk/CANDIDATAS.md`). Las candidatas que quedaron solo en la bitácora pasan ahí, con el formato de las entradas existentes:
  1. presupuesto de memoria de kind (F-02, DD-3);
  2. `banco-ca`: enlazar con la entrada que ya existe (línea 63) y sumar F-03, por el literal duplicado y por valer en cualquier entorno;
  3. `charts.sh` no baja `keycloakx`;
  4. F-04: ruta fija al subchart de los CRDs de Gateway API;
  5. F-05: fixture `u2-keycloak` copiado a mano;
  6. `EXPECTED_WAVES` y `FIXED_WAVES` se solapan.
- **F-03, F-04, F-05 (AMARILLO):** no bloquean. Van a candidatas como arriba.
