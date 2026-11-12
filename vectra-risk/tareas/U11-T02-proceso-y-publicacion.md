# U11-T02 — Proceso y publicación de `product-metrics`: `scheduler`, `collector`, `main` y ejemplos con E/S

**Unidad:** U11 `product-metrics`
**Historias que implementa:** US-503 (North Star: su publicación en `/metrics`, Paso 6) y US-505 (métricas operativas y de producto: los ejemplos con E/S y la allowlist, Pasos 6 y 7), según la trazabilidad del plan (§3). La serie `vectra_product_noise_days_below_floor` de US-504 también se publica aquí, aunque el plan no asigna el Paso 6 a esa historia. Los Pasos 8 y 9 no tienen historia propia.
**Depende de:**
- **U11-T01 fusionada en `main`** (rama `tarea/U11-T01`, commit `9195580`, en revisión al redactar esta tarea). **No se despacha antes.** Hoy `product-metrics/` no existe en `main`: todo comando de esta tarea da `No such file or directory`. De U11-T01 se usan `config`, `params`, `model`, `compute`, `noise`, `reader`, `state`, el doble de U3 (`tests/doubles/registry_double.py` y `entries.py`), `tests/conftest.py`, el `Makefile`, `pytest.ini`, `coveragerc` y `.importlinter`.
- U0 en `main`: `vectra_common.ops_server.create_ops_app(readiness)`, `process.init`, `deps` (breaker en modo `consecutive_failures`, `CircuitState`), `logging` (`configure`, `log_access`, modo `strict`) y `metrics.REGISTRY`.

Sin clúster (AUTONOMIA-01; RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6). No necesita U3, U7 ni U8 desplegados: todas las pruebas usan el doble de U3.
**Rama:** `tarea/U11-T02`, que parte de `origin/main`.

Bloques C y D del plan de U11 (Pasos 6 a 9), juntos en una tarea según `aidlc-docs/construction/plans/demo-recorte-funcional.md` §4 (fusión «C+D», enmienda P-2) y §8 (U11 queda en 3 tareas: A+B · C+D · E+cierre). Los Pasos 6, 8 y 9 entran **completos** (E). El Paso 7 entra como **E\*F**: entran los ejemplos con E/S y se difiere la prueba de volumen (enmienda §3, U11, fila «7»; §2 regla 3). Las PBT no se recortan: PBT-U11-05 entra entera, y PBT-U11-07 se completa aquí sobre las series publicadas. Rige el ritmo RL-1 a RL-5: máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda del 2026-11-09.

La demo que sostiene U11 es D4 (enmienda §1.4): el día D + 1 el presentador abre `product.json` y ve North Star, sostenida, tasa de consulta y días bajo el piso. U11-T01 escribió el cálculo. Esta tarea escribe el proceso que lee, calcula y **publica** esas cifras en `/metrics`. Las reglas `:dedup`, `product.json`, la imagen, el chart y el cierre son de **U11-T03** (Bloque E y cierre: Pasos 10 a 13, 15, 17 y 18).

---

## Alcance

**Dentro:** los Pasos 6 a 9 del plan. Texto del plan, sin recortes salvo la prueba de volumen del Paso 7, que se marca abajo con ~~tachado~~ y va en «Fuera»:

### Bloque C — Proceso y publicación

- [ ] **Paso 6 — `scheduler`, `collector` y `main`** (E)
  - `scheduler`: pasada completa al arrancar y diaria; ciclo incremental cada 5 min, omitido (y contado) si el candado está tomado; plazo y reintentos de la pasada.
  - `collector`: `Collector` de `prometheus-client` sobre la instantánea inmutable; sin instantánea, sin series de producto; series de operación siempre.
  - `main`: `vectra_common.process.init(kind="service")`, `ops_server.create_ops_app(readiness)`, servida sin `run_service` porque no hay API (revisión de consistencia entre unidades, 2026-11-01), con el **predicado de readiness** (instantánea o breaker abierto o semiabierto), apagado con `SIGTERM` (no toma ciclos nuevos, termina la página en curso).
  - Allowlist de series y etiquetas de domain-entities §5 (producto y operación).
  - Diseño: P-U11-02, 03; INF-U11-01; NFR-U11-07, 08, 40.
  - **Aceptación**: `uv run pytest product-metrics/tests/integration/test_process.py tests/integration/test_collector.py`:
    - arranque con U3 caído → series de operación sí (sin `vectra_product_last_full_recompute_timestamp` hasta la primera pasada completa exitosa; pendientes consolidados, 2026-10-10), de producto no, `/readyz` 503 hasta que el breaker abre y 200 después; al cerrarse el breaker sin instantánea → 503;
    - primera pasada que vence su plazo de 75 min con U3 lento pero sin 3 fallos seguidos (reloj simulado) → `/readyz` 503 (revisión del plan de tareas de U11, 2026-10-10);
    - `SIGTERM` durante una pasada: no toma ciclos nuevos, termina la página en curso en ≤ 10 s, descarta la pasada a medias (el estado vigente queda intacto) y sale con código 0 (revisión del plan de tareas de U11, 2026-10-10);
    - desfase de la pasada diaria: con relojes simulados y semillas fijas, el desfase uniforme cae en [0, 600] s en 10 000 sorteos, el inicio entre las 02:30 y las 02:40 UTC, dos semillas fijas distintas dan desfases distintos y la misma semilla repite la secuencia; sin umbrales estadísticos (NFR-U11-04; revisión del plan de tareas de U11, 2026-10-10; prueba determinista, pendientes posteriores al cierre, 2026-10-10);
    - etiqueta `month`: las series con `period="month"` (North Star, desglose, sostenida y sus razones) la llevan con `AAAA-MM`; ninguna otra `period` la lleva; las de consulta de explicación no la tienen (pendientes posteriores al cierre, 2026-10-10);
    - reintentos de la pasada completa: con U3 fallando y reloj simulado, 6 reintentos cada 15 min y después ninguno hasta la del día siguiente, con el estado incremental intacto (NFR-U11-09; revisión del plan de tareas de U11, 2026-10-10);
    - un scrape durante el reemplazo → solo valores de un ciclo;
    - un ciclo durante la pasada → omitido y contado;
    - `/metrics` sin ninguna serie ni etiqueta fuera de la allowlist (PBT-U11-05);
    - PBT-U0-07 en modo strict sobre los logs.

