# Requisitos no funcionales — U7 `scoring-explainability`

Decisiones del plan (`scoring-explainability-nfr-requirements-plan.md`, Q1–Q5 = A). Las
verificaciones «en kind» las ejecuta el operador después de un PR aprobado (AUTONOMIA-01);
las demás corren en CI.

Los IDs `NFR-U7-xx` se referencian en NFR Design, Infrastructure Design y el plan de tareas.

---

## 1. Rendimiento (Q1; NFR-PER-01)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U7-01 | `POST /v1/recommendations`, de punta a punta en scoring: **p95 ≤ 400 ms** y **p99 ≤ 1 s** a 10 solicitudes/s. Fija la latencia que NFR-PER-01 dejó **[INTERNO]** | Prueba de carga en kind (U12, operador) con el reporte adjunto al PR |
| NFR-U7-02 | `POST /v1/explanations`: **p95 ≤ 250 ms** | Misma prueba |
| NFR-U7-03 | `POST /v1/applicant-summaries`: **p95 ≤ 500 ms** | Misma prueba |
| NFR-U7-04 | Una solicitud que termina en `FailClosed` por timeout o por circuito abierto de **KServe, explainability o `serving-config`** responde dentro del p99 (≤ 1 s). Con el **registro** degradado la respuesta puede llegar a ~6,1 s (2 intentos de 2,5 s, P-U7-02) y queda fuera del p99, con la alerta `RegistryAppendSlow` (precisado el 2026-10-03 por U7 NFR Design Q2) | Prueba de integración con dependencias lentas simuladas; propiedad de P-U7-01 |

## 2. Resiliencia (Q2; RESILIENCY-10, NFR-RES-11)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U7-10 | Timeouts por llamada: `serving-config` 500 ms; `:predict` 300 ms; explainability 800 ms; `:explain` 500 ms; diccionario 500 ms; registro 2,5 s. Son **máximos**: rige el menor entre ese y el presupuesto restante (700 ms previos al registro en scoring; `x-vectra-deadline` en explainability, que llama al diccionario y a `:explain` en paralelo; P-U7-01) (precisado el 2026-10-03 por U7 NFR Design Q1) | `conftest`/prueba unitaria sobre la configuración de los clientes; con dobles lentos, cada llamada corta en su timeout |
| NFR-U7-11 | Circuit breaker por dependencia: se abre con ≥ 50 % de fallos en las últimas 20 llamadas dentro de 30 s y pasa a semiabierto a los 10 s. Abierto → fail-closed inmediato con la causa de esa dependencia (`timeout`, `explainer_unavailable`, `serving_config_unavailable` o `registry_unavailable`), sin llamar | Propiedad stateful del circuit breaker de U0 (P-U0-07) + prueba de integración: con explainability caído, tras 20 llamadas el circuito se abre y las respuestas son `FailClosed` en < 50 ms |
| NFR-U7-12 | Sin reintentos dentro de scoring, salvo un reintento del append al registro con la misma `idempotency_key` dentro del presupuesto (BR-U7-15); los demás reintentos los hace el caso (U8) | Prueba con un doble del registro que falla una vez: dos llamadas y una sola entrada |
| NFR-U7-13 | Ningún modo degradado: un circuito abierto o una dependencia caída nunca produce una recomendación sin explicación sincronizada ni sin registro (AUTONOMIA-06) | PBT-U7-07 |

## 3. Disponibilidad y escalado (Q3)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U7-20 | Cada servicio con ≥ 2 réplicas repartidas por zona, PDB y HPA de 2 a 6 por CPU al 70 % | `helm template` + `conftest` |
| NFR-U7-21 | Readiness solo con el proceso (P-U1-04). explainability precarga el diccionario de la versión activa al arrancar si governance responde; si no, lo pide en la primera solicitud | Prueba de arranque con governance caído: el pod queda listo y la primera explicación pide el diccionario |
| NFR-U7-22 | Servicios sin estado: cualquier réplica atiende cualquier solicitud | Prueba de carga con réplicas que se reinician durante la prueba |

## 4. Seguridad

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U7-30 | Sin egress (X02) ni cliente o permiso hacia el core bancario (X01) | AUTONOMIA-03, 05 | Suite de conectividad de U1; prueba estática: ningún cliente HTTP con la URL del core |
| NFR-U7-31 | Logs y métricas sin datos del solicitante: métricas por `outcome`, `cause` y `reason` (cardinalidad acotada), nunca con `case_id` como etiqueta | AUTONOMIA-05, SECURITY-03 | PBT-U0-07 (allowlist) + prueba de las etiquetas de las métricas |
| NFR-U7-32 | Las plantillas (`template:v1`, `applicant:v1`) son archivos versionados de texto; no hay generación por LLM en el MVP (FR-EXP-06 solo como interfaz) | FR-EXP-03, 06 | Prueba que verifica que `NarrativeGenerator` tiene una sola implementación registrada en el MVP |

## 5. Calidad de pruebas (Q4, Q5)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U7-40 | Cobertura de ramas ≥ 95 % en los dos servicios y **100 %** en `policy`, `narrative`, `factuality` y `orchestrator` | `pytest --cov --cov-branch` + umbral por módulo |
| NFR-U7-41 | Mutation testing con `mutmut` en `policy` y `factuality`: 0 sobrevivientes sin justificar | `mutmut run` en el job nocturno y en los PR que tocan esos módulos |
| NFR-U7-42 | PBT-U7-01..08 con el perfil `ci` (500 ejemplos, semilla impresa) | `HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests/property` |
| NFR-U7-43 | El circuit breaker es el de `vectra_common.deps` (U0), no uno propio de U7 | Contrato de import-linter: U7 no importa librerías de circuit breaking |

## 6. Cumplimiento de extensiones (NFR Requirements U7)

Revisada contra el cuerpo del documento antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-01 / 02 | Cumple | NFR-U7-01 (latencia de la ruta crítica dentro del SLO de U1) |
| RESILIENCY-06 | Cumple | NFR-U7-21 |
| RESILIENCY-08 / 09 | Cumple | NFR-U7-20, 22 |
| RESILIENCY-10 | Cumple | NFR-U7-10, 11, 12 |
| AUTONOMIA-02 | Cumple | Cada requisito tiene su verificación |
| AUTONOMIA-03 | Cumple | NFR-U7-30 |
| AUTONOMIA-05 | Cumple | NFR-U7-30, 31 |
| AUTONOMIA-06 | Cumple | NFR-U7-13 |
| SECURITY-03 | Cumple | NFR-U7-31 |
| SECURITY-15 | Cumple | NFR-U7-04, 11, 13 (fail-closed inmediato y acotado en tiempo) |
| PBT-06 | Cumple | Propiedad stateful del circuit breaker (U0, NFR-U7-11) |
| PBT-08 / 09 | Cumple | NFR-U7-42 |

## 7. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio |
|---|---|
| U0 NFR Design P-U0-07 | El circuit breaker vive en `vectra_common.deps`, con propiedad stateful (antes, responsabilidad de cada servicio) |
| U0 plan de tareas, Paso 10 | `deps.py` incluye el circuit breaker y su propiedad stateful |
| `requirements.md` NFR-PER-01 | Latencia fijada en NFR-U7-01 |
