# Patrones de NFR Design — U9 `bias-monitoring`

Decisiones del plan (`bias-monitoring-nfr-design-plan.md`, Q1–Q6 = A). Los IDs `P-U9-xx`
se referencian en Infrastructure Design y en el plan de tareas. Las verificaciones en kind
las ejecuta el operador después de un PR aprobado (AUTONOMIA-01); las demás corren en CI.

---

## 1. Corrida

### P-U9-01 — Corrida todo o nada, con todas las versiones (Q4; BR-U9-10, 12; NFR-U9-01, 21)
1. **Token** de `bias-monitoring-job` (F50). Si falla → corrida fallida, `reason=token` (E7).
2. **Lectura**:
   - `GET /v1/monitoring/freezes` para las reactivaciones;
   - `POST /v1/monitoring/daily:query` con `versions` y, por versión, 4 rangos, en solicitudes de ≤ 12; la primera lleva `unattributable_range`.

   Lectura incompleta, atraso del agregador > 30 min o inválidas > 1 % → corrida fallida **antes** de cualquier `freeze`.
3. **Cálculo** de todas las versiones evaluadas con la librería. Si la librería falla → corrida fallida, sin `freeze`.
4. **Congelamiento**: llama a `freeze` en **cada** versión que cumpla BR-U9-11, aunque falle en otra.
   - Si alguna falla tras los reintentos, `vectra_bias_freeze_failed{model_version_id}` = 1 **solo** para esa versión, en su grupo `freeze-<model_version_id>` del Pushgateway. El grupo se borra cuando un `freeze` posterior de esa versión responde con éxito o con 409, o en una corrida completa en la que la versión ya no cumple la regla o ya no se evalúa (revisión del plan de tareas de U9, 2026-10-10), así que la alerta no se apaga por una corrida que falla antes del cálculo ni queda atascada (BR-U9-20; revisión del Infrastructure Design de U9, 2026-10-10).
   - Al final, la corrida queda fallida (`reason=freeze`) y no actualiza `last_success`.
5. **Publicación** (P-U9-05): siempre el grupo `run`, y el grupo `success` solo si la corrida fue completa.

- **Verificación**:
  - PBT-U9-05, con un comando de dos versiones que superan el umbral y un governance que falla solo para una: la otra queda congelada, la corrida termina fallida y `freeze_failed` = 1 solo para la que falló;
  - prueba de integración de la duración con 3 versiones y celdas densas (NFR-U9-01).
- **Satisface**: NFR-U9-01, 21, 22; RESILIENCY-10; AUTONOMIA-04; SECURITY-15.

### P-U9-02 — Timeouts y reintentos por dependencia (Q1; NFR-U9-03)

| Llamada | Timeout por intento | Reintentos | Peor caso |
|---|---|---|---|
| Token de Keycloak (F50) | 2 s | 1, inmediato | 4 s |
| `GET /v1/monitoring/freezes` (F26) | 3 s | — | 3 s |
| `POST /v1/monitoring/daily:query` (F26) | 5 s | — | 5 s por solicitud |
| `POST /v1/models/{id}/freeze` (F27) | 3 s | 3, a 1, 2 y 4 s | 19 s por versión |
| Push al Pushgateway (F106), dos grupos | 5 s cada uno | — | 10 s |

- **Peor caso de una corrida**: 3 versiones que congelan y fallan, y 2 solicitudes de rangos. Suma 4 + 3 + 10 + 57 + 10 s, unos 1,5 min, por debajo de los 10 min de `activeDeadlineSeconds`.
- **CronJob sin circuit breaker**: es un proceso de pocas llamadas que termina en cada corrida, así que un breaker no acumula estadística. Usa `deps.call` con `breaker="disabled"`, que U0 admite solo con `process_kind="batch"` (NFR-U0-23(c), P-U0-07). El timeout sigue siendo obligatorio.
- **Servicio HTTP con breaker** hacia el registro (F26), con los umbrales de U7: ≥ 50 % de fallos en 20 llamadas dentro de 30 s, y semiabierto a los 10 s. Con el circuito abierto, el dashboard responde 503 sin datos parciales.
- Fallo del breaker: timeout, error de conexión o 5xx; un 4xx no cuenta (NFR-U8-32, U0).
- **Verificación**:
  - `contracts`: `call` sin timeout no compila;
  - pruebas de integración con dobles lentos: cada llamada corta en su timeout;
  - corrida con todo en el peor caso → < 10 min;
  - el servicio HTTP con el registro caído abre el circuito tras 20 llamadas.
- **Satisface**: NFR-U9-03; RESILIENCY-10.

## 2. Consulta

