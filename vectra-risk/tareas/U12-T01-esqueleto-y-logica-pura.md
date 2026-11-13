# U12-T01 — Esqueleto, barreras y lógica pura de `system-verification`

**Unidad:** U12 `system-verification`
**Historias que implementa:** ninguna propia. La trazabilidad del plan (§3) no asigna historias a los Pasos 1 a 4. El Paso 3 escribe el generador del informe y el mapa historia → evidencias que usan US-609 y las historias de domain-entities §4.2.
**Depende de** (comprobado al redactar, sobre `origin/main` `abd1cf8`):
- **U0, tipos:** `contracts/python/vectra_contracts` (`pydantic==2.14.2`). `models/registry.py`: `MetricsProjection` (línea 371) y `FreezeProjection` (línea 397, con `recorded_at`). `labels.py`: `derive_monitoring_labels` (línea 63), `age_range`, `region_of` y `payment_band`. `models/features.py`: `MonitoringLabels` (línea 46: `sexo`, `rango_edad`, `region`, `estrato`, `banda_capacidad_pago`). `models/base.py`: `Timestamp` (línea 43, UTC obligatorio).
- **Workspace de `uv`:** `pyproject.toml` raíz, con `[tool.uv.workspace]` (línea 11), `[tool.uv.sources]` (línea 14), el grupo `dev` (línea 30) y `[tool.ruff.lint.per-file-ignores]` (línea 109). El grupo `dev` ya trae `hypothesis==6.170.14`, `mutmut==3.8.1`, `import-linter==2.15`, `pyyaml==6.0.3`, `pyotp==2.10.0` y `httpx==0.28.1`. `hvac` **no** está en `uv.lock`.
- **Ejemplo de miembro del workspace:** `product-metrics/` (`Makefile`, `pyproject.toml`, `.importlinter`, `pytest.ini`, `coveragerc`, `tests/conftest.py`).
- **U1, pruebas:** `platform/tests/test_traceability.py` y `platform/tests/test_links.py`. `platform/tests/test_unit_plans.py` (línea 13) exige que el plan de U12 conserve su sección de reglas de admisión: no la borres.
- **U2, entornos:** `identity-edge/gateway/values/kind.yaml`, `staging.yaml` y `prod.yaml` (línea 2 de cada uno): `vectra.localtest.me`, `vectra.staging.banco.internal` y `vectra.banco.internal`. El `issuer` es `https://<host>/auth/realms/vectra` (`identity-edge/gateway/generated/<env>/securitypolicies.yaml`, línea 39).
- **U1 y U2, rutas de la bóveda:** `platform/kind/vault_paths.py` (`uv run python platform/kind/vault_paths.py list`): `identity/clients/channel-simulator` e `identity/clients/verification-reader` (propiedades `private-key` y `jwks`), e `identity/synthetic-users` (propiedades `SYNTH_<USUARIO>_PASSWORD` y `SYNTH_<USUARIO>_TOTP_SEED`). KV v2: montaje `secret` en kind y `vectra` en staging (`platform/secrets/cluster-secret-store-kind.yaml` y `cluster-secret-store-staging.yaml`, línea 7).
- **U9, celdas:** `bias-monitoring/disparity/src/vectra_disparity/counts.py` (líneas 14 y 15): `ATTRIBUTES = ("sexo", "rango_edad", "region", "estrato")` y `BANDS = ("lt_20", "20_30", "gt_30")`.
- **U5, muestreo de referencia:** `reference-model/tests/simulation/test_r4_freeze_rate.py`, `stratified_sample` (línea 50). Con ese procedimiento se midió que la variante proxy congela.
- **`.github/CODEOWNERS`** (línea 9) ya tiene `vectra-risk/system-verification/evidence/`. No se toca.
- **No existen** en `main`: `vectra-risk/system-verification/` ni `aidlc-docs/construction/system-verification/code/`. Esta tarea los crea.

Es código estático, lógica pura y pruebas sin clúster ni contenedores (RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6). No necesita ninguna otra unidad desplegada.
**Rama:** `tarea/U12-T01`, desde `origin/main`.

Bloques A y B del plan de U12 (`aidlc-docs/construction/plans/system-verification-code-generation-plan.md`, Pasos 1 a 4), juntos en una tarea según `aidlc-docs/construction/plans/demo-recorte-funcional.md` §4 (fila U12: «A+B (1–4) · C (5–6) · D (8, 10) · E+F (12, 13, 15, 17) · G+H (18–19)») y §8 (U12: 5 tareas, sin cambio). Es la primera de cinco. La enmienda rige donde difiera del alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 1 Esqueleto y prueba de comandos de `kubectl` | **E** | Completo | Enmienda §3 U12, fila «1 · 2: E, E, —»; alcance §3 U12, fila «1 Esqueleto · 2 Barrera de entorno y credenciales: E» |
| 2 Barrera de entorno, credenciales y filtro de evidencias | **E** | Completo | Las mismas dos filas |
| 3 `sampler`, `rt2_latency`, `story_map` y `report` | **E** | Completo, con PBT-U12-01, 02 y 04 | Enmienda §3 U12, fila «3: E, E, `sampler`, `rt2_latency`, `story_map` y `report` (PBT-U12-01, 02, 04)» |
| 4 Resumen de la lógica pura | **E\*F** | Entran la cobertura y el resumen. Se difiere `mutmut` | Enmienda §3 U12, fila «4: E, E\*F, Sin `mutmut` (T3)»; §2 regla 3 («… y U12 Paso 4») |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda del 2026-11-09. **Las PBT no se recortan** (enmienda §5.2: «U12: PBT-U12-01..04»).

Lo que U12 hace en las demos (enmienda §1) y lo que esta tarea aporta:
- **Flujo base y D4:** el `simulator` envía 2 000 casos `normal` y el `driver` los decide. Aquí se escribe `sampler.normal` y la barrera horaria de `decisions`.
- **D2 (RT-2):** lote `stratified` de ≈ 1 500 casos con ≥ 30 por celda, y `rt2_latency` ≤ 1 800 s. Aquí se escriben `sampler.stratified` y `rt2_latency`.
- **D1 y D3:** oráculos de RT-3 y RT-5 (U12-T03). Aquí solo el tipo `Evidence` y el informe que los lista.
- **Todas:** `guard`, `credentials`, el filtro de evidencias y el informe que nunca marca `pasa` sin evidencia.

---

## Alcance

**Dentro:** los Pasos 1 a 4 del plan. Texto del plan, sin recortes salvo el `mutmut` del Paso 4, que va ~~tachado~~ con su cita y en «Fuera»:

### Bloque A — Estructura y barreras

