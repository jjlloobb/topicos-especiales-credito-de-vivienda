# Ronda 4 — U09-T01

VEREDICTO: VERDE

Revisor, 2026-11-09. Punta revisada: `3a9fbaf` (rama `tarea/U09-T01`). Base: `origin/main` = `b442cb2`, que también es el merge-base de la punta. Ronda 3 revisada sobre `3fef6dd`. Alcance cerrado: lo que fija `revisiones/U09-T01/arbitraje-ronda-3.md`, «Qué comprueba el revisor en la ronda 4». Worktree limpio al terminar (`git status --short` sin salida, salvo este informe).

## Criterios de la ronda 4, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1a | `bias-monitoring/` desde la ronda 3 = F-01 + F-06 | `git diff 3fef6dd HEAD -- vectra-risk/bias-monitoring` | pasa: 3 archivos. `disparity/pyproject.toml` +1 comentario NFR-U9-54; `test_disparity_dependencies.py` docstring NFR-U9-30; `test_disparity_examples.py` reordena `counts_from_marginals` (F-06) |
| 1b | Documentos de diseño de U9 = solo F-02 | `git diff 3fef6dd HEAD -- aidlc-docs/construction/bias-monitoring aidlc-docs/construction/plans/bias-monitoring*` | pasa: solo `business-logic-model.md:35` y `:70`, las dos a R4 (z = 3,14, atributo disparador, > 5 pp) |
| 1c | Huella de la rama sin cambios por el merge | `diff <(git diff --name-only <mb> 3fef6dd) <(git diff --name-only origin/main HEAD)` | pasa: misma lista + `DECISIONES-LOOP.md`, `ronda-3.md`, `arbitraje-ronda-3.md` |
| 1d | Conflictos sin perder entradas | `comm -23` (LC_ALL=C, `sort -u`) de cada archivo en `origin/main` y en `3fef6dd` contra `HEAD` | pasa: `audit.md` y `uv.lock`, 0 líneas perdidas de cualquiera de los dos lados. `CANDIDATAS.md`, 0 perdidas de main; las 3 «perdidas» de `3fef6dd` son entradas que main reescribió (grep de cada una: base 1, main 1, HEAD 1). `pyproject.toml`: frente a main solo hay adiciones (U9 en members, sources, dev, per-file-ignores) |
| 1e | `uv.lock` coherente | `uv lock --check` | pasa: rc=0, «Resolved 117 packages». Frente a main el lock solo agrega líneas |
| 2 | `--all` con la regla enmendada (§6, 2026-11-09) | `uv run python platform/tests/test_traceability.py --all` en la rama y en un `git archive origin/main` del repositorio completo | pasa (ver abajo) |
| 3a | `make -C bias-monitoring check` | el mismo comando | pasa: rc=0, 3 min 25 s. ruff ok; import-linter 4 contratos KEPT; 34 + 43 pruebas que pasan; 100 % de cobertura de ramas; simulación 6 pasan (83 s), `newcombe_coverage=0.9470`; 0 omitidas |
| 3b | `make -C platform check` | el mismo comando | pasa: rc=0. 789 pruebas pasan; 2 charts; conftest 707/3/329; integración 46 y 335, 0 fallos |

Primero corrí la base con un `git archive` solo del subárbol `vectra-risk/`. Eso dio 4 fallos de más (NFR-U0-04/17/43 y NFR-U1-40), porque faltaba `.github/`. La repetí con el archivo del repositorio completo. Las cifras de arriba son las de esa segunda corrida.

### `--all`: cruce de cada fallo
- Base (`origin/main`): rc=1, con 18 fallos, todos de U4 (INF-U4-01/02/04 y NFR-U4-01..41). `bias-monitoring: sin código, se omite`.
- Rama: rc=1, con los mismos 18 de U4 más 23 nuevos de U9. No hay ningún otro cambio.
- U4 y U9 no tienen `evidence/cierre-demo.md` (solo lo tienen `decision-registry` y `reference-model`). Los 18 de U4 cumplen la primera condición.
- Para los 23 de U9, asigné cada uno a su paso según las líneas «Diseño:» del plan (`bias-monitoring-code-generation-plan.md:68-283`):

