# Cierre de U11 con alcance acotado a la demo

**Estado: pendiente de revisión; verificación en kind pendiente de U12 Paso 18.** U11 queda cerrada **para kind** (`demo-kind-alcance.md` §3, U11), no para staging ni prod. U11-T01 escribió el cálculo (`model`, `compute`, `noise`, `reader`, `state`, `params`), U11-T02 el proceso (`scheduler`, `collector`, `main`) y U11-T03 la imagen, el chart, las reglas, el dashboard, los runbooks, la Application, el README y este cierre. La demo que sostiene U11 es D4: el día D + 1 el presentador abre `product.json` en Grafana y ve la North Star, la sostenida, la tasa de consulta y `vectra_product_noise_days_below_floor`.

## Comprobado

Lo del codificador, sin clúster, desde `vectra-risk/` (la salida de cada comando está en `bitacoras/U11-T01.md`, `bitacoras/U11-T02.md` y `bitacoras/U11-T03.md`):

| Tarea / Paso | Punto | Comando | Resultado |
|---|---|---|---|
| U11-T01, Pasos 1 a 5 | Modelo, parámetros, `compute` y `noise` puros; cobertura de ramas del 100 % en `compute` y `noise` | `make -C product-metrics coverage` (primer comando) | rc 0; `mutmut` diferido (T3) |
| U11-T02, Pasos 6 a 9 | Proceso real: `scheduler`, `collector`, `main`; readiness; `SIGTERM` con código 0; cobertura de ramas ≥ 90 % | `make -C product-metrics test coverage` | rc 0 (cifras en la bitácora de U11-T03, sección «make check») |
| U11-T03, 10 | Imagen: `hadolint`, usuario `65532:65532`, sin `pytest`/`hypothesis`/`ruff`/`mypy`/`hatchling`, cada `FROM` por digest (2 de 2), import-linter (`sin-fastapi`) | `make -C product-metrics image`; `docker image inspect …`; `uv run lint-imports --config product-metrics/.importlinter` | `65532:65532 ["python","-m","vectra_product.main"]`; `OK`; `OK-entrada`; `Contracts: 3 kept, 0 broken` |
| U11-T03, 10 y 11 | El contenedor real arranca con las variables y el archivo de parámetros que pone el chart (`--read-only`, `65532:65532`, 8081 en un puerto libre): `/readyz` 503 → 200, `/metrics` dentro de la allowlist, `docker stop` → 0 en ≤ 10 s, sin `VECTRA_REGISTRY_URL` → 3, con `noise_sustain_days: 15` → 2, sin línea de log vacía | `make -C product-metrics image-test` | `7 passed`; memoria del contenedor tras la primera pasada: 54,75 MiB (dato para U12) |
| U11-T03, 11 | Render, esquema y `conftest` del chart en kind, staging y prod: 9 documentos por entorno | `make -C product-metrics policy-chart` | `Valid: 9, Invalid: 0` ×3; `540 tests, 540 passed` y `21 tests, 21 passed` ×3 |
| U11-T03, 11 | Una mutación del render por regla (73 casos), paridad de los rangos de los parámetros con `params.parse` (37 filas), identidad, variables, sondas, `checksum/config`, recursos (kind 128 MiB, staging y prod 256 MiB) | `uv run pytest product-metrics/tests/unit/test_chart.py` | rc 0 |
| U11-T03, 11 | Admisión de U1 (Kyverno, `rego` y `--namespace hpa`) por entorno y las pruebas de Kyverno | `make -C product-metrics policy-chart-u1` | `pass: N, fail: 0` ×3; `Test Summary: 81 tests passed and 0 tests failed` (`make -C platform check-chart` entra en pánico con el PDB repetido entre entornos: candidata conocida) |
| U11-T03, 11 | Cuota (NFR-U11-14) y flujos (F28, F50, F60 y los tres casos bloqueados), `Server` `metrics-8081` de U1, `CODEOWNERS` | `make -C product-metrics quota-flows` | rc 0; `requests [0.78, 1.05]`, `limits [3.9, 2.44]` recalculados desde el render de `prod`; `git diff origin/main -- platform/network platform/policies ../.github/CODEOWNERS` vacío |
| U11-T03, 12 | Reglas generadas y `spec` renderizado (identico en los tres entornos); `promtool check rules` y 12 casos de `promtool` con una mutación roja por cada uno | `make -C product-metrics gen-rules rules` | `SUCCESS: 24 rules found`; `SUCCESS` ×4 archivos |
| U11-T03, 13 | `product.json` (17 paneles, mundo cerrado dashboard → reglas → `collector`), panel de ciclos omitidos en `operacion.json`, runbooks | `uv run pytest product-metrics/tests/unit/test_dashboards.py`; `make -C product-metrics runbooks` | `39 passed`; `12 alertas con su runbook en regla`; `1 5` en el conteo de `operacion.json` |
| U11-T03, 15 | Application `product-metrics` (wave 5, sin `syncPolicy.automated`) en los tres entornos | `make -C product-metrics gitops` | rc 0; `kind: 54, staging: 53, prod: 51 Applications en orden`; `pass: 1, fail: 0` ×3 |
| U11-T03, 15 | Trazabilidad con la lista «Diferido por la demo»; cada BR-U11 con una prueba | `make -C product-metrics traceability`; `git grep` de cada BR | `product-metrics: 36 identificadores con trazabilidad`, rc 0; `--all` sin fallos nuevos frente a la base (0 líneas de U11; eran 16) |
| U11-T03, 17 | README (qué mide cada métrica y qué no, parámetros y targets **[INTERNO]**, ciclo, deduplicación, readiness, runbooks) | `make -C product-metrics links runbooks` | `7 archivos Markdown sin enlaces rotos`; `forbidden_phrases.py` sin salida |
| U11-T03, 18 | `make -C product-metrics check` (todo lo anterior, en orden) | `make -C product-metrics check` | rc 0 en **526 s** (`uptime` al empezar: carga 2,73; al terminar, 1,84); `358 passed` con `ci` (100 % en `compute` y `noise`), `204 passed` (98,64 % en total), `7 passed` de la imagen |
| U11-T03, 18 | Candidatas heredadas C-1 a C-7 con su rojo (planificador que cancela la página; plazo a 90 min; sin reinicio de `_retries`; loggers de terceros) | pruebas nombradas en la bitácora | rojo y verde registrados en `bitacoras/U11-T03.md` |
| U11-T03, 18 | **Presupuesto de memoria de kind** | `uv run pytest platform/tests/test_kind_profile.py` | `6 passed`. **Con y sin U11:** `requested_gib()` = 10,3438 GiB en la base (sin U11) y **10,6328 GiB** con U11; diferencia 0,2890 GiB = 2 réplicas × (128 + 20) MiB (± 0,001). `BUDGET_GIB` 10,4 → 10,7 |
| U11-T03, 18 | **Proyección** con U8 y U10 (requests de kind de los diseños; INF-U8-04 e INF-U10-01) | suma sobre la cifra medida | U8: `case-service` y `case-worker` 2 × 276 MiB cada uno y `core-banking-mock` 2 × 84 MiB = 1 272 MiB; U10: `console-bff` 2 × 276 MiB y `console-spa` 2 × 52 MiB = 656 MiB; total 1,8828 GiB. **Proyección: 10,6328 + 1,8828 = 12,5156 GiB (≈ 12,5)**, por debajo de los 13,0 GiB de parada |
| U11-T03, 18 | `make -C platform check` y el `make check` de todas las unidades (RL-4), en serie con `uptime` | `make -C <unidad> check` | **12 de 12 unidades en rc 0** al final, con las duraciones y la carga de cada una en `bitacoras/U11-T03.md` (CA-17): contracts 154 s, platform (`check-local` ≈ 235 s y `check-tools` 129 s, la segunda con `TMPDIR` en el worktree), identity-edge 1 133 s, decision-registry 601 s, governance 607 s, reference-model 342 s, model-serving 231 s, scoring-explainability 393 s, bias-monitoring 1 306 s, case-management 241 s, console 92 s y product-metrics 526 s. Cuatro tuvieron una primera corrida en rojo por el entorno (sin `npm ci`; `/tmp` lleno para `promtool`; una prueba con límite de tiempo con la máquina cargada) y pasaron al repetirlas |

