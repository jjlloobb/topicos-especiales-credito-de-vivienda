# Ronda 2: U03-T07

VEREDICTO: NO-VERDE

Revisé el HEAD `0989ed5`; el código de esta ronda está en `4859247` y `d428ecd`. Rige el arbitraje `arbitraje-ronda-1.md` (tope = espera del pool menos `QUERY_RELEASE_MARGIN_S`, y CA-4 enmendado). Al terminar, el worktree quedó limpio: `git status --short` da 0 líneas. Las mutaciones las corrí sobre copias del paquete en el scratchpad, cargadas con `PYTHONPATH`; no toqué ningún archivo del worktree.

La carga nunca bajó de 5,2. El clúster kind está levantado de forma permanente y otro agente corría suites a la vez.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | El tope corta y libera la conexión | `-k "peor_caso or tope"`, dentro de M6, y la suite completa en `make check` | pasa |
| 2 | Formas de U9: 200 y ≤ 1,5 s en cada solicitud | `-k forma_de_u9`, 16 corridas, más `make check` | **falla en 3 de 17**: u9-03, u9-06 y la corrida de `make check` |
| 3 | Peor caso: 200 o 504 dentro de 2,0 s; `explanation` 200 en menos de 2 s | `-k peor_caso`, 15 corridas | **falla en 1 de 15** (pc-15) |
| 4 | Enmendado: sin `best_of` y sin literales | los tres comandos, con el `python -c` enmendado | pasa: `0.5 1.5` |
| 5 | `QUERY_BUDGET_S` < `QUERY_TIMEOUT_S` | el `python -c` de la tarea | pasa: 1,5 < 5 |
| 6 | U9 no se rompe | `git diff a10b930 --stat -- bias-monitoring platform` | da vacío. **No corrí** `make -C bias-monitoring check` ni `make -C platform check`: no me quedó margen y el diff no toca esas unidades |
| 7 | Sentencias preparadas | `grep U03-T07 CANDIDATAS.md` y las mutaciones M5a y M5b | pasa: las dos mutaciones mueren 2 de 2 por la guarda de `pg_prepared_statements` |
| 8 | Unidad y documentación | `make -C decision-registry check`, de 14:36 a 14:57, con carga de 9,9 a 13,5 | **exit 2**: `1 failed, 671 passed`. Falla el cron (forma a) con **504 a 1,668 s en la primera solicitud**. La cobertura es 96,10 %, sobre el mínimo de 95. Los dos greps de documentación pasan. `test_traceability --all` da 41 identificadores y rc 0 |

Detalle de las corridas de CA-2 y CA-3, por banda de la carga a 1 minuto medida antes de cada corrida:

| Prueba | Carga | Corridas | Fallos |
|---|---|---|---|
| `forma_de_u9` | < 8 | 8 | 1 (u9-03) |
| `forma_de_u9` | ≥ 8 | 8 | 1 (u9-06) |
| `forma_de_u9` | ≈ 10 a 13 | 1 (la de `make check`) | 1 |
| `peor_caso` | < 8 | 7 | 1 (pc-15) |
| `peor_caso` | ≥ 8 | 8 | 0 |

**Ojo con la banda: es un mal predictor.** La carga sube durante la corrida: pc-15 pasó de 6,1 a 16,5 y u9-03 de 5,7 a 8,7.

## Hallazgos

### F-01 · ROJO · CA-2, CA-3 y CA-8 · `queries.py:36-40` con `test_queries.py:633-661` · las formas reales de U9 no caben de forma fiable en el tope de 1,5 s con esta máquina
La causa de cada fallo, con los tiempos medidos:
- **u9-06** (carga de 15,9 a 12,3). La forma (a), el cron, tarda 1,250 s y 1,238 s en las dos primeras solicitudes, y la tercera da **504 a 1,533 s**. El tope cortó una consulta legítima que bajo carga tarda más.
- **`make check`** (carga de 9,9 a 13,5). El cron da **504 a 1,668 s en la primera solicitud**. Misma causa.
- **pc-15** (carga de 6,1 a 16,5). Las 10 solicitudes del peor caso y todas las `explanation` cumplen: 200 en 1,57 a 1,59 s, dentro de 2 s. Falla la comprobación final, «la conexión quedó utilizable»: la forma (b), el descubrimiento, da **504 a 1,54 s**. No es una conexión rota: es la misma consulta legítima cortada por el tope.
- **u9-03** (carga de 5,7 a 8,7). Falla la aserción `last <= 2*first` del descubrimiento: 0,891 frente a 2 × 0,410, sin ninguna sentencia preparada (ver F-02).
- **No vi 200 de las formas de U9 por encima de 1,5 s.** Sí los vi en el peor caso: 200 hasta 1,728 s (pc-12, carga 8,4). Eso confirma que el tope corta sentencias y no la respuesta.

Mis cifras coinciden con las del codificador: él midió 5 de 50 corridas y un `check` en exit 2; yo, 3 de 17 en CA-2 y mi `check` también en exit 2. **El codificador no exageró; el defecto es real.** Lo marco ROJO porque CA-2 exige 200 y ≤ tope en cada solicitud, y la tarea pide que se cumpla de forma fiable. El arbitraje ya anticipaba este límite inferior del tope («el tope no puede dejar esas formas en 504»).

**Con la máquina sin otra carga: no lo sé, y no extrapolo.** No logré ninguna corrida con carga baja: el mínimo fue 5,2, y kind está siempre arriba. Con carga de 5 a 8, la mediana fue de 0,2 s en el cron y de 0,13 a 0,25 s en el descubrimiento. Pero vi primeras solicitudes de **1,141 s** (u9-01, carga 5,9) y **1,003 s** (u9-09, carga 5,7): un 67 a 76 % del tope con carga moderada. Eso no es «cómodamente bajo el tope». La demo corre sobre kind, en esta misma máquina.