- [ ] **Paso 7 — Pruebas de ejemplo del proceso y prueba de volumen** (E\*F)
  - Las pruebas de ejemplo de business-logic-model §3 que dependen de E/S (reinicio a mitad, registro caído 31 min, decisión sobre una recomendación de hace 60 días).
  - ~~**Prueba de volumen** (INF-U11-06): el doble de U3 sirve 10 veces el volumen de NFR-U3-30 durante 7 meses, con la latencia de página del p95 de U3; se miden la duración de la pasada, el pico de memoria (`tracemalloc` y RSS) y la ausencia de lecturas simultáneas.~~ **(diferida por la demo, T3; enmienda §3, U11, fila «7»: «Entran los ejemplos con E/S. Se difiere la prueba de volumen (`-m volume`, T3; no es PBT)»; ver «Fuera»)**.
  - Diseño: NFR-U11-02, 03, 12, 13; P-U11-04. De estos, NFR-U11-12 y P-U11-04 ya están implementados y trazados por U11-T01 (plegado por mes y memoria compacta); lo que se difiere con la prueba de volumen es su **medición**, junto con NFR-U11-02, 03 y 13 (ver «Identificadores diferidos» en las Precisiones). Los ejemplos que entran ejercen BR-U11-01, 07 y 11.
  - **Aceptación**: `uv run pytest product-metrics/tests/integration/test_examples.py`; ~~`uv run pytest product-metrics/tests/volume -m volume` (pasada ≤ 60 min; pico ≤ 70 % de 512 MiB; si se supera, se ajusta INF-U11-01 y el aporte a la cuota antes de seguir)~~ (diferido, T3).

- [ ] **Paso 8 — Resumen del proceso** (E)
  - Cobertura ≥ 90 % en el resto; resumen en `aidlc-docs/construction/product-metrics/code/process.md`.
  - **Aceptación**: `uv run pytest product-metrics/tests --cov=vectra_product --cov-branch --cov-fail-under=90`.

### Bloque D — Repositorio y frontend

- [ ] **Paso 9 — Repositorio, migraciones y frontend: N/A** (E)
  - U11 no tiene base de datos ni interfaz propia; los dashboards son código de Grafana (Paso 13).
  - **Aceptación**: `test ! -d product-metrics/migrations && test ! -d product-metrics/frontend`.

### Precisiones

- **Estructura de §1: qué toca esta tarea.** El árbol «Estructura de destino» del plan ya lo creó U11-T01. Aquí:
  - se **completan** `src/vectra_product/scheduler.py`, `collector.py` y `main.py`, que hoy son una línea de docstring cada uno;
  - se **crean** `tests/integration/test_process.py`, `tests/integration/test_collector.py`, `tests/integration/test_examples.py` y `tests/integration/test_main_process.py` (proceso real, ver abajo); si el proceso real necesita un doble de U3 servido por HTTP y un emisor de token de prueba, van en `tests/doubles/`, junto a `registry_double.py`, sin duplicar su lógica;
  - se **crea** `aidlc-docs/construction/product-metrics/code/process.md`;
  - se **modifican en su sitio** `Makefile`, `state.py`, `reader.py` (solo lo que se nombra abajo) y el plan;
  - `tests/volume/` **se queda como está**, con su `.gitkeep`: la prueba de volumen está diferida;
  - **no** se crean `migrations/` ni `frontend/` (Paso 9), ni nada de `chart/templates/`, `tools/`, `policies/`, `observability/` (Pasos 10 a 13, U11-T03).
- **`scheduler` (P-U11-02; BR-U11-11; NFR-U11-04, 09).**
  - Al arrancar, `state.full_pass()`. Después, cada `config.CYCLE_SECONDS`, `state.incremental()`: si devuelve `SKIPPED`, suma 1 en `vectra_product_cycles_skipped_total` y no lee ni publica nada; si devuelve `DONE`, calcula y publica.
  - Tras cada lectura exitosa (pasada o incremental): `compute(state.snapshot(), params, now)` y **un solo reemplazo de referencia** de lo publicado (P-U11-03). Una lectura fallida conserva lo publicado y no mueve `last_success` (BR-U11-11). Sin lecturas nuevas, la incremental exitosa también recalcula: `now` cambia el día.
  - **Plazo de la pasada:** `config.FULL_PASS_DEADLINE_SECONDS`. Si vence, la pasada falla, el estado vigente queda intacto, el candado se libera y `vectra_product_full_pass_in_progress` vuelve a 0 (P-U11-06 lo necesita: la pasada vencida deja de excluir las alertas).
  - **Reintentos:** una pasada fallida se reintenta cada `config.FULL_PASS_RETRY_SECONDS`, hasta `config.FULL_PASS_RETRIES` veces; después, ninguno hasta la diaria siguiente. El estado incremental sigue intacto y los ciclos de 5 min siguen. Sin instantánea, ver P-2.
  - **Diaria:** 02:30 UTC más un desfase uniforme en [0, `config.FULL_PASS_JITTER_MAX_SECONDS`] s, sorteado con un generador **inyectable** (`random.Random`); en producción, uno por proceso sin semilla fija. Cuándo cuenta la pasada del arranque, ver P-3.
  - `vectra_product_full_pass_in_progress` vale 1 desde que la pasada empieza a esperar el candado hasta que termina, falla o vence.
  - **Reloj y espera inyectables.** El `scheduler` recibe el reloj de pared (`datetime`), el monótono y la función de espera. Ninguna prueba duerme minutos reales: los 75 min, los 15 min × 6 y los 5 min se simulan. `state.ProductState` ya recibe `clock`, y `reader.build_client` recibe el `clock` del breaker.
  - Sin baseline (`state.NoBaseline`), el ciclo de 5 min no lee, no cuenta como omitido y no publica.
