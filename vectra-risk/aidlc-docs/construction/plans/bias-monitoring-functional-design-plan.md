# Plan de Functional Design — U9 `bias-monitoring`

**Alcance de la unidad** (`unit-of-work.md` U9):
- `bias-monitoring-service` y su CronJob de cálculo.
- Librería de disparidad por banda de capacidad de pago y agregada, validada contra Fairlearn. También la usan el `model-validation-job` de U4 y la variante proxy de U5.
- Disparidad de las decisiones humanas (reporta y alerta, no congela).
- Evaluación del umbral y `freeze` vía governance (F27, X04).
- Paquete de contexto, `compare_source` (F25), API del dashboard (F14) y alerta `MonitoreoSesgoDetenido`.
- Sin datos propios: lee el registro (F26, proyección `monitoring`).

**Historias (dueña):**

| Historia | Tema |
|---|---|
| US-301 | Disparidad del modelo por bandas y agregada |
| US-302 | Disparidad de decisiones humanas, aparte |
| US-303 | Congelamiento automático (RT-2) |
| US-304 | Paquete de contexto |
| US-306 | Fuente nueva con medición antes y después |
| US-307 | Dashboard que no certifica |
| US-308 | Alerta si el monitoreo deja de evaluar |

**Ya decidido** (no se pregunta):
- **Etiquetas** (U0 §2.2): `sexo`, `rango_edad`, `region`, `estrato` y `banda_capacidad_pago` (`lt_20`, `20_30`, `gt_30`). Solo para monitoreo; no aparecen en los logs.
- **`outcome`** (U0): `favorable | desfavorable | revision_requerida`; `final_outcome` de la decisión humana.
- **Proyección `monitoring`** (U3 domain-entities §3): `recommendation` con `monitoring_labels`, `evaluated_at` y `seq`; `human_decision` con `final_outcome`, `recommendation_entry_id` y `decided_at`.
- **Momento de negocio**: se mide con `evaluated_at` y `decided_at`, no con `recorded_at` (U3; U8 business-rules §8).
- **Congelar**: bias solo llama a `POST /v1/models/{id}/freeze` y solo sobre la versión `activo` (BR-U4-04, X04). Governance aplica el estado de inmediato y escribe el evento `freeze` con el `context_package` (BR-U4-15). Ninguna ruta automática reactiva (AUTONOMIA-04).
- **Monitoreo detenido** (BR-U4-16): `MonitoreoSesgoDetenido` SEV2 a W y SEV1 a 2W; el modelo **sigue sirviendo**. W lo fija esta unidad.
- **Umbral**: 5 pp sobre la disparidad agregada del modelo (FR-BIA-03), configurable **[INTERNO]**.
- **RT-2** (U5 BR-U5-14): la variante proxy produce ≥ 10 pp y el modelo base < 5 pp, medidos con la librería de U9.
- **Leyenda** «mide y alerta, no certifica» y lint de frases prohibidas en la consola (U10, FR-BIA-08).

**Hallazgos en otras unidades que este FD debe resolver** (detalle en las preguntas):
- P-U7-03 pide contar solo las recomendaciones **entregadas**, pero el registro solo marca la entrega cuando hay una `human_decision` (Q5).
- `ServingConfig.bias_monitoring_age_s` (U0, U4) supone que bias informa la edad de su cálculo a governance, pero bias solo puede llamar a `freeze` (X04) (Q9).
- BR-U4-13 dice que `compare_source` va por **F27**; en el inventario es **F25** (governance → bias). F27 es el `freeze` (bias → governance). Se corrige al aplicar este FD.
- La unidad dice «sin datos propios», pero el CronJob y la API son procesos distintos y el paquete de contexto, el «antes» y el dashboard necesitan resultados guardados (Q8).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Qué es la disparidad (Business Rules; FR-BIA-01, US-301)
La métrica de referencia de Fairlearn es la **diferencia de paridad demográfica**: la tasa
más alta menos la más baja entre los grupos de un atributo. «Agregada» admite dos lecturas:
sobre toda la población, o combinando las diferencias **dentro** de cada banda de capacidad
de pago. La segunda es la que mide «discriminación que no se explica por capacidad de pago»
(US-301).

