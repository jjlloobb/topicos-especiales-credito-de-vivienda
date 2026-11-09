# Alcance de la demo en kind (U2–U12)

**Estado: APROBADO por el usuario el 2026-11-08**, con las recomendaciones de DD-1 a DD-4 (sección 5).
Levanta la restricción de código de `aidlc-state.md` para U3–U12, con este alcance.

**Enmienda del 2026-11-09:** `demo-recorte-funcional.md`, aprobada por el usuario, afina la tabla de §3 con un recorte por funcionalidad (E\*F), amplía RL-1 (P-2) y adelanta U9 A+B en paralelo con U4. Donde las dos difieran, rige la enmienda.

## 1. Qué es «la demo»

La sustentación de la sesión 16 (`entradas/prd.md` §13), corrida en `kind-vectra` en esta máquina
(8 vCPU, 14 GiB), con el código de todas las unidades:

| # | Demo | Guion de U12 (BR-U12-09) | Unidades que la sostienen |
|---|---|---|---|
| 1 | Journey 7.3: desincronía forzada y fail-closed | `journey-7-3.md` (RT-3) | U2, U3, U4, U5 (paquetes RT3), U6, U7, U8, U10 |
| 2 | Journey 7.4: freeze automático, paquete de contexto y resolución de cumplimiento con MFA | `journey-7-4.md` (RT-2) | U2, U3 (agregador), U4, U5 (proxy), U6, U7, U8, U9, U10 |
| 3 | Red-teaming #5: escritura al estado de crédito bloqueada | `rt-5.md` | U1 (Linkerd, alertas), U8 (`core-banking-mock`, Job `rt5-demo`) |
| 4 | Dashboard: North Star y ruido | `dashboard.md` | U3 (proyección `metrics`), U11, U12 (2 000 casos decididos) |

El flujo base que alimenta las cuatro: solicitud por el gateway → `scoring-service` (U7) → modelo de
referencia en KServe (U5, U6) con `serving-config` de U4 → registro (U3) → caso (U8) → decisión del
analista en la consola (U10).

## 2. Reglas del recorte

1. **Lo que entra, entra completo.** Un paso marcado **E** se implementa con el alcance y la aceptación
   del plan de la unidad, sin cambios ([[implementar-segun-unidades]]). Las pruebas de propiedades
   (PBT) nunca se recortan: la extensión es bloqueante.
2. **E\*** = el paso entra con un recorte **nombrado** en la columna «Se difiere». Lo que no se nombra
   entra.
3. **D** = el paso entero se difiere al cierre completo de la unidad (staging, Operations o una
   máquina de ≥ 32 GiB). No se marca `[x]` en el plan; queda `[ ]` con la nota «diferido por la demo».
4. Cada unidad cierra como U1: **cierre acotado a la demo**, con un `evidence/cierre-demo.md` que
   lista lo comprobado, lo diferido y su destino. El plan de la unidad no se reescribe.
5. AUTONOMIA-01 sigue vigente: cada tarea es un PR que fusiona una persona; lo que toca el clúster lo
   ejecuta el operador tras un PR aprobado.

### Recortes transversales

| Id | Recorte | Por qué | Destino |
|---|---|---|---|
| T1 | Firma Cosign, SBOM y attestations de imágenes y paquetes. Las imágenes se construyen y se publican **por digest** en `kind-registry` | `verify-images` no se instala en kind (cierre acotado de U1); Kyverno sigue rechazando `latest` | Staging, con la llave real |
| T2 | Alertas y runbooks, salvo los que lee una demo: `CoreWriteAttempt` (U8) y las reglas generadas de U11 | La demo no las dispara; el resto es operación | Cierre completo |
| T3 | Especificaciones de carga, benchmarks, k6 y pruebas de mutación | No caben en 14 GiB (U12 Paso 11) y no las pide la sustentación | Máquina ≥ 32 GiB u Operations |
| T4 | Workflows de CI propios de cada unidad. Las pruebas corren con el `make check` de la unidad, en la aceptación de cada tarea y en el CI del monorepo que ya exista | Ahorra pasos sin quitar pruebas | Cierre completo |
| T5 | Jobs operativos que ninguna demo usa: retención, archivo, verificación de cadena programada, reconstrucción y sondas X04/X06 | Fuera de las cuatro demos | Cierre completo / U12 X01–X10 |
| T6 | Perfil de recursos «demo»: 1 réplica por servicio, HPA apagado, `InferenceService` con mínimo 1 | 14 GiB. U1 ya usa ≈ 5,5 GiB | Ver la decisión DD-3 |