- **`collector` (P-U11-03; domain-entities §5).**
  - Lo publicado es **una** instantánea inmutable: el `BusinessMetrics` de `compute` más `last_success_at`, `last_full_recompute_at` y los `Params`. `BusinessMetrics` de U11-T01 no trae `last_success` (P-U11-03 dice que sí): **no** lo agregues a `compute`; arma el par en un tipo congelado del `collector` o del `scheduler`. `compute.py` y `noise.py` no se tocan (su cobertura del 100 % es de U11-T01).
  - `collect()` lee la referencia **una sola vez** al entrar y arma todas las familias desde esa copia local. Es lo que garantiza «solo valores de un ciclo».
  - **Sin instantánea** no emite ninguna serie de producto ni `vectra_product_metrics_last_success_timestamp` (nunca ceros). `vectra_product_last_full_recompute_timestamp` no se emite hasta la primera pasada completa exitosa (nunca 0).
  - **Series de operación, siempre** (NFR-U11-40): `vectra_product_cycle_duration_seconds{kind}` con los buckets de domain-entities §5 (1, 5, 15, 30, 60, 120, 300, 600, 1200, 1800 y 3600 s; créalo con `vectra_common.metrics.histogram`), `vectra_product_entries_read_total{kind}`, `vectra_product_full_pass_in_progress`, `vectra_product_cycles_skipped_total` y `vectra_circuit_state{dependency="decision-registry"}`, que ya publica el breaker de U0. `kind` es `incremental` o `full`.
  - **Series de producto:** exactamente las de la primera tabla de domain-entities §5, con esas etiquetas. Lee la tabla entera; lo que no es obvio:
    - los **conteos** (`…_decisions`, `…_breakdown`) van con todos los cortes y **sin** filas `all`; las **razones** van solo en el total (todo en `all`) y por un corte (los demás en `all`), nunca con dos cortes a la vez;
    - una razón con denominador 0 **no se emite** (BR-U11-03); sus conteos sí;
    - `month="AAAA-MM"` solo con `period="month"`. En la exposición, las series de otro `period` **no tienen la clave `month`**, ni siquiera vacía. Una `GaugeMetricFamily` con nombres de etiqueta fijos no sirve tal cual: usa `Metric.add_sample` con el diccionario de etiquetas de cada muestra, o una solución equivalente;
    - las series de consulta de explicación llevan `period="7d"` (la ventana que termina ayer) y nunca `month`. **NFR-U11-10 dice que la tasa de consulta también se publica por mes; el plan (Paso 6) y domain-entities §5, que son posteriores, dicen que no. Rige el plan.** NFR-U11-10 se cumple con los 6 meses cerrados de la North Star y la sostenida;
    - `vectra_product_unattributable_decisions{period}` solo con `day`, `30d` y `month_to_date` (`PeriodMetrics.unattributable` es `None` en los meses);
    - `vectra_product_invalid_entries` y `vectra_product_metrics_degraded` (0 o 1) sin etiquetas;
    - `vectra_product_origination_seconds{quantile,standard="true"}` y `vectra_product_origination_standard_under_target_ratio`: qué día se publica, ver P-4;
    - `vectra_product_target{metric}`: qué valores de `metric`, ver P-5.
  - **Allowlist como dato.** Las dos tablas de domain-entities §5 quedan en **una** constante importable del `collector` (serie → conjunto de etiquetas, separando producto de operación). La usan el `collector`, las pruebas y, en U11-T03, `tools/gen_rules.py` para generar las reglas `:dedup` «desde la allowlist» (Paso 12). La prueba de la allowlist **no** se limita a comparar contra esa constante: transcribe las tablas de domain-entities §5 como oráculo propio.
  - **Series estándar de U0.** `create_ops_app` sirve `vectra_common.metrics.REGISTRY`, que ya trae las series de proceso y las de U0 (`vectra_authz_denied_total`, `vectra_log_fields_dropped_total`, `vectra_http_request_duration_seconds` y otras). Quedan fuera de la allowlist de U11 (domain-entities §5): la prueba las reconoce porque estaban en `REGISTRY` **antes** de registrar nada de U11 (se calcula, no se copia una lista a mano). Toda serie `vectra_product_*`, y toda serie que no estuviera antes, debe estar en la allowlist.
- **`main` (INF-U11-01; NFR-U11-07, 21).**
  - Orden: `process.init("service")`, `vectra_common.logging.configure("product-metrics")`, `params.load()` (si falla, el proceso sale con código distinto de 0 **sin** servir nada), cliente y `Reader`, `ProductState`, `collector` registrado, `create_ops_app(readiness)` y el servidor de 8081.
  - **Sin `run_service` ni `ops_server.serve`**, que exigen una app de 8080. `main` sirve la app de `create_ops_app` con su propio `uvicorn.Server` (`log_config=None`, `access_log=False`, `lifespan="off"`, como `ops_server.serve`). `uvicorn` llega por `vectra-common`; no se declara aparte. `.importlinter` prohíbe importar `fastapi` y `starlette` en `vectra_product`: `main` usa el objeto que devuelve `create_ops_app`, sin importar ninguno de los dos.
  - **Predicado de readiness:** `True` si hay instantánea publicada **o** `reader.breaker_state` es `OPEN` o `HALF_OPEN`. Una pasada fallida o vencida no basta. Al cerrarse el breaker sin instantánea vuelve a `False`. La tabla completa de NFR-U11-07 es parte de la aceptación (CA-2).
  - **`SIGTERM`:** deja de tomar ciclos, **termina la página en curso** (no la cancela a mitad), descarta la pasada a medias (el estado vigente queda intacto), detiene el servidor y **sale con código 0**. Ver la trampa de uvicorn en «Notas».
  - **Entorno.** Solo `main.py` lee variables de entorno, y solo las de cableado: `VECTRA_REGISTRY_URL` (obligatoria; el mismo nombre que usa U9), las `VECTRA_CLIENT_ID`, `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_KEY_PATH` y `VECTRA_CLIENT_KEY_ID` que ya lee `service_token.provider_from_env`, y `VECTRA_POLICY_PATH` (opcional; por omisión `params.POLICY_PATH`), como U9. `config.py` y `params.py` siguen sin leer el entorno (`tests/unit/test_config.py` lo comprueba). Ninguna constante del ciclo sale del entorno. Anótalas en `process.md`: U11-T03 las pone en el chart.
  - **Puerto.** Por omisión `ops_server.OPS_PORT` (8081). La función de arranque lo recibe como **argumento** (no como variable de entorno) para que las pruebas usen un puerto libre: la máquina es compartida y otros agentes ocupan 8080 y 8081 (`CANDIDATAS.md`, línea 469).
  - **Código probable sin subproceso.** Deja en `main.py` una corrutina que reciba sus dependencias (cliente o transporte, relojes, espera, evento de parada, puerto) y un `main()` fino que solo lee el entorno y la llama. Así `test_process.py` la ejerce en el mismo proceso, con reloj simulado, y la cobertura la ve; el subproceso se usa solo para lo que lo necesita (señal real y código de salida). Es la lección de `CANDIDATAS.md`, línea 478.
- **Cambios permitidos en `state.py` y `reader.py`** (de U11-T01), y ninguno más:
  - un punto de parada **entre páginas** para `SIGTERM` y para el plazo (hoy `full_pass` no se puede interrumpir sin cancelar la página en vuelo);
  - el número de entradas leídas por lectura, para `vectra_product_entries_read_total{kind}`;
  - el log del `seq` de una entrada excluida por el logger de U0 (siguiente punto).

  PBT-U11-02 y `tests/integration/test_reader.py` deben seguir pasando; si una prueba de U11-T01 necesita un ajuste por estos cambios, se anota en la bitácora con el porqué.