A) **Tasa de `favorable`; agregada = promedio ponderado de las diferencias por banda**:
   - por atributo (`sexo`, `rango_edad`, `region`, `estrato`) y por banda: `max(tasa) − min(tasa)` entre los grupos con muestra suficiente (Q3), donde tasa = `favorable` / todas las recomendaciones del grupo (`revision_requerida` cuenta como no favorable);
   - **agregada del atributo** = promedio de las diferencias por banda, ponderado por el tamaño de cada banda;
   - **agregada del modelo** = la mayor de las cuatro agregadas por atributo; es la que se compara con el umbral;
   - `no_informado` se reporta, pero no entra en el máximo ni en el mínimo;
   - también se reporta la diferencia sobre toda la población, sin bandas, solo como contexto.

   (Recomendado: es la lectura de US-301 y Fairlearn valida cada diferencia por banda)

B) Agregada = diferencia sobre toda la población, sin bandas. Las bandas se reportan pero no deciden. Una diferencia explicada por la capacidad de pago podría congelar el modelo

C) Igual que A, pero `revision_requerida` se excluye del denominador (tasa = `favorable` / (`favorable` + `desfavorable`))

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Disparidad de las decisiones humanas (Business Rules; FR-BIA-02, US-302)

A) **La misma métrica, sobre `final_outcome`, con alerta y sin congelar**:
   - cada `human_decision` toma las etiquetas de la `recommendation` que referencia (`recommendation_entry_id` → `seq`);
   - tasa = `final_outcome = favorable` / decisiones del grupo; mismas bandas, mismo umbral y misma regla estadística (Q3);
   - se calcula por versión del modelo de la recomendación y se reporta aparte;
   - si supera el umbral → alerta `DisparidadDecisionHumana` (SEV2, a cumplimiento); **nunca** llama a `freeze` (US-302);
   - además se reporta la **tasa de apartamiento** (`se_aparta`) por grupo, para ver si el proceso humano corrige o amplía la disparidad del modelo.

   (Recomendado)

B) Igual que A, sin la tasa de apartamiento por grupo

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Muestra mínima y ruido estadístico (Business Rules; US-301, R8 de U0)
Con 5 pp de umbral, el ruido de muestras pequeñas es mayor que la señal: con 100 casos por
grupo y una tasa cercana al 50 %, la diferencia entre dos grupos tiene un error típico de
≈ 7 pp. Tomar el máximo entre 6 regiones lo empeora. Un congelamiento falso detiene todas las
recomendaciones del banco hasta que cumplimiento reactive.

A) **Celda mínima de 30 y congelamiento solo con una disparidad material y significativa**:
   - una celda (grupo × banda) con menos de `n_min = 30` casos se reporta como «muestra insuficiente» y no entra en el cálculo; una banda con menos de 2 grupos suficientes tampoco;
   - cada diferencia se publica con su intervalo de confianza del 95 % (Newcombe para la diferencia de dos proporciones, entre los dos grupos extremos);
   - **congela** si la agregada del modelo es > 5 pp **y** el intervalo del par extremo excluye 0 en las bandas que la componen (la disparidad es material y no es ruido);
   - si toda la ventana es insuficiente, se reporta «muestra insuficiente» y no se congela; una versión recién activada sirve hasta reunir muestra (se ve en el dashboard).

   (Recomendado: RT-2, con ≥ 10 pp, lo dispara con una muestra moderada)

B) Celda mínima de 30 y congelamiento por el valor puntual > 5 pp, sin intervalo. Más simple y más rápido, con más congelamientos falsos

C) Congelamiento solo si el **límite inferior** del intervalo supera 5 pp. Casi sin congelamientos falsos, pero necesita muestras grandes y tarda más en reaccionar

X) Other (please describe after [Answer]: tag below)

[Answer]: A, con una regla de congelamiento precisa (sustituye la frase «el intervalo del par extremo excluye 0 en las bandas que la componen»):
   - **congela** si la agregada del modelo es > 5 pp **y** el límite inferior del intervalo de la agregada ponderada es > 0;
   - ese intervalo combina las varianzas de las diferencias por banda con los pesos al cuadrado (aproximación normal sobre las diferencias de Newcombe por banda), y se valida con la misma librería;
   - los pesos son el tamaño de cada banda **contando solo las celdas suficientes**, y el cálculo y el intervalo usan los mismos pesos;
   - el intervalo por par extremo se sigue publicando como contexto, pero no decide;
   - el atributo que dispara el congelamiento es el de la agregada máxima, y el paquete de contexto lo indica.

## Question 4 — Ventana, frecuencia y W (Business Logic; US-301, US-308, BR-U4-16)

