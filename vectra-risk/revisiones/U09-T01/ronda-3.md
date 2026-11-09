# Ronda 3 — U09-T01

VEREDICTO: NO-VERDE

El F-01 de la ronda 1 quedó cerrado tal como lo pedía el arbitraje de la ronda 2. R4 está escrita en BR-U9-11, BR-U9-04/05 y BLM §3. La librería expone `aggregate_lower_limit`, el `xfail` ya no está y la simulación usa la librería real. Reproduje con mi propia corrida el rojo contra R0 y el verde con R4, cifra por cifra, y también D\*. CA-1 a CA-10 pasan.

Lo único que bloquea es la regla «sin fallos nuevos» de `--all` (arbitraje ronda 2, punto 5; `DECISIONES-LOOP.md` §6), que no se cumple: F-01. El codificador lo declaró él mismo en la bitácora. Revisé `git diff a6a63f1..HEAD` (ronda 3) sobre `origin/main...tarea/U09-T01`, y la tarea tiene el hash `bb3e6d3…`. No toqué código. `u5_counts.json` no cambió. No se recortó ninguna PBT: el diff de `tests/property` solo agrega pruebas.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Contratos de imports | `uv sync --frozen && uv run lint-imports --config bias-monitoring/.importlinter` | pasa, `4 kept, 0 broken` |
| 2 | Runtime vacío | `uv tree --frozen --package vectra-disparity --no-dev` + prueba | pasa: `vectra-disparity v1.0.0` sin hijos; 3 passed |
| 3 | Estructura §1 | bucle `test -e` de la tarea | pasa, `OK` sin `FALTA` |
| 4 | Config | `uv run pytest bias-monitoring/tests/unit/test_config.py` | pasa, 31 passed (archivos locales, sin estado externo) |
| 5 | Newcombe | `uv run pytest bias-monitoring/tests/unit/test_stats.py` | pasa, 12 passed |
| 6 | PBT 01/02/03/06 + ejemplos | `HYPOTHESIS_PROFILE=ci uv run pytest …` (3 archivos) `-v` | pasa, 31 passed en 136,6 s; ningún skip ni xfail |
| 7 | Cobertura 100 % | el comando de CA-7 | pasa, `TOTAL 229 0 48 0 100%`, rc 0 |
| 8 | Simulación + `library.md` | `make -C bias-monitoring check` (incluye `-m simulation`) + `grep` | pasa: Newcombe 0,9470; falsos `{30: 0.5611, 100: 0.0902, 500: 0.0001, 2000: 0.0}`; base `{30: 0.008, 50: 0.0128, 100: 0.0106}`; D\* 0,9535; 6 passed en 132,7 s; `grep` da 14 líneas |
| 9 | SemVer | el comando de CA-9 | pasa, `1.0.0` (y está en `library.md:3`) |
| 10 | `check` de U9 y U1 | `make -C bias-monitoring check && make -C platform check` | U9: rc 0 en 5 m 29 s. Platform: rc 0 en 3 m 59 s (ruff, pytest 784 passed, helm lint, generadores --check, trazabilidad por defecto, kyverno test 81, conftest 707/3/322, kyverno apply 45 y 309, actionlint) |
| `--all` | «sin fallos nuevos» (arbitraje r2 §5; DECISIONES §6) | `test_traceability.py --all` en la rama y en un `git archive 0a5c990` | **falla**: ver F-01 |

**Reproducción de las cifras de la simulación.**
- **Rojo contra R0.** Escribí `scratchpad/r0_vs_r4.py`, que usa la librería y los generadores de la propia simulación, con R0 y R4 sobre el modelo base y 10 000 repeticiones:
  - R0: `{30: 0.9985, 50: 0.9999, 100: 1.0}`, que coincide con la bitácora;
  - R4: `{30: 0.008, 50: 0.0128, 100: 0.0106}`.
  - Con 500 casos, la cifra de R0 para falsos congelamientos (0,9741) es la misma que medí en la ronda 1.
- **D\*.** `busqueda-dstar-ronda-3.py 10000 1.0 1.70 1.71` da:
  - con t = 1,00: 11,66 pp y 0,4347;
  - con t = 1,70: 17,42 pp y 0,9500;
  - con t = 1,71: 17,47 pp y 0,9535.

  Coincide con `library.md`. Es reproducible y determinista (semilla fija).
- **z.** `norm.isf(0.05/60)` = 3,14398, así que `Z_FREEZE = 3.14` es correcto para 60 comparaciones. Ver F-03 sobre ese 60.

## Hallazgos

### F-01 · ROJO · arbitraje r2 §5 / `DECISIONES-LOOP.md` §6 · `--all` no cumple «sin fallos nuevos»
- **Qué pide la regla.** `--all` cuenta como pasado si se cumplen dos condiciones: (a) cada fallo es de una unidad sin `cierre-demo.md`, y (b) **el conjunto es idéntico al de la base**.
- **Qué medí.** En la base `0a5c990`, U9 sale como «sin código, se omite» y los fallos son 14 de U3. En la rama siguen esos 14 de U3 y aparecen **25 nuevos de U9** (`scratchpad/trace-branch.log` y `trace-base.log`). La condición (a) se cumple; la (b) no.
- **Dos fallos se pueden cerrar dentro del alcance.** `NFR-U9-30` y `NFR-U9-54` son de esta tarea:
  - `NFR-U9-30` son los contratos de import-linter del Paso 1;
  - `NFR-U9-54` es el SemVer del Paso 5.

  Están implementados, pero ningún archivo de `bias-monitoring/` los nombra. Solo `library.md` cita `NFR-U9-54`, y ese archivo está fuera de las raíces de código. Basta con citarlos en `.importlinter` y en `disparity/pyproject.toml` o `__init__.py`.
