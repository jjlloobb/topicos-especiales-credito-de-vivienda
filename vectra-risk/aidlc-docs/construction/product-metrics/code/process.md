# Resumen del proceso — U11 `product-metrics` (Pasos 6 a 9, U11-T02)

Código en `vectra-risk/product-metrics/src/vectra_product/`. Lo que hay en esta tarea: `scheduler`, `collector` y `main`, más tres
cambios a `state` y `reader` de U11-T01. `compute`, `noise` y `model` no se tocaron. **La prueba de volumen (INF-U11-06; NFR-U11-02,
03 y 13) está diferida por la demo (T3, enmienda §3 de `demo-recorte-funcional.md`, fila «7»)**: `tests/volume/` queda vacío y
ningún archivo de `product-metrics/` escribe esos tres identificadores. U11-T03 decide cuáles van en «Diferido por la demo».

## El ciclo real

`main.run(reader, params, stop=…)` sirve 8081 y corre el `Scheduler` hasta que `stop` se activa. El `Scheduler` son dos bucles que
comparten el candado del `reader` (P-U11-02):

| Qué | Cuándo | Qué hace |
|---|---|---|
| Pasada completa del arranque | al arrancar | `state.full_pass()`: lee desde el día 1 del sexto mes cerrado menos 1 día, arma el estado aparte, lo reemplaza en una sola asignación y, con el candado tomado, lee enseguida desde su `last_seq`. Luego `compute` y un solo reemplazo de lo publicado. |
| Pasada diaria | 02:30 UTC + desfase uniforme en [0, 600] s, sorteado cada día con un `random.Random` inyectable (en producción, uno por proceso sin semilla) | igual que la del arranque. |
| Ciclo incremental | cada `config.CYCLE_SECONDS` (5 min) | `state.incremental()`: si el candado está tomado devuelve `SKIPPED`, suma 1 en `vectra_product_cycles_skipped_total` y no lee ni publica. Sin pasada exitosa (`NoBaseline`) no lee, no cuenta y no publica. Con lectura exitosa recalcula y publica (también sin lecturas nuevas: `now` cambia el día). Una lectura fallida conserva lo publicado y no mueve `last_success`. |
| Plazo de la pasada | `config.FULL_PASS_DEADLINE_SECONDS` (75 min) | se comprueba **entre páginas**: si vence, la pasada falla (`PassDeadline`), el estado vigente queda intacto, el candado se libera y `vectra_product_full_pass_in_progress` vuelve a 0. |
| Reintentos | cada `config.FULL_PASS_RETRY_SECONDS` (15 min), hasta `config.FULL_PASS_RETRIES` (6) | después, ninguno hasta la diaria siguiente; el estado incremental sigue intacto y los ciclos de 5 min siguen. |
| Apagado | `SIGTERM` o `SIGINT` | `stop` se activa: no se toman ciclos nuevos, la página en vuelo **termina** (nunca se cancela a mitad), la pasada a medias se descarta (el estado vigente queda intacto), el servidor se detiene y el proceso sale con código 0. |

`vectra_product_full_pass_in_progress` vale 1 desde que la pasada empieza a esperar el candado hasta que termina, falla, vence o se
descarta. Los relojes de pared y monótono, la espera y el generador son parámetros del `Scheduler`: ninguna prueba duerme minutos reales.

**El código de salida 0.** `main` trata `SIGTERM` y `SIGINT` con `loop.add_signal_handler`, que activa `stop`; ese manejador del bucle es el que da el
código 0 (C-4, P-6 (a) de U11-T03). `uvicorn.Server.serve()` captura las señales mientras sirve y, al salir, las vuelve a emitir al manejador que tenía el
bucle, de modo que el proceso no muere con estado `-15`. Esta unidad ya no sobreescribe `capture_signals` (el override era redundante: el revisor de U11-T02
midió que el manejador del bucle basta y ninguna prueba lo ejercía); las pruebas del proceso real (`test_main_process.py`) y la de la imagen
(`test_image.py`, `docker stop`) fijan el código 0. No se tocó `ops_server.serve` de U0 (su estado de salida es la candidata de `CANDIDATAS.md`, línea 437).

## Readiness