A) **Por versión activa, 30 días, cada 15 min, W = 1 h**:
   - cada corrida mide la versión del modelo que aparece en las recomendaciones, con las de los últimos 30 días por `evaluated_at` (desde su activación si es más reciente); las versiones anteriores no se mezclan;
   - el CronJob corre cada 15 min;
   - W = 1 h (SEV2) y 2W = 2 h (SEV1): cuatro corridas fallidas seguidas antes de avisar;
   - las decisiones humanas usan la misma ventana por `decided_at`.

   (Recomendado)

B) Cada hora, ventana de 7 días, W = 3 h. Menos carga sobre el registro y reacción más lenta

C) Diario, ventana de 30 días, W = 26 h

X) Other (please describe after [Answer]: tag below)

[Answer]: A, con una condición de volumen: la lectura del registro (F26) devuelve **conteos agregados** por versión, combinación de etiquetas, banda y resultado (por día), no filas. Con 10 solicitudes/s serían unos 26 millones de recomendaciones en 30 días, que no se pueden paginar en cada corrida. Si la proyección `monitoring` de U3 no ofrece ese agregado, el FD registra el cambio en U3 (agregado por día), y bias suma los días de la ventana.

## Question 5 — Qué recomendaciones cuentan (Data Flow; P-U7-03)
P-U7-03 pide contar solo las recomendaciones **entregadas**. El registro solo lo hace
explícito cuando una `human_decision` referencia la recomendación (`recommendation_entry_id`).
Un caso tiene una sola recomendación entregada (BR-U8-12), pero el registro puede tener otras
de ese caso que case-service descartó (resultados tardíos, BR-U8-08).

A) **Una por caso**:
   - si el caso tiene `human_decision`, la que referencia;
   - si no, la **más reciente** del caso por `evaluated_at`;
   - el error posible (un caso sin decisión cuya última recomendación fue descartada) es raro, y la recomendación descartada viene del mismo modelo y del mismo caso;
   - se documenta como aproximación aceptada; las decisiones humanas son exactas.

   (Recomendado: mide desde que se recomienda, sin esperar a la decisión)

B) **Solo las decididas**: exacto, pero la medición espera a que decidan los analistas, deja fuera los casos que nunca se deciden y RT-2 necesitaría decisiones para congelar

C) Todas las recomendaciones del registro, aunque haya varias por caso

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Regla de congelamiento y fallos al congelar (Business Rules; FR-BIA-03, US-303)

A) **Una decisión por corrida, idempotente y con reintento acotado**:
   - si la versión medida cumple la regla de Q3, bias llama a `freeze` con el paquete de contexto (Q7);
   - si governance responde que ya está `congelado` o que no es la versión `activo` (409), la corrida lo registra y sigue: no es un error;
   - si `freeze` falla (timeout, 5xx o circuito abierto), 3 reintentos en la misma corrida (1, 2 y 4 s) y, si persiste, alerta `BiasFreezeFailed` (SEV1); la corrida siguiente vuelve a evaluar y a intentar;
   - el umbral (5 pp), `n_min` y W son values de Helm versionados en Git: cambiarlos es un PR revisado por cumplimiento, y su valor viaja en cada paquete;
   - una medición posterior por debajo del umbral **no** hace nada sobre un modelo congelado (US-303).

   (Recomendado)

B) Igual que A, pero el umbral vive en la política de negocio (U4), versionada con aprobación del CRO. bias necesitaría leer la política, un flujo que hoy no existe (X04)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Paquete de contexto (Domain Model; FR-BIA-04, US-304)
bias no tiene flujo de lectura hacia governance (X04), así que no conoce las fuentes de datos
ni la disparidad de la validación de la versión.

A) **bias arma las métricas y governance agrega lo que es suyo**:
   - bias: `model_version_id`; ventana y `computed_at`; **antes** = la agregada de la ventana que terminaba en la corrida anterior, **después** = la de esta corrida; por atributo y banda, las tasas, las diferencias, los intervalos y los tamaños; los grupos y bandas implicados (los que superan el umbral); volumen afectado = recomendaciones de la versión en la ventana y cuántas fueron `favorable`; umbral, `n_min` y versión de la librería;
   - governance, al recibir el `freeze`, agrega `data_sources` de la versión e `initial_disparity` de su validación (U4) antes de escribir el evento;
   - el paquete no tiene datos de ningún solicitante: solo agregados.

   (Recomendado: no agrega flujos)