- [ ] **Paso 1 — Esqueleto y prueba de comandos de `kubectl`**
  - Directorios de §1; `pyproject.toml` como miembro del workspace (depende de `vectra_contracts`; **no** de `vectra_common`).
  - import-linter: `sampler`, `report`, `story_map` y `rt2_latency` sin E/S.
  - Prueba estática: el código y los guiones solo invocan `kubectl` con `get`, `auth can-i`, `logs` y `port-forward`; cualquier `exec`, `apply`, `create`, `delete`, `patch`, `scale`, `edit` o `rollout` (y `argocd app sync`) → falla.
  - Diseño: NFR-U12-01, 43; INF-U12-02.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config system-verification/.importlinter`; `uv run pytest system-verification/tests/unit/test_kubectl_verbs.py` (un fixture con `kubectl apply` → falla).

- [ ] **Paso 2 — Barrera de entorno, credenciales y filtro de evidencias**
  - `guard`: lista de `issuer` y hosts de kind y staging; secciones permitidas por entorno (staging: `prepare`, sin parche de Jobs; seguimiento de la quinta revisión de coherencia, 2026-10-31; `decisions` ≤ 100, lectura de `u11`, `report`); `decisions` no empieza después de las 23:00 UTC.
  - `credentials`: lee del Vault de kind (o la bóveda de staging) con la sesión del operador, en las rutas que usa ESO, la llave de `channel-simulator` y de `verification-reader` y las contraseñas y semillas TOTP de los usuarios sintéticos, salvo las de `cumplimiento-*` fuera de kind (excepción de FR-BIA-05; seguimiento de la cuarta revisión de coherencia, 2026-10-31); solo en memoria; TOTP con `pyotp`.
  - `evidence`: filtro que quita `Authorization`, tokens, cookies y semillas; falla si una salida contiene un JWT o una semilla.
  - Diseño: NFR-U12-03, 04, 05, 32; INF-U12-01.
  - **Aceptación**: `uv run pytest system-verification/tests/unit/test_guard.py test_credentials.py test_evidence_filter.py`: `issuer` o host de producción simulados → error y cero solicitudes; `rt2` en staging → se niega; en staging, pedir la semilla de `cumplimiento-1` → error sin leer la bóveda, y una reactivación desde la herramienta fuera de la sección `rt2` → error (seguimiento de la cuarta revisión de coherencia, 2026-10-31); `decisions` a las 22:30 UTC con reloj simulado → se niega; ningún archivo escrito con credenciales; evidencia con un JWT → la generación falla.

### Bloque B — Lógica pura

- [ ] **Paso 3 — `sampler`, `rt2_latency`, `story_map` y `report`**
  - `sampler`: muestra `normal` y `stratified` (≥ 30 por celda de U9: atributo, grupo y banda), determinista con semilla; informa las celdas que no alcanzan.
  - `rt2_latency`: inicio = menor `recorded_at` de las `recommendation` del lote; fin = `recorded_at` del `freeze`; `passed` ≤ 1 800 s.
  - `story_map`: carga `report/story-map.yaml` y falla ante una historia sin fila o una evidencia desconocida.
  - `report`: `VerificationReport` desde las evidencias y el manifiesto (sin evidencia o con hash distinto → `no ejecutado`; `expected ≠ obtained` → `falla`; historias según el mapa); encabezado con el límite del manifiesto (NFR-U12-21).
  - Diseño: BR-U12-01, 06, 07, 11, 13; domain-entities §3, §4; NFR-U12-11, 20, 21.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests/property/test_sampler.py tests/property/test_report.py tests/property/test_rt2_latency.py tests/unit/test_story_map.py`: PBT-U12-01, 02 y 04; las pruebas de ejemplo de business-logic-model §3 del informe y de la latencia.

- [ ] **Paso 4 — Resumen de la lógica pura** (E\*F)
  - Cobertura de ramas **100 %** en `report` y `sampler`; ~~`mutmut` en `report`.~~ **(diferido por la demo, T3: enmienda §3 U12, fila «4»; ver «Fuera»)**
  - Cobertura de ramas **≥ 85 %** en el resto del paquete (NFR-U12-40): se comprueba en el Paso 16, cuando existen los clientes y los escenarios (pendientes posteriores al cierre, 2026-10-10). **(No es de esta tarea. El Paso 16 está en D: alcance §3 U12, fila «16 Workflow de CI: D, T4»; ver «Notas», aviso 6.)**
  - Resumen en `aidlc-docs/construction/system-verification/code/logic.md`.
  - **Aceptación**: `uv run pytest system-verification/tests/unit system-verification/tests/property --cov=vectra_verification.report --cov=vectra_verification.sampler --cov-branch --cov-fail-under=100`; ~~`uv run mutmut run --paths-to-mutate system-verification/src/vectra_verification/report.py`.~~ (diferido, T3)

### Estructura de destino (§1 del plan): lo que esta tarea crea

```text
vectra-risk/system-verification/
|-- Makefile  pyproject.toml  .importlinter      # nuevos (Paso 1)
|-- pytest.ini  coveragerc                       # nuevos: no están en §1; sin ellos pytest usa la configuración de U0
|-- src/vectra_verification/
|   |-- __init__.py
|   |-- guard.py  credentials.py  evidence.py    # Paso 2
|   |-- sampler.py  report.py  story_map.py  rt2_latency.py   # Paso 3, puros
|   |-- manifest.py  simulator.py  driver.py  cli.py          # vacíos, con docstring (Pasos 6 y 13)
|   |-- clients/__init__.py                      # paquete vacío (Paso 5)
|   |-- scenarios/__init__.py                    # paquete vacío (Pasos 8 y 10)
|   `-- load/__init__.py                         # paquete vacío (Paso 11, diferido)
|-- report/story-map.yaml                        # Paso 3, con el mapa de domain-entities §4.2
|-- demos/.gitkeep  demos/verify/.gitkeep        # vacíos (Paso 12)
|-- evidence/.gitkeep                            # vacío (Paso 18)
`-- tests/
    |-- conftest.py                              # perfiles de Hypothesis y semilla impresa
    |-- unit/  test_kubectl_verbs.py  test_guard.py  test_credentials.py  test_evidence_filter.py  test_story_map.py
    |-- property/  test_sampler.py  test_report.py  test_rt2_latency.py
    |-- integration/.gitkeep
    |-- doubles/                                 # doble de la API KV v2 de la bóveda
    `-- fixtures/                                # fixtures de `kubectl`, de `story-map.yaml` y de evidencias

vectra-risk/aidlc-docs/construction/system-verification/code/logic.md   # nuevo (Paso 4)
```

**No** se crean: `Dockerfile` (Paso 15), los módulos de `clients/`, `scenarios/` y `load/`, los guiones de `demos/`, `README.md` (Paso 17), `chart/` ni `migrations/` (el Paso 14 exige que no existan).

### Cambios permitidos fuera de `system-verification/`

Uno por uno. Cualquier otro archivo fuera del directorio es un hallazgo.

1. `pyproject.toml` raíz:
   - `"system-verification"` en `[tool.uv.workspace].members`;
   - `vectra-verification = { workspace = true }` en `[tool.uv.sources]`;
   - `"vectra-verification"` en el grupo `dev`, con su comentario `# U12-T01: …`, como U11;
   - `"system-verification/tests/**" = ["S", "B", "BLE", "T20", "I001"]` en `[tool.ruff.lint.per-file-ignores]`, como las demás unidades;
   - un `[[tool.mypy.overrides]]` solo si un tercero no trae tipos; anótalo en la bitácora.
2. `uv.lock`, regenerado con `uv lock`. Solo debe ganar el miembro nuevo: todas sus dependencias ya están en el lock.
3. `aidlc-docs/construction/plans/system-verification-code-generation-plan.md`: solo las casillas de los Pasos 1 a 4.
4. `aidlc-docs/construction/system-verification/code/logic.md`: nuevo.
5. `CANDIDATAS.md`: las candidatas nuevas de «Notas».
6. `bitacoras/U12-T01.md`: nuevo.

### Precisiones

- **Paquete.** Distribución `vectra-verification`, paquete `vectra_verification` en `system-verification/src/`. Dependencias de `system-verification/pyproject.toml`: `vectra-contracts`, `httpx==0.28.1`, `pyotp==2.10.0` y `pyyaml==6.0.3`, con las versiones que ya fija el lock. **No** `vectra-common` (Paso 1; tech-stack: «`httpx` propio»). `playwright` lo agrega U12-T02 (Paso 5).
- **Paquetes de prueba sin colisión** (`CANDIDATAS.md`, «Todas las unidades, paquetes de prueba», F-06 de U07-T03): sin `__init__.py` en `tests/` ni en sus subcarpetas; `--import-mode=importlib` en `system-verification/pytest.ini`, como `product-metrics/pytest.ini`. `coveragerc` con `source = vectra_verification`.
- **Semilla impresa también en verde** (NFR-U12-41; `CANDIDATAS.md`, «Todas las unidades (revisor, U07-T02)»): `tests/conftest.py` registra los perfiles `dev`, `ci` (500 ejemplos) y `nightly`, y fija e imprime la semilla en el encabezado de pytest, como `product-metrics/tests/conftest.py`. Sin las partes de `vectra_common` de ese archivo.
- **import-linter** (Paso 1). Contratos `forbidden`:
  - `sampler`, `report`, `story_map` y `rt2_latency` no importan `httpx`, `requests`, `socket`, `subprocess`, `asyncio`, `pyotp`, ni los módulos con E/S de la unidad: `credentials`, `evidence`, `manifest`, `simulator`, `driver`, `cli`, `clients`, `scenarios` y `load`. `yaml` se permite solo en `story_map` (P-3);
  - ningún módulo de `vectra_verification` importa `vectra_common` (frase del Paso 1: «**no** de `vectra_common`»). `vectra_common` está instalado en el entorno del workspace: sin el contrato, un import accidental pasa aquí y falla en la imagen.

  `test_traceability.py` no lee `.importlinter` (`CANDIDATAS.md`, línea 531): cita NFR-U12-01 y los demás identificadores en archivos `.py`, no solo en los contratos.