## Decisiones

- **P-1 = (b), decidida por el usuario el 2026-11-12:** el request de memoria de `product-metrics` en kind es de **128 MiB** por réplica (`chart/values-kind.yaml`, por `kind_values`); staging y prod siguen en los 256 MiB de INF-U11-01 y los limits (512 MiB), las réplicas, el PDB y la exención no cambian en kind. **Se aparta de «kind igual a staging»** de `deployment-architecture.md`, solo en ese request y por decisión del usuario (mismo patrón que la opción (c) de `DECISIONES-LOOP.md` §7 para U6). La memoria real del pod con 2 000 decisiones se comprueba en U12.
- **P-2 = (a), por omisión:** entran los cuatro runbooks de las alertas; se difiere `product-metrics-parameter-change`.
- **P-3 = (a), por omisión:** el chart no declara `Server` ni `AuthorizationPolicy`; «8081 solo para Prometheus» se comprueba sobre lo que U1 genera (`platform/network/generated/<env>/vectra-app.yaml`, `Server` `metrics-8081`).
- **P-4 = (a), por omisión:** los archivos canónicos son los de `observability/`; el chart lee copias de `chart/files/` con comprobación de igualdad (`gen_rules.py --check`, `make rules` y una prueba de bytes).
- **P-5 = (a), por omisión:** NFR-U11-13 se traza en el chart (requests y limits); su **medición** con 10 veces el volumen queda «no comprobado» (abajo).
- **P-6 = (a), por omisión:** se quitó `capture_signals`; el código de salida 0 lo da el manejador del bucle y las pruebas del proceso real y de la imagen lo fijan.
- **Cuatro alertas y no tres:** el texto del Paso 12 nombra tres alertas en su paréntesis, pero su aceptación exige exactamente cuatro `alertname`, P-U11-06 y BR-U11-14 listan cuatro y el Paso 13 pide el runbook `product-metrics-degraded`. Entran las cuatro (`RuidoExplicacion`, `ProductMetricsDegraded`, `ProductMetricsStale`, `ProductMetricsFullRecomputeMissing`; seis reglas). Las dos por réplica llevan la etiqueta `branch` (`edad`, `ausencia`) porque `promtool` rechaza como duplicadas dos reglas con el mismo nombre y las mismas etiquetas.
- **No comprobado (NFR-U11-13):** la medición de la memoria y la CPU con 10 veces el volumen no se hizo (la prueba de volumen está diferida, T3). Lo que sí hay es el dato de la imagen: 54,75 MiB tras la primera pasada con las entradas de prueba. NFR-U11-13 está trazado por sus requests y limits en el chart, sin fila en la lista de diferidos.