B) Flujo nuevo bias → governance de solo lectura de la versión. Contradice X04 tal como está escrito

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Dónde quedan los resultados (Data Flow / Integration; FR-UI-05, US-304, US-307)
El CronJob calcula y la API sirve; son procesos distintos. Además el «antes» necesita la
corrida anterior, y `get_context_package` necesita el paquete de un congelamiento pasado.

A) **Sin base propia**:
   - el paquete ya queda en el evento `freeze` del registro (lo escribe governance): la proyección `monitoring` de U3 agrega las entradas `freeze` (`freeze_id`, `model_version_id`, `frozen_at`, `context_package`), y `get_context_package` las lee de ahí;
   - el CronJob publica las métricas de cada corrida (`vectra_bias_disparity{model_version_id, attribute, band, population}`, `vectra_bias_last_success_timestamp`, etc.) en el Pushgateway de U1 (flujo nuevo, como F87), y los dashboards de Grafana leen la historia de Prometheus;
   - `get_disparity` recalcula a pedido desde el registro con la misma librería, con una caché de 15 min;
   - el «antes» se recalcula sobre la ventana anterior en la misma corrida.

   (Recomendado: respeta «sin datos propios»)

B) **Base propia `bias-db`** (CloudNativePG de U1): corridas, resultados y paquetes. Historia y «antes» directos, a cambio de un quinto cluster, sus respaldos y su runbook

C) Sin CronJob: el propio servicio calcula cada 15 min en todas sus réplicas y guarda el último resultado en memoria. Las réplicas pueden congelar en paralelo (governance responde 409 a la segunda) y la historia solo queda en Prometheus

X) Other (please describe after [Answer]: tag below)

[Answer]: A, con dos precisiones:
   - la lectura del registro es el agregado de Q4 (también para el «antes» y para `get_disparity`), y la caché de 15 min de `get_disparity` se mantiene;
   - las métricas del Pushgateway no publican valores de celdas con menos de `n_min` (solo su tamaño o la marca de «muestra insuficiente»); el flujo CronJob → Pushgateway es nuevo (como F87) y se agrega al inventario, a `flows.yaml` y a la `NetworkPolicy`; la historia de Prometheus es de 30 días (INF-U1-07), y los filtros de 90 días de Q11 se sirven recalculando.

## Question 9 — Cómo se sabe que el monitoreo se detuvo (Integration; US-308, BR-U4-16)
U0 y U4 definen `ServingConfig.bias_monitoring_age_s`, «la edad del último cálculo que informó
U9». Pero bias solo puede llamar a `freeze` (X04), así que no tiene cómo informarla, y nada
consume ese campo.

A) **La alerta sale de la métrica de bias**:
   - el CronJob publica `vectra_bias_last_success_timestamp` al terminar una corrida completa (con el `freeze`, si correspondía);
   - `MonitoreoSesgoDetenido`: `time() − max(vectra_bias_last_success_timestamp) > W` → SEV2; `> 2W` → SEV1; **o** `absent()` de la serie durante W → SEV2;
   - se quita `bias_monitoring_age_s` de `ServingConfig` (U0 domain-entities §9.3, U4 domain-entities §5, BR-U4-16, PBT-U4-05 y el Paso 5 del plan de U4); BR-U4-16 pasa a citar la regla de U9.

   (Recomendado: no abre otra ruta hacia governance)

B) Endpoint nuevo en governance para que bias informe su latido. Amplía lo que bias puede llamar (X04, AUTONOMIA-04)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10 — `compare_source`: de dónde sale el «después» (Integration; FR-BIA-06, US-306)
Al proponer una fuente, governance pide `compare_source` (BR-U4-13). Para medir el «después»
hace falta un modelo que use la fuente, y bias no tiene acceso al model-store ni a staging.

A) **governance envía los dos conjuntos etiquetados**:
   - el ingeniero propone la fuente junto con una versión candidata en staging que la declara;
   - el `model-validation-job` (U4) puntúa el mismo dataset de validación con la versión activa (antes) y con la candidata (después) y devuelve, por registro, solo `outcome` y `monitoring_labels`;
   - governance llama a `compare_source(source_id, pre, post)` por F25 y bias devuelve el `PrePostReport` con la métrica de Q1–Q3 para los dos conjuntos y sus diferencias; bias no guarda nada;
   - cambios en U4 (BR-U4-13 y el job) y en el inventario (F25 lleva datos agregables, sin PII).

   (Recomendado)