### P-U9-03 — Caché del dashboard con una sola carga por llave (Q2; BR-U9-18, NFR-U9-02)
- LRU de 64 entradas por réplica; llave (versión, atributo, ventana); cada entrada dura 15 min.
- **Single-flight**: si varias consultas con la misma llave llegan sin caché, solo una lee el registro; las demás esperan su resultado (o su error, que no se cachea).
- Con 2 réplicas, una llave puede calcularse dos veces; se acepta.
- La caché solo guarda la respuesta ya suprimida (P-U9-04) y se pierde al reiniciar.
- **Verificación**:
  - prueba de integración: 10 consultas concurrentes con la misma llave → una sola lectura del registro;
  - una consulta tras 15 min → nueva lectura;
  - un error del registro no queda en la caché;
  - k6 con 10 usuarios (NFR-U9-02).
- **Satisface**: NFR-U9-02.

## 3. Seguridad

### P-U9-04 — Supresión de celdas chicas en la librería (Q5; NFR-U9-31; BR-U9-03, 06)
- `disparity_by_band` produce siempre resultados suprimidos:
  - una celda con `n < n_min` no lleva `rate`;
  - la diferencia sin bandas excluye los grupos con alguna celda insuficiente (`population_difference_partial`).
- Ningún consumidor puede pedir la versión sin suprimir. El servicio, el CronJob, el paquete, el `PrePostReport`, el informe de validación de U4 y la variante de U5 reciben lo mismo.
- Los tipos de U0 §9.4 refuerzan la regla: un `CellResult` con `status = muestra_insuficiente` y `rate` no valida.
- **Verificación**:
  - PBT-U9-03 y PBT-U9-08;
  - prueba de arquitectura (import-linter y una búsqueda estática): ningún módulo fuera de `vectra_disparity` construye un `CellResult` con `rate`;
  - prueba de U0: el `CellResult` inconsistente falla la validación.
- **Satisface**: NFR-U9-31; SECURITY-03; AUTONOMIA-05.

### P-U9-05 — Identidades, procesos y publicación (Q6; NFR-U9-30, 32, 34; BR-U9-20)
- **Una imagen, dos puntos de entrada**: `python -m vectra_bias.run` (CronJob) y `uvicorn vectra_bias.app:app` (servicio).
- **El servicio no puede congelar**:
  - import-linter prohíbe que `vectra_bias.app` y sus módulos importen `freeze_client`;
  - el servicio tiene otro cliente de Keycloak, `bias-monitoring-service`, sin `governance:freeze` (NFR-U9-30).
- **Librería** `vectra_disparity`: paquete propio del workspace, sin dependencias de runtime fuera de la biblioteca estándar. U4 y U5 lo importan sin traer el resto de U9.
- **Publicación**: grupos `success` y `run` del Pushgateway con `PUT`. El grupo `run` se empuja siempre; si el push falla, la corrida termina con código distinto de cero (BR-U9-20).
- **Logs**: `disparity.viewed` y `freeze_context.viewed` (U0 §8.1), con `principal_subject` y `principal_role`.
- **Verificación**:
  - import-linter;
  - prueba del realm de U2 (el servicio no obtiene `governance:freeze`);
  - prueba de que la imagen del servicio arranca sin el módulo de congelamiento cargado;
  - PBT-U0-07 en modo strict sobre los dos eventos.
- **Satisface**: NFR-U9-30, 32, 33, 34; SECURITY-03, 06, 12, 14; AUTONOMIA-04.

## 4. Observabilidad

### P-U9-06 — Alertas (Q3; BR-U9-21, 22; NFR-U9-40)

| Alerta | Expresión | `for` | Severidad |
|---|---|---|---|
| `MonitoreoSesgoDetenido` | `time() - max(vectra_bias_last_success_timestamp) > <W>` | 5 min | SEV2 |
| `MonitoreoSesgoDetenido` | `time() - max(vectra_bias_last_success_timestamp) > <2W>` | 5 min | SEV1 |
| `MonitoreoSesgoDetenido` | `absent(vectra_bias_last_success_timestamp)` | `<W>` | SEV2 |
| `BiasFreezeFailed` | `max by (model_version_id) (vectra_bias_freeze_failed) == 1` | 0 | SEV1 |
| `DisparidadDecisionHumana` | `max by (model_version_id) (vectra_bias_rule_met{population="humana"}) == 1` | 30 min (dos corridas seguidas) | SEV2 |
| `BiasInvalidEntries` | `max(vectra_bias_invalid_entries) > 0` | 0 | SEV2 |

