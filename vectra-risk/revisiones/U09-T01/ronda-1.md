# Ronda 1 — U09-T01

VEREDICTO: NO-VERDE

El código hace lo que dicen BR-U9-01..07, 03, 04 y 11, y lo comprobé con mis propias corridas. El único ROJO no sale del código. CA-8 pide una tasa de congelamientos falsos ≤ 5 % con 500 casos por celda, y con el diseño actual eso no se puede cumplir. El hallazgo del codificador es real. La prueba que lo cubre está marcada `xfail`, y una prueba `xfail` no cuenta como aprobada.

Sin cambios en el código de la rama. Revisé la tarea (hash `bb3e6d3…`, coincide) y el diff `0a5c990..0386295`. Al terminar, el worktree está limpio: `git status --short` sale vacío, HEAD sigue en `0386295` y solo quedan cachés que git ignora (`.charts`, `.tools`, `.hypothesis`, `.coverage`). El diff no toca `platform/`, `reference-model/` ni U0/U1: todos los archivos caen en `bias-monitoring/`, en los documentos de U9, en `pyproject.toml`/`uv.lock` de la raíz y en la bitácora y la tarea.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Cuatro contratos de import-linter | `uv sync --frozen && uv run lint-imports --config bias-monitoring/.importlinter` | pasa, `4 kept, 0 broken`. El «rojo primero» no lo reproduje porque no edito código; leí los contratos y prohíben lo que deben (`httpx` en `freeze_rule`, `freeze_client` en `app`, `pydantic` en `vectra_disparity`) |
| 2 | Árbol de runtime vacío | `uv tree --frozen --package vectra-disparity --no-dev` y la prueba | pasa: una sola línea `vectra-disparity v1.0.0`; 3 pruebas pasan |
| 3 | Estructura de §1 | el bucle `test -e` de la tarea | pasa: ninguna línea `FALTA`, y `OK` al final |
| 4 | Config y parámetros | `uv run pytest bias-monitoring/tests/unit/test_config.py -v` | pasa, 31 pruebas (peor caso 186 s < 600 s, entorno sin efecto, rangos, `n_min: 20` falla) |
| 5 | `stats` frente a Newcombe | `uv run pytest bias-monitoring/tests/unit/test_stats.py -v` | pasa, 12 pruebas. Además corrí los pares de la Tabla II que faltan (ver F-03) |
| 6 | PBT-U9-01/02/03/06 y ejemplos | `HYPOTHESIS_PROFILE=ci uv run pytest …` (los 3 archivos) | pasa, 25 en 164 s con el perfil `ci` de 500 ejemplos |
| 7 | Cobertura de ramas 100 % | el comando de CA-7 | pasa, `TOTAL 212 0 42 0 100%` sobre `vectra_disparity` |
| 8 | Simulación ≤ 5 % con 500 casos y `library.md` | `uv run pytest bias-monitoring/tests/simulation -m simulation -v -rxX && grep …` | **falla**: Newcombe 94,7 %, pero congelamientos falsos `{"30":1.0,"100":1.0,"500":0.9741,"2000":0.001}`; `2 passed, 1 xfailed`. Sale con código 0 solo por el `xfail` |
| 9 | SemVer | el comando de CA-9 | pasa, imprime `1.0.0` |
| 10 | `make -C bias-monitoring check && make -C platform check` | los dos | `bias-monitoring`: código 0 en 3 m 12 s, con 1 xfailed. `platform check-local`: código 0, pytest 784 pasan, helm lint y los generadores `--check` en verde. `check-tools`: todos los pasos pasan (kyverno test, promtool, conftest 707/3/322, kyverno apply 45 y 309, actionlint, check-integration). Lo único que no pasa es la verificación de que existan los binarios: `egctl` y `k6` no se pudieron bajar (504 de los release assets de GitHub, repetido 6 veces y también sin sandbox). `promtool`, `actionlint` y `hadolint` los copié del checkout principal, tras comprobar que sus versiones coinciden con `tools.env`; `kubeconform` lo bajé con su checksum. Es un límite del entorno, no un defecto del diff |

## Hallazgos

### F-01 · ROJO · CA-8 · `bias-monitoring/tests/simulation/test_statistical_validation.py:79-88` · 97,4 % de congelamientos falsos con 500 casos por celda, y la prueba prometida está marcada `xfail`
- **El incumplimiento.** CA-8 y la BLM §3 piden ≤ 5 % con 500 casos o más por celda. El valor reproducido es 0,9741 (determinista, semilla fija). La prueba prometida está en `xfail(strict=True)`. Por la invariante 5 eso es ROJO: documenta el problema con honestidad, pero no aprueba nada.
- **El hallazgo es real y el código no lo causa.**
  - Escribí una implementación independiente, vectorizada, que no usa la librería y sale solo del texto de BR-U9-03, 04 y 11. Con 500 casos por celda da 97,3–97,9 % según la semilla, también con el redondeo a 4 decimales: `scratchpad/indep_sim.py` e `indep_sim_q.py`.
  - Comparé `disparity.py:205-236` con BR-U9-04: pesos `n_b/Σn_b` solo sobre las bandas con diferencia, `v_b` sacada del intervalo de Newcombe, y `D ± 1,96·√Σw²v`. Es fiel.
  - La simulación evalúa la condición correcta: la agregada mayor, el límite inferior de ese mismo atributo y la desigualdad `>` estricta.