B) bias lee los datasets del model-store y llama al modelo candidato en staging. Flujos nuevos hacia MinIO y KServe

X) Other (please describe after [Answer]: tag below)

[Answer]: A, con una variante: el `model-validation-job` no devuelve filas, sino **tablas de conteo** (grupo × banda × resultado, por atributo) para la versión activa («antes») y para la candidata («después»). governance las envía por F25 y bias calcula con la misma librería (el oráculo de Fairlearn expande los conteos). Así el payload no lleva combinaciones de etiquetas por registro, que podrían re-identificar a una persona. Cambios en U4 (BR-U4-13 y el job) y en el inventario (F25 con conteos).

## Question 11 — API del dashboard (Business Logic; FR-UI-05, US-307)

A) **`get_disparity(filter)` para `cumplimiento` y `cro`**:
   - filtros: versión (por omisión, la activa), atributo, ventana (7, 30 o 90 días);
   - respuesta: por atributo y banda, tasas, diferencias, intervalos, tamaños y celdas con «muestra insuficiente»; la agregada del modelo y la de las decisiones humanas, **separadas**; umbral, `n_min` y `computed_at`;
   - la respuesta lleva siempre el campo `disclaimer` («mide y alerta, no certifica»), como el informe de validación de U4; la consola lo muestra (U10);
   - ningún texto de la respuesta dice «sin sesgo» ni equivalentes; una prueba sobre los textos de la API lo comprueba con la lista de U10.

   (Recomendado)

B) Igual que A, sin `disclaimer` en la API: la leyenda queda solo en la consola

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 12 — Errores de una corrida (Error Handling; US-308, SECURITY-15)

A) **Una corrida es todo o nada**:
   - registro caído, lectura incompleta o error de la librería → la corrida falla, **no** congela con datos parciales y **no** actualiza `vectra_bias_last_success_timestamp`; `MonitoreoSesgoDetenido` avisa a W;
   - una página del registro con un `monitoring_labels` inválido → la corrida falla y se registra el `seq` (sin datos del solicitante); no se descarta en silencio;
   - `freeze` fallido: Q6.

   (Recomendado)

B) Las entradas inválidas se descartan y se cuentan en una métrica; la corrida sigue con el resto

X) Other (please describe after [Answer]: tag below)

[Answer]: X: una corrida es todo o nada para los fallos de lectura, de la librería y del registro (como en A), pero **una entrada con `monitoring_labels` inválido no detiene el monitoreo**:
   - la entrada se excluye del cálculo, se cuenta en `vectra_bias_invalid_entries` y se registra su `seq` (sin datos del solicitante);
   - alerta `BiasInvalidEntries` (SEV2, a la ingeniería de datos) si hay al menos una entrada inválida en la ventana;
   - la corrida **falla** (sin congelar con datos parciales ni actualizar `vectra_bias_last_success_timestamp`) solo si las inválidas superan el 1 % de las entradas de la ventana;
   - motivo: el registro es inmutable y U3 valida las etiquetas al escribir, así que una entrada inválida es un defecto; si la corrida fallara siempre, un solo registro dejaría sin monitoreo hasta 30 días, el modelo no se congelaría y `MonitoreoSesgoDetenido` quedaría en SEV1.

---

## Parte B — Checklist de ejecución

- [x] Leer y validar las respuestas; preguntas de aclaración si alguna es ambigua
- [x] `business-rules.md`: métrica, muestra mínima, regla estadística, congelamiento, decisiones humanas, paquete, `compare_source`, monitoreo detenido, errores (BR-U9-xx)
- [x] `domain-entities.md`: `LabeledOutcome`, `DisparityResult`, `DisparityReport`, `FreezeContext`, `PrePostReport`, `DisparityView`, valores de configuración
- [x] `business-logic-model.md`: módulos, flujo de una corrida, `compare_source`, consulta del dashboard; propiedades (PBT-U9-xx), incluido el oráculo contra Fairlearn y una propiedad stateful de la corrida y el congelamiento
- [x] Cambios a otras unidades registrados (U0 `ServingConfig`, U3 proyección `monitoring`, U4 BR-U4-13/16 y `model-validation-job`, inventario de flujos), según las respuestas
- [x] Tabla de cumplimiento de extensiones (SECURITY, RESILIENCY, PBT, AUTONOMIA)
- [x] Validar el contenido (Mermaid y texto alternativo) antes de crear los archivos
- [x] Registrar en `audit.md` y actualizar `aidlc-state.md`