- **Prueba de verbos de `kubectl`** (Paso 1; NFR-U12-43; INF-U12-02; BR-U12-09). Ver P-4.
  - Recorre `system-verification/src/`, `system-verification/demos/`, el `Makefile` y, cuando existan, `README.md` y `Dockerfile`. No recorre `tests/`.
  - Detecta el verbo aunque haya banderas antes (`kubectl -n vectra-app get`, `kubectl --context kind-vectra apply`) y cuando la orden va como lista de argumentos en Python.
  - Hoy ningún archivo real invoca `kubectl`: la prueba se demuestra con fixtures en `tests/fixtures/`. El Paso 12 la reutiliza sobre `demos/` sin tocarla.
  - Un docstring de `src/` que escriba una orden prohibida la hace fallar: no las escribas.
- **`guard`** (Paso 2; NFR-U12-03, 32; INF-U12-01; BR-U12-10).
  - Constantes: `issuer` y host de kind y de staging, tomados de «Depende de». La comparación es **exacta**, sin sufijos ni subcadenas: `vectra.banco.internal` (producción) no debe pasar por parecerse a `vectra.staging.banco.internal`. Una prueba compara las constantes con `identity-edge/gateway/values/kind.yaml` y `staging.yaml`.
  - Dos comprobaciones: la del entorno configurado (`issuer` y host del gateway), antes de cualquier solicitud; y la del `iss` de un token ya obtenido, que usará U12-T02. «Cero solicitudes» se prueba con un transporte de `httpx` que cuenta.
  - Secciones: las 14 de NFR-U12-30 (`prepare`, `network`, `decisions`, `rt1`, `rt4`, `rt5`, `rt3`, `rt2-setup`, `rt2`, `load`, `pii`, `u11`, `resilience`, `report`). En kind, todas. En staging, solo `prepare` (sin el parche de los Jobs de prueba), `decisions` con un máximo de 100 casos, `u11` y `report`. Ver P-6.
  - Acción de reactivación: solo dentro de la sección `rt2`. Desde cualquier otra, error. U12-T02 la llama antes de `resolve_frozen`.
  - Barrera horaria de `decisions`: ver P-2. El reloj se inyecta; `guard` no llama a `datetime.now()`.
- **`credentials`** (Paso 2; NFR-U12-04; BR-U12-03).
  - Lee la bóveda por su API HTTP KV v2 con `httpx`, con `VAULT_ADDR` y `VAULT_TOKEN` del entorno del proceso (deployment-architecture §2b: «su token entra al contenedor como variable de entorno»). Montaje `secret` en kind y `vectra` en staging. Ver P-5.
  - Rutas y propiedades: las de «Depende de». Usuarios: `analista-1`, `analista-2`, `ingeniero-1`, `cro-1` y `cumplimiento-1` (plan §1).
  - Fuera de kind, pedir una credencial de `cumplimiento-*` da error **antes** de cualquier solicitud: el doble de la bóveda cuenta 0. Además, `identity/synthetic-users` es un solo secreto con todos los usuarios: al leerlo en staging, `credentials` descarta las propiedades `SYNTH_CUMPLIMIENTO_*` sin guardarlas.
  - Solo en memoria: nada de `open` en escritura, `write_text` ni `tempfile`. `repr()` y `str()` de sus objetos no muestran ningún secreto. La prueba corre con el directorio de trabajo, `HOME` y `TMPDIR` en `tmp_path` y comprueba que no aparece ningún archivo.
  - TOTP: `pyotp.TOTP(semilla)`, con el instante inyectado. La espera por reuso del código es del Paso 5.
- **`evidence`** (Paso 2; NFR-U12-05). Dos partes: una que quita (`Authorization`, `Cookie`, `Set-Cookie`, y los campos `access_token`, `refresh_token`, `id_token`, `client_assertion`, `password`), y una que **falla** si después queda un JWT (tres segmentos en base64url que empiezan por `eyJ`) o cualquier secreto cargado por `credentials` (semillas, contraseñas, llaves). La escritura de los archivos de evidencia por sección es del Paso 13; aquí queda la función por la que esa escritura tendrá que pasar.
- **Tipos de dominio.** §1 del plan no tiene un módulo de tipos. Ver P-7. Con la recomendación: `Evidence` y `VerificationReport` viven en `report.py`, `Rt2Measurement` en `rt2_latency.py` y el informe de celdas en `sampler.py`. Los demás tipos de domain-entities (`SimulatorScenario`, `DecisionMix`, `RunReport`, `DriverReport`, `LoadProfile`) son de los Pasos 6 y 11.
- **`sampler`** (Paso 3; BR-U12-01, 06; NFR-U12-10, 11).
  - Entrada: una población en memoria, cada fila con su identificador y sus cuatro celdas `(atributo, grupo, banda)`. Derivar las etiquetas con `derive_monitoring_labels` y leer la partición `test` de U5 es del `simulator` (Paso 6).
  - `ATTRIBUTES` y `BANDS` iguales a los de `vectra_disparity`. U12 no depende de esa librería: una prueba los compara (está instalada en el entorno del workspace).
  - `normal`: muestra al azar sin repetición del volumen pedido. Un volumen mayor que la población es un error.
  - `stratified`: el mismo procedimiento que `stratified_sample` de U5: orden al azar; se toma una fila si alguna de sus celdas no llega a `min(min_per_cell, disponibles)`; después se completa al azar hasta el volumen. Así el lote se compone como el que midió U5.
  - Informe de celdas: por cada celda, `disponibles` y `tomadas`, y la lista de las que no alcanzan `min_per_cell`. Una celda que no alcanza toma todas las filas que hay y **no se rellena** con repetidas. Negarse a correr es de la sección `rt2` (Paso 8), no del `sampler`. Ver P-8.
  - Azar con `random.Random(seed)` de la biblioteca estándar: sin `numpy` y sin el generador global.
- **`rt2_latency`** (Paso 3; BR-U12-07; INF-U12-03). Entrada: los `recorded_at` de las `recommendation` del lote y el del `freeze`, en UTC. Salida: `Rt2Measurement` (`run`, `batch_first_recorded_at`, `freeze_recorded_at`, `latency_seconds`, `passed`). `passed` es `latency_seconds ≤ 1 800`: 1 800 exactos pasan. Un lote vacío o un `freeze` anterior al inicio son un error, no una medición.
- **`story_map`** (Paso 3; BR-U12-13; domain-entities §4). Ver P-3.
  - `report/story-map.yaml` lleva las 15 filas de domain-entities §4.2, con sus evidencias, y marca las cuatro de demos (US-304, 503, 504 y 505) como «demostradas».
  - Falla si falta una de las historias de domain-entities §4 (US-101, 106, 109, 111, 303, 305, 603, 604, 608, 609 y 610) o si una evidencia no es un identificador conocido.
  - Identificadores conocidos, los 26: `RT-1` a `RT-5`, `X01` a `X10`, `journey-7-3`, `journey-7-4`, `rt-5`, `dashboard`, `SIM-NORMAL`, `RT2-LATENCY`, `LOGS-NO-PII`, `LOAD`, `RESTORE-DRILL`, `READINESS` y `CASE-SIZE`. `US-609` **no** es un identificador de evidencia: su evidencia es `LOAD` (ver «Notas», aviso 3).