## 3. Tabla por unidad

### U2 `identity-edge` (Pasos 1–11 y 13 ya hechos)

| Paso | Estado | Se difiere |
|---|---|---|
| 12 Applications de GitOps | E | — |
| 14 Especificación de la prueba de carga | D | T3 |
| 15 Resumen del código | E | — |
| 16 Puerta de aprobación, instalación y pruebas en kind | E | — |
| 17 Repositorio, migraciones y frontend: N/A | N/A | — |
| 18 Cierre | E\* | Cierre acotado a la demo |

### U3 `decision-registry`

| Paso | Estado | Se difiere |
|---|---|---|
| 1 Esqueleto | E | — |
| 2 Migraciones de `registry-db` | E | — |
| 3 `chain` · 4 `verify` · 5 `projections` · 6 Resumen | E | — |
| 7 Append | E | — |
| 8 Proyecciones, expediente y verificación bajo demanda | E | — |
| 9 Readiness y contratos de rutas · 10 Resumen | E | — |
| 11 CLI `vectra-registry` | E | — |
| 12 CronJobs, identidades y políticas de la bóveda | E\* | Entran el CronJob `registry-aggregator` (lo usa U9 para el freeze), las ServiceAccounts y las políticas HCL. Se difieren `registry-checkpoint`, `registry-verify-*`, `registry-archive`, `chart-rebuild/` y `x06-probe` (T5) |
| 13 Chart, buckets y flujos | E\* | Perfil demo (T6) |
| 14 Alertas y runbooks | D | T2 |
| 15 Applications de GitOps | E | — |
| 16 Cobertura, mutación y trazabilidad | E\* | Mutación (T3) |
| 17 Benchmarks y especificación de carga | D | T3 |
| 18 Verificación en kind | E\* | Solo los escenarios que usan las demos; el resto pasa a `cierre-demo.md` |
| 19 Frontend: N/A · 20 Cierre | N/A · E\* | Cierre acotado |

### U4 `governance`

| Paso | Estado | Se difiere |
|---|---|---|
| 1 Esqueleto · 2 Migraciones | E | — |
| 3 `model_fsm` · 4 `policy` · 5 `serving_config` · 6 `registration` · 7 Resumen | E | — |
| 8 Evidencia en dos fases, reconciliador y barridos | E | — |
| 9 `serving-config` en memoria, convergencia y pools | E | — |
| 10 Endpoints · 11 Resumen | E | — |
| 12 `promotion-tool` | E | — (despliega por PR el `InferenceService` de RT-2 y RT-3) |
| 13 `model-validation-job` | E | — (RT-3b `validacion_fallida`; validación de RT-2) |
| 14 Scripts de CI | D | T4 |
| 15 `model-archive` | D | T5 |
| 16 Chart, flujos y RBAC | E\* | Perfil demo (T6) |
| 17 Alertas, runbooks y documentación | E\* | Alertas y runbooks (T2); la documentación entra |
| 18 Application de GitOps | E | — |
| 19 Cobertura, mutación, trazabilidad y carga | E\* | Mutación y carga (T3) |
| 20 Verificación en kind | E\* | Solo los escenarios de las demos |
| 21 Frontend: N/A · 22 Cierre | N/A · E\* | Cierre acotado |

### U5 `reference-model`

| Paso | Estado | Se difiere |
|---|---|---|
| 1 Esqueleto · 2 Configuración y generador | E | — |
| 3 Entrenamiento · 4 Envolvente y `confidence` · 5 Empaquetado | E | — |
| 6 Variante proxy | E | — (se generan las 5 versiones; cuántas corre la demo es DD-1) |
| 7 Conjunto adversarial | E | — (paquetes RT3 a–d; pares RT-1 y casos RT-4 se generan aunque su sección se difiera) |
| 8 Workflow de entrega y release firmada | D | T1, T4 |
| 9 Procedimiento de entrega al model-store | E\* | Sin descargar la release ni `cosign verify`: `make release` local, verificación de cada SHA-256 del manifiesto y subida al MinIO de kind (T1) |
| 10 Cobertura, trazabilidad y resumen | E | — |
| 11 N/A · 12 Cierre | N/A · E\* | Cierre acotado |

