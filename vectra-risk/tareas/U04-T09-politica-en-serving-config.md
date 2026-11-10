# U04-T09 — La política activa viaja en `serving-config` (U0, U4 y el arranque de scoring en U7)

**Unidad:** U4 `governance`, dueña de la semántica de `serving-config` (domain-entities §5; BR-U0-93: «El tipo vive aquí [U0] y U4 documenta su semántica»). Toca además el tipo de U0 y el arranque de scoring en U7.
**Historias que implementa:** ninguna nueva. Quita el bloqueo que impide desplegar scoring, y con él las cuatro demos: US-103 (`policy_version_id = P` en la respuesta) y BR-U7-04 (las cinco reglas con los parámetros de la política activa).
**Depende de:**
- **U07-T03 fusionado en `main`**, porque esta tarea toca su `orchestrator.py`, `clients.py`, `app.py` y sus dobles;
- en `main`: U0 (`ServingConfig`, `ChannelRule`, `PolicyDraft`, `codegen.py`), U4 (`serving_config.compose`, `evidence.recompute_serving_config`, `convergence.ServingConfigCache`, la API de políticas) y U04-T08 (punto de entrada de governance).

**Se despacha** cuando U07-T03 esté fusionado en `main` y **antes de U07-T04**, que depende de esta tarea.
**Rama:** `tarea/U04-T09`, desde `origin/main`.

**Origen.** Decisión del usuario del 2026-11-10: ampliar `ServingConfig` con `cutoff`, `low_confidence_threshold` y `channel_rules` de la política activa. Descartó una ruta nueva `GET /v1/policies/{id}` con scope de servicio y los valores en el chart. El hueco lo encontró U07-T03:
- `revisiones/U07-T03/ronda-1.md`, sección «Lo que se pidió decidir»;
- en `CANDIDATAS.md`, la candidata bloqueante «Fuente de la política activa (U0/U4)».

Hoy:
- `ServingConfig` (`contracts/python/vectra_contracts/src/vectra_contracts/models/governance.py:42-50`) trae solo `policy_version_id`;
- U7 domain-entities (`aidlc-docs/construction/scoring-explainability/functional-design/domain-entities.md`, `PolicyEvaluationInput`) dice que `cutoff`, `low_confidence_threshold` y `channel_rules` salen de la «política activa (`policy_version_id` de `serving-config`)»;
- la única ruta que sirve políticas es `GET /v1/policies`, con `roles=ANA_CRO_CUM` y sin scope de servicio (`contracts/python/vectra_contracts/src/vectra_contracts/routes/__init__.py`);
- por eso `scoring.app.main` termina con `policy_source_undefined`.