- **`report`** (Paso 3; BR-U12-11, 13; NFR-U12-20, 21).
  - Puro: recibe en memoria las evidencias, los hashes declarados del manifiesto y los observados. Leer archivos y `manifest.json` es de `manifest` y `cli` (Paso 13).
  - Una fila por elemento: los 26 identificadores y las 15 historias. Cada fila lleva resultado, evidencia, commit, digests de las imágenes y fecha (BR-U12-11).
  - Reglas de un elemento: sin evidencia, o con hash ausente o distinto → `no ejecutado`; `expected ≠ obtained` → `falla`, aunque `result` diga `pasa`; `result = falla` → `falla`, aunque `expected = obtained`; `pasa` solo con una evidencia íntegra que pasa. Evidencias repetidas: ver P-1.
  - Reglas de una historia: `pasa` si pasan todas sus evidencias; `falla` si alguna falla; `no ejecutado` en otro caso. Las cuatro de demos salen como «demostrada».
  - `render` produce el Markdown del informe, con el encabezado de NFR-U12-21: el manifiesto detecta alteraciones accidentales y archivos faltantes, no a quien edite la evidencia y el manifiesto a la vez; esa protección la da la revisión del PR con `CODEOWNERS`.
  - **Nada se recorta del informe por la demo.** Los elementos de secciones diferidas (RT-1, RT-4, X01 a X10, `LOAD`, `LOGS-NO-PII`, `CASE-SIZE`, `RESTORE-DRILL`, `READINESS`) no tendrán evidencia y saldrán `no ejecutado` (alcance §3 U12, fila 13: «Las demás quedan registradas como `no ejecutado` (BR-U12-11)»).
- **Pruebas de ejemplo del Paso 3** (business-logic-model §3, las del informe y de la latencia). Van dentro de los cuatro archivos de la aceptación:
  - RT-2 con una corrida de 31 min → `passed = false`, la medición queda registrada, y con esa evidencia `RT2-LATENCY` sale `falla` y US-303 sale `falla`;
  - informe con X07 sin evidencia → `no ejecutado`;
  - US-111 con `RT-3` en `pasa` y `journey-7-3` sin evidencia → `no ejecutado`;
  - un `story-map.yaml` con una evidencia desconocida → el generador falla; y uno sin la fila de una historia → falla;
  - un byte cambiado en una evidencia → su elemento sale `no ejecutado` (NFR-U12-20);
  - el encabezado del informe dice el límite del manifiesto (NFR-U12-21);
  - sin ninguna evidencia → 41 filas, todas `no ejecutado`, ninguna `pasa`;
  - una población de fixture con una celda chica → el `sampler` la informa (NFR-U12-11; que `rt2` se niegue es del Paso 8).

  Los demás ejemplos de business-logic-model §3 son de otros pasos: simulador, `RunReport` y conductor (Paso 6); RT-1 (Paso 7); RT-3 y X04 (Pasos 8 y 9); `LOGS-NO-PII` (Paso 10). El del guion con `kubectl apply` o `argocd app sync` es la prueba del Paso 1 (CA-3).
- **`make -C system-verification check`.** Corre en orden: `ruff check` y `ruff format --check`; mypy en modo estricto sobre `system-verification/src/vectra_verification`; import-linter; las pruebas de `tests/unit` y `tests/property` con el perfil `ci` y la semilla impresa, sin `-q`; y la cobertura del 100 % del Paso 4. Termina en 0. No incluye `traceability` (falla hasta el Paso 17; ver CA-13) ni `links` (no hay Markdown en la unidad hasta el Paso 17).
- **`logic.md`.** Describe las firmas reales de `sampler`, `rt2_latency`, `story_map` y `report`; las reglas del informe con la decisión de P-1; la fórmula de P-2; la tabla BR-U12 → prueba de lo que entra (BR-U12-01, 06, 07, 10, 11 y 13); y dice que `mutmut` está diferido por la demo.
- **Trazabilidad a mano de las BR.** `test_traceability.py` no reconoce las BR-U12, porque están en párrafos en negrita (`CANDIDATAS.md`, líneas 183 y 272). Cítalas igual en las pruebas y en `logic.md`.
- **Plan.** Marca `[x]` los Pasos 1 a 4 con `(U12-T01)`; en el Paso 4, la nota «`mutmut` diferido por la demo (T3)».

**Fuera** (recházalo aunque lo veas roto o tentador):

- **`mutmut` del Paso 4** sobre `report`, y la parte de NFR-U12-40 que lo pide. Recorte E\*F: enmienda §3, U12, fila «4»: «Sin `mutmut` (T3)»; y §2 regla 3, que nombra «U12 Paso 4». `mutmut` ya está en el grupo `dev`; no hace falta agregarlo ni configurarlo.
- **Bloques C a H de U12** (Pasos 5 a 19): clientes, login OIDC con Playwright, `simulator`, `driver`, PBT-U12-03, escenarios y oráculos, carga, demos, `cli`, `manifest`, imagen, workflow, README y verificación en kind. Los módulos `manifest.py`, `simulator.py`, `driver.py` y `cli.py` quedan vacíos.
- **La comprobación de cobertura ≥ 85 % del resto del paquete.** El Paso 4 la remite al Paso 16.
- **Quitar del código lo que el recorte difiere en pasos posteriores.** Las 14 secciones en `guard`, los 26 identificadores y las 15 historias en `story_map` y `report` entran completos: la enmienda no recorta nada de los Pasos 1 a 3.
- `.github/CODEOWNERS` (la línea de `evidence/` ya existe), los workflows, `platform/`, `contracts/`, `identity-edge/`, `reference-model/` y `bias-monitoring/`. Si algo de U0, U2, U5 o U9 no encaja con lo que pide U12, se reporta como candidata.
- Leer la partición `test` de U5 o cualquier archivo de `reference-model/.out/`.
- Cualquier llamada a un clúster, a Keycloak o a una bóveda real.

---

## Candidatas (`CANDIDATAS.md`)

**Se atienden aquí** (tocan el esqueleto o la lógica pura):

| Línea | Candidata | Qué se hace |
|---|---|---|
| 333 | U12, BR-U12-06: 4 de las 65 celdas de U9 no llegan a 30 casos en todo `test` | El `sampler` informa `disponibles` y `tomadas` por celda y no rellena. La decisión de qué hace `rt2` es P-8 |
| 428 | Todas las unidades: imprimir la semilla también en verde | `tests/conftest.py` |
| 444 y 549 | Todas las unidades, paquetes de prueba | Sin `__init__.py` en `tests/`; `--import-mode=importlib` |
| 531 y 415 | `test_traceability.py` no lee `.importlinter` | Los identificadores se citan en `.py` |
| 183 y 272 | `test_traceability.py` no reconoce las BR en párrafos | Tabla BR-U12 → prueba en `logic.md` |
| 474, 479 y 530 | Bitácoras: sin plantillas sin expandir, con la semilla y con rutas absolutas | `bitacoras/U12-T01.md` |

**Para una tarea posterior de U12** (no las atiendas):

- Línea 207: marcadores que busca `LOGS-NO-PII` (Paso 10, diferido).
- Línea 251: caso bidi de RT-1 (Paso 7, diferido).
- Línea 252: variante proxy de U5 (U12-T03, RT-2).
- Líneas 435, 481, 515, 518, 568, 572, 577, 591 y 607: comprobaciones en kind de U6, U4, U7, U10 y U11 (U12-T05, Paso 18).
- Línea 601: `TMPDIR` dentro del worktree y `make -C platform check` (ver «Restricciones del entorno»).

---

## Preguntas abiertas

**Ninguna necesita la decisión del usuario antes de despachar esta tarea.** Si nadie responde, rige la recomendación y el codificador la anota en `logic.md`. **P-8 sí necesita al usuario antes de despachar U12-T03**; esta tarea no depende de la respuesta.