- **Logs (NFR-U11-22; BR-U11-10; PBT-U0-07).** Hoy `state.py` registra la entrada excluida con `logging` estándar: `log.warning("entry_excluded seq=%d", seq)`. En cuanto `main` llama a `vectra_common.logging.configure`, el filtro de U0 descarta el **texto** de todo mensaje que no sea un evento del catálogo, así que ese `seq` **desaparece del log** y BR-U11-10 («su `seq` va solo al log») deja de cumplirse sin que nada falle. Usa `vectra_common.logging.log_access(seq=seq)`, como hace U9 (`bias-monitoring/src/vectra_bias/run.py`, línea 342): `seq` está en `LOG_RECORD_FIELDS` y no hace falta tocar U0. Lo mismo para cualquier otro log propio: solo campos de `LOG_RECORD_FIELDS` (por ejemplo `error_code`, `status`, `exception_type`, `duration_ms`), nunca texto libre. Esto atiende la candidata 2 de `bitacoras/U11-T01.md` sin cambiar U0.
- **PBT-U11-05, entera.** Para toda salida de `compute` (instantáneas generadas con `tests/doubles/entries.py`, con cortes generados), toda serie publicada usa solo etiquetas de la allowlist, y ningún valor de etiqueta es un `case_id`, un `seq` ni un identificador de usuario. El generador debe **poner** esos valores al alcance: los ítems crudos ya traen `case_id`, `seq` y `recommendation_entry_id`; agrégales campos de más con forma de identificador de usuario. El oráculo: cada valor de etiqueta sale de un conjunto cerrado (`period`, `part`, `kind`, `quantile`, `standard`, `metric`, `outcome` del catálogo, `all`), cumple `^\d{4}-\d{2}$` (`month`), o es un `channel` o `model_version_id` de las recomendaciones generadas; y ninguno coincide con un `case_id`, un `seq` o un identificador generado.
- **PBT-U11-07, sobre lo publicado.** U11-T01 la corrió sobre `BusinessMetrics` y dejó para esta tarea la comprobación sobre las series: para toda partición por cortes, la suma de los conteos publicados (`…_decisions{part}` con todos los cortes) es igual al numerador y al denominador del total, y la razón total publicada es `sum(numerador) / sum(denominador)`; lo mismo para cada razón por un corte. Va en `test_collector.py`, con el perfil `ci`.
- **Ejemplos con E/S del Paso 7** (business-logic-model §3), todos con el doble de U3 y reloj simulado, en `tests/integration/test_examples.py`:
  - **reinicio a mitad:** un proceso publica `vectra_product_noise_days_below_floor = 3`; se descarta (a mitad de un ciclo) y uno nuevo arranca contra los mismos datos → publica el mismo valor (BR-U11-07: la serie sale de los datos, no del tiempo que lleva el proceso). Arma los datos como `tests/unit/test_compute_examples.py` (ventana móvil de 7 días; la candidata 1 de `bitacoras/U11-T01.md` explica la lectura del ejemplo);
  - **recomendación de hace 60 días:** una decisión de ayer cuya recomendación se evaluó hace 60 días (fuera de los 35 días del estado) llega con `recommendation` resuelta → es atribuible y entra en el denominador de `day`; una decisión cuyo `recommendation_entry_id` apunta a una entrada `freeze` llega con `recommendation: null` → no atribuible: suma en `vectra_product_unattributable_decisions` y en ningún cociente (BR-U11-01). El doble sirve lo que serviría U3 (`_recommendation_ref` de `decision-registry/src/vectra_registry/projections.py`);
  - **registro caído 31 min:** con instantánea publicada, U3 deja de responder 31 min (reloj simulado) → los valores de producto siguen iguales, `vectra_product_metrics_last_success_timestamp` no avanza y queda a más de 1 800 s de `now`, `vectra_product_full_pass_in_progress` vale 0 y el breaker está abierto; al volver U3, la incremental sigue desde `last_seq` (E1 y E6 de P-U11 §3). Que `ProductMetricsStale` dispare es `promtool` (Paso 12, U11-T03): aquí se comprueba la condición que la alerta lee.
  - De la misma lista, «`/metrics` no tiene ninguna etiqueta fuera de la allowlist (US-505)» es PBT-U11-05 (Paso 6). Los ejemplos de `gen_rules.py`, `promtool` y dashboard son de U11-T03.
- **Meses cerrados publicados (NFR-U11-10).** Con 7 meses de datos en el doble, `/metrics` trae exactamente los 6 `month` cerrados, y no el séptimo ni el mes en curso con `period="month"`.
- **Trazabilidad.** Deben quedar citados **en código o pruebas de `product-metrics/`** (el resumen de `aidlc-docs/` no cuenta) los identificadores de los pasos que esta tarea cubre y que hoy no lo están: `P-U11-03`, `INF-U11-01`, `NFR-U11-07`, `NFR-U11-08`, `NFR-U11-10`, `NFR-U11-21` y `NFR-U11-22`. `NFR-U11-21` hoy solo está en `.importlinter`, que `test_traceability.py` no lee (`CANDIDATAS.md`, línea 415): cítalo en `main.py`.
- **Identificadores diferidos: no los escribas.** `NFR-U11-02`, `NFR-U11-03` y `NFR-U11-13` son de la prueba de volumen y del dimensionamiento. **No escribas esos tres identificadores en ningún archivo de `product-metrics/`**: U11-T03 decide cuáles van en «Diferido por la demo» de `evidence/cierre-demo.md`, y `test_traceability.py` falla si un identificador diferido ya tiene código. Tampoco en un rango: `test_traceability.py` expande `NFR-U11-01..04` y lo cuenta como cita de los cuatro. En `process.md` y en la bitácora sí puedes nombrarlos.
- **`make -C product-metrics check`.** Sigue corriendo, en orden, lint, mypy estricto, import-linter, las pruebas con el perfil `ci` y la cobertura. A `coverage` se le **agrega** la del Paso 8 (≥ 90 % de ramas sobre `vectra_product`) sin quitar la del 100 % de `compute` y `noise`. Sigue sin correr `-m volume`.
- **Plan.** Marca `[x]` los Pasos 6 a 9 con `(U11-T02)`; en el Paso 7, la nota «prueba de volumen diferida por la demo (T3)».
- **`process.md`.** Resume el ciclo real (arranque, incremental, diaria, plazo, reintentos, apagado), la readiness, lo que se publica y cuándo, y deja escrito para U11-T03: el nombre de la constante de la allowlist, los valores de `metric` de `vectra_product_target`, las variables de entorno, el comando de arranque de la imagen y qué se decidió en P-1 a P-5. Dice que la prueba de volumen está diferida.

**Fuera** (recházalo aunque lo veas roto o tentador):

