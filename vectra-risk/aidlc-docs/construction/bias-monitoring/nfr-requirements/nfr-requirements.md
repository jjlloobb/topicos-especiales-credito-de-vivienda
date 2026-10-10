# NFR Requirements — U9 `bias-monitoring`

Decisiones del plan (`bias-monitoring-nfr-requirements-plan.md`): Q2, Q3, Q4, Q5, Q6 y Q9 = A;
Q1, Q7 y Q8 = A con ajustes del usuario. Los IDs `NFR-U9-xx` se referencian en NFR Design,
Infrastructure Design y el plan de tareas. Las verificaciones en kind las ejecuta el operador
después de un PR aprobado (AUTONOMIA-01).

Procesos: el **CronJob** de cálculo (cliente `bias-monitoring-job`), el **servicio HTTP**
`bias-monitoring-service` y la librería **`vectra_disparity`**.

---

## 1. Rendimiento

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U9-01 | **Corrida y detección** (Q1): una corrida (lectura, cálculo de todas las versiones evaluadas, `freeze` si corresponde y push) dura **p95 ≤ 2 min** y como máximo 10 min (`activeDeadlineSeconds: 600`, por debajo del intervalo de 15 min). **Latencia de detección** (del `recorded_at` de las entradas que llevan la agregada sobre el umbral hasta `congelado`): **p95 ≤ 30 min**, ≈ 27 min en el caso típico = atraso p95 del agregador de U3 ≤ 10 min (NFR-U3-24) + 15 min de intervalo + 2 min de cálculo + 6 s de propagación (BR-U4-14). Con el peor caso de la corrida (≈ 186 s, P-U9-02) la cuenta sube a **≈ 28 min**, así que el margen es de unos 2 min (segunda revisión del Infrastructure Design de U10, 2026-10-10). Si RT-2 mide un p95 > 28 min, el plan es bajar el intervalo a 10 min (admitido por INF-U9-03) antes que subir el objetivo, y se registra en el PR | Prueba de integración con dobles: duración de la corrida con 3 versiones y celdas densas; en kind, la demostración RT-2 de U12 mide la latencia de detección |
| NFR-U9-02 | **Latencia de la API** (Q2), con 10 usuarios de consola concurrentes: `GET /v1/disparity` con caché caliente p95 ≤ 200 ms y sin caché (90 días, una versión) p95 ≤ 2 s; `GET /v1/freezes` y `GET /v1/freezes/{id}` p95 ≤ 500 ms; `POST /v1/source-comparisons` p95 ≤ 1 s | Script k6 en kind (operador) |
| NFR-U9-03 | **Timeouts explícitos** en toda llamada con `vectra_common.deps.call`: F26 (registro), F27 (`freeze`) y el push a F106. Sus valores, dentro del presupuesto de NFR-U9-01, se fijan en NFR Design | Contrato de U0: `call` sin timeout no compila; prueba de integración por dependencia con un doble lento |
| NFR-U9-04 | **Recursos del CronJob** (Q9): requests 100m / 128 MiB y limits 500m / 256 MiB iniciales; una prueba mide el pico de memoria y el tiempo de una corrida con 3 versiones y celdas densas, y si el pico supera el 70 % del límite se ajusta en el Infrastructure Design | Prueba de integración con medición de memoria (CI) |

## 2. Disponibilidad y escalado

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U9-10 | **Criticidad por proceso** (Q3): el CronJob es **High** (`vectra-high`); el servicio HTTP es **Medium** (`vectra-normal`). La caída del servicio deja sin dashboard ni `compare_source`, pero no detiene el monitoreo ni el congelamiento | `helm template` + `conftest` (`priorityClassName` por proceso) |
| NFR-U9-11 | **Servicio HTTP con 2 réplicas fijas, sin HPA** (Q4), repartidas por zona y con PDB `minAvailable: 1`. Carga baja: pocos usuarios de cumplimiento y CRO, y `compare_source` ocasional; la caché de 15 min absorbe las consultas repetidas. Exento de `require-hpa-bounds` con la anotación `vectra.io/hpa-exempt` y esta justificación (NFR-U1-12) | `kyverno test` de U1 con la exención; prueba de carga con 10 usuarios: 2 réplicas sobran (CPU < 50 %) |
| NFR-U9-12 | **Readiness del servicio**: solo el proceso (no tiene base propia, P-U1-04). Con el registro caído, la consulta responde 503 sin datos parciales | Prueba de arranque con el registro caído: los pods quedan `Ready` y la consulta da 503 |
| NFR-U9-13 | **Una sola corrida a la vez**: `concurrencyPolicy: Forbid` y `backoffLimit: 0` (una corrida fallida no se repite; la siguiente llega a los 15 min); nunca dos `freeze` en paralelo desde U9 | `helm template` + `conftest` |