- **P-1 — Evidencias repetidas del mismo elemento.** PBT-U12-02 pide generar «duplicados», pero el diseño no dice qué resultado da un elemento con dos evidencias.
  - (a) **Recomendada.** Gana lo peor, como en las historias (BR-U12-13): `falla` si alguna falla; si ninguna falla y alguna tiene el hash ausente o distinto, `no ejecutado`; `pasa` solo si todas son íntegras y pasan.
  - (b) Gana la de `executed_at` más reciente. Una repetición que pasa taparía una falla anterior.
  - (c) Un duplicado es un error del generador. Rompe la retoma de una sección (NFR-U12-30).
- **P-2 — Barrera horaria de `decisions`.** El Paso 2 dice «no empieza después de las 23:00 UTC» y su aceptación dice «a las 22:30 UTC → se niega». NFR-U12-32 las concilia: «si no puede terminar antes de las 23:00 UTC, no empieza». Hace falta una duración estimada, y el diseño no la da.
  - (a) **Recomendada.** `guard` recibe el volumen y el ritmo y estima `volumen / ritmo + volumen × DECISION_SECONDS_PER_CASE + margen`, con constantes en `guard` (`DECISION_SECONDS_PER_CASE = 1`, margen de 300 s; valores iniciales, se miden en el Paso 18). Se niega si `ahora + estimado` pasa de las 23:00 UTC del mismo día. Con 2 000 casos a 10/s da ≈ 42 min: a las 22:30 se niega y a las 22:00 empieza.
  - (b) Una hora de corte fija (por ejemplo, 22:00 UTC). Más simple, pero no sirve para los 100 casos de staging ni se ajusta al medir.
  - (c) La letra del Paso 2: solo se niega desde las 23:00. Contradice su propia aceptación.
- **P-3 — `story_map` «sin E/S» y a la vez «carga `report/story-map.yaml`».** El Paso 1 lo pone entre los módulos sin E/S y el Paso 3 le pide cargar un archivo.
  - (a) **Recomendada.** `story_map` tiene una función pura que valida el texto del YAML y una de una línea que lee el archivo con `pathlib`. El contrato de import-linter prohíbe red, procesos y los módulos con E/S de la unidad; `yaml` se permite solo aquí.
  - (b) `story_map` solo valida y el archivo lo lee `cli` (Paso 13). La prueba del Paso 3 tendría que leerlo ella.
- **P-4 — Prueba de verbos: lista cerrada o lista de prohibidos.** El Paso 1 dice «solo invocan `kubectl` con…» y después enumera ocho prohibidos.
  - (a) **Recomendada.** Lista cerrada: pasa solo `get`, `auth can-i`, `logs` y `port-forward`; cualquier otro verbo falla (también `cp`, `run`, `replace`, `label`, `annotate`, `drain` o `auth reconcile`, que la enumeración no nombra). De `argocd` falla `app sync` y cualquier otra invocación: U12 no lo usa.
  - (b) Solo los ocho verbos y `argocd app sync`. Deja pasar escrituras que el plan no enumeró.
- **P-5 — Cliente de la bóveda.** El diseño dice «con la sesión del operador» y no nombra librería.
  - (a) **Recomendada.** `httpx` contra la API KV v2 (`GET <VAULT_ADDR>/v1/<montaje>/data/<ruta>`, cabecera `X-Vault-Token`). No agrega dependencias. Se prueba con un doble.
  - (b) Agregar `hvac`. No está en `uv.lock` y trae `requests`.
- **P-6 — Secciones que conoce `guard`.** El Paso 2 entra completo, pero la enmienda saca del Paso 13 `network`, `rt1`, `rt4`, `load`, `pii` y `resilience`.
  - (a) **Recomendada.** Las 14 de NFR-U12-30. El recorte de la CLI se aplica en U12-T04; el informe registra las diferidas como `no ejecutado`.
  - (b) Solo las 8 del Paso 13 recortado. Recorta el Paso 2, y la enmienda no lo dice.
- **P-7 — Dónde viven los tipos de dominio.**
  - (a) **Recomendada.** En el módulo que los produce (`report.py`, `rt2_latency.py`, `sampler.py`). No cambia la estructura de §1.
  - (b) Un `entities.py` nuevo, puro. Más ordenado, pero §1 no lo tiene.
- **P-8 — `rt2` frente a las celdas que no alcanzan (para U12-T03; necesita al usuario antes de despachar esa tarea).** NFR-U12-11 dice que `rt2` se niega si una celda no llega a 30. Con el `test` real de U5, 4 de las 65 celdas no llegan (`CANDIDATAS.md`, línea 333): `rt2` se negaría siempre y D2 no correría.
  - (a) **Recomendada.** `rt2` se niega solo si una celda **alcanzable** (con 30 o más disponibles) queda corta; las inalcanzables se informan en la evidencia. Es la lectura de U5 (`test_r4_freeze_rate.py`: «cada celda alcanzable») y de PBT-U12-01 («con datos suficientes»). Hay que precisar NFR-U12-11 y BR-U12-06.
  - (b) Ampliar `test` en U5 hasta que las 65 celdas lleguen a 30. Cambia U5 y sus hashes.
  - (c) Muestrear también de otra partición. BR-U12-01 lo evita para no repetir el dataset de validación.

  En esta tarea el `sampler` entrega lo que cualquiera de las tres necesita: `disponibles` y `tomadas` por celda.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/system-verification-code-generation-plan.md` (§1, Bloques A y B, §3)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§1, §2, §3 U12, §4, §5.2, §8)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§3 U12, T1 a T6, §6 RL-1 a RL-5)
- `DECISIONES-LOOP.md` (§6 y §9)
- `aidlc-docs/construction/system-verification/functional-design/business-rules.md` (BR-U12-01, 06, 07, 10, 11, 13)
- `aidlc-docs/construction/system-verification/functional-design/business-logic-model.md` (§1 y §3: PBT-U12-01, 02, 04 y pruebas de ejemplo)
- `aidlc-docs/construction/system-verification/functional-design/domain-entities.md` (§2 `Rt2Measurement`, §3 y §4)
- `aidlc-docs/construction/system-verification/nfr-requirements/nfr-requirements.md` (NFR-U12-01, 03, 04, 05, 10, 11, 20, 21, 30, 32, 40, 41, 43) y `tech-stack-decisions.md`
- `aidlc-docs/construction/system-verification/infrastructure-design/infrastructure-design.md` (INF-U12-01, 02 y la parte de latencia de INF-U12-03) y `deployment-architecture.md` (§2b)
- `product-metrics/Makefile`, `pyproject.toml`, `.importlinter`, `pytest.ini`, `coveragerc` y `tests/conftest.py`
- Los archivos de «Depende de»
- `tareas/U11-T01-esqueleto-y-logica.md` y `bitacoras/U11-T01.md`, como ejemplo de una tarea gemela
- `CANDIDATAS.md`: las líneas citadas en «Candidatas»

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`. Los comandos del plan abrevian rutas (`test_credentials.py`); aquí van completas.

- [ ] **CA-1** — Esqueleto, dependencias y contratos de imports (Paso 1; NFR-U12-01).
  ```bash
  uv sync --frozen && uv run lint-imports --config system-verification/.importlinter
  ```
  Esperado: código 0 y `Contracts: N kept, 0 broken.`, con los contratos de «Precisiones» listados como `KEPT`. **Rojo primero:** un `import httpx` en `sampler.py`, un `import subprocess` en `report.py`, un `from vectra_verification import credentials` en `rt2_latency.py` y un `import vectra_common` en `guard.py` rompen cada uno su contrato; regístralo antes de dejar los contratos. Sobre `main` hoy: `Could not find system-verification/.importlinter.`, código 1.