## Pendiente en U12

Lo que verifica U12 Paso 18 (enmienda §8), más el push de la imagen:

| Punto | Qué verifica U12 |
|---|---|
| Escenario 5 del Paso 16: North Star, sostenida, tasa de consulta y `ProductMetricsStale` con datos reales | El día siguiente a las 2 000 decisiones (BR-U12-06). Los periodos excluyen el día en curso y son días **UTC** |
| Escenario 4: permisos de `Vectra / Producto` con los usuarios de U2 | Solo si el presentador usa `cro-1` o `cumplimiento-1` |
| Escenario 1: conectividad mínima | F28, F50, F60 y los tres casos bloqueados; el `/readyz` del kubelet |
| Push de la imagen y digest real | `product-metrics/docs/imagenes.md`: `docker push` y el digest en `vectra-risk-gitops/values/kind/product-metrics.yaml`, más `generate.py` |
| `ExternalSecret` de la llave | Que ESO materialice `product-metrics-client` desde `identity/clients/product-metrics` de la bóveda de kind |
| `PrometheusRule` y dashboard | Que Prometheus cargue la `PrometheusRule` de `vectra-app` y Grafana descubra el `ConfigMap` del dashboard (etiqueta `vectra.io/dashboard`, carpeta `Vectra / Producto`) |
| Memoria real del pod con 2 000 decisiones (NFR-U11-13 «kind a 1 vez») | Frente al request de kind de P-1 (128 MiB); el dato de la imagen es 54,75 MiB con las entradas de prueba |
| **Orden de arranque en la wave 5** | Si `product-metrics` arranca antes de que `decision-registry-service` responda, la primera pasada falla y el siguiente intento es a los 15 min (`process.md`, P-1 (a) y P-2 (b) de U11-T02): **el dashboard queda vacío hasta entonces y `/readyz` da 503 hasta 30 min.** El operador debe saberlo antes de D4 |

