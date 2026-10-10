# Plan de tareas (Code Generation Part 1) — U12 `system-verification`

**Este plan es la única fuente de verdad para generar el código de U12.**

> **Alcance del trabajo actual (instrucción del usuario, `aidlc-state.md`):** aquí se
> detiene U12. Code Generation Part 2 y Build and Test **no** se ejecutan. Las casillas
> quedan en `[ ]` para quien implemente.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U12 `system-verification`: herramientas de verificación que corren **fuera** del clúster (simulador, conductor de decisiones, escenarios RT y X, carga, demos e informe) |
| Historias (dueña) | US-609 |
| Verifica de extremo a extremo | US-101, 106, 109, 111, 303, 305, 603, 604 (mapa de domain-entities §4.2) y las demos de US-304, 503, 504 y 505 |
| Ubicación | `vectra-risk/system-verification/`; no hay Applications ni recursos en el clúster |
| Datos propios | Ninguno en el clúster; evidencias en el monorepo por PR |
| Depende de | U0 (`vectra_contracts`), U1 (suite de conectividad, binding K16, F07 desde fuera, F111), U2 (`channel-simulator`, `verification-reader`, usuarios sintéticos `analista-1`, `analista-2`, `ingeniero-1`, `cro-1`, `cumplimiento-1`), U3 (`x06-probe`, proyecciones `metrics` y `monitoring`), U5 (partición `test` y manifiesto adversarial), U7, U8 (Job de RT-5, BFF de casos, scripts k6), U9 (`x04-probe`), U10 (BFF y perfil de carga), U11 (métricas y dashboard) |

**Diseño de entrada:**
- Functional Design: `construction/system-verification/functional-design/` (BR-U12-01..13, PBT-U12-01..04, mapa historia → evidencias).
- NFR Requirements: `construction/system-verification/nfr-requirements/` (NFR-U12-01..50).
- NFR Design: SKIP.
- Infrastructure Design: `construction/system-verification/infrastructure-design/` (INF-U12-01..05).

**AUTONOMIA-01:** U12 no aplica nada al clúster. Las pruebas de sus componentes corren en CI con
dobles. La verificación real la ejecuta **un operador en kind** después de un PR aprobado
(Paso 18), y los cambios que necesita (Jobs de prueba, artefacto alterado, modelo proxy) entran
por PRs preparados y syncs manuales.

### Estructura de destino

