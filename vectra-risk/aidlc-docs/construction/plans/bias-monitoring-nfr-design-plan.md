# Plan de NFR Design — U9 `bias-monitoring`

**Alcance:** convertir NFR-U9-01..54 en patrones y componentes lógicos, y fijar lo que el
NFR dejó para esta etapa: los timeouts de NFR-U9-03 y las expresiones de las alertas
(NFR-U9-40).

**Ya decidido** (no se pregunta):
- el Functional Design (BR-U9-01..22) y el NFR Requirements (NFR-U9-01..54);
- una corrida cada 15 min, todo o nada, de p95 ≤ 2 min y máximo 10 min, con detección en p95 ≤ 30 min;
- el CronJob es High y el servicio HTTP es Medium, con 2 réplicas fijas;
- librería en Python puro;
- RESILIENCY-14 = C: los escenarios E1–E7 se documentan aquí y se ejecutan en Operations;
- severidades del proyecto (P-U1-10): SEV1 → 15 min, SEV2 → 1 h, SEV3 → siguiente día hábil, todas con `runbook_url`;
- las tareas pendientes del Infrastructure Design: `backoffLimit: 0`, `Forbid`, `vectra-high`, sidecar nativo y los `ExternalSecret` de los dos clientes.

**Categorías obligatorias:**

| Categoría | Preguntas |
|---|---|
| Resilience Patterns | Q1, Q4 |
| Scalability Patterns | Sin preguntas: 2 réplicas fijas y una sola corrida a la vez ya están decididas (NFR-U9-11, 13) |
| Performance Patterns | Q1, Q2 |
| Security Patterns | Q5 |
| Logical Components | Q4, Q6 |
| Observabilidad | Q3 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Timeouts y circuit breaker por dependencia (Resilience / Performance; NFR-U9-03)
El presupuesto de una corrida es p95 ≤ 2 min, con un máximo de 10 min (`activeDeadlineSeconds: 600`).

A)
   | Llamada | Timeout por intento | Reintentos | Peor caso |
   |---|---|---|---|
   | Token de Keycloak (F50, `bias-monitoring-job`) | 2 s | 1, inmediato | 4 s |
   | `GET /v1/monitoring/freezes` (F26) | 3 s | Ninguno | 3 s |
   | `POST /v1/monitoring/daily:query` (F26; U3 responde con p95 ≤ 200 ms y su pool espera hasta 2 s) | 5 s | Ninguno | 5 s por solicitud |
   | `POST /v1/models/{id}/freeze` (F27) | 3 s | 3, a 1, 2 y 4 s (BR-U9-12) | 19 s por versión |
   | Push al Pushgateway (F106), dos grupos | 5 s cada uno | Ninguno | 10 s |

   - Peor caso de una corrida con 3 versiones y 2 solicitudes de rangos: ≈ 4 + 3 + 10 + 57 + 10 s ≈ 1,5 min, por debajo de los 10 min.
   - **Sin circuit breaker en el CronJob**: un proceso de pocas llamadas que termina en cada corrida no acumula estadística. `deps.call` se usa con el breaker en modo `disabled`, que U0 admite solo para procesos batch (se registra como precisión de NFR-U0-23).
   - El servicio HTTP sí usa breaker hacia el registro, con los umbrales de U7.

   (Recomendado)

B) El CronJob también con circuit breaker, con los umbrales de U7

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Caché del dashboard (Performance; BR-U9-18, NFR-U9-02)

A) **Caché en memoria por réplica, con una sola carga por llave**:
   - LRU de 64 entradas por réplica; la llave es (versión, atributo, ventana); la entrada dura 15 min;
   - *single-flight*: si llegan varias consultas con la misma llave sin caché, solo una lee el registro y las demás esperan su resultado;
   - con 2 réplicas, una llave puede calcularse dos veces; se acepta, porque son unas pocas consultas;
   - la caché no guarda nada que la respuesta no tenga (solo agregados) y se pierde al reiniciar.

   (Recomendado)

B) Sin *single-flight*: cada consulta sin caché lee el registro

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Expresiones y ventanas de las alertas (Observabilidad; BR-U9-21, 22; NFR-U9-40)
Las métricas del grupo `run` del Pushgateway quedan con el valor de la última corrida hasta
la siguiente, unos 15 min.