- **La prueba de volumen del Paso 7** (`tests/volume`, `-m volume`, INF-U11-06: 10 veces el volumen de NFR-U3-30 durante 7 meses, duración de la pasada, pico de memoria con `tracemalloc` y RSS) y el benchmark de `compute` de NFR-U11-03. Recorte E\*F: enmienda §3, U11, fila «7»; §2 regla 3, que nombra «U11 Pasos 5 y 7». No escribas una versión reducida «para tener algo».
- **`mutmut`** (ya diferido en U11-T01; T3).
- **Bloque E y cierre, de U11-T03:** `Dockerfile` (Paso 10), chart, cuotas y flujos (Paso 11), `tools/gen_rules.py`, `PrometheusRule`, recording rules `:dedup` y las cuatro alertas con `promtool` (Paso 12), `product.json`, el panel de ciclos omitidos en `platform/observability/dashboards/operacion.json` y los runbooks (Paso 13), la Application y la trazabilidad completa (Paso 15), el `README.md` (Paso 17) y el cierre con `evidence/cierre-demo.md` (Paso 18). El Paso 14 (workflow) está en D y el Paso 16 (kind) se consolidó en U12 Paso 18 (enmienda §8).
- Cambios a U0, U1, U2 o U3. En particular: no agregues un `LogEvent` ni un campo a `LOG_RECORD_FIELDS`, no toques `ops_server.serve` (su estado de salida con `SIGTERM` es la candidata de la línea 437), no agregues un parámetro de puerto por entorno a U0 y no cambies la proyección `metrics`. Lo que no encaje se reporta como candidata.
- `compute.py` y `noise.py`: no se tocan.
- Un catálogo de canales: `channel` es texto libre de hasta 40 caracteres en U0 y llega tal cual a una etiqueta. Es la candidata 3 de `bitacoras/U11-T01.md`; no se resuelve aquí.
- OpenTelemetry (`telemetry.configure`): el plan no lo pide para U11.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/product-metrics-code-generation-plan.md` (§1, Bloques C y D, §3)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§6, RL-1 a RL-5)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§1.4 D4, §2, §3 U11, §4, §8)
- `aidlc-docs/construction/product-metrics/functional-design/business-rules.md` (BR-U11-01, 03, 05, 07, 08, 10, 11)
- `aidlc-docs/construction/product-metrics/functional-design/domain-entities.md` (§2, §3, §4 y, sobre todo, **§5**: las dos tablas de series)
- `aidlc-docs/construction/product-metrics/functional-design/business-logic-model.md` (§2.1 y §3: PBT-U11-05, 07 y las pruebas de ejemplo)
- `aidlc-docs/construction/product-metrics/nfr-requirements/nfr-requirements.md` (NFR-U11-04, 07, 08, 09, 10, 21, 22, 30, 40)
- `aidlc-docs/construction/product-metrics/nfr-design/nfr-design-patterns.md` (P-U11-02, 03, 06 y §3, E1 a E8) y `logical-components.md`
- `aidlc-docs/construction/product-metrics/infrastructure-design/infrastructure-design.md` (INF-U11-01: readiness, breaker y apagado)
- `aidlc-docs/construction/product-metrics/code/logic.md` (la firma real de `compute`, `Snapshot` y el plegado; de U11-T01)
- `product-metrics/src/vectra_product/` (`config.py`, `model.py`, `compute.py`, `state.py`, `reader.py`, `params.py`), `product-metrics/tests/doubles/` y `product-metrics/tests/conftest.py`, `Makefile`, `pytest.ini`, `.importlinter`
- `bitacoras/U11-T01.md` («Desvíos y decisiones» y «Tareas candidatas»)
- `contracts/python/vectra_common/src/vectra_common/ops_server.py`, `process.py`, `logging.py`, `metrics.py`, `deps.py` (`CircuitBreaker`, `CircuitState`) y `service_token.py` (`provider_from_env`)
- `contracts/python/vectra_contracts/src/vectra_contracts/catalog.py` (`LOG_RECORD_FIELDS`, `LogEvent`)
- `bias-monitoring/src/vectra_bias/run.py` (`log_access(seq=…)`, entorno `VECTRA_*`) y `bias-monitoring/tests/integration/test_run.py` (la prueba de logs en modo strict)
- `scoring-explainability/tests/integration/test_app.py` (`_RealProcess`: un proceso real con dobles HTTP, emisor de token y puertos libres)
- `decision-registry/src/vectra_registry/projections.py` (`_metrics`, `_recommendation_ref`)
- `DECISIONES-LOOP.md` (§5 y §6) y `CANDIDATAS.md` (líneas 415, 428, 437, 444, 469, 474, 478, 524 y 530)

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`. «Hoy» quiere decir: sobre el árbol de U11-T01 (`tarea/U11-T01`, commit `9195580`), que es como quedará `main` al despachar. Ahí `scheduler.py`, `collector.py` y `main.py` son una línea de docstring y no existe ninguno de los cuatro archivos de prueba.

- [ ] **CA-1** — El proceso: arranque, readiness, plazo, reintentos, `SIGTERM`, desfase, ciclo omitido y logs (Paso 6; P-U11-02; INF-U11-01; NFR-U11-04, 07, 09, 22).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest product-metrics/tests/integration/test_process.py -v
  ```
  Esperado: código 0 y un caso, con nombre reconocible, por cada una de estas viñetas del plan:
  - arranque con U3 caído → `/metrics` trae las series de operación, **sin** `vectra_product_last_full_recompute_timestamp` y sin ninguna serie de producto; `/readyz` 503 mientras el breaker está cerrado, 200 cuando abre (y en semiabierto), y 503 otra vez cuando se cierra sin instantánea;
  - primera pasada que vence el plazo de 75 min con U3 lento pero sin 3 fallos seguidos (reloj simulado) → `/readyz` 503, `vectra_product_full_pass_in_progress` de vuelta en 0 y el candado libre;
  - `SIGTERM` durante una pasada → no toma ciclos nuevos, la página en vuelo **termina** (el doble la ve completa), la pasada se descarta, el estado y lo publicado quedan como antes;
  - desfase: 10 000 sorteos en [0, 600] s, inicio entre las 02:30 y las 02:40 UTC, dos semillas distintas dan desfases distintos y la misma semilla repite la secuencia; sin umbrales estadísticos;
  - reintentos: con U3 fallando, exactamente 6 reintentos separados 15 min y ninguno más hasta la diaria siguiente; el estado incremental intacto y los ciclos de 5 min siguen;
  - un ciclo durante la pasada → `vectra_product_cycles_skipped_total` sube en 1 y el doble no recibe ninguna solicitud de más;
  - PBT-U0-07 en modo strict: con `VECTRA_LOG_STRICT=1` y `configure("product-metrics", stream)`, un recorrido con entradas excluidas, fallos de lectura, breaker abierto y apagado deja solo líneas con claves de `LOG_RECORD_FIELDS`, y los `seq` de las excluidas salen en el campo `seq`.

  Ningún caso duerme más de unos segundos reales. **Rojo primero:** (a) un predicado de readiness que devuelve `True` cuando la primera pasada falló o venció hace fallar el caso del plazo; (b) dejar el `log.warning("entry_excluded seq=%d", …)` de `state.py` hace fallar el caso de logs, porque el `seq` no aparece; regístralos. Hoy: `ERROR: file or directory not found: product-metrics/tests/integration/test_process.py`, código 4.

- [ ] **CA-2** — La publicación: allowlist (PBT-U11-05), PBT-U11-07 sobre las series, `month`, scrape durante el reemplazo y readiness (Paso 6; P-U11-03; NFR-U11-07, 08, 10, 40; domain-entities §5; US-503, US-505).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest product-metrics/tests/integration/test_collector.py -v
  ```
  Esperado: código 0; el encabezado muestra el perfil `ci` y la semilla; y pasan:
  - **PBT-U11-05** (propiedad): ninguna serie ni etiqueta fuera de la allowlist, y ningún valor de etiqueta es un `case_id`, un `seq` ni un identificador de usuario. El oráculo transcribe domain-entities §5;
  - **PBT-U11-07** (propiedad) sobre las series publicadas;
  - `/metrics` del `ops_server` real (`create_ops_app`) con instantánea: toda serie nueva respecto de las de U0 está en la allowlist, con sus etiquetas exactas;
  - `month`: las series con `period="month"` de North Star, desglose y sostenida (conteos y razones) la llevan con `AAAA-MM`; ninguna otra serie tiene la clave `month`; las de consulta de explicación no la tienen; con 7 meses de datos salen exactamente los 6 cerrados;
  - el ejemplo de US-503 de punta a punta: las 10 decisiones del business-logic-model §3 servidas por el doble → `vectra_product_north_star_ratio` total de `day` = 0,4 y `vectra_product_north_star_breakdown` = 2, 1 y 1;
  - denominador 0 → la razón no se emite y los conteos sí;
  - sin instantánea → ninguna serie de producto, sin `…_last_success_timestamp` ni `…_last_full_recompute_timestamp`; las de operación sí, con los buckets exactos del histograma;
  - un scrape durante el reemplazo: con dos instantáneas A y B y el reemplazo intercalado en medio de `collect()`, cada scrape es entero de A o entero de B;
  - la tabla de NFR-U11-07 sobre el predicado: sin instantánea y breaker cerrado → 503; sin instantánea y abierto → 200; sin instantánea y semiabierto → 200; con instantánea y cualquier estado → 200; pasada fallida o vencida sin instantánea y breaker cerrado → 503; breaker que se cierra sin instantánea → 503; predicado que lanza una excepción → 503.

  **Rojo primero:** (a) emitir `month=""` en las series de `period="day"`, o `month` en las de consulta de explicación; (b) leer la referencia de la instantánea dos veces dentro de `collect()`; (c) emitir `vectra_product_last_full_recompute_timestamp 0` al arrancar; (d) una etiqueta `seq` o `case_id` en cualquier serie. Cada uno hace fallar su caso; regístralos. Hoy: `file or directory not found`, código 4.