- [ ] **CA-2** — Estructura de §1, sin lo que no toca.
  ```bash
  cd system-verification && for p in Makefile pyproject.toml .importlinter pytest.ini coveragerc src/vectra_verification/__init__.py src/vectra_verification/guard.py src/vectra_verification/credentials.py src/vectra_verification/evidence.py src/vectra_verification/sampler.py src/vectra_verification/report.py src/vectra_verification/story_map.py src/vectra_verification/rt2_latency.py src/vectra_verification/manifest.py src/vectra_verification/simulator.py src/vectra_verification/driver.py src/vectra_verification/cli.py src/vectra_verification/clients/__init__.py src/vectra_verification/scenarios/__init__.py src/vectra_verification/load/__init__.py report/story-map.yaml demos/verify evidence tests/conftest.py tests/unit tests/property tests/integration tests/doubles tests/fixtures; do test -e "$p" || echo "FALTA $p"; done; test ! -e chart && test ! -e migrations && test ! -e Dockerfile && ! find tests -name __init__.py | grep -q . && ! grep -rqE "vectra[-_]common" pyproject.toml src && echo OK
  ```
  Esperado: ninguna línea `FALTA` y `OK` al final. El `OK` comprueba también que no hay `chart/`, `migrations/` ni `Dockerfile`, que `tests/` no tiene `__init__.py` y que nada nombra `vectra_common`.

- [ ] **CA-3** — Prueba de verbos de `kubectl` (Paso 1; NFR-U12-43; INF-U12-02; BR-U12-09).
  ```bash
  uv run pytest system-verification/tests/unit/test_kubectl_verbs.py -v
  ```
  Esperado: pasan estos casos, cada uno con su nombre:
  - los archivos reales (`src/`, `demos/`, `Makefile`) → sin hallazgos;
  - un fixture con `kubectl apply` → la comprobación falla y nombra archivo, línea y verbo;
  - un fixture por cada verbo prohibido (`exec`, `apply`, `create`, `delete`, `patch`, `scale`, `edit`, `rollout`) → falla;
  - un guion de fixture con `argocd app sync` → falla;
  - `kubectl -n vectra-app get pods`, `kubectl auth can-i get pods`, `kubectl logs job/x` y `kubectl port-forward pod/x 8080` → pasan;
  - `kubectl --context kind-vectra apply -f x.yaml` y la lista de Python con `kubectl`, `-n`, `vectra-app` y `delete` → fallan;
  - con P-4 (a): `kubectl cp` y `kubectl auth reconcile` → fallan.

  **Rojo primero:** un detector que solo mira la palabra que sigue a `kubectl` deja pasar el caso con `--context`; regístralo. Sobre `main` hoy: `file or directory not found`, código 4.

- [ ] **CA-4** — `guard` (Paso 2; NFR-U12-03, 32; INF-U12-01; BR-U12-10).
  ```bash
  uv run pytest system-verification/tests/unit/test_guard.py -v
  ```
  Esperado: pasan, cada uno con su nombre:
  - `issuer` de producción (`https://vectra.banco.internal/auth/realms/vectra`) → error y **cero** solicitudes en el transporte que cuenta; host de producción → lo mismo;
  - `https://vectra.localtest.me.ejemplo.test/auth/realms/vectra` y un host desconocido → error;
  - kind y staging reales → pasan, y las constantes coinciden con `identity-edge/gateway/values/kind.yaml` y `staging.yaml`;
  - `rt2` en staging → se niega; también `rt2-setup`, `rt3`, `rt5`, `rt1`, `rt4`, `network`, `load`, `pii` y `resilience`;
  - en staging: `prepare`, `u11` y `report` → pasan; `decisions` con 100 casos → pasa; con 101 → se niega; el parche de los Jobs de prueba → se niega;
  - en kind, las 14 secciones → pasan;
  - una reactivación fuera de la sección `rt2` → error; dentro de `rt2` en kind → pasa;
  - `decisions` a las 22:30 UTC con reloj simulado → se niega; a las 23:30 → se niega; a las 10:00 → empieza.

  **Rojo primero:** comparar el host con `endswith("banco.internal")` deja pasar producción; regístralo antes de dejar la comparación exacta.

- [ ] **CA-5** — `credentials` (Paso 2; NFR-U12-04; BR-U12-03).
  ```bash
  uv run pytest system-verification/tests/unit/test_credentials.py -v
  ```
  Esperado: pasan, con el doble de la bóveda de `tests/doubles/`:
  - en kind se leen las llaves de `channel-simulator` y de `verification-reader` y la contraseña y la semilla de cada usuario, en las rutas y propiedades de «Depende de»; el doble comprueba el montaje (`secret`) y la cabecera del token;
  - en staging, el montaje es `vectra`;
  - en staging, pedir la semilla de `cumplimiento-1` → error y **0** solicitudes en el doble; y al leer `analista-1`, ninguna propiedad `SYNTH_CUMPLIMIENTO_*` queda en memoria;
  - el TOTP es igual a `pyotp.TOTP(semilla).at(instante)`;
  - ningún archivo escrito con credenciales: con el directorio de trabajo, `HOME` y `TMPDIR` en `tmp_path`, no aparece ningún archivo; y `credentials.py` no tiene `open` en escritura, `write_text`, `write_bytes` ni `tempfile` (por AST);
  - `repr()` y `str()` de los objetos no contienen ningún secreto;
  - una ruta ausente o un 403 de la bóveda → error claro, sin el token en el mensaje.

  **Rojo primero:** leer la bóveda y filtrar después hace que el doble cuente 1 en el caso de `cumplimiento-1`; regístralo.

- [ ] **CA-6** — Filtro de evidencias (Paso 2; NFR-U12-05).
  ```bash
  uv run pytest system-verification/tests/unit/test_evidence_filter.py -v
  ```
  Esperado: pasan:
  - una salida con `Authorization: Bearer …`, `Cookie`, `Set-Cookie` y los campos `access_token`, `refresh_token` e `id_token` → salen sin sus valores;
  - evidencia con un JWT en el cuerpo, fuera de una cabecera → la generación falla;
  - evidencia con una semilla TOTP o una contraseña cargada por `credentials` → la generación falla, y el mensaje de error no la repite;
  - una salida limpia → pasa sin cambios.

  **Rojo primero:** un filtro que solo quita la cabecera `Authorization` deja pasar el JWT del cuerpo; regístralo.

- [ ] **CA-7** — Los tres archivos del Paso 2 juntos, como en el plan.
  ```bash
  uv run pytest system-verification/tests/unit/test_guard.py system-verification/tests/unit/test_credentials.py system-verification/tests/unit/test_evidence_filter.py
  ```
  Esperado: código 0, sin omitidas ni `xfail`.