## 3. Resiliencia

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U9-20 | **Escenarios de resiliencia** (Q8, RESILIENCY-14 = C): E1 registro caído; E2 agregador de U3 atrasado más de 30 min; E3 governance caído durante un congelamiento; E4 Pushgateway caído; E5 el pod del CronJob muere a mitad de corrida (sin `freeze` con datos parciales; un `freeze` ya aplicado a una versión antes de morir se mantiene, y la corrida siguiente evalúa las demás); E6 modelo proxy (RT-2); **E7 Keycloak caído**: el CronJob no obtiene token (F50), la corrida falla antes de congelar, `MonitoreoSesgoDetenido` a 1 h y el modelo sigue sirviendo. Resultados esperados en NFR Design | Prueba de integración en CI de E1, E3, E4, E5 y E7; E2 y E6 en kind (operador) |
| NFR-U9-21 | **Corrida todo o nada** (BR-U9-10): nunca congela con datos parciales ni con conteos atrasados, y no actualiza `vectra_bias_last_success_timestamp` si falla | PBT-U9-05 |
| NFR-U9-22 | **Reintentos acotados de `freeze`**: 3 reintentos en la corrida (1, 2 y 4 s) y `BiasFreezeFailed` (SEV1); sin reintentos fuera de ese caso | PBT-U9-05; prueba de integración con governance que responde 503 |

## 4. Seguridad y privacidad

| ID | Requisito | Extensión | Verificación |
|---|---|---|---|
| NFR-U9-30 | **Identidades separadas** (Q7): el CronJob con el cliente `bias-monitoring-job` (`governance:freeze`, `registry:read:monitoring`) y el servicio con `bias-monitoring-service` (`registry:read:monitoring`); llaves `private_key_jwt` distintas, cada una desde su `ExternalSecret` (ESO) | SECURITY-06, 12; AUTONOMIA-04 | Prueba del realm de U2; X04: el servicio HTTP → `freeze` → 403 |
| NFR-U9-31 | **Sin datos del solicitante y sin celdas chicas**: el dashboard, el paquete, el `PrePostReport` y las métricas nunca muestran la tasa de una celda con menos de `n_min` casos (BR-U9-03, 20) ni la tasa sin bandas de un grupo con alguna celda insuficiente, que se podría deducir restando (BR-U9-06; `population_difference_partial`) | SECURITY-03; AUTONOMIA-05 | PBT-U9-03 y PBT-U9-08 extendidas a la diferencia sin bandas |
| NFR-U9-32 | **Logs de consulta** (Q7): `disparity.viewed` y `freeze_context.viewed` con `principal_subject` y `principal_role` (ya en la allowlist de U0 §8), retenidos ≥ 90 días como los demás logs de auditoría (NFR-SEC-14) | SECURITY-03, 14 | PBT-U0-07 en modo strict sobre los dos eventos |
| NFR-U9-33 | Logs y métricas sin datos del solicitante; las entradas inválidas solo con `seq` (BR-U9-09) | SECURITY-03 | PBT-U0-07 (allowlist) |
| NFR-U9-34 | **Sin egress** (X02); la única llamada a governance es `freeze` desde el CronJob (X04) | AUTONOMIA-04, 05 | Suite de conectividad de U1 |

## 5. Observabilidad

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U9-40 | Métricas en dos grupos de Pushgateway (BR-U9-20) y alertas `MonitoreoSesgoDetenido` (SEV2 / SEV1), `BiasFreezeFailed` (SEV1), `DisparidadDecisionHumana` (SEV2) y `BiasInvalidEntries` (SEV2), cada una con `runbook_url`; las expresiones se fijan en NFR Design | `promtool test rules`; test de runbooks de U1 |
| NFR-U9-41 | Métricas HTTP del servicio en el puerto 8081 (F60) y trazas con el `correlation_id` de U0 | Prueba de que `/metrics` expone las series esperadas |