- [ ] **CA-3** — El proceso **real** publica y se apaga con código 0: lectura de vuelta de `/metrics` y `/readyz` por HTTP (Paso 6; INF-U11-01; NFR-U11-21).
  ```bash
  D=$(mktemp -d) && uptime && uv run pytest product-metrics/tests/integration/test_main_process.py -v --basetemp="$D" && uptime \
    && grep -E '^vectra_product_north_star_ratio\{' "$(find "$D" -name metrics.txt)" | grep 'period="day"' | grep 'channel="all"' | grep 'outcome="all"' | grep 'model_version_id="all"' \
    && grep -cE '^vectra_product_(metrics_last_success|last_full_recompute)_timestamp ' "$(find "$D" -name metrics.txt)" \
    && cat "$(find "$D" -name readyz.txt)" "$(find "$D" -name paths.txt)" "$(find "$D" -name exit-code.txt)"
  ```
  La prueba arranca `vectra_product.main` como **subproceso** (el `main()` real, con las variables `VECTRA_*`, un puerto libre pasado como argumento, el doble de U3 y un emisor de token de prueba servidos por HTTP en puertos libres), le hace `GET` a `/readyz` antes y después de la primera pasada y a `/metrics` después, guarda en `tmp_path` lo que **leyó del proceso** (`metrics.txt`, `readyz.txt`, `paths.txt`, `exit-code.txt`) y le manda `SIGTERM` mientras una pasada lee una página lenta.
  Esperado: código 0 de pytest, y de los archivos (que son la evidencia, no el código de salida de pytest):
  - una línea `vectra_product_north_star_ratio{…period="day"…} 0.4` (los datos del doble son el ejemplo de US-503, fechado ayer);
  - `2` (las dos marcas de tiempo están publicadas);
  - `readyz.txt`: `503` y después `200`;
  - `paths.txt`: `/metrics 200`, `/healthz 200`, `/readyz 200` y `/v1/entries 404` (no hay rutas de negocio en 8081);
  - `exit-code.txt`: `0`, con el apagado en ≤ 10 s desde el `SIGTERM` y la página en vuelo completa en el doble.

  **Rojo primero:** servir con `uvicorn.Server.serve()` sin tratar la señal deja el estado de salida en `-15` (ver «Notas»); regístralo antes de arreglarlo. Hoy: `file or directory not found`, código 4; y `python -m vectra_product.main` termina al instante con 0 **sin servir nada**, por eso el criterio lee `/metrics` y no el código de salida.