### U6 `model-serving`

| Paso | Estado | Se difiere |
|---|---|---|
| 1 Esqueleto | E | — |
| 2 Cargador y concurrencia · 3 Predictor · 4 Explicador | E | — |
| 5 Dockerfiles y cadena de suministro | E\* | Firma y SBOM (T1) |
| 6 Plantilla del `InferenceService` · 7 Integración con `promotion-tool` · 8 Flujos | E | — |
| 9 Alertas y runbooks | D | T2 |
| 10 Applications, cobertura y trazabilidad | E | — |
| 11 Verificación en kind | E\* | Solo los escenarios de las demos |
| 12 N/A · 13 Cierre | N/A · E\* | Cierre acotado |

### U7 `scoring-explainability`

| Paso | Estado | Se difiere |
|---|---|---|
| 1 Esqueleto · 2 Presupuestos | E | — |
| 3 `policy` · 4 `narrative` · 5 `factuality` · 6 `applicant` · 7 Resumen | E | — |
| 8 `POST /v1/explanations` · 9 `POST /v1/applicant-summaries` | E | — |
| 10 Clientes y caché de `serving-config` · 11 `orchestrator` · 12 Endpoints · 13 Resumen | E | — |
| 14 Dockerfiles y cadena de suministro | E\* | T1 |
| 15 Chart, cuota y flujos | E\* | T6 |
| 16 Alertas y runbooks | D | T2 |
| 17 Applications, carga y trazabilidad | E\* | Carga (T3) |
| 18 Verificación en kind | E\* | Solo los escenarios de las demos |
| 19 N/A · 20 Cierre | N/A · E\* | Cierre acotado |

### U8 `case-management`

| Paso | Estado | Se difiere |
|---|---|---|
| 1 Esqueleto · 2 Constantes · 3 Migraciones de `case-db` | E | — |
| 4 `case_fsm` · 5 `backoff` · 6 `decision` · 7 `views` · 8 Resumen | E | — |
| 9 `intake` · 10 `evidence` · 11 `sweeps`, `retry`, `db_gauges` · 12 `credit` · 13 API | E | — |
| 14 Clientes y caché de gobierno · 15 `job_queue`, `evaluation` y `worker` | E | — |
| 16 CLI `case-retention` | D | T5 |
| 17 `core-banking-mock` | E | — (RT-5) |
| 18 Resumen | E | — |
| 19 Dockerfiles y cadena de suministro | E\* | T1 |
| 20 Chart, values, cuotas y flujos | E\* | T6; el Job `rt5-demo` entra |
| 21 Alertas y runbooks | E\* | Solo `CoreWriteAttempt`; el resto T2 |
| 22 Documentación | E | — |
| 23 Applications, carga y trazabilidad | E\* | Carga (T3) |
| 24 Verificación en kind | E\* | Solo los escenarios de las demos |
| 25 N/A · 26 Cierre | N/A · E\* | Cierre acotado |

### U9 `bias-monitoring`

| Paso | Estado | Se difiere |
|---|---|---|
| 1 Esqueleto · 2 Constantes | E | — |
| 3 `stats` · 4 `counts` y `disparity` · 5 Resumen y simulación | E | — |
| 6 `window`, `freeze_rule`, `context` · 7 Clientes y `publish` · 8 `run` | E | — |
| 9 `dashboard`, `freezes`, `compare` y la app · 10 Resumen | E | — |
| 11 Dockerfile y cadena de suministro | E\* | T1 |
| 12 Chart, parámetros, cuota y flujos | E\* | T6; `x04-probe` (T5) |
| 13 Alertas, runbooks y dashboard | D | T2; la vista de sesgo la da la consola (U10 Paso 14) |
| 14 Applications, carga y trazabilidad | E\* | Carga (T3) |
| 15 Workflow de CI | D | T4 |
| 16 Verificación en kind | E\* | Solo los escenarios de las demos |
| 17 N/A · 18 Cierre | N/A · E\* | Cierre acotado |