- **Los otros 23 son estructurales.** `INF-U9-01/02/04/05`, `NFR-U9-01/02/04/10..13/20..22/32..34/40/41`, `P-U9-01/06/07` y `NFR-U9-51` pertenecen a los Bloques C–G o al `mutmut` diferido. Ninguna primera tarea de código de una unidad puede cumplir (b).
- **A quién le toca.** Con la regla tal como está escrita, esto es ROJO. Su resolución es del orquestador: aclarar si una unidad que gana código en la tarea cuenta, como propone `CANDIDATAS.md`. Mientras tanto, el codificador sí debe cerrar los 2 fallos que le corresponden.

### F-02 · NARANJA · `business-logic-model.md:35` y `:70` · La BLM sigue mostrando R0 fuera de §3
- El diagrama (`rule{"Agregada > 5 pp y limite inferior > 0?"}`) y el pseudocódigo (`decide(modelo): agregada > 5 pp y límite inferior > 0 ?`) contradicen BR-U9-11 y BLM §3 dentro del mismo documento.
- El Bloque C (`freeze_rule`) se implementa desde aquí.
- Barrido: en los documentos vigentes de U9 no queda ninguna otra aparición. Las de los planes y de `audit.md` son históricas.

### F-03 · NARANJA · `business-rules.md` BR-U9-11 · R4 solo sobre el atributo disparador deja escapar una disparidad bien medida
- BR-U9-11 y la simulación (`_freezes`) aplican el límite solo al atributo de la mayor agregada **puntual**. El arbitraje dice «la agregada ponderada del atributo», que es ambiguo.
- Contraejemplo corrido con la librería:
  - `region` con 40 casos por celda y 20 pp tiene límite 0,0132;
  - `sexo` con 3 000 casos por celda y 10 pp tiene límite **0,0768**;
  - el disparador es `region`, así que no congela, aunque `sexo` supera los 5 pp con z de Bonferroni.
- Un atributo ruidoso enmascara a otro preciso. Hay que decidirlo antes del Bloque C, porque tocaría BR-U9-05/11, PBT-U9-04 y la condición 1 medida.

### F-04 · AMARILLO · `stats.py:15-17` y BR-U9-11 · Se dice que son «60 comparaciones (15 pares × 4 atributos)», pero `sexo` tiene 2 grupos
Los pares reales son 1 + 15 + 15 + 15 = 46, con z = 3,065. El 60 viene del arbitraje y 3,14 es más conservador, así que no cambia el resultado, pero el texto de la justificación es incorrecto.

### F-05 · AMARILLO · `test_statistical_validation.py:38` y `library.md` · D\* está calibrado con la misma semilla de la prueba y con un reparto idealizado
- **La semilla.** La búsqueda y la prueba usan `SEED + 3`. El 95,35 % queda unos 1,6 errores estándar sobre el 95 %, y 17,42 pp da exactamente 0,9500.
- **El reparto.** La simulación reparte el lote en celdas iguales: 83 casos por celda, y 250 en `sexo`. BR-U12-06 define `stratified` como «≥ 30 por celda», que no es lo mismo.
- **La medida.** La agregada de D\* se mide con los totales de `validation`.
- **Recomendación.** Que U05-T05 apunte con margen (≥ 18 pp) y vuelva a medir con el lote real de RT-2.

### F-06 · AMARILLO · `test_disparity_examples.py:16-18` · Import fuera de orden
`aggregate_lower_limit` está entre `counts_from_marginals` y `counts_from_records`. Ruff no tiene la regla `I` activa.

## Tareas candidatas (defectos reales fuera de alcance)
- **Regla `--all`.** Aclarar cómo cuentan los fallos de una unidad que pasa de «sin código» a tener código en la tarea (F-01, parte estructural).
- **Bloque C.** Decidir si R4 se evalúa sobre el disparador o sobre el máximo de los límites por atributo (F-03). Además, `initial_disparity`/`FreezeContext` no traen el límite R4 que decidió el congelamiento: el paquete muestra solo `aggregate_ci_95`.
- **U05-T05.** Agregada por `region` de al menos 17,5 pp con margen, verificada con el lote `stratified` real (F-05).
- Siguen en pie las candidatas de la ronda 1 (F-03, F-04 y F-05 de entonces), ya registradas en `CANDIDATAS.md`.

## Rutas de transcripciones largas
En `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/`:
- `bias-check.log`
- `platform-check.log`
- `trace-branch.log`
- `trace-base.log`
- `r0_vs_r4.py` y `r0_vs_r4.log`
- `dstar.log`

Estado del worktree al terminar: `git status --short` vacío antes de escribir este informe (solo cachés ignoradas: `.tools`, `.charts`, `.hypothesis`, `.coverage`); el único archivo nuevo es este informe, sin commit, como pidió el orquestador.