- [ ] **CA-4** — Ejemplos con E/S del Paso 7 (BR-U11-01, 07, 11; US-505).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest product-metrics/tests/integration/test_examples.py -v
  ```
  Esperado: código 0 y un caso por ejemplo de «Ejemplos con E/S del Paso 7» de las Precisiones: reinicio a mitad (`noise_days_below_floor` igual antes y después), recomendación de hace 60 días (atribuible) y referencia a una `freeze` (no atribuible), y registro caído 31 min (valores conservados, `last_success` a más de 1 800 s, incremental desde `last_seq` al volver). **Rojo primero:** actualizar `last_success` en un ciclo fallido hace fallar el de los 31 min; regístralo. Hoy: `file or directory not found`, código 4.

- [ ] **CA-5** — La prueba de volumen quedó diferida y sus identificadores no se escribieron (enmienda §3, U11, fila «7»).
  ```bash
  find product-metrics/tests/volume -type f ! -name .gitkeep | wc -l; grep -rnE "NFR-U11-(02|03|13)\b" product-metrics/ --include='*' -I | grep -v '/\.' ; grep -n "volume" product-metrics/Makefile product-metrics/pytest.ini
  ```
  Esperado: `0`; ninguna línea del segundo `grep`; y del tercero, el marcador `volume` de `pytest.ini` y el `-m "not volume"` del `Makefile`, sin ningún objetivo que corra `-m volume`. Es una guarda: **hoy ya pasa** y debe seguir pasando.

- [ ] **CA-6** — Cobertura ≥ 90 % en el resto, 100 % en `compute` y `noise`, y resumen del proceso (Paso 8; NFR-U11-30).
  ```bash
  uv run pytest product-metrics/tests --cov=vectra_product --cov-branch --cov-fail-under=90 --cov-report=term-missing \
    && uv run pytest product-metrics/tests/unit product-metrics/tests/property --cov=vectra_product.compute --cov=vectra_product.noise --cov-branch --cov-fail-under=100 \
    && grep -nE "SIGTERM|readiness|allowlist|VECTRA_REGISTRY_URL|vectra_product_target|volumen" aidlc-docs/construction/product-metrics/code/process.md
  ```
  Esperado: código 0. En la primera tabla, `scheduler.py`, `collector.py` y `main.py` aparecen **con sentencias** (no en 0) y cada uno con 90 % o más; si alguno queda por debajo aunque el total pase, `process.md` dice cuál y por qué. La segunda sigue en `TOTAL … 100%`. `process.md` existe y cubre lo que pide «`process.md`» en las Precisiones, incluida la nota de la prueba de volumen diferida. Hoy: las dos corridas de cobertura **pasan** (los tres módulos tienen 0 sentencias), y el `grep` falla porque `process.md` no existe; por eso el criterio exige ver los tres módulos con sentencias.

- [ ] **CA-7** — Paso 9: sin repositorio, migraciones ni frontend.
  ```bash
  test ! -d product-metrics/migrations && test ! -d product-metrics/frontend && echo OK
  ```
  Esperado: `OK`. Es una guarda: **hoy ya pasa** y debe seguir pasando.

- [ ] **CA-8** — `check` de la unidad (RL-4).
  ```bash
  uptime && make -C product-metrics check && uptime
  ```
  Esperado: código 0, con lint, mypy estricto, import-linter (los tres contratos `KEPT`: `model`, `compute` y `noise` sin E/S; `httpx` solo vía `vectra_common.deps`; sin `fastapi` ni `starlette`), las pruebas con el perfil `ci` y la semilla en el encabezado (la lista incluye `test_process.py`, `test_collector.py`, `test_examples.py` y `test_main_process.py`), y las dos coberturas (100 % y 90 %). Hoy: termina en 0 pero **sin** esos cuatro archivos ni la cobertura del 90 %. El diff no toca U1, así que `make -C platform check` no hace falta.

- [ ] **CA-9** — Trazabilidad «sin fallos nuevos» (`DECISIONES-LOOP.md` §6, con su enmienda).
  ```bash
  uv run python platform/tests/test_traceability.py --unit product-metrics; uv run python platform/tests/test_traceability.py --all
  ```
  Esperado del primero: código 1 con **exactamente** estas 16 líneas `sin trazabilidad`, todas de pasos que esta tarea no cubre (Bloque E) o de la prueba de volumen diferida: `INF-U11-02`, `03`, `04`, `05`; `NFR-U11-02`, `03`, `05`, `06`, `13`, `14`, `32`, `33`, `41`, `42`; `P-U11-05`, `06`. **No** deben aparecer `P-U11-03`, `INF-U11-01`, `NFR-U11-07`, `08`, `10`, `21` ni `22`. Esperado del segundo: los fallos de las demás unidades son idénticos a los de `origin/main` (el revisor lo corre también sobre la base) y los de `product-metrics` son esos 16. Hoy: el primero lista 23 identificadores (esos 16 más los 7 que esta tarea traza). Si U11-T01 se fusionó citando alguno más o alguno menos, manda la base: la lista esperada es la de `origin/main` menos esos 7.

- [ ] **CA-10** — Plan.
  ```bash
  grep -nE "^- \[x\] \*\*Paso [6-9] " aidlc-docs/construction/plans/product-metrics-code-generation-plan.md && git diff origin/main -- aidlc-docs/construction/plans/product-metrics-code-generation-plan.md | grep -E "^[-+]- \["
  ```
  Esperado: los Pasos 6 a 9 en `[x]` con `(U11-T02)`, el 7 con la nota de la prueba de volumen diferida; ningún otro paso cambia. Hoy: el primer `grep` no encuentra nada.

**Resumen de «hoy»:** fallan CA-1, CA-2, CA-3, CA-4 (los archivos de prueba no existen), CA-6 (falta `process.md`), CA-9 (7 identificadores sin trazar) y CA-10. Pasan ya CA-5 y CA-7 (guardas) y, en código de salida, CA-8 (sin las pruebas nuevas).

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `tests/integration/test_process.py`: las viñetas de CA-1, con el doble de U3 (`registry_double.RegistryDouble`: `fail_all`, `fail_requests`, `timeout_requests`, `latency`), reloj de pared, reloj monótono y espera simulados, y un generador con semilla para el desfase.
- `tests/integration/test_collector.py`: PBT-U11-05 y PBT-U11-07 (perfil `ci`, generadores de `tests/doubles/entries.py`) y los casos de CA-2. El oráculo de la allowlist es la transcripción de domain-entities §5, no la constante del `collector`.
- `tests/integration/test_main_process.py`: el subproceso de CA-3. Escribe en `tmp_path` lo que leyó por HTTP.
- `tests/integration/test_examples.py`: los tres ejemplos con E/S del Paso 7.
- Ajustes a `tests/integration/test_reader.py` o a las pruebas de `state` solo si los cambios permitidos a `state.py` y `reader.py` lo exigen; PBT-U11-02 no se debilita.
- **Rojo primero:** antes de cada arreglo, el codificador reproduce el fallo y lo registra en `bitacoras/U11-T02.md`; como mínimo los de CA-1 (a y b), CA-2 (a, b, c y d), CA-3 y CA-4. El par falla-pasa es la prueba.
- **No** se escribe ninguna prueba en `tests/volume/`.

---

## Preguntas

Ninguna bloquea el despacho: cada una tiene una opción por omisión. P-2 es la que más conviene que el usuario mire, porque cambia qué ve el presentador si U3 tarda en estar disponible.

- **P-1 — Con U3 caído al arrancar, ¿en cuánto abre el breaker?** INF-U11-01 dice que «el breaker se abre en unos 15 s, la réplica queda lista y el despliegue no se bloquea» (tres timeouts de 5 s seguidos). Pero NFR-U11-09 prohíbe reintentar dentro del ciclo y manda reintentar la pasada cada 15 min: una pasada falla en su **primera** página fallida, así que el breaker recibe un fallo por intento y abre al tercero, a los 30 min. Durante esos 30 min `/readyz` da 503.
  - (a) **Por omisión.** Literal de NFR-U11-09 y del plan: un fallo por intento. La línea de aceptación del plan («503 hasta que el breaker abre y 200 después») se cumple igual, con reloj simulado. El «unos 15 s» de INF-U11-01 no se cumple; se anota como candidata de diseño y en `process.md`. El escenario que lo sufriría (rollout con U3 caído, Paso 16.3) está diferido.
  - (b) Sin instantánea, la pasada del arranque reintenta enseguida hasta que el breaker abre (3 intentos), y después sigue la cadencia de 15 min. Cumple INF-U11-01, pero es un reintento dentro del ciclo que NFR-U11-09 no contempla.

- **P-2 — Sin instantánea y con los 6 reintentos agotados, ¿qué hace el `scheduler`?** El plan y NFR-U11-09 dicen «6 reintentos cada 15 min y después ninguno hasta la del día siguiente, **con el estado incremental intacto**»: describen una diaria que falla cuando ya hay estado. Si la que falla es la pasada **del arranque** (E2, U3 caído al arrancar más de 90 min), no hay estado: los ciclos de 5 min no tienen baseline y la réplica quedaría sin series de producto hasta las 02:30 UTC siguientes o hasta que alguien la reinicie.
  - (a) Literal: tras 6 reintentos, nada hasta la diaria.
  - (b) **Recomendada, y por omisión.** Mientras **nunca** haya habido una pasada exitosa, el reintento cada 15 min no tiene tope; el tope de 6 rige cuando ya hay estado, que es el caso que el plan prueba. No contradice ninguna línea de aceptación y evita un `product.json` vacío en D4 si U3 tarda en levantar en kind.
  - Con cualquiera de las dos, el caso del plan (con estado) se prueba tal cual, y se agrega un caso para el arranque sin estado según la opción que rija.

- **P-3 — ¿La pasada del arranque cuenta como «la recomputación de hoy»?** El business-logic-model §2.1 dice «¿02:30 UTC + desfase y sin recomputación hoy?». Si la del arranque cuenta, un proceso que arranca a las 00:01 UTC no vuelve a recomputar hasta las 02:30 del día siguiente (≈ 26 h 30 min después) y `ProductMetricsFullRecomputeMissing` (edad > 26 h, `for: 0`) dispara en falso.
  - (a) **Por omisión.** La diaria corre en el primer instante «02:30 UTC + desfase» posterior al arranque y después cada día, haya corrido o no la del arranque. Como mucho hay una pasada de más si el proceso arranca poco antes de las 02:30.
  - (b) La del arranque cuenta como la de hoy solo si empezó después de las 02:30 UTC de ese día.

- **P-4 — ¿Qué día publican `vectra_product_origination_seconds` y `vectra_product_origination_standard_under_target_ratio`?** BR-U11-05 dice «por día», `BusinessMetrics.origination` trae un valor por día, y la serie de domain-entities §5 no tiene etiqueta de periodo.
  - (a) **Por omisión.** El día de **ayer** (el periodo `day` de BR-U11-08: días UTC completos, sin el día en curso). Si ayer no hubo casos estándar, la serie no se emite (no 0). Prometheus guarda la historia día a día.
  - (b) Los 30 días que terminan ayer, recalculando los cuantiles sobre todas las muestras. Exigiría cambiar `compute`, que está fuera.

- **P-5 — ¿Qué valores lleva `metric` en `vectra_product_target`?** domain-entities §5 dice «los targets de §4, para las líneas de referencia», y §4 mezcla parámetros (F, S, N) y targets. `product.json` (Paso 13, U11-T03) dibuja «la tasa de consulta con el piso», y solo puede leer series.
  - (a) **Por omisión.** `complete_response`, `origination_hours`, `origination_ratio`, `sustained_ratio_month6`, `north_star` (solo si no es `null`: ausente quiere decir «sin target acordado») y `noise_floor` (F, que es una línea de referencia del panel). S y N no se publican: no son líneas.
  - (b) Solo los cuatro o cinco `target_*`; el piso lo escribiría U11-T03 en el dashboard desde el archivo de parámetros, con una plantilla.

Lo que rija en cada una queda escrito en `process.md`.

---

## Notas

- Archivos que se **modifican en su sitio**: `product-metrics/src/vectra_product/scheduler.py`, `collector.py` y `main.py` (se completan), `state.py` y `reader.py` (solo los tres cambios permitidos), `product-metrics/Makefile` (objetivo `coverage`) y `aidlc-docs/construction/plans/product-metrics-code-generation-plan.md` (casillas de los Pasos 6 a 9). Nada de duplicados con sufijo. `pyproject.toml` raíz y `uv.lock` **no** cambian: no hay dependencias nuevas.
- Archivo nuevo de documentación que pide el plan: `aidlc-docs/construction/product-metrics/code/process.md`.
- **Trampa: uvicorn y el código de salida.** `uvicorn.Server.serve()` captura `SIGTERM` con `signal.signal` y, al salir, **vuelve a emitir la señal** (`capture_signals` termina con `signal.raise_signal`). Con el manejador por omisión el proceso muere con estado `-15`, no 0. Es la candidata de `CANDIDATAS.md`, línea 437 («tras un SIGTERM el proceso termina con estado `-SIGTERM`»), y el plan exige código 0. `main` tiene que tratar la señal él mismo (por ejemplo, con un `uvicorn.Server` cuyo `capture_signals` no haga nada y un manejador propio en el bucle). No toques U0.
- **Trampa: `REGISTRY` es global.** `create_ops_app` sirve siempre `vectra_common.metrics.REGISTRY`. Registrar el `collector` dos veces da `Duplicated timeseries`: el `collector` recibe el registro como parámetro (por omisión el de U0), las pruebas que usan el de U0 lo desregistran al terminar, y los contadores se comprueban por **diferencia**, no por valor absoluto.
- **Trampa: series `_created`.** `prometheus-client` 0.26 emite una serie `…_created` por cada contador e histograma en el formato de texto, también para los de U0. La prueba de la allowlist compara por familia y sufijo estándar (`_total`, `_created`, `_bucket`, `_sum`, `_count`, con `le` en los buckets); usa `prometheus_client.parser.text_string_to_metric_families`.
- **Trampa: el «≤ 10 s» es tiempo real.** La página en vuelo dura lo que tarde U3, con un timeout de 5 s que `deps` aplica por fase y no a la llamada entera (`CANDIDATAS.md`, línea 524). En CA-3 usa una latencia de página corta en el doble y anota `uptime`: con la máquina cargada (8 núcleos, 14 GiB, hasta 3 codificadores y sus revisores a la vez; U11-T01 midió cargas de 10 a 33) el arranque del intérprete puede tardar varios segundos. Si CA-3 falla solo bajo carga, repítelo en serie y anota las dos corridas con su `uptime`; no subas el umbral.
- **Trampa: semiabierto.** El breaker pasa de abierto a semiabierto cuando alguien lee `state` pasados 60 s; el predicado de readiness lo lee en cada sonda. Semiabierto cuenta como «U3 no responde» (INF-U11-01) para que la readiness no oscile.
- **Paquetes de prueba sin colisión** (`CANDIDATAS.md`, línea 444): ningún `__init__.py` en `tests/`; `pytest.ini` ya usa `--import-mode=importlib`.
- **Semilla** (`CANDIDATAS.md`, línea 428): `tests/conftest.py` ya la imprime en verde; cópiala en la bitácora en cada corrida con Hypothesis.
- **Bitácora** `bitacoras/U11-T02.md`: la salida real de cada comando, pegada, con rutas absolutas a los logs largos y **sin plantillas sin expandir** (`CANDIDATAS.md`, líneas 474 y 530).
- **Máquina compartida:** corre `make check` y las corridas con el perfil `ci` en serie, nunca en paralelo, con `uptime` antes y después; usa una carpeta propia en el scratchpad para logs y temporales. U11-T01 midió ≈ 16 min para `make -C product-metrics check` con carga alta. Si una corrida pasa de 2 horas sin avanzar, detenla, anótalo y repítela.
- **Candidatas de `CANDIDATAS.md` y de `bitacoras/U11-T01.md` que esta tarea atiende:** línea 437 (código de salida con `SIGTERM`: resuelto para U11 en `main`, sin tocar U0), línea 469 (puertos fijos: puerto por argumento y puertos libres en las pruebas), línea 478 (el `main` en subproceso no cuenta en la cobertura: lógica en el mismo proceso), línea 415 (`.importlinter` no cuenta para la trazabilidad: `NFR-U11-21` citado en `main.py`), y de la bitácora de U11-T01 la candidata 2 (log del `seq` con `log_access`) y la 1 (lectura del ejemplo de ruido, en el ejemplo del reinicio).
- **Candidatas que no son de esta tarea:** de la bitácora de U11-T01, la 3 (catálogo de canales, U0) y la 5 (página vacía con `next_seq_after`, U3); la línea 524 (timeout por fase en `deps`, U0); y para U11-T03, la línea 357 (peso de la imagen por `vectra_common`) y la 511 (`/livez` frente a `/healthz`: el plan de U11 ya dice `/healthz`).
- PBT-U11-01..07 nunca se recortan. Con esta tarea quedan las siete: 01, 02, 03, 04 y 06 en U11-T01; 05 aquí; 07 en las dos.
- U11 no tiene datos propios: no hay migraciones, ni base de datos, ni nada que limpiar.