`/readyz` (`main.make_readiness`) da 200 si hay instantánea publicada **o** `reader.breaker_state` es `OPEN` o `HALF_OPEN`; si no, 503.
Una pasada fallida o vencida no basta; al cerrarse el breaker sin instantánea vuelve a 503; un predicado que lanza una excepción es 503
(lo resuelve `ops_server`). Semiabierto cuenta como «U3 no responde» para que la readiness no oscile. `/healthz` es solo el proceso.

## Qué se publica y cuándo

- **Una** instantánea inmutable (`collector.Published`): el `BusinessMetrics` de `compute`, los `Params`, el `now` del cálculo,
  `last_success_at` y `last_full_recompute_at`. `Holder` guarda una sola referencia y `Collector.collect()` la lee **una sola vez**: un
  scrape nunca mezcla dos ciclos. `BusinessMetrics` no trae `last_success` (P-U11-03 dice que sí): no se agregó a `compute`.
- **Sin instantánea:** ninguna serie de producto ni `vectra_product_metrics_last_success_timestamp` (nunca ceros).
  `vectra_product_last_full_recompute_timestamp` no se emite hasta la primera pasada completa exitosa.
- **Series de operación, siempre** (`collector.Operations`, en el registro de U0): `vectra_product_cycle_duration_seconds{kind}` con los
  buckets 1, 5, 15, 30, 60, 120, 300, 600, 1200, 1800 y 3600 s (creado con `vectra_common.metrics.histogram`),
  `vectra_product_entries_read_total{kind}`, `vectra_product_full_pass_in_progress`, `vectra_product_cycles_skipped_total` y
  `vectra_circuit_state{dependency="decision-registry"}` (del breaker de U0). `kind` es `incremental` o `full`.
- **Series de producto:** exactamente las de la primera tabla de domain-entities §5. Los conteos van con todos los cortes y sin filas
  `all`; las razones, solo en el total y por un corte; una razón con denominador 0 no se emite. `month="AAAA-MM"` solo con
  `period="month"` (las demás series no tienen la clave `month`, ni vacía). Las series de consulta de explicación llevan
  `period="7d"` y nunca `month` (el plan y §5, posteriores a NFR-U11-10, mandan; NFR-U11-10 se cumple con los 6 meses cerrados de la
  North Star y la sostenida). `vectra_product_unattributable_decisions` solo con `day`, `30d` y `month_to_date`.
- **Allowlist como dato:** `collector.PRODUCT_SERIES` y `collector.OPERATION_SERIES` (serie → conjunto de etiquetas; los contadores con
  `_total`; del histograma salen `_bucket` con `le`, `_sum`, `_count` y `_created`). Las usan el `collector`, las pruebas y, en U11-T03,
  `tools/gen_rules.py` (Paso 12). La prueba de la allowlist no se compara contra esa constante: transcribe las tablas de §5.
  `collector.TARGET_METRICS` lista los valores de `metric`.

## Decisiones de las preguntas de la tarea

El usuario fusionó la tarea sin responder: rige la opción por omisión de cada una.

- **P-1 (a).** Un fallo por intento: con U3 caído al arrancar, el breaker abre al tercero, a los 30 min (reintentos cada 15 min). El «unos
  15 s» de INF-U11-01 **no** se cumple; `/readyz` da 503 durante esos 30 min. Candidata de diseño (`CANDIDATAS.md`). El escenario que lo
  sufriría (rollout con U3 caído, Paso 16.3) está diferido.
- **P-2 (b).** Mientras **nunca** haya habido una pasada exitosa, el reintento cada 15 min no tiene tope; el tope de 6 rige con estado.
- **P-3 (a).** La diaria corre en el primer instante «02:30 UTC + desfase» posterior al arranque y después cada día (una vez por día, con
  su propio desfase), haya corrido o no la del arranque.
- **P-4 (a).** `vectra_product_origination_seconds{quantile,standard="true"}` y `…_standard_under_target_ratio` publican el día de
  **ayer**; si ayer no hubo casos estándar, la serie no se emite (no 0).
- **P-5 (a).** `vectra_product_target{metric}` con `complete_response`, `origination_hours`, `origination_ratio`,
  `sustained_ratio_month6`, `north_star` (solo si `target_north_star` no es `null`) y `noise_floor`. S y N no se publican.