### U10 `console`

| Paso | Estado | Se difiere |
|---|---|---|
| 1 Esqueleto · 2 Constantes | E | — |
| 3 `object_rules` y `errors` · 4 Resumen | E | — |
| 5 Rutas, clientes y composición · 6 `client_errors` y métricas · 7 Matriz rol × endpoint · 8 Arranque y resumen | E | — |
| 9 Repositorio: N/A | N/A | — |
| 10 Prueba de concepto del step-up | E | — (puerta de 11–15; la reactivación con MFA es parte de 7.4) |
| 11 `auth`, `stepup`, `inactivity` · 12 `api`, `i18n`, `reporter`, `version` | E | — |
| 13 Vistas de casos · 14 Vistas de gobierno y sesgo | E | — |
| 15 CSP, accesibilidad y e2e con dobles | E | — |
| 16 Resumen del frontend · 17 Imágenes | E · E\* | T1 en el 17 |
| 18 Chart, cuotas y flujos | E\* | T6 |
| 19 Alertas, runbooks y dashboard | D | T2 |
| 20 Workflows de CI y de release | D | T4 |
| 21 Applications, carga y trazabilidad | E\* | Carga (T3) |
| 22 Verificación en kind | E\* | Solo los escenarios de las demos |
| 23 Documentación · 24 Cierre | E · E\* | Cierre acotado |

### U11 `product-metrics`

| Paso | Estado | Se difiere |
|---|---|---|
| 1 Esqueleto · 2 Constantes | E | — |
| 3 `model`, `compute`, `noise` · 4 `state`, `reader` · 5 Resumen | E | — |
| 6 `scheduler`, `collector`, `main` · 7 Pruebas del proceso y de volumen · 8 Resumen | E | — |
| 9 N/A | N/A | — |
| 10 Imagen | E\* | T1 |
| 11 Chart, cuotas y flujos | E\* | T6 |
| 12 Reglas generadas y alertas | E\* | Las reglas generadas entran (calculan North Star y `RuidoExplicacion`); las alertas, T2 |
| 13 Dashboards y runbooks | E\* | Los dashboards entran (demo 4); los runbooks, T2 |
| 14 Workflow de CI | D | T4 |
| 15 Application y trazabilidad | E | — |
| 16 Verificación en kind | E | — |
| 17 Documentación · 18 Cierre | E · E\* | Cierre acotado |

### U12 `system-verification`

| Paso | Estado | Se difiere |
|---|---|---|
| 1 Esqueleto · 2 Barrera de entorno y credenciales | E | — |
| 3 `sampler`, `rt2_latency`, `story_map`, `report` · 4 Resumen | E | — |
| 5 Clientes de lectura y del gateway (login headless) | E | — |
| 6 Simulador y conductor | E | — (2 000 casos `normal`: alimentan el dashboard) |
| 7 RT-1 y RT-4 | D | No es demo de la sustentación; los datos de U5 quedan listos |
| 8 RT-2, RT-3 y RT-5 | E\* | RT-2 con el número de versiones de DD-1 |
| 8b Sección `resilience` | D | Operations (RESILIENCY-14) |
| 9 X01–X10 | D | T5 |
| 10 `SIM-NORMAL`, `LOGS-NO-PII`, `CASE-SIZE` | E\* | `CASE-SIZE` se difiere |
| 11 Carga (US-609) | D | T3 |
| 12 Demos (cuatro guiones, `verify/*.sh`, PRs preparados) | E | — |
| 13 CLI, manifiesto y `CODEOWNERS` | E\* | Secciones: `prepare`, `decisions`, `rt5`, `rt3`, `rt2-setup`, `rt2`, `pii`, `u11`, `report`. Las demás quedan registradas como `no ejecutado` (BR-U12-11) |
| 14 N/A · 15 Imagen | N/A · E\* | T1 |
| 16 Workflow de CI | D | T4 |
| 17 Documentación y trazabilidad | E | — |
| 18 Primera verificación completa en kind | E\* | Con las secciones del Paso 13 |
| 19 Cierre | E\* | Cierre acotado |