## 6. Calidad y pruebas

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U9-50 | Cobertura de ramas **100 %** en `stats`, `disparity`, `freeze_rule`, `context` y `window`; ≥ 95 % en el resto | `pytest --cov --cov-branch` con umbral por módulo |
| NFR-U9-51 | `mutmut` en `stats`, `disparity` y `freeze_rule`, con 0 sobrevivientes sin justificar | `mutmut run` en CI |
| NFR-U9-52 | PBT-U9-01..08 con el perfil `ci` (500 ejemplos, semilla impresa) | CI |
| NFR-U9-53 | **Simulación estadística** (BLM §3): cobertura del intervalo y tasa de congelamientos falsos, con 10 000 repeticiones, **cada noche** en CI y en todo PR que cambie `stats` o `freeze_rule` | Workflow nocturno y regla de rutas en el PR |
| NFR-U9-54 | La librería `vectra_disparity` se versiona con SemVer; su versión viaja en cada paquete de contexto (BR-U9-15) y en el informe de validación de U4 | Prueba de que el paquete lleva `library_version` |

## 7. Cumplimiento de extensiones (NFR Requirements U9)

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-01 / 02 | Cumple | NFR-U9-10 (criticidad por proceso) |
| RESILIENCY-05 / 07 / 15 | Cumple | NFR-U9-40 |
| RESILIENCY-06 | Cumple | NFR-U9-12 |
| RESILIENCY-08 / 09 | Cumple | NFR-U9-11: 2 réplicas fijas con PDB y spread, exentas de HPA con justificación (carga baja y caché); NFR-U9-04 |
| RESILIENCY-10 | Cumple | NFR-U9-03, 22 |
| RESILIENCY-14 | Cumple | NFR-U9-20 (enfoque C) |
| SECURITY-03 / 06 / 12 / 14 | Cumple | NFR-U9-30..33 |
| SECURITY-15 | Cumple | NFR-U9-21 |
| AUTONOMIA-04 / 05 | Cumple | NFR-U9-30, 34 |
| PBT-01..10 | Cumple | NFR-U9-50..53 |

## 8. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio | Origen |
|---|---|---|
| `components.md` C11; `application-design.md` | Criticidad: CronJob High, servicio HTTP Medium | Q3 |
| U1 NFR-U1-12; plan de U1, Paso 5 | `require-hpa-bounds` admite un Deployment de réplicas fijas con `vectra.io/hpa-exempt`, `replicas ≥ 2` y PDB | Q4 |
| U9 FD BR-U9-06, 18, 20; domain-entities §2.4; U0 §9.4 `AttributeResult` | Sin inferencia por resta en la diferencia sin bandas: `population_difference_partial` | Q7 |
| U9 FD §8b (U12) | Latencia de detección p95 ≤ 30 min (≈ 27 min), en lugar de ≈ 20 min | Q1 |
| U3 BR-U3-11 y 17, INF-U3-03/04, deployment-architecture, plan (Pasos 12, 14, 18); `component-dependency.md` (§4, F26, F107, F108, §8) | Reconstrucción con Jobs normales en Git activados por `monitoringRebuild.runId`, en la Application aparte `decision-registry-rebuild` (PR con `runId` `AAAAMMDD-HHMM` sin repetir y sync manual con prune; los crea Argo CD) y *advisory lock*; contingencia si supera 1 h; sin hooks de sync ni K15 (los dos diseños anteriores quedan descartados) | aclaración del NFR Requirements de U9 (Q1 = A), 2026-10-10 |
| U0 BR-U0-71 (`read_only`, scope de lectura, sin efectos), domain-entities §7.1b (`RouteContract`) y §8.1 (catálogo de eventos) | Ruta `POST` de consulta y eventos `disparity.viewed` y `freeze_context.viewed` | Revisiones del NFR Requirements de U9 |
| U1 P-U1-09, NFR-U1-12, plan (estructura `namespaces/`, Paso 5 con casos nombrados, Paso 6, Paso 16 con la variante de render con `runId`) | Jobs a demanda en las PriorityClasses y la cuota; exención de HPA | Revisiones del NFR Requirements de U9 |
| U9 FD BR-U9-06, 18, 19, 20; BLM (PBT-U9-03, 05, 08 y ejemplos) | `population_difference_partial` y etiqueta `partial`; motivo `token` (E7); logs de consulta | revisión del NFR Requirements de U9, 2026-10-10 (segunda) |