No es un paso del plan de U4 ni del de U7: es una corrección de diseño entre unidades, como U00-T01 y U00-T02. Rige RL-1 a RL-5 (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea.

---

## Alcance

**Dentro:**

1. **U0, el tipo.**
   - `ServingConfig` gana tres campos **obligatorios**, con los tipos de `PolicyDraft` y en el mismo orden: `cutoff: UnitDecimal4`, `low_confidence_threshold: UnitDecimal4` y `channel_rules: list[ChannelRule]`. `channel_rules` reutiliza el `ChannelRule` que ya existe y no crea un tipo nuevo (P-1).
   - Regenera el OpenAPI (`make -C contracts openapi`) y el cliente TypeScript (`npm run -w contracts/ts generate`).
   - Pruebas de contrato del tipo nuevo.
   - Entrada en `contracts/CHANGELOG.md`, bajo «Sin publicar». Añadir propiedades obligatorias a una respuesta no es un cambio incompatible para `oasdiff`, así que no se sube la versión mayor (BR-U0-91 y 92). Compruébalo con `contracts/tools/version_gate.py` si `oasdiff` está disponible; si no lo está, regístralo en la bitácora.
2. **U4, la composición.**
   - `serving_config.compose` copia los tres campos de la `PolicyVersion` `activa` que ya recibe.
   - El `etag` los cubre sin cambiar `compute_etag`, porque hoy se calcula sobre todos los campos salvo el propio `etag` (BR-U4-11 y 14; PBT-U4-05).
   - `SECTION_5_FIELDS` de `governance/tests/property/test_serving_config.py` se amplía con los tres campos.
   - **Sin migración** (P-2): la fila `serving_config` guarda `policy_version_id`, y la caché (`ServingConfigCache._install`) ya recompone desde la fila de `policies`. `gov_app` no puede cambiar `cutoff`, `low_confidence_threshold` ni `channel_rules` de una política (`0003_grants.py` solo da `UPDATE (state, approved_by, activated_at, superseded_at, rejection_justification)`), así que esos valores son inmutables para un `policy_version_id`.
   - Sin política `activa`, todo sigue igual que hoy: `compose` devuelve `None`, la fila queda nula y `GET /v1/serving-config` responde 503 con `no_serving_config`. Queda escrito en U4 domain-entities §5.
   - Se actualizan los fixtures de U4 que construyen un `ServingConfig`, incluidos los de `promotion_tool`.
3. **U7, solo lo mínimo para quitar el bloqueo** (P-3).
   - El orquestador toma `cutoff`, `low_confidence_threshold` y `channel_rules` **del mismo `ServingConfig`** que usa para `policy_version_id`, `model_version_id` e `inference_service`, en la misma foto y sin una segunda llamada.
   - Se quitan `PolicySource`, `PolicyParameters` y el parámetro `policy_source` de `Orchestrator`, `build_deps` y `create_scoring_app`.
   - `scoring.app.main` arranca con las variables reales (`REQUIRED_ENV`) y ya no lanza `policy_source_undefined`.
   - Los dobles de governance de `scoring-explainability/tests/doubles/` sirven los tres campos. Las pruebas de la rama que ya no existe (la fuente de política lenta o sin la política, hoy en `test_edges.py`) se retiran, y su retiro se justifica en la bitácora.
   - PBT-U7-07 y PBT-U7-08 siguen pasando; el generador de fallos pierde la dimensión «política».
4. **Diseños.**
   - U0 domain-entities §9.3, fila `ServingConfig`.
   - U4 domain-entities §5: una fila por campo nuevo con su origen, y la nota «sin política `activa` → `no_serving_config`».
   - U7 domain-entities, `PolicyEvaluationInput`: `cutoff`, `low_confidence_threshold` y `channel_rules` vienen de `serving-config`, copiados por governance de la política `activa`. Cada cambio lleva la nota «(precisado el 2026-11-10, U04-T09: decisión del usuario)».
5. **`CANDIDATAS.md`.**
   - Cierra la candidata bloqueante «Fuente de la política activa (U0/U4)» y la de la etiqueta `stage="serving_config"` de la `PolicySource` (`revisiones/U07-T03/ronda-1.md`, F-04), porque esa rama desaparece.

**Fuera** (rechazar aunque se vea roto):
- Una ruta nueva de políticas, scopes nuevos, cambios en la matriz de roles o en el realm de U2. El usuario los descartó.
- Valores de política en el chart o en variables de entorno.
- El chart, las imágenes y la Application de U7. Son de U07-T04.
- El resto de las candidatas de U7: el `dictionary` de `check_preconditions`, el host de KServe, el scope de la precarga, INF-U7-03, `-SIGTERM` y la cobertura de PBT-U7-07 (F-02 de U07-T03).
- U8 (case-service también lee `serving-config`, BR-U4-14). Todavía no tiene código; solo se le avisa en la bitácora.
- Nada contra un clúster (AUTONOMIA-01).

---

## Archivos de contexto

- `revisiones/U07-T03/ronda-1.md` y `ronda-2.md`, si existe, y `bitacoras/U07-T03.md`.
- `contracts/python/vectra_contracts/src/vectra_contracts/models/governance.py`, `contracts/tools/codegen.py`, `contracts/tools/version_gate.py`, `contracts/Makefile`, `contracts/CHANGELOG.md`, `contracts/tests/unit/test_models.py`.
- `governance/src/vectra_governance/serving_config.py`, `evidence.py` (`recompute_serving_config`), `convergence.py` (`ServingConfigCache`), `api.py` (`serving_config`), `governance/migrations/versions/0001_governance_schema.py` y `0003_grants.py`.
- `governance/tests/property/test_serving_config.py`, `governance/tests/integration/test_api_policies.py`, `test_convergence.py`, `evidence_support.py`.
- `scoring-explainability/scoring/src/scoring/` (`orchestrator.py`, `clients.py`, `app.py`) y `scoring-explainability/tests/doubles/` (`governance.py`, `worlds.py`, `run_scoring.py`).
- Diseños:
  - `aidlc-docs/construction/contracts/functional-design/domain-entities.md` §9.3;
  - `aidlc-docs/construction/governance/functional-design/domain-entities.md` §5;
  - `aidlc-docs/construction/governance/functional-design/business-rules.md` (BR-U4-11, 12 y 14);
  - `aidlc-docs/construction/governance/nfr-design/nfr-design-patterns.md` (P-U4-07);
  - `aidlc-docs/construction/scoring-explainability/functional-design/domain-entities.md` y `business-rules.md` (BR-U7-01 y 04).

---

## Criterios de aceptación

Desde `vectra-risk/`. Cada uno con su par rojo-verde en la bitácora cuando cambia comportamiento.

- [ ] **CA-1 — Tipo de U0.**
  ```bash
  uv run pytest contracts/tests/unit/test_models.py -v -k serving_config
  ```
  Esperado: pasan al menos tres pruebas con `serving_config` en el nombre:
  - un `ServingConfig` con los tres campos se valida;
  - uno sin alguno de ellos se rechaza;
  - un `cutoff` fuera de [0, 1] o con más de 4 decimales se rechaza.
  Además, `channel_rules` es `list[ChannelRule]`:
  ```bash
  uv run python -c "from vectra_contracts.models.governance import ServingConfig as S, ChannelRule as C; f=S.model_fields; assert f['channel_rules'].annotation == list[C]; assert all(f[n].is_required() for n in ('cutoff','low_confidence_threshold','channel_rules')); print('OK')"
  ```
  Esperado: `OK`.

- [ ] **CA-2 — OpenAPI y TypeScript regenerados.**
  ```bash
  uv run python -c "import yaml; s=yaml.safe_load(open('contracts/openapi/governance-service.yaml'))['components']['schemas']['ServingConfig']; assert {'cutoff','low_confidence_threshold','channel_rules'} <= set(s['required']); print('OK')"
  make -C contracts check
  ```
  Esperado: `OK`, y `make -C contracts check` en 0. Esto incluye su `git diff --exit-code` sobre `contracts/openapi/` y `contracts/ts/src/generated/`.

- [ ] **CA-3 — Composición y `etag` (PBT-U4-05).**
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_serving_config.py -v
  ```
  Esperado: pasan PBT-U4-05, con `SECTION_5_FIELDS` ampliado, y además:
  - `compose` copia exactamente los tres valores de la política `activa`;
  - dos políticas que solo difieren en `cutoff`, en `low_confidence_threshold` o en una `channel_rule` dan `etag` distintos.
  Rojo primero: con `compose` sin los campos nuevos, la prueba de copia falla.

- [ ] **CA-4 — Activar otra política cambia lo servido, con lectura de vuelta.**
  ```bash
  uv run pytest governance/tests/integration/test_api_policies.py -v -k serving_config
  ```
  Esperado: una prueba de integración contra Postgres real (Testcontainers) hace esto, en orden:
  1. propone y aprueba la política A con dos personas distintas (BR-U4-10);
  2. `GET /v1/serving-config` sirve los tres valores de A, y coinciden con `SELECT cutoff, low_confidence_threshold, channel_rules FROM policies WHERE state = 'activa'`;
  3. propone y aprueba B con otro `cutoff` y otra `channel_rule`;
  4. **en ≤ 1 s** (NFR-U4-05), `GET /v1/serving-config` sirve los valores de B y un `etag` distinto;
  5. `If-None-Match` con el `etag` de A da 200 con B, no 304;
  6. el `SELECT` de vuelta muestra A en `historica` y B en `activa`.

- [ ] **CA-5 — Sin política activa, todo como hoy.**
  ```bash
  uv run pytest governance/tests/integration/test_convergence.py -v -k "sin_version_servible or no_serving_config or sin_politica"
  ```
  Esperado:
  - la prueba que ya existe (`no_serving_config`) sigue pasando;
  - una nueva comprueba que, con modelo `activo` y sin política `activa`, `GET /v1/serving-config` da 503 con `no_serving_config` y la fila `serving_config` queda nula.

- [ ] **CA-6 — Scoring toma la política de `serving-config` y su proceso real arranca.**
  ```bash
  ! grep -rnE "PolicySource|PolicyParameters|policy_source_undefined" scoring-explainability/scoring/src
  uv run pytest scoring-explainability/tests/integration/test_app.py -v -k "main or policy"
  ```
  Esperado: el `grep` no encuentra nada, y pasan dos pruebas:
  1. **El proceso real.** Lanza `python -m scoring.app` como proceso, con las variables de `REQUIRED_ENV` apuntando a los dobles HTTP de governance, KServe, explainability y el registro. `/readyz` da 200, y un `POST /v1/recommendations` devuelve una `Recommendation` cuyo `policy_result` sale del `cutoff` del doble. Si se cambia el `cutoff` del doble para que el mismo `score` quede del otro lado del corte, el `outcome` y `reasons` cambian.
  2. **La misma foto.** Si el doble cambia `serving-config` entre dos solicitudes, cada respuesta lleva el `policy_version_id` y los parámetros de su propia foto, nunca mezclados.

  Rojo primero: con el `main` actual, el proceso termina con `policy_source_undefined`.

- [ ] **CA-7 — Las PBT de U7 siguen en pie.**
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests/property -v
  ```
  Esperado: pasan PBT-U7-07, las dos de PBT-U7-08 y la propiedad de P-U7-01, con la semilla impresa. Los pares RT-1 de U5 dan salidas idénticas con la política servida por el doble de `serving-config`.

- [ ] **CA-8 — Diseños actualizados.**
  ```bash
  grep -n "low_confidence_threshold" aidlc-docs/construction/contracts/functional-design/domain-entities.md | grep -n "ServingConfig"
  grep -nE "^\| .*(cutoff|channel_rules)" aidlc-docs/construction/governance/functional-design/domain-entities.md
  grep -n "U04-T09" aidlc-docs/construction/scoring-explainability/functional-design/domain-entities.md aidlc-docs/construction/governance/functional-design/domain-entities.md aidlc-docs/construction/contracts/functional-design/domain-entities.md
  grep -n "no_serving_config" aidlc-docs/construction/governance/functional-design/domain-entities.md
  ```
  Esperado: cada `grep` encuentra al menos una línea, y hay una nota «U04-T09» en cada uno de los tres archivos.

- [ ] **CA-9 — Checks de las unidades tocadas.**
  ```bash
  make -C contracts check && make -C governance check && make -C scoring-explainability check && make -C platform check && uv lock --check
  ```
  Esperado: todos en 0. Si faltan herramientas, primero `platform/install-tools.sh`. No se vale saltar un objetivo.

- [ ] **CA-10 — Candidatas cerradas.**
  ```bash
  grep -n "U04-T09" CANDIDATAS.md
  ```
  Esperado: la candidata bloqueante de la fuente de política y F-04 de U07-T03 aparecen cerradas, cada una con «cerrada en U04-T09».

---

## Preguntas (rige la recomendación si el usuario no responde)

- **P-1. Forma de los campos.** Hay dos opciones:
  - (a) planos en `ServingConfig`: `cutoff`, `low_confidence_threshold` y `channel_rules`, con los mismos nombres y tipos que `PolicyDraft`;
  - (b) anidados en un objeto `policy`.

  **Recomiendo (a).** Es lo que decidió el usuario, sigue el patrón de `normative_current` y permite que scoring construya `PolicyEvaluationInput` campo por campo sin un tipo nuevo. Con (a), `channel_rules` reutiliza `ChannelRule`.
- **P-2. ¿Guardar los campos en la fila `serving_config`, con una migración?**

  **Recomiendo que no.** La caché recompone desde la fila de `policies`, que es inmutable para `gov_app` en esos campos (`0003_grants.py`). Además, el `etag` guardado solo se usa para detectar cambios, y cambia igual porque cambia `policy_version_id`. Si el revisor encuentra un lector de la fila que necesite los valores, se agrega la migración `0005` y se dice en la bitácora.
- **P-3. ¿El cambio de scoring entra aquí o en U07-T04?**

  **Recomiendo que entre aquí,** como criterio de arranque real (CA-6). Si se deja para U07-T04, esta tarea cambiaría el contrato sin que nadie lo consuma, y U07-T04 tendría que tocar el orquestador además del chart. La lección de U04-T06 y U04-T08 es que un servicio que no arranca se descubre tarde.

---

## Notas

- **Bitácora:** `bitacoras/U04-T09.md`, con el acuse del hash de esta tarea, los pares rojo-verde de CA-3, CA-4 y CA-6, y la salida real de cada comando de aceptación, sin flags extra (ver `revisiones/U07-T03/ronda-1.md`, F-01).
- **El plan no cambia de casillas.** Los Pasos 5 y 10 de U4 y los Pasos 10 y 11 de U7 siguen `[x]`. A la nota de cada uno se le añade «ampliado en U04-T09 (política en `serving-config`)».
- No uses `git stash`.