## Entorno y arranque (para U11-T03)

Solo `main.py` lee variables de entorno, y solo de cableado; `config.py` y `params.py` siguen sin leerlo. Ninguna constante del ciclo
sale del entorno.

| Variable | Uso |
|---|---|
| `VECTRA_REGISTRY_URL` | obligatoria; URL de U3 (el mismo nombre que usa U9). Sin ella el proceso sale con código 3. |
| `VECTRA_POLICY_PATH` | opcional; por omisión `params.POLICY_PATH` (`/etc/vectra/product-metrics-policy/values-product-metrics-policy.yaml`). Un archivo inválido: código 2, sin servir nada. |
| `VECTRA_CLIENT_ID`, `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_KEY_PATH`, `VECTRA_CLIENT_KEY_ID` | las lee `vectra_common.service_token.provider_from_env`. |
| `VECTRA_CA_BUNDLE` | la lee `vectra_common.deps` si `VECTRA_REGISTRY_URL` es `https://`. |

- **Comando de arranque de la imagen:** `python -m vectra_product.main`. Sirve 8081 (`/metrics`, `/healthz`, `/readyz`); no hay 8080 ni
  rutas de negocio. `main(port=OPS_PORT)` recibe el puerto como argumento (las pruebas usan puertos libres, no variables de entorno).
- Códigos de salida: 0 tras `SIGTERM`/`SIGINT`; 2 con parámetros inválidos; 3 sin `VECTRA_REGISTRY_URL`.
- `terminationGracePeriodSeconds: 10` (INF-U11-01): el apagado espera a la página en vuelo, que tarda lo que tarde U3 (timeout de 5 s por
  fase que `deps` aplica por fase y no a la llamada entera, `CANDIDATAS.md`, línea 524).

## Cambios permitidos a U11-T01

- `state.py`: un punto de parada entre páginas (`checkpoint`, para `SIGTERM` y para el plazo; `Stopped` y `PassDeadline`); el número de
  entradas leídas por página (`on_read`, para `vectra_product_entries_read_total{kind}`); y el `seq` de una entrada excluida por
  `vectra_common.logging.log_access(seq=…)` (antes `logging` estándar, cuyo texto el filtro de U0 descarta una vez que `main` llama a
  `configure`: el `seq` desaparecía del log sin que nada fallara; atiende la candidata 2 de la bitácora de U11-T01). Los logs propios
  usan solo campos de `LOG_RECORD_FIELDS`.
- `reader.py`: sin cambios de código (el candado y `breaker_state` ya bastaban). `tests/integration/test_reader.py`: el caso del `seq`
  en el log lee ahora la salida JSON del logger configurado en lugar de `caplog`; PBT-U11-02 no se tocó.

## Pruebas

`tests/integration/`: `test_process.py` (arranque, readiness, plazo, `SIGTERM`, desfase, reintentos, ciclo omitido, logs en modo strict;
reloj simulado), `test_collector.py` (PBT-U11-05 y PBT-U11-07 sobre las series publicadas, `month`, scrape durante el reemplazo,
readiness), `test_examples.py` (ejemplos con E/S del Paso 7) y `test_main_process.py` (el proceso real como subproceso, con el doble de
U3 y un emisor de token servidos por HTTP). Dobles nuevos: `process_world.py`, `virtual_time.py` y `http_servers.py`.

## Cobertura (Paso 8, NFR-U11-30)

`make -C product-metrics check` corre, además de la cobertura del 100 % de `compute` y `noise`, la de ≥ 90 % de ramas sobre
`vectra_product` entero (todas las pruebas, también las del proceso real). Los números de la última corrida están en la bitácora
(`bitacoras/U11-T02.md`); `main()` se ejerce también en el proceso de la prueba (`test_main_in_the_test_process…`) para que la cobertura
lo vea, además de en el subproceso.

## Qué no está aquí

La prueba de volumen y el benchmark de `compute` (diferidos, T3); `mutmut` (T3); imagen, chart, reglas `:dedup`, alertas, dashboards,
runbooks, workflow y cierre (Pasos 10 a 18, U11-T03 y U12). Paso 9: U11 no tiene `migrations/` ni `frontend/`.