- **W viene de `stale_after`** (revisión del Infrastructure Design de U9, 2026-10-10): la `PrometheusRule` es una plantilla del chart que toma `stale_after` de `values-monitoring-policy.yaml` (aprobado por cumplimiento, INF-U9-03) y genera `<W>` y `<2W>` en segundos; con el valor actual, 3600 y 7200. Nunca hay un número escrito a mano. La prueba de `promtool` se genera con el mismo value y comprueba los dos lados de W y de 2W.
- `BiasFreezeFailed` lee los grupos por versión del `freeze` fallido (P-U9-01), que persisten hasta un `freeze` exitoso.
- Las métricas del grupo `run` conservan el valor de la última corrida hasta la siguiente (unos 15 min). Por eso un `for: 30m` equivale a dos corridas seguidas.
- Cada regla lleva `severity` y `runbook_url` (P-U1-10). El runbook de `BiasInvalidEntries` explica cómo silenciar una entrada conocida hasta que salga de la ventana (§8b del FD).
- **Verificación**: `helm template` de la `PrometheusRule` con `stale_after` = 1 h y = 2 h, y `promtool test rules` generado para cada valor; `promtool test rules` de cada alerta con series sintéticas a los dos lados del umbral; un caso de `BiasFreezeFailed` con una corrida siguiente que falla antes del cálculo (la alerta sigue) y otro con un `freeze` exitoso (se apaga); con un caso sin serie para `MonitoreoSesgoDetenido` y un caso de una sola corrida para `DisparidadDecisionHumana` (no dispara); el test de runbooks de U1.
- **Satisface**: NFR-U9-40; RESILIENCY-05, 07, 15; SECURITY-14.

## 5. Resiliencia

### P-U9-07 — Escenarios de U9 (NFR-U9-20; RESILIENCY-14 = C)

| # | Escenario | Resultado esperado | Dónde |
|---|---|---|---|
| E1 | Registro caído | Corridas fallidas (`reason=lectura`); `MonitoreoSesgoDetenido` a 1 h; el modelo sigue sirviendo; dashboard 503 (circuito abierto) | CI y Operations |
| E2 | Agregador de U3 atrasado > 30 min | Corridas fallidas (`agregador_atrasado`); `MonitoringAggregatorStale` (U3) y luego `MonitoreoSesgoDetenido` | kind |
| E3 | governance caído durante un congelamiento | 4 intentos por versión; las demás versiones se intentan igual (P-U9-01); `BiasFreezeFailed` (SEV1); la corrida siguiente vuelve a intentar | CI y Operations |
| E4 | Pushgateway caído | La corrida termina con error; el `freeze` ya aplicado se mantiene; `PushgatewayDown` (U1) | CI y Operations |
| E5 | El pod del CronJob muere a mitad de corrida | Sin `freeze` con datos parciales; un `freeze` ya aplicado se mantiene; la corrida siguiente evalúa las demás versiones | CI y Operations |
| E6 | Modelo proxy (RT-2) | Congelado dentro de NFR-U9-01 (p95 ≤ 30 min), con el paquete completo | kind (U12) |
| E7 | Keycloak caído | Sin token: corrida fallida (`token`) antes de congelar; `MonitoreoSesgoDetenido` a 1 h; el modelo sigue sirviendo | CI y Operations |

- **Verificación**: en CI, las pruebas de integración de E1, E3, E4, E5 y E7; en kind y en Operations, los siete, con el resultado esperado como criterio y el reporte adjunto al runbook de la unidad.
- **Satisface**: RESILIENCY-14 (enfoque C); NFR-U9-20.

## 6. Cumplimiento de extensiones (NFR Design U9)

Revisada contra el cuerpo del documento antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-05 / 07 / 15 | Cumple | P-U9-06 |
| RESILIENCY-10 | Cumple | P-U9-01, 02 |
| RESILIENCY-14 | Cumple | P-U9-07 (enfoque C) |
| SECURITY-03 / 06 / 12 / 14 | Cumple | P-U9-04, 05, 06 |
| SECURITY-15 | Cumple | P-U9-01 (todo o nada sobre los datos) |
| AUTONOMIA-02 | Cumple | Cada patrón tiene su «Verificación» |
| AUTONOMIA-04 / 05 | Cumple | P-U9-01, 04, 05 |
| PBT-06 | Cumple | PBT-U9-05 extendida en P-U9-01 |

## 7. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio | Origen |
|---|---|---|
| U0 NFR-U0-23 (c), P-U0-07 y plan de U0 (Paso 10) | Modo `breaker="disabled"`, solo con `process_kind="batch"`; un servicio HTTP que lo intente falla al crear el cliente | Q1 |
| U9 FD BR-U9-12 (precisión) | Con varias versiones, se intentan todas las que cumplan la regla; la corrida falla al final si alguna falló (P-U9-01) | Q4 |