## Diferido por la demo

Lista que acepta `platform/tests/test_traceability.py --unit product-metrics --all` (P-4, `demo-recorte-funcional.md` §2.4 y §6). Cada fila lleva el identificador, el paso del plan que lo implementaría y la cita del recorte. Un identificador de esta lista no puede tener código ni prueba: la herramienta falla si ya lo tiene.

| Identificador | Paso del plan | Cita del recorte | Qué falta |
|---|---|---|---|
| NFR-U11-02 | Paso 7 (prueba de volumen, `-m volume`) | Enmienda §3 U11, fila «7», y §2 regla 3; T3 | La prueba de volumen de la lectura completa |
| NFR-U11-03 | Paso 7 (benchmark de `compute` con el volumen × 10) | Enmienda §3 U11, fila «7», y §2 regla 3; T3 | El benchmark de `compute` con el volumen × 10 |

Lo diferido sin identificador propio (no lo mira la herramienta; cada uno con su destino):

| Qué | Paso del plan | Cita del recorte | Destino |
|---|---|---|---|
| Workflow de CI (`.github/workflows/product-metrics.yml`, `actionlint`, el disparador `contracts/**`, el workflow nocturno) | Paso 14 | T4; alcance §3 U11, fila 14 | Fuera de la demo. Las comprobaciones corren en `make -C product-metrics check` |
| `mutmut` en `compute` y `noise` | Paso 5 | T3 | Fuera de la demo |
| Prueba de volumen con la medición de NFR-U11-13 (volumen × 10) | Paso 7 | T3 | Fuera de la demo (NFR-U11-13 está trazado por el chart; su medición va en «No comprobado») |
| Firma de la imagen, SBOM y escaneo (y la frase de la aceptación sobre el SBOM) | Paso 10 | T1; alcance §3 U11, fila 10 | Fuera de la demo; la imagen va fijada por digest, sin firmar |
| Runbook `product-metrics-parameter-change` | Paso 13 | T2; enmienda §3 U11, fila 13, y §6 P-3 (P-2 = a) | Fuera de la demo. El README dice que el cambio de parámetros es un PR sobre `values-product-metrics-policy.yaml` con la aprobación de producto y riesgo |
| Escenarios 2 (E1 a E8) y 3 (rollouts) del Paso 16 | Paso 16 | Enmienda §3 U11, fila 16 | Fuera de la demo; los que entran (1, 4 y 5) los verifica U12 (arriba) |
| Reconciliar INF-U11-01 («unos 15 s» con U3 caído al arrancar) con NFR-U11-09 (30 min) | Diseño de U11 | `CANDIDATAS.md` (U11-T02, P-1 a) | Antes del rollout con U3 caído. El README describe lo que el código hace (30 min) |
| Perfil de 1 réplica (`values-kind-demo.yaml`) | Paso 11 | T6; DD-3 b | Descartado: kind mantiene las 2 réplicas fijas |
