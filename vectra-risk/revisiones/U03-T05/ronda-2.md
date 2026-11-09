# Ronda 2 — U03-T05

VEREDICTO: NO-VERDE

El veredicto es NO-VERDE por una sola causa, y no viene del diff del codificador. CA-9 no pasa tal como está escrito: su tercera orden (`test_traceability.py --all`) sale con rc=1. Las 26 líneas que fallan son todas identificadores de U4 (`governance`), que entraron a la rama al integrar `origin/main` (U04-T01) antes de esta ronda. En `9352400` sale el mismo conjunto, línea por línea. U3 está limpio. Arreglarlo aquí sería un desborde de alcance, porque obligaría a tocar U4. Decide el orquestador: o enmienda CA-9 para que pida «U3 limpio y ningún fallo nuevo respecto a la base», o lo arbitra como hizo con CA-11b en la ronda 1. Por mi parte, el veredicto se queda donde está.

La ronda 2 aplica el arbitraje **exactamente y nada más**. CA-11 pasa entero.

## Integridad
- Worktree en `a278a9d` y limpio antes y después de la revisión (`git status --short` sin salida).
- El blob de la tarea es `ce810fc9cc9d125dbf6e25b3a0e8169bec6389e9` y coincide.
- El diff de la ronda (`git show a278a9d`) cambia 4 archivos:
  - `platform/tests/test_kind_profile.py`: `BUDGET_GIB` pasa de 5.5 a 6.1, con un comentario que cita la decisión del 2026-11-09, el arbitraje y DD-3/Paso 16.
  - `evidence/cierre-demo.md`: una fila nueva para NFR-U3-41 (Paso 11 `checkpoint`; Enmienda §3 U3, Paso 11; T5).
  - `decision-registry/tests/unit/test_chart.py:400`: sale NFR-U3-41 del docstring.
  - La bitácora.
- No hay ningún otro cambio. NFR-U3-41 ya no aparece en código ni en pruebas, solo en el diseño y en la lista de diferidos.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 9a | Trazabilidad U3 | `uv run python platform/tests/test_traceability.py --unit decision-registry --all` | pasa, rc=0, 41 identificadores |
| 9b | CLI de trazabilidad | `uv run pytest platform/tests/test_traceability_cli.py -v` | pasa, 6 passed (0,12 s; son pruebas puras sobre fixtures, el tiempo es razonable) |
| 9c | Trazabilidad global | `uv run python platform/tests/test_traceability.py --all` | **falla, rc=1**: 26 líneas `INF-U4-*`, `NFR-U4-*` y `P-U4-*` «sin trazabilidad». Ninguna de U3 (ver F-01) |
| 11a | `make -C decision-registry check` | el mismo, solo | 1.ª corrida rc=2 por una prueba inestable bajo carga (F-02). 2.ª corrida **rc=0** en 6 min 43 s: 669 passed, cobertura 95,93 %, `chain`/`verify`/`append` al 100 %, conftest 1260/1260 y 9/9, U1 ×3 `pass: 26, fail: 0`, trazabilidad 41 |
| 11b | `make -C platform check` | el mismo, solo, después de 11a | **rc=0** en 3 min 40 s: 789 passed, 0 skipped, helm lint 2/2, trazabilidad 54, waves 81/81, conftest 707/3/329, Kyverno `pass: 335, fail: 0`. `test_the_profile_requests_fit_the_budget` PASSED (lo corrí además con `-v -rs`) |

## Hallazgos
### F-01 · ROJO · CA-9 (3.ª orden, `test_traceability.py --all`) · el criterio falla por U4, no por el diff
- **Qué falla.** `uv run python platform/tests/test_traceability.py --all` da rc=1. Todas las líneas que fallan son de `governance`: INF-U4-01/02/04/05, NFR-U4-01..07/10..13/20..23/25/31/40/41 y P-U4-05/07/08.
- **El origen está fuera de la rama.** Extraje `9352400` (U04-T01 en main) con `git archive` y corrí la misma orden. Las líneas `U4-` son las mismas 26 (`diff` vacío entre `main-u4.txt` y `br-u4.txt` en el scratchpad). En `c620c4f` (main actual) también sale rc=1.
- **La rama no las causa.** No toca `governance`. Su cambio en `test_traceability.py` es de la ronda 1 y no altera esas 26.
- **El codificador no lo detectó.** No volvió a correr CA-9 tras la integración: la sección «Verde» de su bitácora de la ronda 2 solo cita los `check`. Es evidencia que falta, no evidencia falsa.
- **Remedio.** No lo puede arreglar el codificador sin desbordar el alcance. Hace falta un arbitraje del orquestador sobre la redacción de CA-9 o sobre la regla de `--all` para unidades en curso.