```text
vectra-risk/system-verification/
|-- Makefile  pyproject.toml  .importlinter  Dockerfile
|-- src/vectra_verification/
|   |-- guard.py  credentials.py  evidence.py  manifest.py     # barrera, credenciales en memoria, filtro
|   |-- sampler.py  report.py  story_map.py  rt2_latency.py    # puros
|   |-- clients/   gateway.py  bff.py  registry.py  prom.py  loki.py  k8s_read.py
|   |-- simulator.py  driver.py
|   |-- scenarios/  rt1.py rt2.py rt3.py rt4.py rt5.py x_network.py x_behavior.py logs_pii.py case_size.py
|   |-- load/       capacity.py  run.py
|   `-- cli.py                                                   # secciones
|-- report/story-map.yaml
|-- demos/   journey-7-3.md  journey-7-4.md  rt-5.md  dashboard.md  verify/*.sh
|-- evidence/                                                    # una carpeta por verificación (PR)
`-- tests/   unit/ property/ integration/ doubles/ fixtures/
```

---

## 2. Pasos

### Bloque A — Estructura y barreras

- [ ] **Paso 1 — Esqueleto y prueba de comandos de `kubectl`**
  - Directorios de §1; `pyproject.toml` como miembro del workspace (depende de `vectra_contracts`; **no** de `vectra_common`).
  - import-linter: `sampler`, `report`, `story_map` y `rt2_latency` sin E/S.
  - Prueba estática: el código y los guiones solo invocan `kubectl` con `get`, `auth can-i`, `logs` y `port-forward`; cualquier `exec`, `apply`, `create`, `delete`, `patch`, `scale`, `edit` o `rollout` (y `argocd app sync`) → falla.
  - Diseño: NFR-U12-01, 43; INF-U12-02.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config system-verification/.importlinter`; `uv run pytest system-verification/tests/unit/test_kubectl_verbs.py` (un fixture con `kubectl apply` → falla).

- [ ] **Paso 2 — Barrera de entorno, credenciales y filtro de evidencias**
  - `guard`: lista de `issuer` y hosts de kind y staging; secciones permitidas por entorno (staging: `decisions` ≤ 100, lectura de `u11`, `report`); `decisions` no empieza después de las 23:00 UTC.
  - `credentials`: lee del Vault de kind (o la bóveda de staging) con la sesión del operador, en las rutas que usa ESO, la llave de `channel-simulator` y de `verification-reader` y las contraseñas y semillas TOTP de los usuarios sintéticos; solo en memoria; TOTP con `pyotp`.
  - `evidence`: filtro que quita `Authorization`, tokens, cookies y semillas; falla si una salida contiene un JWT o una semilla.
  - Diseño: NFR-U12-03, 04, 05, 32; INF-U12-01.
  - **Aceptación**: `uv run pytest system-verification/tests/unit/test_guard.py test_credentials.py test_evidence_filter.py`: `issuer` o host de producción simulados → error y cero solicitudes; `rt2` en staging → se niega; `decisions` a las 22:30 UTC con reloj simulado → se niega; ningún archivo escrito con credenciales; evidencia con un JWT → la generación falla.

### Bloque B — Lógica pura

- [ ] **Paso 3 — `sampler`, `rt2_latency`, `story_map` y `report`**
  - `sampler`: muestra `normal` y `stratified` (≥ 30 por celda en `region` × `estrato`), determinista con semilla; informa las celdas que no alcanzan.
  - `rt2_latency`: inicio = menor `recorded_at` de las `recommendation` del lote; fin = `recorded_at` del `freeze`; `passed` ≤ 1 800 s.
  - `story_map`: carga `report/story-map.yaml` y falla ante una historia sin fila o una evidencia desconocida.
  - `report`: `VerificationReport` desde las evidencias y el manifiesto (sin evidencia o con hash distinto → `no ejecutado`; `expected ≠ obtained` → `falla`; historias según el mapa); encabezado con el límite del manifiesto (NFR-U12-21).
  - Diseño: BR-U12-01, 06, 07, 11, 13; domain-entities §3, §4; NFR-U12-11, 20, 21.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests/property/test_sampler.py tests/property/test_report.py tests/property/test_rt2_latency.py tests/unit/test_story_map.py`: PBT-U12-01, 02 y 04; las pruebas de ejemplo de business-logic-model §3 del informe y de la latencia.

- [ ] **Paso 4 — Resumen de la lógica pura**
  - Cobertura de ramas **100 %** en `report` y `sampler`; `mutmut` en `report`.
  - Resumen en `aidlc-docs/construction/system-verification/code/logic.md`.
  - **Aceptación**: `uv run pytest system-verification/tests/unit system-verification/tests/property --cov=vectra_verification.report --cov=vectra_verification.sampler --cov-branch --cov-fail-under=100`; `uv run mutmut run --paths-to-mutate system-verification/src/vectra_verification/report.py`.

### Bloque C — Clientes, simulador y conductor

- [ ] **Paso 5 — Clientes de lectura y del gateway**
  - `gateway` y `bff`: `httpx` con la cabecera de escenario de U8 y un `traceparent` con el prefijo de la corrida.
  - **Login y step-up sin navegador visible** (revisión del plan de tareas de U12, 2026-10-10): el BFF no hace el flujo OIDC, lo hace el cliente público `vectra-console` (U2), y Keycloak solo ofrece Authorization Code + PKCE (sin *password grant*). La herramienta actúa como ese cliente:
    1. genera `state`, `nonce` y `code_verifier`;
    2. abre la URL de autorización (`prompt=login`, `max_age=0`, `acr_values=mfa` para el step-up) en **Chromium sin interfaz con Playwright**, que llena el formulario de Keycloak con la contraseña y el código TOTP calculado con `pyotp`;
    3. intercepta la navegación al `redirect_uri` registrado (`/callback` o `/stepup-callback`) **antes** de cargar la SPA, y toma de la URL `code` y `state`;
    4. valida que `state` coincida, canjea `code` con el `code_verifier` en el endpoint de token y valida el `nonce` y `acr = mfa` del ID token.

    Los tokens solo quedan en memoria; el contexto de Playwright se descarta tras cada login. El mismo mecanismo sirve para el login normal de los analistas y para el step-up de `cumplimiento-1` en la reactivación de RT-2.
  - **Aceptación del login**: `uv run pytest system-verification/tests/integration/test_oidc_headless.py` contra un Keycloak de Testcontainers con el realm de kind: login de `analista-1` → token con su rol; step-up de `cumplimiento-1` → `acr = mfa` y `auth_time` reciente; un `state` alterado → error sin canje; ningún token ni contraseña en disco.
  - `registry`: por `kubectl port-forward` a `decision-registry-service`, con el token de `verification-reader` (`registry:read:metrics` y `registry:read:monitoring`).
  - `prom` y `loki`: por `port-forward`, sus APIs de lectura.
  - `k8s_read`: envoltorio de `kubectl get`, `logs`, `auth can-i` y `port-forward` (lo único que el Paso 1 admite).
  - Diseño: INF-U12-03; NFR-U12-50.
  - **Aceptación**: `uv run pytest system-verification/tests/integration/test_clients.py` con dobles (cada solicitud lleva la cabecera y el prefijo; el cliente del registro manda el token de `verification-reader`; un `port-forward` caído → error claro, sin reintento silencioso).

- [ ] **Paso 6 — Simulador y conductor de decisiones**
  - `simulator`: escenarios `normal`, `stratified`, `rt1`, `rt4` desde U5 (partición `test` y manifiesto adversarial), con `generator_version` y `seed` registrados; una `Idempotency-Key` por solicitud; ritmo ≤ 30/s; `RunReport` sin datos del solicitante.
  - `driver`: `analista-1` y `analista-2` por el BFF; `DecisionMix` con semilla; 409 y 422 contados, sin reintentar con otro contenido.
  - Diseño: BR-U12-01..03; NFR-U12-10.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests/property/test_driver_mix.py tests/integration/test_simulator.py tests/integration/test_driver.py` (dobles del gateway y del BFF): PBT-U12-03; el simulador nunca supera 30/s; claves distintas; el `RunReport` sin identificadores; el conductor ante un 409 `decision_already_recorded` sigue con el caso siguiente.

### Bloque D — Escenarios y mediciones

- [ ] **Paso 7 — RT-1 y RT-4**
  - RT-1: por cada par de U5, por el BFF con `analista-1`: `free_text` del detalle igual byte a byte; recomendación y narrativa iguales a las del par; sin llamadas distintas de scoring y explainability.
  - RT-4: los 18 casos; `confidence` bajo el umbral, `revision_requerida` y `baja_confianza`.
  - Diseño: BR-U12-04; INF-U12-03.
  - **Aceptación**: `uv run pytest system-verification/tests/unit/test_oracles_rt1_rt4.py`: los oráculos contra respuestas correctas → `pasa` e incorrectas (narrativa distinta, `free_text` alterado, confianza alta) → `falla` (NFR-U12-42).

- [ ] **Paso 8 — RT-2, RT-3 y RT-5**
  - RT-3: tras cada sync del paquete alterado, solo `FailClosed(version_mismatch)`; cero `recommendation` en la ventana (proyección `metrics`); casos `en_sincronizacion`.
  - RT-2: tras el sync del modelo proxy, lote `stratified` (la sección se niega si una celda no alcanza 30); espera la entrada `freeze`; los casos nuevos `modelo_congelado`; sigue congelada tras 3 corridas más; reactivación por `cumplimiento-1` con MFA por el BFF; 5 corridas con `rt2_latency`.
  - **Paquete completo** (revisión del plan de tareas de U12, 2026-10-10; BR-U12-04 y Paso 16 de U9): el oráculo lee la entrada `freeze` por la proyección `monitoring_freezes` (`verification-reader`) y exige un `context_package` válido según `FreezeContext` de U0 §9.4 (`before`, `after`, `last_7_days`, `trigger_attribute`, `implicated`, `affected_volume`, `threshold_pp`, `n_min`), y además `data_sources` e `initial_disparity` presentes y no vacíos (los agrega governance, BR-U9-16). Un paquete al que le falta cualquiera → `falla`.
  - RT-5: lee el Job de U8 y `kubectl auth can-i` de las tres identidades; `CoreWriteAttempt` en Prometheus y `vectra_core_write_attempts_total` en 0.
  - Diseño: BR-U12-04, 07; NFR-U12-11.
  - **Aceptación**: `uv run pytest system-verification/tests/unit/test_oracles_rt2_rt3_rt5.py` (una sola `recommendation` en RT-3 → `falla`; una corrida de RT-2 de 31 min → `falla` con la medición registrada; un `freeze` sin `data_sources` o sin `initial_disparity`, o con un `FreezeContext` incompleto → `falla`; `auth can-i` = yes → `falla`; revisión del plan de tareas de U12, 2026-10-10).

- [ ] **Paso 9 — X01–X10**
  - Red: toma la salida de la suite de conectividad de U1 (X01, X02, X05, X07, X08, X09) como evidencia.
  - Comportamiento: X03 (`ingeniero-1` y `cro-1` intentan `resolve_frozen` → 403); X04 y X06 desde los Jobs `x04-probe` y `x06-probe`, que solo cuentan con el `runId` del manifiesto y un `completionTime` posterior al `started_at` que fijó la sección `prepare` (Paso 13), **antes** del PR de los Jobs (revisión del plan de tareas de U12, 2026-10-10); X10 (`/auth/admin` → 404).
  - Diseño: BR-U12-05; INF-U12-02.
  - **Aceptación**: `uv run pytest system-verification/tests/unit/test_oracles_x.py` (un Job de otro `runId` o con `completionTime` anterior → `no ejecutado`; un 200 en X03 → `falla`; un 200 en X10 → `falla`).

- [ ] **Paso 10 — `SIM-NORMAL`, `LOGS-NO-PII` y `CASE-SIZE`**
  - `SIM-NORMAL`: `accepted = sent`, un caso por solicitud y cada uno en `listo` o en un fail-closed documentado.
  - `LOGS-NO-PII`: consulta de Loki sobre el periodo por los `SYN-…` y los nombres de U5 enviados → 0 resultados.
  - `CASE-SIZE`: crecimiento de `case-db` y del registro por caso con los primeros 1 000 casos (series de Prometheus de U1 y U8).
  - Diseño: BR-U12-06, 12; domain-entities §4.1.
  - **Aceptación**: `uv run pytest system-verification/tests/unit/test_oracles_measurements.py` (un `SYN-` encontrado → `falla`; `accepted < sent` → `falla`).

- [ ] **Paso 11 — Carga (US-609)**
  - `capacity`: asignable de los 4 workers frente a la suma de máximos de los HPA (`vectra-app`, `vectra-edge`, `vectra-serving`) y de KServe, y CPU y memoria libres del host; si no alcanza, `scale = 0,5` y se registra.
  - `run`: línea base a 5/s; después 20/s + 200 usuarios durante 30 min con los scripts k6 de U7, U8 y U10 en un contenedor de 2 CPU y 2 GiB; HPA muestreados cada 30 s (lectura); p95 contra NFR-U7-01..03, NFR-U8-01 y NFR-U10-01; tasa de fail-closed frente a la línea base.
  - Diseño: BR-U12-08; INF-U12-05.
  - **Aceptación**: `uv run pytest system-verification/tests/unit/test_capacity.py test_load_oracle.py` (capacidad insuficiente → `scale = 0,5` y la nota en la evidencia; una réplica sobre el máximo → `falla`; fail-closed sobre la línea base → `falla`); `k6 inspect` de cada script.

### Bloque E — Demos, informe y CLI

- [ ] **Paso 12 — Demos**
  - Guiones `journey-7-3.md`, `journey-7-4.md`, `rt-5.md` y `dashboard.md` con los pasos del presentador, las lecturas y las llamadas a la API, y un `verify/<demo>.sh` por demo que comprueba cada paso.
  - Los cambios al clúster (artefacto alterado, modelo proxy, Jobs de prueba) son PRs preparados en `demos/prs/`, que el operador sincroniza antes.
  - Diseño: BR-U12-09.
  - **Aceptación**: la prueba del Paso 1 sobre `demos/`; `shellcheck system-verification/demos/verify/*.sh`.

- [ ] **Paso 13 — CLI por secciones, manifiesto y `CODEOWNERS`**
  - `cli`: secciones `prepare`, `network`, `decisions`, `rt1`, `rt4`, `rt5`, `rt3`, `rt2`, `load`, `pii`, `u11`, `report`, en el orden de business-logic-model §2.1, con retoma desde una sección y evidencia al terminar cada una.
  - **`prepare`** (revisión del plan de tareas de U12, 2026-10-10): primera sección, **antes** del PR de los Jobs de prueba. Genera el `runId` de la verificación, escribe el manifiesto inicial con ese `runId` y `started_at = ahora`, y produce el parche de values de kind (`probes.runId`, y el de U8 para RT-5) que el operador usa en el PR. Así los Jobs de prueba terminan **después** de `started_at`, y el oráculo de X04 y X06 (Paso 9) puede aceptarlos. Sin `prepare`, las demás secciones se niegan a correr.
  - `manifest`: `manifest.json` con SHA-256 por archivo, `runId` de los Jobs de prueba, `started_at`, semillas, `generator_version`, digests (leídos del clúster) y tamaño de `test`; tope de 50 MB.
  - `CODEOWNERS` del monorepo: `system-verification/evidence/` para los equipos `calidad` y `cumplimiento` (crearlos si no existen).
  - Diseño: NFR-U12-10, 20, 30; INF-U12-04.
  - **Aceptación**: `uv run pytest system-verification/tests/integration/test_cli.py` (interrumpir en `rt3` y retomar → no se repiten las anteriores; manifiesto con todos los campos; > 50 MB → resumen y hash; `network` sin `prepare` → se niega; `prepare` → manifiesto con `runId` y `started_at` y el parche de values con ese `runId`; revisión del plan de tareas de U12, 2026-10-10); un PR de fixture que toca solo `system-verification/evidence/` pide la aprobación de *code owners* (prueba de `branch-protection-check` de U4).

### Bloque F — Imagen, CI y documentación

- [ ] **Paso 14 — Repositorio, migraciones, frontend y despliegue en el clúster: N/A**
  - U12 no tiene base de datos, interfaz ni recursos de Kubernetes.
  - **Aceptación**: `test ! -d system-verification/chart && test ! -d system-verification/migrations`; la imagen no contiene manifiestos de Kubernetes.

- [ ] **Paso 15 — Imagen**
  - Python oficial por digest, sin privilegios; incluye `kubectl`, `k6`, Playwright y su Chromium por versión fijada (el Chromium sin interfaz del login del Paso 5); construida, escaneada, con SBOM y firmada por `supply-chain.yml` de U1.
  - Diseño: INF-U12-01.
  - **Aceptación**: `hadolint system-verification/Dockerfile`; el SBOM lista `kubectl`, `k6`, Playwright y Chromium con su versión.

- [ ] **Paso 16 — Workflow de CI**
  - `.github/workflows/system-verification.yml`, en cada PR que toca `system-verification/`: `uv sync --frozen`, ruff, mypy, import-linter, pruebas con perfil `ci` y semilla impresa, cobertura, prueba de verbos de `kubectl`, `shellcheck`; perfil `nightly` y `mutmut` en el nocturno.
  - **AUTONOMIA-01**: ningún paso ejecuta la verificación contra un clúster.
  - **Aceptación**: `actionlint .github/workflows/system-verification.yml`; `! grep -E "kubectl|helm (install|upgrade)|terraform apply|argocd" .github/workflows/system-verification.yml`.

- [ ] **Paso 17 — Documentación y trazabilidad**
  - `system-verification/README.md`: cómo ejecutar cada sección, requisitos (K16, PRs preparados, `runId` de los Jobs), presupuesto de tiempo (con las esperas de PRs aparte), cómo leer el informe y su límite.
  - Trazabilidad de cada BR-U12 a una prueba.
  - **Aceptación**: `test -s system-verification/README.md`; `uv run python platform/tests/test_traceability.py --unit system-verification --all`.

### Bloque G — Verificación en kind (con aprobación humana)

- [ ] **Paso 18 — Primera verificación completa en kind**
  - **Requisito previo**: un PR con los Pasos 1–17 aprobado por un humano, con U1–U11 instalados en kind, el modelo de referencia activo y el binding K16 presente.
  - **Orden** (revisión del plan de tareas de U12, 2026-10-10):
    1. el operador ejecuta `prepare`, que fija el `runId` y el `started_at`;
    2. abre el PR de los Jobs de prueba con el parche que produjo `prepare` y lo sincroniza (con prune);
    3. ejecuta las demás secciones en orden, empezando por `network`, que lee los Jobs ya terminados (con `completionTime` posterior a `started_at`).
  - El operador ejecuta todas las secciones en orden, con los PRs preparados de RT-3 y RT-2 y sus reversiones, y el día siguiente la sección `u11`; genera el informe y abre el PR de verificación.
  - Diseño: BR-U12-04..13; NFR-U12-30, 31; INF-U12-01..05. Historias: US-609 y las de domain-entities §4.2.
  - **Aceptación**: el PR de verificación con `evidence/<fecha>-<commit>/`, `manifest.json` y `verification-report.md`, revisado por `calidad` y `cumplimiento`; el informe lista cada RT, X, demo e historia con su resultado y no marca `pasa` sin evidencia.

### Bloque H — Cierre

- [ ] **Paso 19 — Cierre de la unidad**
  - **Aceptación**: `make -C system-verification check`, que corre en orden las verificaciones estáticas, las propiedades y las pruebas con dobles de los Pasos 1–17 y termina en 0. La verificación en kind (Paso 18) se revisa como el PR de verificación.

---

## 3. Trazabilidad

| Historia o elemento | Pasos |
|---|---|
| US-609 (dueña) | 11, 18 |
| US-101 (`SIM-NORMAL`) | 6, 10, 18 |
| US-106 (RT-4), US-109 (RT-1) | 7, 18 |
| US-111 (RT-3, `journey-7-3`), US-303 (RT-2, `RT2-LATENCY`, `journey-7-4`), US-305 (`journey-7-4`, X03) | 8, 9, 12, 18 |
| US-603 (RT-5, X01, `rt-5`), US-604 (X02, `LOGS-NO-PII`) | 8, 9, 10, 12, 18 |
| Demos US-304, 503, 504, 505 | 12, 18 |

| Diseño | Pasos |
|---|---|
| BR-U12-01..03 | 6 |
| BR-U12-04, 05, 07 | 7, 8, 9 |
| BR-U12-06, 12 | 10 |
| BR-U12-08 | 11 |
| BR-U12-09 | 12 |
| BR-U12-10 | 2 |
| BR-U12-11, 13 | 3, 13 |
| BR-U12-04 (paquete completo de RT-2) | 8 |
| NFR-U12-01..50 | 1–3, 5, 6, 8, 11, 13, 15, 16 |
| INF-U12-01..05 | 2, 5, 9, 11, 13, 15 |

| Propiedad | Pasos |
|---|---|
| PBT-U12-01, 02, 04 | 3 |
| PBT-U12-03 | 6 |

## 4. Cumplimiento de extensiones (plan de tareas U12)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | Sin recursos de U12 en el clúster; `kubectl` sin escritura (Paso 1); la verificación la ejecuta el operador (Paso 18) |
| AUTONOMIA-02 | Cumple | Oráculos probados contra respuestas incorrectas (Pasos 7–11); informe que no marca `pasa` sin evidencia (Paso 3) |
| AUTONOMIA-03 | Cumple | RT-5, X01, X04, X06 (Pasos 8, 9) |
| SECURITY-03 / 11 / 12 | Cumple | Pasos 2, 6, 10 |
| RESILIENCY-09 | Cumple | Paso 11 |
| PBT-01..10 | Cumple | PBT-U12-01..04 (Pasos 3, 6), perfiles `ci` y `nightly` (Paso 16) y pruebas de ejemplo (Pasos 3, 6–11) |