- [ ] **CA-8** — PBT-U12-01, `sampler` (Paso 3; BR-U12-01, 06; NFR-U12-10, 11).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests/property/test_sampler.py -v
  ```
  **Propiedad:** para toda población y todo `min_per_cell` alcanzable, la muestra tiene ≥ `min_per_cell` casos en cada celda de U9 (atributo, grupo y banda) con datos suficientes, no repite filas y es determinista con la semilla; si una celda no alcanza, lo informa y no la rellena.
  **Generadores:** poblaciones con distribuciones de celdas generadas, incluidas celdas pequeñas (entre 0 y `min_per_cell − 1` filas), celdas vacías y filas que comparten celdas entre atributos; `min_per_cell` entre 1 y 40; semillas y volúmenes generados.
  Esperado: todo pasa; el encabezado muestra el perfil `ci` y la semilla. La salida tiene una prueba por cada parte: mínimo por celda con datos suficientes; sin filas repetidas y todas de la población; misma semilla → misma muestra, en el mismo orden; celda corta → informada, con `tomadas = disponibles`; `normal` → tamaño pedido, sin repetidas y determinista; volumen mayor que la población → error. Hay además la prueba que compara `ATTRIBUTES` y `BANDS` con `vectra_disparity` y el ejemplo de la celda chica. El oráculo cuenta por definición, recorriendo la muestra; no reusa funciones de `sampler`. **Rojo primero:** rellenar una celda corta repitiendo filas, o usar el generador global en vez de `random.Random(seed)`, hace fallar la propiedad; regístralo.

- [ ] **CA-9** — PBT-U12-02, `report`, y sus ejemplos (Paso 3; BR-U12-11, 13; NFR-U12-20, 21).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests/property/test_report.py -v
  ```
  **Propiedad:** para todo conjunto de evidencias, un elemento sin evidencia sale `no ejecutado`, uno con `expected ≠ obtained` sale `falla` aunque su `result` diga `pasa`, y ningún elemento sale `pasa` sin una evidencia que lo respalde; una historia sale `pasa` solo si pasan todas las evidencias de su fila del mapa (domain-entities §4.2), `falla` si alguna falla y `no ejecutado` en otro caso.
  **Generadores:** conjuntos de evidencias con faltantes, contradicciones (`expected ≠ obtained` con `result = pasa`, y al revés) y duplicados; hashes iguales, distintos y ausentes del manifiesto; mapas generados y el mapa real.
  Esperado: todo pasa, con una prueba por cada parte de la propiedad y un caso por cada ejemplo del informe de «Precisiones» (X07, US-111, US-303 con `RT2-LATENCY` en `falla`, el byte cambiado, el encabezado y las 41 filas sin evidencia). El oráculo aplica BR-U12-11 y 13 por definición. **Rojo primero:** confiar en `result` cuando `expected ≠ obtained`, o usar «alguna pasa» en vez de «todas pasan» para una historia, hace fallar la propiedad; regístralo.

- [ ] **CA-10** — PBT-U12-04, `rt2_latency`, y sus ejemplos (Paso 3; BR-U12-07; INF-U12-03).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests/property/test_rt2_latency.py -v
  ```
  **Propiedad:** la latencia es `freeze.recorded_at − min(recorded_at de las recommendation del lote)`, nunca menor que la medida desde cualquier otra entrada del lote, y una corrida con latencia > 1 800 s sale `passed = false`.
  **Generadores:** lotes de entradas y un `freeze` con tiempos generados: lotes de 1 a 2 000 `recorded_at` en UTC, desordenados y con empates; el `freeze` alrededor del límite de 1 800 s.
  Esperado: todo pasa, con los ejemplos: 31 min → `passed = false` y la medición registrada; 1 800 s exactos → `passed = true`; 1 800,001 s → `false`; lote vacío → error; `freeze` anterior al inicio → error. **Rojo primero:** tomar la primera entrada de la lista, o el máximo, en vez del mínimo hace fallar la propiedad; regístralo.

- [ ] **CA-11** — `story_map` y el comando completo del Paso 3 (BR-U12-13; domain-entities §4).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests/property/test_sampler.py system-verification/tests/property/test_report.py system-verification/tests/property/test_rt2_latency.py system-verification/tests/unit/test_story_map.py -v
  ```
  Esperado: código 0. En `test_story_map.py`: el `report/story-map.yaml` real carga con sus 15 filas y coincide, fila por fila, con domain-entities §4.2; un mapa sin la fila de US-603 → falla; un mapa con la evidencia `X99` → falla; un mapa con `US-609` como evidencia → falla. **Rojo primero:** sin la comprobación de identificadores conocidos, el caso `X99` pasa; regístralo.

- [ ] **CA-12** — Cobertura de ramas del 100 % en `report` y `sampler`, y resumen (Paso 4; NFR-U12-40).
  ```bash
  uv run pytest system-verification/tests/unit system-verification/tests/property --cov=vectra_verification.report --cov=vectra_verification.sampler --cov-branch --cov-fail-under=100 && grep -nE "sampler|rt2_latency|story_map|report|mutmut|P-1|P-2" aidlc-docs/construction/system-verification/code/logic.md
  ```
  Esperado: código 0, con `TOTAL … 100%` sobre esos dos módulos (no sobre U0). `logic.md` existe y tiene lo que piden las «Precisiones». Sin `# pragma: no cover` en `report.py` ni en `sampler.py`.

- [ ] **CA-13** — Trazabilidad (`DECISIONES-LOOP.md` §6, regla «sin fallos nuevos», con su enmienda).
  ```bash
  uv run python platform/tests/test_traceability.py --unit system-verification --all; uv run python platform/tests/test_traceability.py --all
  ```
  Esperado:
  - el primero **no** dice `sin código`. Puede salir con código 1, y entonces cada línea que imprime es de este conjunto: NFR-U12-02, 10, 30, 31, 42, 50 e INF-U12-03, 04, 05 (pasos que esta tarea no cubre);
  - **ninguna** línea nombra NFR-U12-01, 03, 04, 05, 11, 20, 21, 32, 40, 41, 43 ni INF-U12-01, 02: son de los Pasos 1 a 4 y quedan trazados en archivos `.py`;
  - el segundo da, para las demás unidades, el mismo conjunto de fallos que en la base de la rama. El revisor lo corre en la base y en la rama y los compara.

  Sobre `main` hoy: `system-verification: sin código`, código 1.

- [ ] **CA-14** — `check` de la unidad (RL-4).
  ```bash
  uptime; time make -C system-verification check; uptime
  ```
  Esperado: código 0, con lint, mypy estricto, import-linter, las pruebas con el perfil `ci` (semilla impresa) y la cobertura del 100 %. Tiempo esperado: **menos de 5 min** con la máquina cargada. Es una estimación de quien redacta (lógica pura y tres PBT de 500 ejemplos), no una medida: anota el tiempo real y los dos `uptime`. Si pasa de 10 min, revisa los generadores antes de seguir. Sobre `main` hoy: `make: *** system-verification: No such file or directory.  Stop.`, código 2.

- [ ] **CA-15** — `check` de U1, porque el diff toca el workspace (RL-4; como CA-7 de U11-T01).
  ```bash
  uptime; time make -C platform check; uptime
  ```
  Esperado: código 0, corrido **después** de CA-14, nunca a la vez. Referencia: ≈ 14 min en U11-T01 con carga 7 a 11. Necesita `platform/.tools/bin` y `platform/.charts` (ver «Restricciones del entorno»).

- [ ] **CA-16** — Lock y alcance del diff.
  ```bash
  uv lock --check && git diff --name-only origin/main...HEAD | grep -vE "^vectra-risk/(system-verification/|pyproject\.toml$|uv\.lock$|CANDIDATAS\.md$|bitacoras/U12-T01\.md$|aidlc-docs/construction/system-verification/code/logic\.md$|aidlc-docs/construction/plans/system-verification-code-generation-plan\.md$)"; echo "fuera=$?"
  ```
  Esperado: `uv lock --check` en 0 y `fuera=1` (ningún archivo fuera de la lista). `git diff origin/main...HEAD -- vectra-risk/uv.lock` solo agrega `vectra-verification` (el paquete, su entrada en los miembros y en el grupo `dev`): ninguna versión de un tercero cambia.

- [ ] **CA-17** — Plan.
  ```bash
  grep -nE "^- \[x\] \*\*Paso [1-4] " aidlc-docs/construction/plans/system-verification-code-generation-plan.md && git diff origin/main...HEAD -- aidlc-docs/construction/plans/system-verification-code-generation-plan.md | grep -E "^[-+]- \["
  ```
  Esperado: los Pasos 1 a 4 en `[x]` con `(U12-T01)`, el 4 con la nota de `mutmut`; el diff muestra solo esas cuatro casillas. La sección de reglas de admisión sigue en el plan.

- [ ] **CA-18** — Enlaces.
  ```bash
  uv run python platform/tests/test_links.py
  ```
  Esperado: `N archivos Markdown sin enlaces rotos`, código 0.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `tests/conftest.py`: perfiles `dev`, `ci` y `nightly`, y la semilla fija e impresa.