## 4. Orden y tamaño

Ruta crítica: U2 (cierre) → U3 → U4 → U6 → U7 → U8 → U9 → U10 → U11 → U12. U5 solo depende de U0 y
U1, así que puede ir en paralelo con U3 y U4.

| Unidad | Pasos E | Pasos E\* | Pasos D |
|---|---|---|---|
| U2 | 3 | 1 | 1 |
| U3 | 12 | 5 | 2 |
| U4 | 14 | 5 | 2 |
| U5 | 8 | 2 | 1 |
| U6 | 8 | 3 | 1 |
| U7 | 13 | 5 | 1 |
| U8 | 18 | 6 | 1 |
| U9 | 10 | 5 | 2 |
| U10 | 16 | 5 | 2 |
| U11 | 11 | 5 | 1 |
| U12 | 8 | 6 | 5 |
| **Total** | **121** | **48** | **19** |

Un paso ≈ una tarea del loop, salvo los resúmenes (unos 14), que van en la tarea del bloque
anterior. El loop de U2 llevó 16 tareas para 13 pasos, con 2 a 4 rondas cada una. La demo pide del
orden de **150 a 190 tareas**. El recorte quita 19 pasos y aligera 48; el grueso es el código de los
servicios, que entra completo.

## 5. Decisiones del usuario (aprobadas el 2026-11-08: la recomendación en cada una)

| Id | Pregunta | Recomendación |
|---|---|---|
| DD-1 | ¿RT-2 corre las 5 versiones del proxy o 1? Cada versión es un `InferenceService` más y ≈ 30 min de corrida | **1 en la demo**; U5 genera las 5 igual, y el cierre completo corre las 5 |
| DD-2 | ¿Se aceptan los recortes T1–T5? | Sí |
| DD-3 | ¿Cómo se define el perfil demo (T6)? Opción a: un `values-kind-demo.yaml` por chart, que es un cambio del Infrastructure Design de cada unidad. Opción b: solo los values de kind existentes, y se mide | **b primero**: medir la memoria con U1 + U2 al cerrar el Paso 16 de U2, proyectar por unidad y pasar a la a solo si no cabe |
| DD-4 | ¿Se levanta la restricción de código para U3–U12 con este alcance? | Sí, al aprobar este documento |

## 6. Ritmo del loop para la demo (decisión del usuario, 2026-11-08)

U02-T17, un paso pequeño, costó unas 12 horas, 3 rondas, 2 revisiones de código y 2 PR. A ese ritmo, los
≈ 170 pasos de la demo no son viables. Desde U02-T18 rige:

| Id | Regla |
|---|---|
| RL-1 | **Una tarea por bloque** del plan de la unidad (A, B, C…), no por paso. Bloques contiguos pueden juntarse en una tarea, hasta unos 6 pasos con código; la fusión de cada unidad está en `demo-recorte-funcional.md` §4 (enmienda P-2, 2026-11-09). El alcance y la aceptación de cada paso, con el recorte E\*F de la enmienda, se copian sin más recortes |
| RL-2 | **Máximo 2 rondas** por tarea. Solo un ROJO bloquea. NARANJA y AMARILLO van a `CANDIDATAS.md`, salvo que rompan una de las cuatro demos (§1). Si tras la ronda 2 queda un ROJO, decide el usuario |
| RL-3 | **Sin revisión de código adicional** después de un VERDE, salvo que el usuario la pida |
| RL-4 | Cada tarea corre el `make check` **de su unidad** y las pruebas de U1 que su diff toque. El `make check` de todas las unidades corre una vez, al cerrar la unidad |
| RL-5 | **Hasta 3 codificadores en paralelo**, en unidades independientes. Una unidad puede empezar su código estático (lógica, pruebas con dobles, charts) aunque la unidad de la que depende en runtime no haya cerrado su verificación en kind; la verificación en kind sí sigue el orden de la ruta crítica (§4) |

Lo que no cambia: la tabla de §3, la regla de no recortar pasos E, PBT siempre, AUTONOMIA-01 y que cada PR lo
fusiona una persona.
