# U03-T04 — CLI `vectra-registry` y CronJob del agregador de `decision-registry`

**Unidad:** U3 `decision-registry`
**Historias que implementa:** US-402 (verificador) y la parte de U9 que depende de U3 (BR-U3-17, agregador).
**Depende de:** U03-T03 (servicio). Si su PR todavía no está fusionado, **la rama parte de `origin/tarea/U03-T03`** (o de la punta local de esa rama, `62254e2` o posterior), y el orquestador la integra con `main` cuando se fusione.

Bloque E del plan de U3 (Pasos 11 y 12). El alcance de la demo (`aidlc-docs/construction/plans/demo-kind-alcance.md` §3, U3) dice:
- Paso 11 **E** (completo);
- Paso 12 **E\***: entran el CronJob `registry-aggregator` (lo usa U9 para el freeze de la demo 7.4), las ServiceAccounts y las políticas HCL de la bóveda; se difieren `registry-checkpoint`, `registry-verify-*`, `registry-archive`, `chart-rebuild/` y `x06-probe` (T5).

Rige el ritmo RL-1 a RL-5 (§6): máximo 2 rondas, y solo un ROJO bloquea.

## Alcance

**Dentro:**

- **Paso 11 — CLI `vectra-registry`**, con el texto y la aceptación del plan sin recortes (`aidlc-docs/construction/plans/decision-registry-code-generation-plan.md`, Paso 11):
  - `verify --mode incremental|nightly|full|range [--source db|archive]`, con códigos 0, 1 y 2;
  - `checkpoint`;
  - `archive --month`;
  - `aggregator run` (y `--until-head`);
  - `aggregator reset`.

  Cada viñeta de aceptación es un caso de `tests/integration/test_cli.py`, con Testcontainers: PostgreSQL, MinIO con object lock y Vault dev.
- **Paso 12, solo lo que entra en la demo:**
  - el **CronJob `registry-aggregator`**: cada 5 min, `Forbid`, `activeDeadlineSeconds: 280`, `vectra-high`, sidecar nativo de Linkerd, rol `registry_aggregator`, F107; itera lotes hasta la cabeza o 240 s. Aplica BR-U3-17 con la regla de una recomendación por caso, las inválidas y la marca de agua en la misma transacción que los conteos, más la métrica del atraso para `MonitoringAggregatorStale`;
  - las **ServiceAccounts por identidad** (P-U3-08);
  - las **políticas HCL versionadas** de la bóveda: la firma solo para checkpoint y archivo, ninguna para la API;
  - su aceptación, recortada a eso:
    - `HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_aggregator.py decision-registry/tests/integration/test_aggregator.py`: PBT-U3-09 y todas las viñetas del plan sobre el agregador, como matar el proceso entre lotes, 20 000 pendientes, purga a 181/179 días, `human_decision` no atribuible, recomendación inválida, `reactivar`, `region` fuera del catálogo y CronJob y Job solapados;
    - `uv run pytest decision-registry/tests/unit/test_vault_policies.py`;
    - `helm template` + `conftest` del **chart** solo para el CronJob del agregador y las ServiceAccounts: límites de tiempo, `Forbid`, anotación del sidecar nativo y sin Secret plano.
  - El chart del servicio completo es el Paso 13 (Bloque F). Aquí basta con el `chart/` mínimo que contiene el CronJob y las ServiceAccounts, y que el Paso 13 completará.

**Decisión de diseño pendiente que puede afectar a `checkpoint`.** Hay una candidata de U03-T03: la firma del checkpoint cubre el `recorded_at` de su propia entrada, que el append asigna dentro del lock, así que la CLI no lo conoce antes de firmar. Lee domain-entities §1.1 y §2.2 y BR-U3-08 y 10.
- **Si el diseño ya lo resuelve** (por ejemplo, firmando la cabeza anterior y no la propia entrada), impleméntalo así y cítalo.
- **Si no lo resuelve,** **detente y repórtalo** antes de escribir `checkpoint`, con las opciones que veas. Lo decide el usuario.
- En ese caso, el resto de la tarea (`verify`, `archive`, `aggregator`, Paso 12) puede seguir.

**Fuera:**
- Los CronJobs `registry-checkpoint`, `registry-verify-*` y `registry-archive`; `chart-rebuild/`; `x06-probe` (diferidos, T5).
- El chart completo del servicio y los buckets (Paso 13); las alertas (Paso 14, diferido); las Applications (Paso 15).
- Cambiar U0 o U1. Si a U1 le falta un rol o un Secret, se reporta.

## Archivos de contexto

- `aidlc-docs/construction/plans/decision-registry-code-generation-plan.md` (Pasos 11 y 12)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§3, U3, y §6)
- `aidlc-docs/construction/decision-registry/` (BR-U3-08, 10, 11, 13, 17; PBT-U3-09; NFR-U3-04, 12, 24, 35, 40, 42; P-U3-03, 05, 07, 08; INF-U3-02, 03; domain-entities §1.1, §1.3 y §2.2)
- Diseño de U9 en la parte del agregador y de la proyección `monitoring_*`
- `decision-registry/` (lo que dejaron U03-T01 a U03-T03), `revisiones/U03-T03/` y `CANDIDATAS.md`
- `platform/data/` (roles de U1) y `platform/network/flows.yaml` (F107)

## Criterios de aceptación

- [ ] **CA-1** — CLI.
  ```bash
  uv run pytest decision-registry/tests/integration/test_cli.py -v
  ```
  Esperado: hay un caso por cada viñeta del Paso 11 y todos pasan. Si `checkpoint` quedó detenido por la decisión de diseño, sus casos faltan y la bitácora lo dice.

- [ ] **CA-2** — Agregador.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_aggregator.py decision-registry/tests/integration/test_aggregator.py -v
  ```
  Esperado: PBT-U3-09 y todas las viñetas del agregador del Paso 12 pasan.

- [ ] **CA-3** — Bóveda y chart mínimo.
  ```bash
  uv run pytest decision-registry/tests/unit/test_vault_policies.py -v && helm template decision-registry decision-registry/chart | conftest test --policy <políticas del chart> -
  ```
  Esperado: código 0 en las dos. La forma exacta del comando de `conftest` va en el `Makefile` y en la bitácora.

- [ ] **CA-4** — `check` de U3 y de U1.
  ```bash
  make -C decision-registry check && make -C platform check
  ```
  Esperado: código 0 en los dos.

## Plan de pruebas

Rojo primero con una mutación por regla. Por ejemplo:
- `verify` que devuelve 0 en una cadena alterada;
- dos `checkpoint` en la misma hora que escriben dos veces;
- agregador sin la marca de agua en la misma transacción;
- `aggregator reset` permitido a `registry_aggregator`;
- una política HCL que da `sign` a la API.

Registra todo en `bitacoras/U03-T04.md`.

## Notas

- Archivos que se modifican en su sitio: `decision-registry/src/vectra_registry/{cli,checkpoint,archive,vault,worm,aggregator}.py`, `decision-registry/chart/`, `decision-registry/vault-policies/`, `tests/`, el plan de U3 (marca `[x]` el Paso 11 y deja el 12 como `[x] (U03-T04, acotado a la demo)`) y `CANDIDATAS.md`.
- Hay otro codificador en paralelo en `reference-model/` (U05-T04). No toques ese directorio.
