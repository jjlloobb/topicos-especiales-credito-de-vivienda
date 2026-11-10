# U09-T03 — Servicio HTTP de `bias-monitoring`: `dashboard`, `freezes`, `compare`, la app con su punto de entrada y el resumen

**Unidad:** U9 `bias-monitoring`
**Historias que implementa:** US-304 (Paso 9, el paquete por `GET /v1/freezes/{id}`), US-306 (Paso 9, `compare_source`) y US-307 (Paso 9, el dashboard con `disclaimer`).
**Depende de:**
- U09-T02 (Bloque C: `window`, `freeze_rule`, `context`, `registry_client`, `freeze_client`, `publish`, `run`, y los dobles de `tests/doubles/`), en `main`;
- en `main`, como contratos de los dobles: U0 (`create_app`, `REGISTRY["bias-monitoring-service"]`, `Scope`, `deps` con `BreakerConfig`, `service_token`, `authn`, `ops_server`, `LogEvent`, modelos de `monitoring.py`), U3 (`GET /v1/monitoring/freezes` y `POST /v1/monitoring/daily:query`) y U4 (el cliente F25 `HttpSourceComparer`, que llama a `POST /v1/source-comparisons`).

**Se despacha** cuando U09-T02 (#114) esté en `main`. Puede correr en paralelo con otras unidades (RL-5).
**Rama:** `tarea/U09-T03`, desde `origin/main`.

Bloque D del plan de U9 (`aidlc-docs/construction/plans/bias-monitoring-code-generation-plan.md`), Pasos 9 y 10. Es la tarea «D» de `demo-recorte-funcional.md` §4 y §8 («U9: C · D · E+cierre»). **No** se junta con el Bloque C (§4: «U9 C con D (cuatro PBT compuestas)») ni con el E (chart, imagen y cierre van en U09-T04, §8).

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 9 `dashboard`, `freezes`, `compare` y la app | **E** | Completo, con PBT-U9-07 y **las cuatro rutas** de `REGISTRY["bias-monitoring-service"]`: `/v1/freezes` y `/{id}` (D2); `/v1/disparity` y `compare` porque `create_app` los exige. Con punto de entrada real (`python -m vectra_bias.app`). El `preStop` de 5 s es un campo del `Deployment`: va con el chart (Paso 12, U09-T04) | Enmienda §3 U9, fila «9 Servicio»; §2 regla 2; §5.1, fila «Rutas sin demo»; §6 P-1 |
| 10 Resumen del CronJob y del servicio | **E\*F** | Cobertura de ramas, PBT-U9-01..08 con el perfil `ci` y `services.md`. **Se difiere `mutmut`** en `freeze_rule` (NFR-U9-51) | Enmienda §3 U9, fila «5 · 10 Resúmenes»: «Sin `mutmut` (T3)»; §2 regla 3 («U9 Pasos 5 y 10») |

Lo que queda fuera es de otros pasos: el Dockerfile, el chart, el `ConfigMap`, el `preStop`, la Application y el k6 (Pasos 11, 12 y 14, U09-T04); las alertas y el workflow (Pasos 13 y 15, D); el Paso 16 (consolidado en U12 Paso 18, enmienda §8). El cierre de U9 va en U09-T04, la última tarea de código (enmienda §8).

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda del 2026-11-09.

---

**P-1:** opción (a) para U9, como en U4 y U7 (enmienda §6 P-1: «(a) donde el handler es fino (U8, U9, U10…)»). `create_app` falla si falta o sobra un handler (`vectra_common/app_factory.py`, `ContractViolation`), así que las cuatro rutas entran completas.

**Lección de U04-T06 y U04-T08** (`revisiones/U04-T06/ronda-1.md`, F-01): el contenedor de governance no arrancaba porque solo había handlers, sin `service.py` ni `build_app`. Aquí el punto de entrada es parte del Paso 9 y tiene su propio criterio (CA-2), que arranca el proceso real con variables reales.

---


**Decisiones del usuario (2026-11-10), antes del despacho:**
1. **NFR-U9-52 enmendado:** las PBT stateful se escalan con su número nombrado (PBT-U9-05 a 120 × 80, como quedó en U09-T02), conservando comandos e invariantes. La tarea lo documenta en `code/services.md` y en la prueba; ya no es una desviación.
2. **Literales del Bloque C:** la corrección de rutas y scopes de `freeze_client.py` y `run.py` (F-02 de U09-T02) **entra** en esta tarea, además de `registry_client.py`.

## Alcance

**Dentro:** los Pasos 9 y 10 del plan, con su texto y su aceptación. Léelos allí. Precisiones:

### Paso 9 — `dashboard`, `freezes`, `compare` y la app (E)

**Rutas y scopes** (de `REGISTRY`, nunca literales):
- Los handlers se registran con las llaves `(route.method, route.path)` de `REGISTRY["bias-monitoring-service"]` (`contracts/python/vectra_contracts/src/vectra_contracts/routes/__init__.py`, `_bias`). Roles y scopes los aplica `create_app`:
  - `POST /v1/source-comparisons`: scope `Scope.BIAS_COMPARE` (solo `governance-service`), cuerpo ≤ 64 KiB;
  - `GET /v1/disparity`: `cro` y `cumplimiento`, `query_model = DisparityFilter`;
  - `GET /v1/freezes`: `cro` y `cumplimiento`;
  - `GET /v1/freezes/{id}`: solo `cumplimiento`.
- Las llamadas al registro usan las rutas de `REGISTRY["decision-registry-service"]` y `Scope.REGISTRY_READ_MONITORING`. Ningún módulo de `vectra_bias` escribe una ruta del contrato o un scope como literal (ver «Literales de U09-T02», abajo).

**`dashboard`** (BR-U9-18; P-U9-03; US-307):
- Versión: la que manda el BFF en `version`. Si no llega, la de las recomendaciones más recientes de la población `modelo`, con `include_versions` de `daily:query` (`VersionWindow.last_day`). bias no lee governance (X04).
- Ventana: el filtro `window` (7, 30 o 90; U0 lo valida). Sin filtro, `window_days` de la política. El inicio respeta BR-U9-08 con `vectra_bias.window` (la última `reactivar` de la versión, leída de `GET /v1/monitoring/freezes`). No reimplementes `window`.
- Cálculo con `vectra_disparity` y las funciones de `context` de U09-T02 (`measure`, `departure_rates`): `model` y `human` **separadas**, tasa de apartamiento, supresión de celdas chicas (P-U9-04). Si `attribute` llega, solo ese atributo.
- `DisparityView` de U0 con los cinco parámetros de la política (`threshold_pp`, `n_min`, `window_days`, `schedule`, `stale_after_s`), `invalid_entries` (la suma de `RangeTotals.invalid_entries` de los rangos pedidos) y `disclaimer = "mide y alerta, no certifica"`.
- Log `LogEvent.DISPARITY_VIEWED` en **cada** consulta, también desde la caché, con `principal_subject`, `principal_role`, `model_version_id`, `window_from` y `window_to` (NFR-U9-32).
- Registro caído o circuito abierto → 503 con el `Problem` de U0, sin datos parciales.

**`cache`** (P-U9-03; NFR-U9-02):
- LRU de `config.CACHE_ENTRIES` (64) y `config.CACHE_TTL_S` (15 min), por réplica. Llave: (versión, atributo, ventana). Con la versión ausente, decide si la llave usa la versión resuelta o «sin versión» y anótalo en la bitácora.
- *Single-flight*: con la misma llave y sin caché, una sola lectura del registro; las demás esperan su resultado o su error. Un error no se guarda.
- Solo guarda la respuesta ya suprimida.
- Métricas de la caché en el registro de U0 (`vectra_common.metrics.REGISTRY`), por ejemplo aciertos y fallos con la etiqueta `result`. El diseño no fija sus nombres: elígelos y escríbelos en `services.md`.

**`freezes`** (BR-U9-19; US-304):
- Lee `GET /v1/monitoring/freezes` (lista de `FreezeRecord`) con `registry_client`. U3 no tiene una ruta por id: `GET /v1/freezes/{id}` busca por `freeze_id` en la lista. Inexistente → 404 `not_found`.
- `GET /v1/freezes` → `list[FreezeSummary]`: `trigger_attribute` del paquete, `model_aggregate` de `context_package.after`, y `resolution` = la **más reciente** (con `investigar` y luego `reactivar`, la `reactivar`).
- `GET /v1/freezes/{id}` → `FreezeRecord` de U0 tal como lo guardó el registro, con `context_package` (`FreezeContextPackage`). El contrato de U0 manda: la BLM §2.3 dice `FreezeContext`, pero `REGISTRY` dice `FreezeRecord`. No cambies U0.
- Log `LogEvent.FREEZE_CONTEXT_VIEWED` con `principal_subject`, `principal_role` y `model_version_id`.
- **«`investigar` seguido de `reactivar` reinicia la ventana según BR-U9-08, con prueba»** (plan): con un `FreezeRecord` con esas dos resoluciones (la `reactivar` a las 23:50 UTC del día D), `GET /v1/freezes` muestra la `reactivar` y `GET /v1/disparity` de esa versión mide desde el día D + 1.

**`compare`** (BR-U9-17; US-306; F25):
- Recibe `CompareSourceRequest` (U0 ya exige los cuatro atributos sin repetir y conteos ≥ 0).
- Valida además el catálogo de U0 §2.2: grupos y bandas fuera del catálogo → 422 `validation_error`, sin cálculo parcial. Los 22 grupos salen de los `Literal` de U0 (`Sex`, `RangoEdad`, `Region`, `Stratum` y `Band`), no de una lista escrita a mano ni de `vectra_registry`.
- Calcula `pre` y `post` con la librería y `delta = post − pre` de cada agregada y de `model_aggregate` (`PrePostDelta` de U0). Un `delta` es `null` si falta una de las dos agregadas.
- `PrePostReport` ≤ 48 KiB en JCS (`vectra_contracts.canonical`). Si no cabe, quita las celdas de `pre` y después las de `post`; conserva agregadas, bandas y `delta`; `truncated = true`. Lleva `threshold_pp`, `n_min` y `disclaimer`. No guarda nada.
- Es el servidor del cliente de U4 `HttpSourceComparer` (`governance/src/vectra_governance/clients.py`): responde 200 con `PrePostReport`.

**La app y su punto de entrada** (P-U9-05; NFR-U9-12, 41):
- `app.py` tiene `config_from_env()`, `build_app()` y `main()`, con el patrón de `decision-registry/src/vectra_registry/service.py`, y `if __name__ == "__main__": main()`. `python -m vectra_bias.app` es el punto de entrada del plan (P-U9-05).
- `config_from_env()` lee **solo** el entorno:
  - `VECTRA_REGISTRY_URL`;
  - `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_ID`, `VECTRA_CLIENT_KEY_PATH` y `VECTRA_CLIENT_KEY_ID` (cliente `bias-monitoring-service`, `service_token.provider_from_env` con `Scope.REGISTRY_READ_MONITORING`);
  - `VECTRA_OIDC_ISSUER` y `VECTRA_JWKS_URL` (`authn.authenticator_from_env`), y `VECTRA_CA_BUNDLE` con `https`;
  - `VECTRA_POLICY_PATH` si el `ConfigMap` no está en `config.POLICY_PATH`.

  Son los nombres de `run.py`, más los de U0. Si falta una obligatoria, falla al arrancar con un mensaje que la nombra. Una política inválida detiene el arranque (`config.load_policy`). Escribe la lista en el docstring de `app.py` y en `services.md`: el chart de U09-T04 la usará.
- `build_app()` arma un `DependencyClient` hacia el registro **con breaker**: `BreakerConfig(open_for=10, window_size=20, failure_ratio=0.5, window_seconds=30)` (P-U9-02, los umbrales de U7), timeouts de `config.py` (3 s y 5 s). Llama a `create_app("bias-monitoring-service", handlers=…)`. Readiness solo del proceso (`readiness=None`).
- `main()` llama a `vectra_common.ops_server.run_service(app)`: 8080 con el contrato y 8081 con `/metrics`, `/healthz` y `/readyz`, y la espera de ≤ 10 s en el apagado (`GRACEFUL_SHUTDOWN`).
- `app.py`, `dashboard.py`, `freezes.py`, `compare.py` y `cache.py` **no** importan `freeze_client` ni `run` (que lo importa). El contrato `servicio-no-congela` de `.importlinter` revisa también los imports indirectos. No reutilices `run.build_deps`.
- Diseño: BR-U9-17, 18, 19; P-U9-03, 05; NFR-U9-02, 12, 32, 33 (y NFR-U9-41 de la aceptación, A7). Historias: US-304, US-306, US-307.

**Literales de U09-T02** (candidata F-02 de `revisiones/U09-T02/ronda-1.md`): `registry_client.py` lo usa ahora el servicio, así que sus rutas salen de `REGISTRY["decision-registry-service"]`. Haz lo mismo en `freeze_client.py` (ruta de `freeze` de `REGISTRY["governance-service"]`) y en los scopes de `run.py` (`Scope`). Es un cambio mecánico: las pruebas de U09-T02 deben seguir pasando sin cambios de comportamiento.

### Paso 10 — Resumen del CronJob y del servicio (E\*F)

- Cobertura de ramas **100 %** en `freeze_rule`, `context` y `window`, y **≥ 95 %** en el resto de `vectra_bias` (NFR-U9-50). pytest-cov con `--cov-branch` y `coverage report --include` por módulo (plan).
- PBT-U9-01..08 con el perfil `ci` (NFR-U9-52). **PBT-U9-05** sigue con el ajuste de escala de U09-T02 (`max_examples=120`, `stateful_step_count=80` en `test_run_machine.py`, no 500): conserva todos los comandos e invariantes, pero contradice NFR-U9-52 al pie de la letra (candidata F-01 de `revisiones/U09-T02/ronda-1.md`). **Nombra la decisión**: en `services.md`, en una sección «PBT-U9-05 frente a NFR-U9-52», con la razón (≈ 0,15 s por corrida; 500 × 80 pasaba de 6 min), las cifras de exploración medidas y la cita de la candidata; y en el comentario de `test_run_machine.py` y del objetivo `property` del `Makefile`, con «NFR-U9-52». No cambies el texto de NFR-U9-52: eso lo decide el usuario.
- Resumen en `aidlc-docs/construction/bias-monitoring/code/services.md` (archivo nuevo): módulos del CronJob y del servicio, rutas y roles, variables de entorno de los dos puntos de entrada, nombres de las métricas de la caché, cobertura por módulo, semillas, la decisión sobre PBT-U9-05 y lo diferido con su cita (`mutmut`, T3; k6 de NFR-U9-02, Paso 14, T3).
- Diseño: NFR-U9-50, 51, 52.

### Makefile

- `property`: agrega `tests/property/test_compare.py`. Corrige el comentario «30 × 60» (candidata F-04 de U09-T02): di 120 × 80 y cita NFR-U9-52.
- Un objetivo de cobertura de `vectra_bias` con los dos comandos de CA-5, dentro de `check`. Que `check` no corra dos veces las mismas pruebas más de lo necesario; si para medir la cobertura hay que repetirlas, anótalo.
- `test` ya recoge `tests/integration/` y `tests/unit/`: las pruebas nuevas de esas carpetas entran solas.

### Plan y candidatas

- Marca `[x]` los Pasos 9 y 10 con `(U09-T03)`. En el Paso 10 agrega «`mutmut` diferido por la demo (T3)». No cambies el resto del texto.
- En `CANDIDATAS.md`, marca como resuelta por U09-T03, con una línea de cómo, «U9, literales de rutas y scopes (revisor, U09-T02, F-02, NARANJA)». En «U9, PBT-U9-05 (revisor, U09-T02, F-01, NARANJA)», agrega que la decisión quedó nombrada en `services.md` y que el texto de NFR-U9-52 queda para el usuario. En la de AMARILLOS de U09-T02, marca el comentario «30 × 60» como corregido.

**Fuera** (recházalo aunque lo veas roto o tentador):

- **`mutmut`** en `freeze_rule` (NFR-U9-51) y **toda prueba de carga** (k6, NFR-U9-02 medido): T3 (enmienda §2 regla 3; §3 U9 filas «5 · 10» y «14»). **No escribas «NFR-U9-51» en ningún archivo de `bias-monitoring/`**: U09-T04 lo pondrá en «Diferido por la demo» de `cierre-demo.md`, y `test_traceability.py` falla si un id diferido tiene código.
- Dockerfile, chart, `ConfigMap`, `preStop`, `ServiceMonitor`, Application y `CODEOWNERS` (Pasos 11, 12 y 14, U09-T04). El `ConfigMap` de prueba del Paso 9 es un archivo temporal en `VECTRA_POLICY_PATH`, no una plantilla del chart.
- Alertas, runbooks, `bias.json` y workflow de CI (Pasos 13 y 15, D).
- La guardiana de `test_run_machine.py` que depende del orden (F-03), `_rewrite` (F-05), `plan_queries(unattributable)` (F-06; el dashboard no lo usa) y el margen fino de D\* en `library.md` (F-04): siguen como candidatas. Si la guardiana te rompe el comando de CA-5, arréglala y anótalo.
- `ACTIVE_DEADLINE_SECONDS` (Paso 12), los pares de Newcombe de `test_stats.py` y `combined_variance`.
- Cambios a U0, U3, U4 o U5. No cambies la librería `vectra_disparity` ni la regla de `freeze_rule`.
- Toda orden contra el clúster (AUTONOMIA-01).

---

## Archivos de contexto

- `aidlc-docs/construction/plans/bias-monitoring-code-generation-plan.md`: §1 (estructura, dobles, AUTONOMIA-01), Bloque D (Pasos 9 y 10), §3.
- `aidlc-docs/construction/plans/demo-recorte-funcional.md`: §1.2 (fila «Paquete en vivo»), §2, §3 U9, §4, §5.1, §5.2, §6 (P-1, P-14) y §8.
- `aidlc-docs/construction/plans/demo-kind-alcance.md` §2 y §6; `DECISIONES-LOOP.md` §6 con su enmienda.
- `aidlc-docs/construction/bias-monitoring/functional-design/`: `business-rules.md` (BR-U9-08, 13, 17, 18, 19), `business-logic-model.md` (§2.2, §2.3; §3: PBT-U9-07 y los ejemplos de `compare_source`, dashboard, versión por omisión y logs) y `domain-entities.md` (§3.2, §3.3, §3.4, §4).
- `aidlc-docs/construction/bias-monitoring/nfr-requirements/nfr-requirements.md` (NFR-U9-02, 12, 31, 32, 33, 41, 50, 51, 52); `nfr-design/nfr-design-patterns.md` (P-U9-02, 03, 04, 05) y `nfr-design/logical-components.md`; `infrastructure-design/deployment-architecture.md` (puertos 8080 y 8081).
- `aidlc-docs/construction/bias-monitoring/code/library.md`.
- `bias-monitoring/`: `src/vectra_bias/` (`config.py`, `window.py`, `context.py`, `registry_client.py`, `run.py`), `.importlinter`, `Makefile`, `pytest.ini`, `coveragerc`, `tests/conftest.py`, `tests/doubles/` (`world.py`: dobles de U3 y Keycloak, `freeze_record`), `tests/integration/test_run.py` (logs en modo strict), `tests/property/test_run_machine.py`.
- `contracts/python/vectra_contracts/src/vectra_contracts/`: `routes/__init__.py` (`_bias`, `_registry`, `_governance`, `REGISTRY`), `catalog.py` (`Scope`, `LogEvent`, `LOG_RECORD_FIELDS`, `ProblemCode`), `models/monitoring.py` (`DisparityFilter`, `DisparityView`, `FreezeSummary`, `FreezeRecord`, `CompareSourceRequest`, `PrePostReport`, `PrePostDelta`), `models/features.py` y `models/application.py` (catálogos), `canonical.py`.
- `contracts/python/vectra_common/src/vectra_common/`: `app_factory.py` (`create_app`), `ops_server.py` (`run_service`), `deps.py` (`BreakerConfig`, `DependencyClient`), `authn.py`, `service_token.py`, `metrics.py`, `logging.py`.
- `contracts/tests/strategies/auth.py` (JWKS y tokens de prueba de U0) y `contracts/tools/forbidden_phrases.py` con `contracts/forbidden-phrases.yaml`.
- `contracts/openapi/bias-monitoring-service.yaml` y `decision-registry-service.yaml`.
- `decision-registry/src/vectra_registry/service.py` (patrón del punto de entrada), `decision-registry/tests/service_harness.py`, `decision-registry/src/vectra_registry/api.py` (las dos lecturas de U3).
- `governance/src/vectra_governance/clients.py` (`HttpSourceComparer`, F25).
- `revisiones/U09-T02/ronda-1.md` (F-01, F-02, F-04), `revisiones/U04-T06/ronda-1.md` (F-01) y `tareas/U04-T08-punto-de-entrada-del-servicio.md`.
- `CANDIDATAS.md`: las entradas de U9.

---

## Criterios de aceptación

Desde `vectra-risk/`. Ninguno toca el clúster. Los dobles de U3 y de Keycloak viven en `bias-monitoring/tests/doubles/` y siguen los contratos de `vectra_contracts`. Los oráculos de los ejemplos se escriben a mano en la prueba (tablas con tasas elegidas y su resultado calculado a mano), no con la función que se prueba. El plan escribe varias rutas relativas a `bias-monitoring/`; aquí van completas.

- [ ] **CA-1** — Paso 9: aceptación del plan.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/property/test_compare.py bias-monitoring/tests/unit/test_compare_examples.py bias-monitoring/tests/integration/test_app.py bias-monitoring/tests/integration/test_cache.py -v
  ```
  Esperado: código 0, con la semilla impresa. Pasan **todas** las líneas de la aceptación del Paso 9 del plan:
  - **PBT-U9-07**: `compare_source(pre, pre)` da `delta = 0` en todas las agregadas; intercambiar `pre` y `post` invierte el signo de cada `delta` (los `null` siguen `null`). Tablas con 1 a 7 grupos del catálogo, 3 bandas, conteos de 0 a 5 000 y celdas alrededor de `n_min`;
  - ejemplos a mano (`test_compare_examples.py`): `sexo` F 0,50 y M 0,60 en `pre`, F 0,50 y M 0,55 en `post`, celdas suficientes → `delta` de `sexo` = −0,0500; `PrePostReport` con los catálogos completos → ≤ 48 KiB, o `truncated = true` con agregadas, bandas y `delta` intactos (BLM §3);
  - toda respuesta de `GET /v1/disparity` y `POST /v1/source-comparisons` lleva `disclaimer = "mide y alerta, no certifica"` (los dos modelos de U0 con ese campo), y ningún texto de las cuatro respuestas pasa `contracts/tools/forbidden_phrases.py` con la lista única de U0 (BR-U0-94; US-307);
  - con un archivo de política de prueba en `VECTRA_POLICY_PATH` (umbral 7 pp, `n_min` 40, ventana 20 días, horario `"4,14,24,34,44,54 * * * *"`, W 2 h): `GET /v1/disparity` informa esos cinco valores y no los de producción; y el paquete de `GET /v1/freezes/{id}` también. El paquete sale de una corrida de `run` con esa misma política contra los dobles (el `freeze` llega al doble de U4 y el doble de U3 lo devuelve en `monitoring/freezes`), no de un paquete escrito a mano (BR-U9-13);
  - registro caído al arrancar → `/readyz` en 200 y `GET /v1/disparity` da 503 (NFR-U9-12);
  - `GET /metrics` en 8081 expone `vectra_http_request_duration_seconds` del servicio y las series de la caché, y ninguna etiqueta fuera de esta lista: `service`, `route_template`, `method`, `status`, `code`, `result`, `dependency`, `event` (las de U0 más `result` de la caché). Ninguna lleva `model_version_id`, `freeze_id`, `source_id` ni `principal_*` (NFR-U9-41);
  - una consulta servida desde la caché emite `disparity.viewed` con el `principal_subject` del que consulta, no el del que llenó la caché (NFR-U9-32);
  - 10 consultas concurrentes con la misma llave → una sola lectura del registro; un error no queda en la caché; la entrada 65 saca la menos usada; a los 15 min la entrada vence (reloj simulado);
  - `GET /v1/freezes/{id}` valida contra `FreezeRecord` de U0 (US-304); un id inexistente → 404;
  - `investigar` y luego `reactivar` (23:50 UTC del día D) → `resolution` = la `reactivar` y el dashboard de esa versión mide desde D + 1;
  - versión por omisión: con `version`, esa; sin `version`, la de las recomendaciones más recientes;
  - `compare_source` con un grupo fuera del catálogo → 422 `validation_error` (US-306); con una banda fuera del catálogo → 422;
  - un rol no permitido → 403 con `authz.denied` (`cro` en `GET /v1/freezes/{id}`; `analista` en `GET /v1/disparity`; un token sin `bias:compare` en `POST /v1/source-comparisons`);
  - PBT-U0-07 en modo strict (`VECTRA_LOG_STRICT=1`, como `tests/integration/test_run.py`) sobre `disparity.viewed` y `freeze_context.viewed`;
  - registro caído → 503 sin datos parciales, y el circuito abierto tras 20 llamadas (`vectra_circuit_state{dependency="registry"}` = 2 y sin llamada al doble).

- [ ] **CA-2** — Paso 9: el punto de entrada arranca con variables reales.
  ```bash
  uv run pytest bias-monitoring/tests/integration/test_entrypoint.py -v
  ```
  Esperado: código 0. La prueba levanta en `127.0.0.1` un doble HTTP real (no `MockTransport`) que sirve el JWKS y el endpoint de token de Keycloak y las dos rutas de U3, y escribe la llave del cliente y el archivo de política en un directorio temporal. Después lanza **`python -X importtime -m vectra_bias.app`** como subproceso, con las variables de `config_from_env` y nada más. Pasan:
  - `/healthz` y `/readyz` en 8081 responden 200 en ≤ 10 s;
  - `GET /v1/freezes` en 8080 con un token de `cumplimiento` firmado con la llave del JWKS doble → 200 con la lista del doble de U3; el doble de U3 recibió un token de `bias-monitoring-service` con `registry:read:monitoring`;
  - la salida de `-X importtime` no nombra `vectra_bias.freeze_client` ni `vectra_bias.run` (P-U9-05; además de import-linter);
  - con el doble de U3 apagado: `/readyz` sigue en 200 y la consulta da 503 (NFR-U9-12);
  - sin `VECTRA_REGISTRY_URL` → el proceso termina con código distinto de 0 y el mensaje nombra la variable; lo mismo con una política fuera de rango;
  - `SIGTERM` → el proceso termina en ≤ 10 s.

  **Rojo primero:** con el `app.py` vacío de hoy, `python -m vectra_bias.app` termina sin servir y `/healthz` nunca responde. Si 8080 u 8081 están ocupados en la máquina, la prueba falla con un mensaje claro (no se salta); regístralo. No agregues parámetros de puerto a U0.

- [ ] **CA-3** — Literales de U09-T02 y regresión del Bloque C.
  ```bash
  ! grep -nE '"/v1/|"(registry|governance|bias):' bias-monitoring/src/vectra_bias/*.py \
    && uv run pytest bias-monitoring/tests/integration/test_clients.py bias-monitoring/tests/integration/test_publish.py bias-monitoring/tests/integration/test_run.py -v
  ```
  Esperado: el `grep` no encuentra nada y las pruebas de U09-T02 pasan sin cambios en sus aserciones.

- [ ] **CA-4** — Imports y arquitectura (P-U9-04, P-U9-05).
  ```bash
  uv run lint-imports --config bias-monitoring/.importlinter && uv run pytest bias-monitoring/tests/unit/test_architecture.py -v
  ```
  Esperado: los cuatro contratos `KEPT`. La búsqueda estática de `test_architecture.py` (ningún `CellResult` con `rate` fuera de `vectra_disparity`) cubre también los módulos nuevos. **Rojo primero:** un `from vectra_bias import run` en `dashboard.py` rompe `servicio-no-congela`.

- [ ] **CA-5** — Paso 10: cobertura.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests --cov=vectra_bias --cov-branch --cov-fail-under=95 \
    && uv run coverage report --include='*/freeze_rule.py,*/context.py,*/window.py' --fail-under=100
  test -s aidlc-docs/construction/bias-monitoring/code/services.md
  ```
  Esperado: código 0 en los dos. `--cov=vectra_bias` reemplaza el `source` de `bias-monitoring/coveragerc` (que mide solo `vectra_disparity`). Cada módulo de `vectra_bias` queda ≥ 95 % (anota la tabla por módulo en la bitácora y en `services.md`). Los dos comandos quedan en el `check` del `Makefile`.

- [ ] **CA-6** — Paso 10: PBT-U9-01..08 con el perfil `ci` y la decisión sobre PBT-U9-05.
  ```bash
  make -C bias-monitoring property coverage
  grep -nE "NFR-U9-52" aidlc-docs/construction/bias-monitoring/code/services.md bias-monitoring/tests/property/test_run_machine.py bias-monitoring/Makefile
  ```
  Esperado: código 0 con la semilla impresa: PBT-U9-01..04, 06 y 08 con 500 ejemplos, PBT-U9-07 con 500 y PBT-U9-05 con 120 × 80. El `grep` da al menos una línea en cada uno de los tres archivos, y la de `services.md` está en la sección «PBT-U9-05 frente a NFR-U9-52» con la razón y la cita.

- [ ] **CA-7** — Trazabilidad.
  ```bash
  uv run python platform/tests/test_traceability.py --all
  ```
  Esperado: cumple la regla de `DECISIONES-LOOP.md` §6 con su enmienda. Corre en la base y en la rama. Ningún fallo nuevo es de los Pasos 9 y 10. NFR-U9-02, 12, 32 y 41, que hoy salen «sin trazabilidad», quedan trazados en archivos de `bias-monitoring/` que la prueba lee (`.py`, `.md`, `Makefile`…; **no** `.importlinter`, que no tiene sufijo). BR-U9-17, 18, 19, P-U9-03, 05, NFR-U9-33, 50 y 52 siguen trazados. **NFR-U9-51** sigue sin trazabilidad a propósito: está en «Fuera» con su cita (T3), como en U09-T01 (`CANDIDATAS.md`, «Loop, `DECISIONES-LOOP.md` §6 …»).

- [ ] **CA-8** — `check` de la unidad (RL-4).
  ```bash
  make -C bias-monitoring check
  ```
  Esperado: código 0, con `test_compare.py` en `property` y el objetivo de cobertura de `vectra_bias`. Si el diff toca `pyproject.toml` o `uv.lock`, corre además `make -C platform check` y debe dar 0.

- [ ] **CA-9** — Estado del plan.
  ```bash
  git diff origin/main -- aidlc-docs/construction/plans/bias-monitoring-code-generation-plan.md | grep -E "^\+- \[.\] \*\*Paso (9|10) "
  ```
  Esperado: Pasos 9 y 10 en `[x]` con `(U09-T03)`; el 10 con la nota de `mutmut`. Ningún otro cambio en el texto del plan.

---

## Plan de pruebas

Se escriben **en esta tarea**:
- `tests/property/test_compare.py` (PBT-U9-07) y `tests/unit/test_compare_examples.py`;
- `tests/integration/test_app.py`, `tests/integration/test_cache.py` y `tests/integration/test_entrypoint.py`;
- el doble HTTP real de U3 y de Keycloak para el subproceso, en `tests/doubles/`;
- los cambios de `tests/unit/test_architecture.py` si la búsqueda estática no cubre los módulos nuevos.

**Rojo primero**, con cada par falla-pasa en `bitacoras/U09-T03.md`:
- `create_app` sin el handler de `GET /v1/disparity` → `ContractViolation` (el rojo de P-1);
- `python -m vectra_bias.app` con el `app.py` vacío de hoy → CA-2 falla;
- `delta = pre − post` → el ejemplo a mano de −0,0500 falla (PBT-U9-07 sola no lo ve: el signo invertido también cumple sus dos invariantes);
- un recorte del `PrePostReport` que quita las agregadas → el ejemplo de 48 KiB falla;
- un grupo `"Bogota"` aceptado → el 422 de US-306 falla;
- `DisparityView` sin `disclaimer` → no valida contra U0 y la prueba falla;
- los parámetros de la política fijos en 5 pp → la prueba del archivo de política de prueba falla;
- readiness atada al registro → la prueba de NFR-U9-12 falla;
- la caché sin *single-flight* → 10 lecturas en vez de 1;
- la caché que guarda un error → la segunda consulta no vuelve a leer y la prueba falla;
- `disparity.viewed` solo en un fallo de caché → la prueba de NFR-U9-32 falla;
- `resolution` = la primera resolución → el caso `investigar` → `reactivar` falla;
- el dashboard sin `window` → la ventana no empieza en D + 1 y el caso falla;
- un import de `run` en un módulo del servicio → CA-2 (`-X importtime`) y CA-4 fallan;
- `model_version_id` como etiqueta de una métrica de la caché → la prueba de NFR-U9-41 falla.

---

## Notas

- **Puntos de detención** (detente y repórtalo; decide el usuario o el orquestador):
  - U0 no expresa algo que el Paso 9 necesita: un campo, un código de error o una forma de `create_app`. No cambies U0. (Que `FreezeSummary` y `FreezeRecord` no tengan `disclaimer` **no** es un punto de detención: el `disclaimer` va en los dos modelos que lo tienen, ver «Interpretaciones».)
  - `GET /v1/monitoring/freezes` de U3 no trae lo que `FreezeSummary` o el paquete necesitan;
  - falta un campo de log en `LOG_RECORD_FIELDS` para `disparity.viewed` o `freeze_context.viewed`;
  - el subproceso de CA-2 no puede usar 8080 y 8081 en esta máquina y no hay forma de liberarlos;
  - la cobertura de un módulo del Bloque C no llega al 95 % sin cambiar su comportamiento.
- **Interpretaciones de esta tarea** (anótalas en la bitácora; si el revisor no está de acuerdo, decide el usuario):
  - «toda respuesta lleva `disclaimer`» del plan se lee como en la BLM §3 («dashboard (US-307): toda respuesta lleva `disclaimer`»): va en `DisparityView` y en `PrePostReport`. `FreezeSummary` y `FreezeRecord` de U0 no tienen el campo y son `StrictModel`. El lint de frases prohibidas sí cubre las cuatro respuestas;
  - el dashboard aplica el inicio de ventana de BR-U9-08 («Cumplimiento reactivó con justificación y el dashboard lo muestra») y por eso lee también `monitoring/freezes`;
  - sin `window`, el dashboard usa `window_days` de la política;
  - `invalid_entries` del dashboard = la suma de `RangeTotals.invalid_entries` de los rangos de la consulta, sin `unattributable_range`;
  - la lista de etiquetas de métricas de CA-1: el diseño de U9 no tiene una allowlist propia (U7 sí, en P-U7-07); se toma la regla de U0 «sin identificadores en las etiquetas» (`vectra_common/metrics.py`).
- **Trazabilidad:** NFR-U9-02 se traza en `cache.py` (P-U9-03 lo satisface). Su medición con k6 sigue en el Paso 14 (T3), así que U09-T04 no debe poner NFR-U9-02 en «Diferido por la demo». Anótalo en `services.md`.
- **Para U09-T04:** el chart debe poner en el `Deployment` las variables de `config_from_env` y montar el `ConfigMap` en `config.POLICY_PATH`. Conviene que su criterio compare los nombres, como CA-2 de U04-T08. Anótalo en `services.md`.
- Archivos que se **modifican en su sitio**:
  - `bias-monitoring/src/vectra_bias/` (`app.py`, `dashboard.py`, `freezes.py`, `compare.py` y `cache.py`, hoy vacíos; `registry_client.py`, `freeze_client.py` y `run.py` solo por los literales);
  - `bias-monitoring/Makefile` y `bias-monitoring/tests/`;
  - el plan (solo las casillas y la nota del Paso 10) y `CANDIDATAS.md`.

  Archivo nuevo: `aidlc-docs/construction/bias-monitoring/code/services.md`. Nada de duplicados con sufijo.
- **Otros codificadores en paralelo:** no toques directorios de otras unidades.
- **Bitácora:** `bitacoras/U09-T03.md`, con:
  - la semilla de cada PBT;
  - los pares falla-pasa;
  - la cobertura de partida y la final, por módulo;
  - la llave de la caché sin versión y los nombres de las métricas de la caché;
  - las variables de entorno del servicio;
  - las interpretaciones de arriba;
  - el tiempo de `make -C bias-monitoring check`.