Decisión para el usuario: ningún margen cumple CA-2 y CA-3 a la vez de forma fiable con esta carga. Sin margen, M7 da 503 en la `explanation` en 6 de 6 corridas. Con 0,5 s, el cron recibe 504 en los picos. Las opciones del codificador (i) a (iii) siguen siendo las que hay.

### F-02 · NARANJA · `test_queries.py:649` y `:655` · la aserción `timings[-1] <= 2*timings[0]` ya no detecta nada y falla sola
- **En el descubrimiento, sobra.** M5a (quitar `prepare=False` del rango) y M5b (quitarlo de `versions`) mueren 2 de 2 cada una por la guarda de `pg_prepared_statements`. La razón 2x **no los detectó en ninguna**: en M5a, 0,850 → 0,629 s; en M5b, 0,500 → 0,472 s y 0,615 → 0,978 s. Además produjo un rojo falso sin causa (u9-03).
- **En el cron no tiene a qué proteger**, porque el plan con versión no cambia (lo medí en la ronda 1). Con una primera solicitud fría (1,141 s, o 0,649 s en u9-15) no puede fallar, y con un pico al final falla en falso. El codificador registra 2 fallos así.
- Lo exige la letra de CA-7 («el décimo no supera al doble del primero»). Por eso no se puede quitar sin decisión: **quitarla es una enmienda de CA-7**, y la guarda determinista ya cubre su propósito en el descubrimiento.

### F-03 · AMARILLO · `test_queries.py` (peor caso) · la mutación M6 (quitar el `min()`) sobrevive 1 de 3 corridas
M6 deja `statement_timeout` fijo en 2000 ms. Muere en m6-1 (2,17 s) y en m6-2 (2,09 s), pero sobrevive en m6-3: 10 respuestas 504 entre 1,57 y 1,89 s, todas por debajo de 2,0 s. Con el margen de 0,5 s, el `min()` solo se nota cuando la última sentencia pasa de 2,0 s. La detección es probabilística.

### F-04 · AMARILLO · documentación desactualizada
- `api-summary.md:34` dice «La sentencia de rango va sin preparar»; hoy también va sin preparar la de `versions`.
- `CANDIDATAS.md:254` sigue diciendo «derivado de POOL_SIZES, 2 s». La línea 255 lo corrige, pero la 254 quedó desactualizada.

### Ronda 1, punto por punto
- **F-01 de la ronda 1:** **atendido**, y su variante sigue en pie como F-01 de esta ronda:
  - la constante y la derivación están bien;
  - CA-4 enmendado detecta M7 (sin margen) y M7b (margen 0);
  - CA-3 detecta M7 en 6 de 6, con 503 entre 2,020 y 2,036 s y el `daily` en 504 a ~2,11 s;
  - quité el retraso artificial y confirmé que la `explanation` sale a la vez que el `daily`.
- **F-02 de la ronda 1:** atendido. M5 queda en rojo de forma determinista.
- **F-03 de la ronda 1:** atendido. Hay un `arm` por sentencia en `monitoring_lag`.
- **F-04 de la ronda 1:** atendido. La aserción vuelve a `waited < POOL_SIZES['projections'][1]`.
- **Fila 20 de `cierre-demo.md`:** es honesta (registra exit 0 y exit 2). Mi `check` confirma el exit 2.
- **Alcance:** el diff solo toca `decision-registry/`, la documentación de U3, el plan, la bitácora, `CANDIDATAS.md` y `revisiones/`. No hay desborde.
- **Hallazgo propio del codificador** (`prepare=False` en `versions`): es correcto y cabe en P-6. M5b lo demuestra.

## Tareas candidatas (defectos reales fuera de alcance)
- La consulta sin versión hace `Parallel Seq Scan`, sin usar el índice. Ya está en `CANDIDATAS.md:256`. Si se resuelve, el descubrimiento ganaría holgura bajo carga.
- Las suites de integración con tiempos absolutos comparten la máquina con kind y con otros agentes. Hace falta una política de carga para `make check`, emparentada con la candidata de U03-T05 F-02.

## Rutas de transcripciones largas
Todas están en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u03-t07-r2/`:
- `resumen.txt`: las 31 corridas de CA-2 y CA-3, con la carga y los tiempos de cada una;
- `runs/u9-NN.log` y `runs/pc-NN.log`: cada corrida completa;
- `resumen-mut.txt`, `mut/m5a-*.log`, `mut/m5b-*.log`, `mut/m6-*.log`, `mut/m7-*.log` y `mut-ca4.log`: las mutaciones;
- `check-dr-1.log`: el `make check` completo, con la carga antes y después.

```
VEREDICTO: NO-VERDE
ROJO|CA-2, CA-3 y CA-8, queries.py:36-40|las formas reales de U9 reciben 504 con tope de 1,5 s bajo carga (3 de 17 en CA-2, 1 de 15 en CA-3; make check exit 2 con el cron en 504 a 1,668 s)
NARANJA|test_queries.py:649 y :655|la aserción last<=2*first no detecta M5a ni M5b y falla en falso (u9-03); quitarla requiere enmendar CA-7
AMARILLO|test_queries.py (peor caso)|M6 (sin min() en statement_timeout) sobrevive 1 de 3 corridas
AMARILLO|api-summary.md:34 y CANDIDATAS.md:254|documentación desactualizada (versions sin preparar; 2 s)
INFORME: revisiones/U03-T07/ronda-2.md
```
