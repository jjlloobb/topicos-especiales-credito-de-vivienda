# U03-T03 — Servicio de `decision-registry`: append, consultas, expediente, verificación bajo demanda y readiness

**Unidad:** U3 `decision-registry`
**Historias que implementa:** US-401, US-402, US-403 y US-404, en su parte de servicio.
**Depende de:** U03-T01 y U03-T02 (PR 80 y 83), ya en `main`.

Bloque D del plan de U3 (Pasos 7 a 10), que entra **completo** en la demo (E). Rige el ritmo RL-1 a RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6: máximo 2 rondas, y solo un ROJO bloquea.

Es el bloque más grande de U3. Si en la ronda 1 no llegas a cubrir los cuatro pasos con su aceptación completa, **entrega los pasos terminados con todos sus criterios en verde** y deja los demás sin marcar, explicando en la bitácora qué falta. No entregues pasos a medias. El orquestador decide si el resto va en una segunda tarea.

## Alcance

**Dentro:** los Pasos 7 a 10 del plan (`aidlc-docs/construction/plans/decision-registry-code-generation-plan.md`, «Bloque D — Servicio»), con su texto, su diseño y **todas** las viñetas de aceptación, **sin recortes**. No se copian aquí porque son largas: el plan es la fuente. Cada viñeta de aceptación es un caso de prueba, y en la bitácora el codificador lista viñeta → prueba.

- **Paso 7 — Append:**
  - autorización por scope, tipo y forma del payload de `fail_closed` (BR-U3-03, simétrica);
  - 64 KiB (BR-U3-07);
  - idempotencia por campos de negocio (BR-U3-06);
  - la ventana de ±5 min y `check_business_time` solo para llaves nuevas (BR-U3-05);
  - lock, hash, `INSERT` y `synchronous_commit = remote_apply` (BR-U3-04);
  - tiempos límite de P-U3-02 y pools de P-U3-04;
  - PBT-U3-07 y 08, y la stateful PBT-U3-01 contra primaria + standby de Testcontainers.
- **Paso 8 — Proyecciones, expediente y verificación bajo demanda:**
  - `GET /v1/entries`, con paginación por clave y la proyección `metrics` (U11);
  - el gauge `vectra_registry_monitoring_lag_seconds`;
  - `POST /v1/monitoring/daily:query` y `GET /v1/monitoring/freezes`;
  - `GET /v1/dossiers/{case_id}`;
  - `POST` y `GET /v1/integrity-checks`.
- **Paso 9 — Readiness y contratos de rutas:**
  - `/readyz` con `registry_health` y una cache de 5 s;
  - las rutas como `RouteContract` en U0, de modo que `make -C contracts openapi` las incluye.
- **Paso 10 — Resumen del servicio:** `aidlc-docs/construction/decision-registry/code/api-summary.md`.

**También entran estas candidatas de `CANDIDATAS.md`**, porque este bloque es el que las toca:
1. **Prioritaria (revisor, U03-T02, F-01).** `column_mismatch` sin cobertura para `policy_version_id` ni `actor_role`. `tests/chain_builder.py` escribe esas columnas, y PBT-U3-02 las altera. **Rojo:** quitar su comparación en `verify.py` hace fallar la prueba.
2. **Prioritaria (revisor, U03-T02, F-02).** PBT-U3-06 sortea solo combinaciones (tipo, consumidor, proyección) permitidas, para que las omisiones de campos se prueben. **Rojo:** quitar `context_package` del `freeze` o `received_at` de `metrics` falla con 5 semillas distintas.
3. **Revisor, U03-T01, F-05.** El append no depende del nombre de la restricción de unicidad: detecta el duplicado por la búsqueda de idempotencia de BR-U3-04, paso 0, y no por el texto del error.
4. **Codificador, U03-T02.** `Forbidden` de `projections` → 403 en la API, y `delivery_status` en `metrics` según `MetricsProjection` de U0. La diferencia con domain-entities §3 queda en candidatas para el diseño; no se corrige aquí.

Marca cada una como atendida en `CANDIDATAS.md`.