| Id | Pasos del plan | ¿Paso cubierto (1 a 5)? |
|---|---|---|
| INF-U9-01, 02, 04 | 12 (y 02/04 en 16) | no |
| INF-U9-05 | 13 | no |
| NFR-U9-01 | 8, 16 | no |
| NFR-U9-02 | 9, 14, 16 | no |
| NFR-U9-04 | 16 | no |
| NFR-U9-10, 11, 13, 34 | 12 | no |
| NFR-U9-12, 32, 33 | 9 | no |
| NFR-U9-20, 21 | 8 | no |
| NFR-U9-22 | 7 | no |
| NFR-U9-40, 41 | 13 | no |
| P-U9-01 | 7, 8, 16 | no |
| P-U9-06 | 13, 16 | no |
| P-U9-07 | 8, 16 | no |
| **NFR-U9-51** | **5**, 10, 15 | Paso 5 sí; el id está excluido de la tarea (ver F-01) |

P-U9-01, P-U9-07 y NFR-U9-22, los tres que el codificador no comprobó a fondo, quedan bien asignados: ninguno aparece en las líneas «Diseño:» de los Pasos 1 a 5. Todos los ids de los Pasos 1 a 5 tienen trazabilidad, incluidos NFR-U9-30 y NFR-U9-54 (no salen en la lista de fallos): P-U9-02..05, NFR-U9-03, 30, 31, 50, 53, 54, INF-U9-03 y BR-U9-01..07.

**Dictamen sobre NFR-U9-51.** Es correcto tratarlo como diferido. NFR-U9-51 es «`mutmut` en `stats`, `disparity` y `freeze_rule`» (`nfr-requirements.md:61`), y lo excluyen dos fuentes:
- la tarea lo pone en «Fuera» por id: `tareas/U09-T01-esqueleto-y-libreria.md:110`, «`mutmut` del Paso 5 … y NFR-U9-51», con la cita del recorte E\*F (T3);
- el plan marca el Paso 5 con «`mutmut` diferido por la demo (T3)».

Además, `freeze_rule` es del Paso 6, así que el requisito no se puede cumplir dentro de esta tarea. Una traza ahora sería falsa, porque nombraría una mutación que no corre. El lugar de este id es la sección «Diferido por la demo» del `cierre-demo.md` de U9, en el Paso 18. La letra de la regla enmendada dice «paso», no «identificador», y ese desajuste va como F-01 (AMARILLO).

## Hallazgos
### F-01 · AMARILLO · `DECISIONES-LOOP.md` §6, enmienda del 2026-11-09 · La regla mira el paso y no el id recortado
La segunda condición exige que el id «no pertenezca a un paso que la tarea cubre». NFR-U9-51 pertenece al Paso 5, que la tarea cubre, aunque la tarea lo excluye por id con la cita del recorte. Leída al pie de la letra, la regla lo haría fallar. Leída por su intención («un identificador de un paso que la tarea cubre debe quedar trazado» porque la tarea lo implementa), lo deja pasar. Dictaminé por la intención. Para que la próxima tarea con un recorte dentro de un paso cubierto no dependa de ese dictamen, propongo aclarar la regla así: «o el id está en el "Fuera" de la tarea con la cita del recorte de la demo».

## Tareas candidatas (defectos reales fuera de alcance)
- `DECISIONES-LOOP.md` §6: aclarar la segunda condición por id recortado (F-01).
- Cierre de U9 (Paso 18): NFR-U9-51 debe entrar en «Diferido por la demo» de `bias-monitoring/evidence/cierre-demo.md`, con el paso y la cita del recorte T3, para que `--all` no lo siga contando como fallo.

## Rutas de transcripciones largas
- Las salidas de `--all` (rama y base) y de los dos `make check` quedaron en el scratchpad de la sesión del revisor: `all-rama.txt`, `all-base.txt`, `bm-check.txt` y `pf-check.txt`, en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/`. Son efímeras.