A)
   | Alerta | Expresión | `for` | Severidad |
   |---|---|---|---|
   | `MonitoreoSesgoDetenido` | `time() - max(vectra_bias_last_success_timestamp) > 3600` | 5 min | SEV2 |
   | `MonitoreoSesgoDetenido` | `time() - max(vectra_bias_last_success_timestamp) > 7200` | 5 min | SEV1 |
   | `MonitoreoSesgoDetenido` | `absent(vectra_bias_last_success_timestamp)` | 1 h | SEV2 |
   | `BiasFreezeFailed` | `max(vectra_bias_freeze_failed) == 1` | 0 (dispara con la primera corrida que falla) | SEV1 |
   | `DisparidadDecisionHumana` | `max(vectra_bias_rule_met{population="humana"}) == 1` | 30 min (dos corridas seguidas, para no alertar por una sola medición) | SEV2 |
   | `BiasInvalidEntries` | `max(vectra_bias_invalid_entries) > 0` | 0 | SEV2 |

   Cada alerta lleva `model_version_id` cuando aplica y su `runbook_url`. (Recomendado)

B) Igual que A, pero `DisparidadDecisionHumana` sin `for`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Una corrida con varias versiones (Resilience / Logical Components; BR-U9-10, 12)
BR-U9-12 dice que si `freeze` falla tras los reintentos, la corrida falla. No dice qué pasa
con las demás versiones de la misma corrida.

A) **Evaluar todas, congelar todas, y fallar al final si alguna falló**:
   - la corrida calcula todas las versiones evaluadas y llama a `freeze` en cada una que cumpla la regla, aunque otra haya fallado;
   - al final, si algún `freeze` falló, la corrida queda fallida (`reason=freeze`, `vectra_bias_freeze_failed{model_version_id}` = 1 solo para esa versión) y no actualiza `last_success`;
   - un error de lectura o de la librería sí detiene la corrida antes de cualquier `freeze` (todo o nada sobre los datos).

   (Recomendado: un governance que rechaza una versión no deja sin congelar a otra)

B) Detener la corrida en el primer `freeze` fallido

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Dónde se aplica la supresión de celdas chicas (Security; NFR-U9-31)

A) **En la librería, siempre**:
   - `disparity_by_band` produce resultados en los que una celda con `n < n_min` nunca lleva `rate` y la diferencia sin bandas excluye los grupos con alguna celda insuficiente (`population_difference_partial`);
   - ningún consumidor puede pedir la versión sin suprimir: el servicio, el CronJob, el paquete, el `PrePostReport`, el informe de validación de U4 y la variante de U5 reciben lo mismo;
   - una prueba de arquitectura comprueba que ningún módulo construye un `CellResult` con `rate` fuera de la librería.

   (Recomendado)

B) En la capa de API y de métricas; la librería devuelve todo y cada consumidor suprime

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Imagen y procesos (Logical Components; NFR-U9-10, 11)

A) **Una imagen, dos puntos de entrada**:
   - `python -m vectra_bias.run` (CronJob) y `uvicorn vectra_bias.app:app` (servicio), con el mismo paquete y la misma librería;
   - el servicio no importa `freeze_client` (contrato de import-linter): el código que congela solo está en el punto de entrada del CronJob, además de la separación de identidades (NFR-U9-30);
   - la librería `vectra_disparity` se publica como paquete del workspace, que U4 y U5 importan sin traer el resto de U9.

   (Recomendado)

B) Dos imágenes, una por proceso

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] Leer y validar las respuestas; preguntas de aclaración si alguna es ambigua
- [x] `nfr-design-patterns.md`: patrones P-U9-xx (corrida, timeouts y reintentos, caché, supresión, alertas, escenarios E1–E7, procesos), cada uno con su verificación
- [x] `logical-components.md`: inventario, dependencias (diagrama y texto alternativo), presupuesto de la corrida
- [x] Cambios a otras unidades registrados (p. ej., U0 NFR-U0-23 si se adopta el breaker `disabled`)
- [x] Tabla de cumplimiento de extensiones
- [x] Validar el contenido (Mermaid y texto alternativo) antes de crear los archivos
- [x] Registrar en `audit.md` y actualizar `aidlc-state.md`