Precisiones:
- **Framework:** la app sale de `create_app` de U0 (`vectra_common`), con `deps.call` para las dependencias y sin cliente HTTP propio. Revisa cómo lo hace `identity-edge` o U0 antes de inventar.
- **Autenticación en pruebas:** tokens firmados con llaves de prueba y el JWKS de prueba de U0, si existe. No se usa Keycloak real.
- **Testcontainers:** primaria + standby síncrono, para PBT-U3-01 y para el 503 con el standby pausado. Si la réplica síncrona en Testcontainers es inviable en esta máquina, **detente y repórtalo** antes de sustituirla.
- **Plan:** marca `[x]` los Pasos 7 a 10, con `(U03-T03)`.

**Fuera:**
- La CLI `vectra-registry`, los CronJobs, el chart, las alertas y las Applications (Bloques E y F).
- `checkpoint`, `archive` y `vault` (Paso 12), salvo lo que el append necesite como interfaz.
- Las candidatas no listadas arriba.

## Archivos de contexto

- `aidlc-docs/construction/plans/decision-registry-code-generation-plan.md` (Bloque D)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§6)
- `aidlc-docs/construction/decision-registry/` (FD: BR-U3-03..07, 13..17 y PBT-U3-01, 06..08; NFR: NFR-U3-11, 20, 21, 43, 51; NFR Design: P-U3-01, 02, 04, 05; Infra: INF-U3-04)
- `aidlc-docs/construction/contracts/` (P-U0-12, `RouteContract`, `create_app`, `deps.call`, `check_business_time` BR-U0-37) y `contracts/`
- Diseños de U9, U11 y U7 que el plan cita, para `monitoring_*`, `metrics` y `explanation`
- `decision-registry/` (lo que dejaron U03-T01 y U03-T02), `revisiones/U03-T01/`, `revisiones/U03-T02/` y `CANDIDATAS.md`

## Criterios de aceptación

- [ ] **CA-1** — Append (Paso 7).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_append_*.py decision-registry/tests/integration/test_append.py -v
  ```
  Esperado: pasan, y hay un caso por cada viñeta de aceptación del Paso 7 (la lista viñeta → caso va en la bitácora). PBT-U3-01, 07 y 08 corren con el perfil `ci`.

- [ ] **CA-2** — Consultas, expediente y verificación bajo demanda (Paso 8).
  ```bash
  uv run pytest decision-registry/tests/integration/test_dossier.py decision-registry/tests/integration/test_queries.py decision-registry/tests/integration/test_integrity_api.py -v
  ```
  Esperado: pasan, con un caso por cada viñeta de aceptación del Paso 8.

- [ ] **CA-3** — Readiness y contratos (Paso 9).
  ```bash
  uv run pytest decision-registry/tests/integration/test_health.py -v && make -C contracts openapi && git diff --exit-code contracts/openapi/
  ```
  Esperado: con el standby detenido, `/readyz` da 503 en ≤ 5 s. El OpenAPI regenerado está versionado e incluye las rutas de U3.

- [ ] **CA-4** — Resumen (Paso 10).
  ```bash
  uv run python platform/tests/test_traceability.py --unit decision-registry --section api
  ```
  Esperado: código 0. Además, la bitácora muestra con `grep` que BR-U3-01..07 y 13..16 aparecen en las pruebas, porque la prueba de trazabilidad es débil (candidata de U03-T02).

- [ ] **CA-5** — Candidatas.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_verify.py decision-registry/tests/property/test_projections.py -v
  ```
  Esperado: pasan, y las mutaciones de los ítems 1 y 2 están en rojo en la bitácora.

- [ ] **CA-6** — `check` de U3, de U0 y de U1.
  ```bash
  make -C decision-registry check && make -C contracts check && make -C platform check
  ```
  Esperado: código 0 en los tres.

## Plan de pruebas

Rojo primero de cada criterio, con una mutación por regla. Por ejemplo:
- idempotencia con `occurred_at` en la llave;
- la ventana de ±5 min aplicada a llaves existentes;
- scope sin comprobar la forma de `fail_closed`;
- sin `remote_apply`;
- `daily:query` que suma en el cliente;
- `integrity-checks` que crea una segunda activa.

Regístralo en `bitacoras/U03-T03.md`.

## Notas

- Archivos que se modifican en su sitio:
  - `decision-registry/src/vectra_registry/` (`append.py`, `dossier.py`, `api.py`, `pools.py`, `health.py` y los demás de §1);
  - `contracts/` (registro de rutas y OpenAPI);
  - el plan de U3 y `CANDIDATAS.md`.
- Hay otros codificadores en paralelo, en `reference-model/` (U05-T02) y en `identity-edge/` y `platform/kind/` (U02-T19). No toques esos directorios.
