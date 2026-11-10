# U03-T07 — Tope por solicitud en `POST /v1/monitoring/daily:query` y medición por solicitud en `test_queries.py`

**Unidad:** U3 `decision-registry`
**Historias que toca:** ninguna nueva. Cierra la candidata **«Prioritaria (U3, antes de la verificación en kind)»** de `CANDIDATAS.md` (revisor, U03-T03 ronda 2, F-01). La nombran U03-T06 P-1 y el `cierre-demo.md` de U3, en «Candidatas abiertas».
**Decisión del usuario:** 2026-11-10, abrir esta tarea (U03-T06 P-1, opción (a)).
**Depende de:**
- en `main`: U03-T03 (`queries.py`, `pools.py`, `test_queries.py`) y U09-T03 (#122, `bias-monitoring/src/vectra_bias/registry_client.py` y `dashboard.py`), que son los llamadores reales;
- **conviene que U03-T06 esté fusionada antes**, porque esta tarea actualiza la sección «Candidatas abiertas» del `cierre-demo.md` de U3 que U03-T06 crea. Si U03-T06 no está en `main`, la tarea no toca `cierre-demo.md` y deja la actualización anotada en la bitácora.

**Se despacha** antes de U12 (enmienda §8: la verificación en kind de U3 está consolidada en U12 Paso 18). Puede correr en paralelo con tareas que no toquen `decision-registry/`.
**Rama:** `tarea/U03-T07`, desde `origin/main`.

Es un arreglo del Paso 8 del plan de U3 (`aidlc-docs/construction/plans/decision-registry-code-generation-plan.md`), ya marcado `[x]` por U03-T03. No reabre el paso. Hace cumplir dos viñetas de su aceptación que hoy solo se cumplen a medias:
- «`POST /v1/monitoring/daily:query` con 12 rangos de 90 días responde dentro del tiempo límite del pool `projections` (2 s)»;
- «una consulta `explanation` concurrente no supera su límite» (segunda revisión del FD de U9, 2026-10-08).

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea.

---

## El problema, medido (de la candidata)

- **Sin tope por solicitud.** `queries.monitoring_daily` corre unas 16 sentencias en una sola transacción del pool `projections`: una por rango, más totales, versiones, `unattributable` e `invalid_seqs`. `start_read` pone `SET LOCAL statement_timeout = STATEMENT_TIMEOUT_MS` (2 000 ms), y eso corta **cada sentencia**, no la solicitud. Una consulta de 12 rangos **sin versión** retiene así la **única** conexión del pool `projections` (`POOL_SIZES["projections"] = (1, 2.0)`) hasta unos 16 × 2 s, y deja sin conexión a `GET /v1/entries` (`explanation`, U7) y al gauge del atraso.
- **Una medición que esconde los fallos.** `test_f04_300_mil_filas_diarias_con_12_rangos_responden_en_menos_de_2_s` usa `best_of`: toma el **mínimo** de 3 medidas y **descarta los 504**. Medido solicitud por solicitud, 4 de 10 del peor caso superan 2 s, hasta 9,6 s.
- **La forma que usa U9 no está afectada hoy.** Con versión tarda 0,14–0,21 s. Pero el dashboard de U9 hace una consulta de descubrimiento **sin versión** (`dashboard.py:77-89`: un rango de la población `modelo`, con `include_versions=True`).
- **Sentencias preparadas que se degradan.** La candidata pide además investigar por qué las sentencias preparadas en la réplica se degradan al repetirse.

---

## Alcance

**Dentro:**

1. **Tope por solicitud** en `monitoring_daily` (`decision-registry/src/vectra_registry/queries.py`):
   - Un presupuesto único para toda la solicitud. Arranca **al obtener la conexión** del pool `projections` (P-2), porque lo que hay que acotar es cuánto tiempo se retiene la conexión.
   - Antes de cada sentencia, `statement_timeout` se fija al **mínimo** entre `STATEMENT_TIMEOUT_MS` y el presupuesto restante. Si el presupuesto ya se agotó, la solicitud termina sin lanzar la sentencia siguiente. Es el mismo patrón que `append._commit`, que descuenta lo transcurrido (`append.py:261`).
   - **Valor del tope:** una constante tipada, `QUERY_BUDGET_S: Final`, que **se deriva** del tiempo límite del pool `projections` (`pools.POOL_SIZES["projections"][1]`, 2 s). Ese es el valor que fija el diseño: `nfr-design/nfr-design-patterns.md`, fila `projections` de la tabla de pools; y la aceptación del Paso 8, «responde dentro del tiempo límite del pool `projections` (2 s)». Ningún literal `2`, `2.0` ni `2000` en el punto de decisión (P-1).
   - **Al pasarse:** 504 con `code = deadline_exceeded`, levantando `DependencyTimeout` como hoy (`queries.timed_out`). Es el significado de U0 para «presupuesto agotado durante el trabajo» (`contracts/functional-design/domain-entities.md`, tabla de códigos, fila `deadline_exceeded`; NFR-U0-23). No hace falta ningún `ProblemReason` nuevo (P-3).
   - La conexión vuelve al pool **utilizable**: la solicitud siguiente responde 200.
   - Mismo tope para `monitoring_freezes` y `GET /v1/entries`, **solo si** comparten la función de inicio de lectura (`start_read`) y el cambio no altera su comportamiento medido. Si no, quedan como están y se anota en la bitácora (P-4).
2. **Medición por solicitud** en `decision-registry/tests/integration/test_queries.py`:
   - Se retira `best_of`. Cada medida exige **200** y su propio tiempo ≤ `QUERY_BUDGET_S`, sin descartar 504 ni tomar mínimos.
   - **Formas reales de U9**, 10 solicitudes seguidas cada una (sección siguiente):
     - (a) 12 rangos **con** versión, 4 por versión y 3 versiones, el primero con `unattributable_range`, como fija `aidlc-docs/construction/bias-monitoring/nfr-design/nfr-design-patterns.md` (paso 1 del CronJob) y construye `vectra_bias.window.version_ranges`;
     - (b) el descubrimiento del dashboard: 1 rango sin versión de 90 días de `modelo`, con `include_versions=True`.
   - **El peor caso** (12 rangos sin versión, las dos poblaciones) se **reetiqueta**. Ya no promete 200 en ≤ 2 s; prueba el tope: cada una de 10 solicitudes responde **200 o 504** (ningún otro código), dentro de `QUERY_BUDGET_S + TOPE_MARGEN_S` (P-5), y una consulta `explanation` concurrente responde 200 dentro de su límite (BR-U3-17, Paso 8).
   - El volumen sigue siendo el de NFR-U3-35: 3 versiones × 594 celdas × 180 días (`full_volume_rows`).
3. **Sentencias preparadas** (P-6):
   - Se investiga con `EXPLAIN (ANALYZE, BUFFERS)` en la réplica de Testcontainers: plan de la sentencia de rango en la ejecución 1 y en la ejecución 6 o posterior (`prepare_threshold` de psycopg es 5 por omisión), con versión y sin versión. El resultado queda en la bitácora.
   - Si la causa es el plan genérico, la sentencia de rango se ejecuta sin preparar (`prepare=False`) y se cita la evidencia. Si no, no se cambia nada y la causa medida queda en `CANDIDATAS.md`.
4. **Documentación:**
   - `aidlc-docs/construction/decision-registry/code/api-summary.md`: el tope, su origen y el 504.
   - En el plan, una nota en el Paso 8: «(tope por solicitud de `daily:query` y medición por solicitud: U03-T07)», **sin cambiar** la casilla ni el texto del paso.
   - En `CANDIDATAS.md`, la entrada «Prioritaria (U3, antes de la verificación en kind)» pasa a cerrada, con referencia a esta tarea. Lo que quede sin resolver va en una entrada nueva.
   - Si U03-T06 ya está en `main`, se actualiza la viñeta correspondiente de «Candidatas abiertas» del `cierre-demo.md` de U3.

**Fuera:**
- Cambios en U0 (`MonitoringQuery`, catálogo de códigos), en U9 o en el chart de U3. Si el tope obliga a cambiar algo de U9 (por ejemplo `QUERY_TIMEOUT_S`), **detente y repórtalo**.
- El índice o el esquema de `monitoring_daily` (migraciones). Si la investigación de P-6 señala un índice, se registra como candidata.
- Los benchmarks del Paso 17 (diferido por la demo, T3) y la p95 ≤ 200 ms de NFR-U3-24, que se mide en kind (U12 Paso 18).
- La candidata de `test_dossier.py:148` (U03-T05, ronda 2, F-02), salvo que el cambio de `start_read` la toque.

---

## Archivos de contexto

- `CANDIDATAS.md`: «Prioritaria (U3, antes de la verificación en kind)» y la de U03-T05 F-02 sobre los límites de 2 s.
- `tareas/U03-T06-cierre.md`, P-1.
- `revisiones/U03-T03/` (la ronda 2, F-01, origen de la candidata).
- `aidlc-docs/construction/plans/decision-registry-code-generation-plan.md`: Paso 8 y su aceptación.
- `aidlc-docs/construction/decision-registry/nfr-design/nfr-design-patterns.md`: P-U3-02 (patrón de presupuesto del append) y la tabla de pools (fila `projections`).
- `aidlc-docs/construction/decision-registry/nfr-requirements/nfr-requirements.md`: NFR-U3-24 y NFR-U3-35.
- `aidlc-docs/construction/decision-registry/functional-design/business-rules.md`: BR-U3-13b (lecturas cortas en la réplica) y BR-U3-17.
- `aidlc-docs/construction/contracts/functional-design/domain-entities.md`: tabla de códigos (`deadline_exceeded`) y NFR-U0-23.
- `decision-registry/src/vectra_registry/queries.py`, `pools.py`, `append.py` (`_commit`) y `api.py`.
- `decision-registry/tests/integration/test_queries.py` (`daily`, `query`, `day_range`, `seed_daily`, `full_volume_rows` y los dos tests `test_f04_*` y `test_br_u3_17_*`).
- `bias-monitoring/src/vectra_bias/config.py` (`QUERY_TIMEOUT_S = 5`), `registry_client.py`, `dashboard.py` y `window.py`.
- `aidlc-docs/construction/bias-monitoring/nfr-design/nfr-design-patterns.md`: forma de las solicitudes y tabla de timeouts (F26, 5 s por solicitud).
- `aidlc-docs/construction/plans/demo-kind-alcance.md` §6.

---

## Criterios de aceptación

Todos desde `vectra-risk/`. Los de integración levantan Testcontainers (primaria y réplica), como `test_queries.py` hoy.

**CA-1 — El tope corta la solicitud y libera la conexión.** Una prueba nueva en `test_queries.py` hace dos cosas:
- con `QUERY_BUDGET_S` reducido por `monkeypatch` a un valor menor que lo que tarda la forma (a) con el volumen de NFR-U3-35, la consulta responde **504** con `code = deadline_exceeded`;
- la solicitud siguiente, con el presupuesto real, responde **200** (la conexión del pool quedó utilizable).

```
uv run pytest decision-registry/tests/integration/test_queries.py -k "tope" -v
```
**Rojo previo:** sobre `main` no hay tope, así que con el presupuesto reducido la consulta responde 200 y la prueba falla. La bitácora guarda la salida del rojo y del verde.

**CA-2 — Las formas de U9 responden 200 en cada solicitud.** Para las formas (a) y (b) del Alcance, 10 solicitudes seguidas cada una: **todas** 200, y cada una ≤ `QUERY_BUDGET_S`. La prueba imprime los 10 tiempos de cada forma, que van a la bitácora.

```
uv run pytest decision-registry/tests/integration/test_queries.py -k "forma_de_u9" -v -s
```
**Rojo previo:** la misma aserción por solicitud aplicada al **peor caso** sobre `main` falla (la candidata midió 4 de 10 por encima de 2 s). La bitácora guarda esa corrida. Si en esta máquina no reproduce, lo dice y guarda los 10 tiempos.

**CA-3 — El peor caso respeta el tope y no deja sin conexión a `explanation`.** La prueba reetiquetada del peor caso: 10 solicitudes, cada una 200 o 504, cada una dentro de `QUERY_BUDGET_S + TOPE_MARGEN_S`. En paralelo, dos consultas `explanation` (como `test_br_u3_17_una_consulta_explanation_concurrente_no_supera_su_limite`) responden 200, cada una dentro del tiempo límite del pool.

```
uv run pytest decision-registry/tests/integration/test_queries.py -k "peor_caso" -v -s
```
**Rojo previo:** sobre `main`, la aserción de tiempo por solicitud falla (hasta 9,6 s según la candidata) o `explanation` supera su límite.

**CA-4 — Sin `best_of` y sin literales en el punto de decisión.**
```
! grep -n "best_of\|min(timings)" decision-registry/tests/integration/test_queries.py \
&& uv run python -c "from vectra_registry import pools, queries; assert queries.QUERY_BUDGET_S == pools.POOL_SIZES['projections'][1]" \
&& ! grep -nE "statement_timeout = (2000|2)\b|timeout=2(\.0)?\b" decision-registry/src/vectra_registry/queries.py
```

**CA-5 — El tope de U3 cabe dentro del timeout de U9.**
```
uv run python -c "from vectra_registry.queries import QUERY_BUDGET_S; from vectra_bias import config; assert QUERY_BUDGET_S < config.QUERY_TIMEOUT_S, (QUERY_BUDGET_S, config.QUERY_TIMEOUT_S)"
```
U9 (CronJob y servicio) recibe así un 504 de U3 antes de agotar su propio timeout de 5 s por solicitud, y lo trata como `RegistryError` (BR-U9-10: la corrida falla con `reason=lectura` y nunca congela).

**CA-6 — U9 no se rompe.**
```
make -C bias-monitoring check
```
termina en 0. El diff no toca `bias-monitoring/` (`git diff origin/main --stat -- bias-monitoring/` vacío).

**CA-7 — Sentencias preparadas (P-6).** La bitácora contiene las dos salidas de `EXPLAIN (ANALYZE, BUFFERS)` (ejecución 1 frente a ejecución ≥ 6, con y sin versión) y la decisión. Si se aplicó `prepare=False`, CA-2 lo demuestra con los 10 tiempos sin degradación (el décimo no supera al doble del primero). Si no, `CANDIDATAS.md` tiene la entrada con la causa medida:
```
grep -n "U03-T07" CANDIDATAS.md
```

**CA-8 — Unidad, platform y documentación.**
```
make -C decision-registry check && make -C platform check \
&& grep -n "QUERY_BUDGET_S" aidlc-docs/construction/decision-registry/code/api-summary.md \
&& grep -n "U03-T07" aidlc-docs/construction/plans/decision-registry-code-generation-plan.md
```
Las dos órdenes `make` terminan en 0. La cobertura de ramas de `decision-registry` no baja del umbral del `Makefile` (`coverage`). El diff del plan es solo la nota del Paso 8. `uv run python platform/tests/test_traceability.py --unit decision-registry --all` no da fallos nuevos frente a `main`.

---

## Plan de pruebas

| Prueba | Qué demuestra | Rojo previo |
|---|---|---|
| `test_..._tope_corta_la_solicitud_y_libera_la_conexion` | CA-1 | 200 sobre `main` con el presupuesto reducido |
| `test_..._forma_de_u9_cron_12_rangos_con_version_200_en_cada_solicitud` | CA-2 (a) | — (la forma de U9 pasa hoy; el rojo es CA-2 sobre el peor caso) |
| `test_..._forma_de_u9_descubrimiento_sin_version_200_en_cada_solicitud` | CA-2 (b) | ídem |
| `test_..._peor_caso_sin_version_respeta_el_tope_y_libera_la_conexion` | CA-3 | > `QUERY_BUDGET_S + margen` sobre `main` |

Los nombres siguen el estilo de `test_queries.py` (en español, con el id: `test_br_u3_17_...` o `test_f04_...`).

---

## Preguntas

**P-1 — Valor del tope.** El diseño no tiene una fila de «timeout total del handler» para las lecturas. La tiene solo el append (P-U3-02, 2,5 s). Para `daily:query` la aceptación del Paso 8 dice «dentro del tiempo límite del pool `projections` (2 s)». Opciones:
- (a) `QUERY_BUDGET_S` = el tiempo límite del pool `projections` (2 s), derivado de `POOL_SIZES`;
- (b) 2,5 s, por analogía con P-U3-02.

**Recomendación: (a).** Es el número que nombra la aceptación del Paso 8. Además, mientras la conexión no se retiene más de 2 s, una `explanation` que espera hasta 2 s por el pool la obtiene a tiempo. Si nadie responde, rige (a).

**P-2 — Cuándo empieza a contar el presupuesto.** (a) al obtener la conexión; (b) al entrar al handler (incluye la espera por el pool). **Recomendación: (a).** El defecto es retener la conexión. La espera por el pool ya tiene su propio límite de 2 s (`POOL_SIZES`). Con (b), una solicitud que esperó 1,9 s solo tendría 0,1 s para trabajar. Si nadie responde, rige (a).

**P-3 — Código al pasarse.** (a) 504 `deadline_exceeded` (`DependencyTimeout`, lo que devuelve hoy `timed_out`); (b) 503 `dependency_unavailable`, como los tiempos límite del append (P-U3-02). **Recomendación: (a).** U0 define 504 `deadline_exceeded` como «presupuesto agotado durante el trabajo» (domain-entities, tabla de códigos), y no cambia lo que U9 ya recibe ni cómo lo trata (`RegistryError`). Si nadie responde, rige (a).

**P-4 — ¿El tope también en `monitoring_freezes` y `GET /v1/entries`?** Las dos hacen pocas sentencias por solicitud: el riesgo de retener la conexión es bajo. **Recomendación:** aplicar el mismo `start_read` con presupuesto solo si el cambio es la misma función y no cambia ningún resultado medido de sus pruebas. Si no, dejarlas y anotarlo. Si nadie responde, rige la recomendación.

**P-5 — Margen de la aserción del peor caso.** La consulta puede tardar algo más que el presupuesto: la última sentencia corta en `statement_timeout`, y hay que sumar el rollback y la respuesta HTTP. **Recomendación:** `TOPE_MARGEN_S = 0.5` como constante del módulo de pruebas, con su comentario, y la medición real en la bitácora. Si la máquina cargada lo hace intermitente, se sube solo en el perfil de pruebas y se registra (candidata de U03-T05 F-02). Si nadie responde, rige la recomendación.

**P-6 — Alcance de la investigación de las sentencias preparadas.** **Recomendación:** acotarla a lo que describe el Alcance, punto 3: dos `EXPLAIN` y una decisión. Si el arreglo no es `prepare=False` en la sentencia de rango, va a `CANDIDATAS.md` y no a esta tarea. Si nadie responde, rige la recomendación.

---

## Notas

- **Rojo primero.** Cada criterio con prueba registra en la bitácora su rojo sobre `main` (o con la mutación indicada) y su verde, con el comando y la salida real.
- Los tiempos se miden con `time.monotonic()` alrededor de cada solicitud HTTP, como hoy.
- No toques `vectra-risk/pyproject.toml` ni `uv.lock`.
- Si `make -C identity-edge check` u otra unidad falla en `main` por causas ajenas, no es criterio de esta tarea: anótalo y no lo arregles.