- **La causa es algo más amplia que la que da el codificador.** El par extremo elegido entre 6 grupos es la parte principal, pero hay tres factores:
  1. `d_b = max − min` nunca es negativa, así que la diferencia arranca sesgada hacia arriba.
  2. La agregada promedia 3 bandas. Eso achica el intervalo en un factor √3, pero no corrige ese sesgo.
  3. Se toma el máximo de 4 atributos.
- **Cifras de mi simulación**, como insumo para la decisión de diseño:
  - Solo `sexo` (2 grupos): 20,8 % con 30 casos, 18,7 % con 100, ~2,2 % con 500.
  - Los 4 atributos: 29 % con 1 000 casos y ~0,05 % con 2 000.
  - «Exigir más muestra» significaría unos 2 000 casos por celda.
  - La frase de la BLM «por debajo queda como limitación conocida, que el umbral de 5 pp acota» no se sostiene por debajo de unos 1 000 casos.
- **Qué hace falta para cerrarlo.** Que el usuario enmiende la BLM §3 y CA-8, o que cambie la regla (intervalo o umbral). El codificador no puede arreglarlo en la ronda 2 sin esa decisión.

### F-02 · AMARILLO · `test_statistical_validation.py:83` · El texto del `xfail` no coincide con lo medido
El `reason` dice «~96 %», pero lo medido es 97,41 %, que es lo que dicen `library.md` y la bitácora.

### F-03 · AMARILLO · `bias-monitoring/tests/unit/test_stats.py:11-22` · Una referencia atribuida a Newcombe que no sale de su tabla
- El comentario atribuye los 4 pares a la «Tabla II» de Newcombe (1998). Las cifras son de segunda mano (DescTools), y el par 84/101 frente a 89/105 no está en esa tabla. El codificador lo reconoce en la bitácora.
- Faltan los pares de la tabla con ceros en los bordes. Los corrí yo y la implementación los cumple con tolerancia 1e-4:

  | Par | Intervalo |
  |---|---|
  | 5/56 − 0/29 | −0,0381 a 0,1926 |
  | 0/10 − 0/20 | −0,1611 a 0,2775 |
  | 0/10 − 0/10 | ±0,2775 |
  | 10/10 − 0/10 | 0,6075 a 1 |

- Conviene agregarlos y corregir la cita. No rompe CA-5: los tres pares publicados que trae la prueba son correctos.

### F-04 · AMARILLO · `bias-monitoring/src/vectra_bias/config.py:40` · El plazo del CronJob queda como constante de código
`ACTIVE_DEADLINE_SECONDS = 600` repite un valor que pertenece al CronJob del chart (INF-U9-03 lo ata al intervalo del horario). Si el chart del Paso 12 no lo deriva de aquí, o no lo verifica contra este valor, los dos pueden quedar distintos.

### F-05 · AMARILLO · `disparity/src/vectra_disparity/stats.py:73` · Una desviación documentada del plan
`combined_variance` devuelve `float` y no `Decimal4` como dice el plan. La razón es válida (lo que se publica es el intervalo) y está en `library.md`; queda anotada.

## Tareas candidatas (defectos reales fuera de alcance)
- **Decisión de diseño sobre BR-U9-11 y BLM §3** antes del Bloque C (`freeze_rule`), con las cifras de F-01.
- **`platform/install-tools.sh`**: no reintenta, no salta los binarios que ya existen y falla entero con un 504. Por eso `make -C platform check` no se puede reproducir en un worktree nuevo (`egctl` y `k6` no se pudieron bajar hoy).
- **Chart de U9 (Paso 12)**: derivar `activeDeadlineSeconds` de la misma fuente que `config.ACTIVE_DEADLINE_SECONDS`, o verificar que coincidan (F-04).

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/4b74319d-fa8c-408a-94c3-00933d95328f/scratchpad/`:
- `make-check-bias.log`
- `ca678.log`
- `platform-check-local.log`
- `check-tools.log`
- `install-tools.log`
- `indep_sim.py`
- `indep_sim_q.py`

```
VEREDICTO: NO-VERDE
ROJO|CA-8 · bias-monitoring/tests/simulation/test_statistical_validation.py:79|Congelamientos falsos 97,4 % con 500 casos por celda (se exige ≤ 5 %); prueba prometida en xfail; requiere decisión de diseño
AMARILLO|bias-monitoring/tests/simulation/test_statistical_validation.py:83|El reason del xfail dice ~96 % y lo medido es 97,41 %
AMARILLO|bias-monitoring/tests/unit/test_stats.py:11|Cita «Tabla II» de Newcombe con valores de segunda mano; faltan los pares con ceros
AMARILLO|bias-monitoring/src/vectra_bias/config.py:40|ACTIVE_DEADLINE_SECONDS duplica un valor del chart
AMARILLO|bias-monitoring/disparity/src/vectra_disparity/stats.py:73|combined_variance devuelve float y no Decimal4 (desviación documentada)
INFORME: revisiones/U09-T01/ronda-1.md
```
