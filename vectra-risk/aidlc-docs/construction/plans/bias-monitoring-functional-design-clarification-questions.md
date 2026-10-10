# Preguntas de aclaración — U9 Functional Design

Las respuestas de Q1, Q2, Q3, Q6, Q7, Q9, Q10 y Q11 son claras. Q4 (conteos agregados por
día) cambia la forma en que bias lee el registro, y eso entra en conflicto con Q5, con el
«antes» de Q7 y con Q12. Además hay que decidir cómo produce U3 ese agregado.

---

### Clarification Question 1
**Cómo produce U3 el agregado diario (Q4).**
Con la proyección actual, el pool `projections` de U3 tiene **1 conexión** y un tiempo límite
de **2 s** en la réplica (P-U3-04). Un `GROUP BY` sobre ~26 millones de filas cada 15 min no
cabe en ese límite y compite con las demás proyecciones.

A) **Tabla de agregados incremental en U3**:
   - un proceso de U3 (`registry-aggregator`, CronJob cada 5 min o hilo del servicio) lee las entradas nuevas por `seq` a partir de una marca de agua y suma en `monitoring_daily` (versión, día de `evaluated_at` o `decided_at`, combinación de etiquetas, banda, `outcome` o `final_outcome`/`decision`);
   - es idempotente: la marca de agua y los conteos se escriben en la misma transacción;
   - la proyección `monitoring_daily` lee esa tabla y responde en milisegundos; el append no cambia (sin costo en el camino crítico);
   - la tabla es derivada: se puede reconstruir desde la cadena, y `verify_chain` no la toca.

   (Recomendado)

B) **Agregado en el mismo `append`**: la transacción del append también suma en la tabla. Siempre al día, a cambio de más trabajo y bloqueos en el camino crítico del registro (Critical)

C) **`GROUP BY` a pedido en la réplica**, con un pool propio para bias y un tiempo límite de 60 s

X) Other (please describe after [Answer]: tag below)

[Answer]: A, con una salvaguarda: el agregador usa un rol propio con escritura solo sobre las tablas derivadas (`monitoring_daily`, el índice por caso y la tabla de inválidas) y lectura de las entradas; los triggers de solo-anexar de `registry-db` siguen aplicando a las entradas y a la cadena, y no a las tablas derivadas. Los conteos de bias salen solo de `monitoring_daily`.

### Clarification Question 2
**Una recomendación por caso con conteos agregados (Q5 = A frente a Q4).**
Q5 cuenta una recomendación por caso: la que referencia la decisión o, sin decisión, la más
reciente. Con conteos agregados por día, bias ya no ve casos, así que esa regla tiene que
aplicarla quien agrega (U3). La recomendación «más reciente» de un caso puede cambiar después
de contada, incluso de día.

A) **El agregador de U3 aplica la regla por caso**:
   - mantiene, por `case_id`, cuál recomendación cuenta y en qué celda y día la contó;
   - si llega una recomendación más reciente del mismo caso, o una `human_decision` que referencia otra, **resta** la anterior de su celda y **suma** la nueva, en la misma transacción;
   - el índice por caso es interno de U3 y bias nunca lo ve.

   (Recomendado: conserva Q5 sin que bias vea filas)

B) **Contar todas las recomendaciones** (Q5 = C): sin estado por caso; los duplicados son raros (resultados tardíos descartados) y vienen del mismo modelo

C) **Contar solo la primera recomendación de cada caso**: el agregador suma una sola vez por caso y nunca resta. Puede contar una recomendación descartada en lugar de la entregada

X) Other (please describe after [Answer]: tag below)

[Answer]: A, con dos precisiones: «la más reciente» se decide por `evaluated_at` y, en empate, por el mayor `seq`; y la `human_decision` toma las etiquetas de la recomendación que referencia (`recommendation_entry_id` → `seq`) para su propia celda de decisiones. Restar y sumar van en la misma transacción que avanza la marca de agua.

### Clarification Question 3
**El «antes» del paquete de contexto con granularidad diaria (Q7 = A frente a Q4).**
Q7 define el «antes» como la ventana que terminaba en la corrida anterior, 15 min antes.
Con conteos por día, esa ventana es casi la misma que la actual, y el «antes» no diría nada.

A) **Antes = la misma ventana de 30 días desplazada 7 días** (de `t − 37 d` a `t − 7 d`), de la misma versión:
   - si la versión tiene menos de 7 días activa, el «antes» es «sin datos» y el paquete lo dice;
   - el paquete también lleva la `initial_disparity` de la validación, que agrega governance (Q7).

   (Recomendado)

B) **Antes = la última corrida en que la versión estaba bajo el umbral** (su fecha y su valor). Necesita guardar ese resultado, que con Q8 = A solo queda en Prometheus (30 días)

C) **Antes = solo la `initial_disparity` de la validación** (la agrega governance); bias no calcula un «antes»

X) Other (please describe after [Answer]: tag below)

[Answer]: A, con una adición: el paquete también lleva la agregada de los **últimos 7 días solos** (sin celdas de más de 7 días), porque la ventana de 30 días desplazada 7 días comparte 23 días con la actual y diluiría un cambio reciente. Así el paquete muestra: antes (t − 37 d a t − 7 d), después (t − 30 d a t) y los últimos 7 días. Si la versión tiene menos de 7 días activa, el «antes» es «sin datos» y el paquete lo dice.

### Clarification Question 4
**Entradas inválidas con conteos agregados (Q12 = X frente a Q4).**
Q12 pide excluir una entrada con `monitoring_labels` inválido, contarla, registrar su `seq` y
fallar la corrida si superan el 1 %. Con conteos agregados, bias no ve entradas ni `seq`.
Además, U3 ya valida las etiquetas al escribir.

A) **El agregador de U3 detecta y separa las inválidas**:
   - una entrada cuyas etiquetas no pertenecen al catálogo de U0 §2.2 no suma en las celdas; suma en un contador `invalid` del día y su `seq` queda en la tabla de inválidas de U3;
   - la proyección devuelve, junto con los conteos, el total de inválidas de la ventana y sus `seq`;
   - bias aplica Q12 tal como está: excluye, publica `vectra_bias_invalid_entries`, registra los `seq` (sin datos del solicitante), dispara `BiasInvalidEntries` y falla la corrida por encima del 1 %.

   (Recomendado)

B) bias solo recibe el total de inválidas por día, sin `seq`; la investigación se hace en U3 con el día y la versión

X) Other (please describe after [Answer]: tag below)

[Answer]: A, con un tope en la respuesta: la proyección devuelve el total de inválidas de la ventana y como máximo los 100 `seq` más recientes (el resto se consulta en U3). bias calcula el 1 % sobre el total de entradas de la ventana (válidas más inválidas), que la proyección también devuelve.