- `tests/unit/test_kubectl_verbs.py` y sus fixtures: CA-3.
- `tests/unit/test_guard.py`, `test_credentials.py` y `test_evidence_filter.py`: CA-4 a CA-6.
- `tests/doubles/`: el doble de la API KV v2 de la bóveda, que cuenta solicitudes y comprueba montaje, ruta y cabecera.
- `tests/property/test_sampler.py`: PBT-U12-01 y sus ejemplos.
- `tests/property/test_report.py`: PBT-U12-02 y los ejemplos del informe.
- `tests/property/test_rt2_latency.py`: PBT-U12-04 y los ejemplos de la latencia.
- `tests/unit/test_story_map.py`: el mapa real y los mapas rotos de `tests/fixtures/`.
- **Rojo primero:** antes de cada arreglo, el codificador reproduce el fallo y lo registra en `bitacoras/U12-T01.md`, como mínimo los de CA-1, CA-3, CA-4, CA-5, CA-6, CA-8, CA-9, CA-10 y CA-11. El par falla-pasa es la prueba.

---

## Restricciones del entorno

- **`/tmp` es un tmpfs con cuota y está casi lleno** (80 % al redactar). No copies el repositorio ni corras `npm ci` allí. Los temporales y los logs van dentro del worktree, en una carpeta sin versionar (por ejemplo, `platform/.tools/tmp/`), o en la carpeta propia del scratchpad si son pequeños.
- **`TMPDIR` y `make -C platform check`** (`CANDIDATAS.md`, línea 601): con `TMPDIR` dentro del worktree, `check-local` da falsos rojos (`test_identity_seed`). Para CA-15, deja `TMPDIR` sin definir o fuera del repositorio; para lo demás, dentro. Anota qué usaste en cada corrida.
- **`platform/.tools` y `platform/.charts` no están versionados.** CA-15 los necesita. Crea `platform/.tools/` real en el worktree y enlaza o copia **solo** `platform/.tools/bin`; llena `platform/.charts` con `make -C platform charts` o cópialo del árbol principal, sin enlazarlo (`CANDIDATAS.md`, línea 291). No enlaces los directorios enteros: en U11-T03 eso borró archivos del árbol principal.
- **Máquina compartida y cargada** (hasta 3 codificadores, RL-5). Anota `uptime` junto a cada medida de tiempo. Una prueba que falla por tiempo con carga alta se repite en frío antes de darla por rota, y se anotan las dos corridas.
- **Sin clúster.** Nada de `kubectl`, `helm install`, `argocd`, Keycloak ni bóveda reales. Tampoco Docker ni Testcontainers: esta tarea no los necesita.
- **No toques el árbol principal ni otros worktrees.** Escribe solo en el tuyo.
- **Otros codificadores en paralelo.** Esta tarea no abre puertos: el doble de la bóveda va en proceso, con un transporte de `httpx`. Si necesitas un puerto, pide uno libre al sistema (puerto 0); nunca 8080, 8081 ni 8200. Si otra tarea toca a la vez `pyproject.toml` o `uv.lock`, el orquestador fusiona `origin/main` y vuelve a correr `uv lock`.

---

## Notas

- **Orden sugerido:** esqueleto, workspace y contratos (CA-1 y CA-2) → `sampler` y `rt2_latency` → `story_map` y `report` → `guard`, `credentials` y `evidence` → prueba de verbos → cobertura, `logic.md`, plan y bitácora. Lo que sostiene D2 y el informe queda primero.
- **Lo que las tareas siguientes necesitan de esta:**
  - **U12-T02 (C, Pasos 5 y 6):** `guard` (entorno, `iss` del token, reactivación solo en `rt2`), `credentials` (llaves, contraseñas y TOTP en memoria), el filtro de `evidence`, `sampler.normal` y `sampler.stratified`, y los módulos vacíos `simulator.py`, `driver.py` y `clients/`. Agrega `playwright` y lo que firme el `client_assertion` al `pyproject.toml` de la unidad, y sus módulos nuevos a los contratos de import-linter. La prueba de verbos cubrirá `clients/k8s_read.py` sin cambios.
  - **U12-T03 (D, Pasos 8 y 10):** `rt2_latency`, el tipo `Evidence`, el informe de celdas del `sampler` (P-8) y `scenarios/`.
  - **U12-T04 (E+F, Pasos 12, 13, 15 y 17):** `report` y `story_map`, `manifest.py` y `cli.py` vacíos, la prueba de verbos sobre `demos/`, la barrera de secciones y del parche de `prepare`, y el `Makefile`, al que agrega `links`, `traceability` y la imagen. Si extiende `report` con las duraciones por sección (NFR-U12-31), la cobertura del 100 % debe seguir.
  - **U12-T05 (G+H, Pasos 18 y 19):** `make -C system-verification check` completo y la trazabilidad en 0, con la lista «Diferido por la demo» de `evidence/cierre-demo.md`.
- **Avisos: contradicciones entre plan, recorte, diseño y código** vistas al redactar. Déjalas en `CANDIDATAS.md` las que no estén ya:
  1. Paso 2, texto («no empieza después de las 23:00 UTC») frente a su aceptación («22:30 → se niega») y NFR-U12-32. Resuelta con P-2.
  2. Paso 1 (`story_map` sin E/S) frente al Paso 3 (`story_map` carga un archivo). Resuelta con P-3.
  3. domain-entities §3 pone `US-609` entre los `id` de `Evidence`; §4.1 y §4.2, posteriores, usan `LOAD`. Rige `LOAD`.
  4. NFR-U12-11 frente al `test` real de U5: P-8.
  5. NFR-U12-04 nombra solo `channel-simulator` y los dos analistas; el Paso 2, posterior, agrega `verification-reader` y los demás usuarios sintéticos. Rige el plan.
  6. El Paso 4 remite el ≥ 85 % al Paso 16, que está en D (T4). Con el recorte, nadie lo comprueba: U12-T04 o U12-T05 deciden si entra en `make check`.
  7. La bóveda de kind es `http://vault.vault.svc:8200`, dentro del clúster, y K16 (`platform/rbac/verification-operator/k16.yaml`) solo da `port-forward` en `vectra-app` y `vectra-observability`. El diseño no dice cómo llega la estación del operador a la bóveda. Aquí no estorba (se prueba con un doble); hay que resolverlo antes del Paso 18.
  8. Con el recorte, el informe marcará `no ejecutado` US-603 (falta `X01`) y US-305 (falta `X03`), aunque D3 y D2 pasen, además de US-106, 109, 604, 608, 609 y 610. Es correcto según BR-U12-13; conviene que U12-T04 lo diga en el informe o en el README.
  9. El plan §3 asigna BR-U12-10 al Paso 2 y BR-U12-01 al Paso 6, pero las líneas «Diseño» de los Pasos 2 y 3 no coinciden con esa tabla. Sin efecto en el código.
- Archivos que se **modifican en su sitio**: `pyproject.toml` raíz, `uv.lock`, el plan (casillas de los Pasos 1 a 4) y `CANDIDATAS.md`. Nada de duplicados con sufijo.
- **Nombres que rompen las herramientas:** nada de directorios `generated`, `rendered` ni `dist` dentro de `system-verification/`: `test_traceability.py` los salta.
- **Enlaces:** `test_links.py` lee como enlace cualquier corchete cerrado seguido de un paréntesis fuera de un bloque de código sin sangría. Cuidado con los patrones de `grep` en `logic.md` y en la bitácora.
- **Bitácora** `bitacoras/U12-T01.md`: la salida real de cada comando, pegada, con rutas absolutas a los logs largos y sin plantillas sin expandir. Incluye la semilla de cada corrida con Hypothesis, los pares falla-pasa, la decisión tomada en P-1 a P-7, el tiempo de cada `make check` con sus `uptime`, y el `uv tree --package vectra-verification`.
- PBT-U12-01..04 nunca se recortan. En esta tarea entran las tres del Bloque B (01, 02 y 04); PBT-U12-03 es del Paso 6 (U12-T02).
- U12 no tiene datos propios ni recursos en el clúster: no hay migraciones, chart ni nada que limpiar en kind.