### F-02 · AMARILLO · `decision-registry/tests/integration/test_dossier.py:148` · prueba de integración inestable bajo carga
- **Qué pasó.** En la primera corrida de `make -C decision-registry check` falló `test_br_u3_14_una_columna_alterada_es_not_verified_con_column_mismatch`. `env.append` recibió `503 dependency_unavailable` tras `duration_ms: 2067.2`, o sea, el límite de 2 s de la dependencia.
- **Contexto de carga.** A la vez corrían el clúster kind y el bucle de U04-T03 (load ~3).
- **No la causa el diff.** Aislada da 24 passed en 6,55 s, y en la segunda corrida completa pasó. El archivo no cambió desde U03-T04.
- **Es de la misma clase** que la prueba de tiempo de `test_queries.py` que ya anotó el codificador. Candidata: aislar o marcar las pruebas sensibles al tiempo.

### F-03 · AMARILLO · `CANDIDATAS.md` (commit `49cef43` del orquestador) · falta la F-03 de la ronda 1
- El arbitraje manda F-02..F-08 a `CANDIDATAS.md`. Están F-02 y F-04..F-08, pero no F-03 (`platform/tests/test_platform.py:285`, un archivo de U1 que la tarea no nombra).
- La omisión es del orquestador, no del codificador.

## Tareas candidatas (defectos reales fuera de alcance)
- **U1/U4, `test_traceability.py --all`.** Mientras una unidad tenga código a medias (hoy `governance`), `--all` falla en cualquier rama basada en main. O se excluyen las unidades sin cierre, o los CA de las otras unidades dejan de exigir `--all` en rc=0.
- **U3, pruebas de integración con límite de 2 s** (`test_dossier.py`, `test_queries.py`). Son inestables con la máquina cargada. Aislarlas, o subir el límite solo en el perfil de pruebas.
- **F-03 de la ronda 1** (edición de `platform/tests/test_platform.py:285`): registrarla en `CANDIDATAS.md`.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/aedc6fa7-798a-4ae8-9684-b7a8b42aa668/scratchpad/dr-check.log` (1.ª corrida, rc=2)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/aedc6fa7-798a-4ae8-9684-b7a8b42aa668/scratchpad/dr-check2.log` (2.ª corrida, rc=0)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/aedc6fa7-798a-4ae8-9684-b7a8b42aa668/scratchpad/pf-check.log` (platform, rc=0)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/aedc6fa7-798a-4ae8-9684-b7a8b42aa668/scratchpad/main-u4.txt` y `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/aedc6fa7-798a-4ae8-9684-b7a8b42aa668/scratchpad/br-u4.txt` (fallos de U4 idénticos en main y en la rama)

## Hallazgos en pie
| SEVERIDAD | Ubicación | Resumen |
|---|---|---|
| ROJO | CA-9 (`test_traceability.py --all`) | rc=1 por 26 identificadores de U4 que vienen de main (U04-T01); no lo causa el diff; hace falta un arbitraje |
| AMARILLO | `decision-registry/tests/integration/test_dossier.py:148` | 503 a los 2 s bajo carga; pasa aislada y en la 2.ª corrida |
| AMARILLO | `CANDIDATAS.md` (`49cef43`) | falta la F-03 de la ronda 1 |

```
VEREDICTO: NO-VERDE
ROJO|CA-9 (test_traceability.py --all)|rc=1 por 26 identificadores de U4 (governance) que vienen de main; el diff no los causa, hace falta un arbitraje
INFORME: revisiones/U03-T05/ronda-2.md
```
