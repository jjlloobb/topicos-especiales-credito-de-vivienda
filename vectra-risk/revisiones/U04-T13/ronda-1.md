# Ronda 1 — U04-T13

VEREDICTO: VERDE

Contexto comprobado: HEAD `150908c`, hash de la tarea `28b908d074b90247ccae6fca085f06471746c4f2` (coincide). Diff `61f9036..HEAD`: `bitacoras/U04-T13.md`, `governance/promotion_tool/vectra_promotion/gitops.py` (+23/-1) y `governance/tests/unit/test_promotion_tool.py` (+71/-1). Todo lo corrí con `KUBECONFIG=/nonexistent`, sin `/snap/bin` y sin `~/.local/bin` en el PATH, así que no había `gh`, `kubectl` ni `argocd` (solo `uv` y `uvx`, enlazados en el scratchpad).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Las pruebas `-k rollback_note` pasan y recogen las tres clases de PR | `uv run pytest governance/tests/unit/test_promotion_tool.py -q -p no:cacheprovider -k rollback_note` (con `--collect-only` primero) | pasa: 7 passed y 17 deselected en 3,59 s, sin omisiones (`-rs`). El filtro recoge 3+3 parametrizadas `[promocion|post-activacion|rollback]` y 1 de contenido. El tiempo cuadra con git y helm reales sobre el repo de fixture. |
| 1b | Rojo primero con el `gitops.py` de la base | `git show 61f9036:…/gitops.py > gitops.py`, el mismo pytest, y después `git checkout --` | 4 failed y 3 passed: fallan las 3 de `passes_the_ci_checker` y la de contenido. Las 3 de mutación pasan también con la base, porque prueban el comprobador y no el código. Coincide con la bitácora. |
| 2 | El comprobador real de la CI acepta los cuerpos | Saqué los tres cuerpos que `open_pr` pasa a `gh pr create --body` con una prueba en el scratchpad que reutiliza el fixture `bodies`. Después `python3 platform/tests/rollback_note.py <archivo>` | HEAD: rc 0 en las tres clases. Base: rc 1 en las tres («El PR no tiene nota de rollback…»). La evidencia de HEAD es idéntica a la de la base: solo se añade una línea en blanco y la sección. |
| 3 | `make -C governance check` | `uptime` antes (load 1.56/1.87/2.14) y una sola corrida | rc 0 en 4 min 48 s. ruff y mypy limpios, 662 passed, cobertura de 97,28 % (100 % en fsm, policy y evidence), conftest 1027/1027 y 10/10, kyverno con fail 0. Sale «kubectl no disponible: se omite policy-runbook» (ver la nota de abajo). |

**`policy-runbook` sin medir.** Confirmo que se omite sin `kubectl` (`governance/Makefile:88`). Lo que queda sin medir: que el Pod que genera `governance/docs/kind/llamar.sh --dry-run` y la SA `console-bff` pasen las políticas de Kyverno de U1. No toca ningún archivo del diff, así que no afecta a esta tarea.

## Comprobaciones pedidas
- **Bordes del comprobador.** La sección va al final del cuerpo, así que nada que venga detrás puede resetear `inside`.
  - Un `kubectl diff` con líneas `# …` o `## otra`: rc 0.
  - Un ```` ``` ```` suelto dentro del diff: rc 0. En GitHub, en cambio, el `## Rollback` se vería dentro del bloque de código, porque el comprobador no entiende los bloques de código.
  - Un `<!--` sin cerrar en el diff: rc 1, un falso negativo que deja la CI en rojo. GitHub lo mostraría como texto literal.
  - Con la salida real de `kubectl diff` (cada línea empieza por ` `, `+`, `-`, `@@`, `diff`, `---` o `+++`) no aparecen `#` ni bloques de código en la columna 0. Solo el `<!--` es alcanzable, y falla hacia el lado seguro. Es un defecto del comprobador de U1 (lo dejo como candidata).
- **Mutaciones del código** (cada una revertida con `git checkout`).
  - Quitar la nota de `open_pr`: 4 fallan.
  - `## Rollback` vacío seguido de otro encabezado: 3 fallan.
  - Encabezado renombrado: 4 fallan.
  - Las tres clases con el texto de promoción: 1 falla (la de contenido).
- **La prueba aflojada `…never_applies`.** Añadí a `open_pr` un `self._run(...)` real con binarios falsos en el PATH que salen con 0, uno por mutación: `kubectl apply -f -`, `argocd app sync model-serving`, `helm install ms chart` y `helm upgrade --install ms chart`. En los cuatro casos falla con `assert not ['<orden>']`. Lo único que se ignora es lo que va detrás de `--body` (ver F-02).
- **Las órdenes nombradas existen.** La Application `model-serving` existe en `vectra-risk-gitops/apps/kind/model-serving.yaml`, con el mismo nombre en staging y prod, y sin sync automático, así que «cuando se sincroniza» es correcto. `rollback-pr` y `mark-active` son subcomandos de `cli.py`.
- **Alcance.** No toca `rollback_note.py`, el workflow, los values de `model-serving`, `mark-active` ni la rama o el commit de `open_pr`, y no hay órdenes contra el clúster ni contra GitHub. `commands.py` no cambia. No hay desborde.

## Hallazgos

### F-01 · AMARILLO · gitops.py:100-119 · El texto de la nota es cierto pero incompleto en dos frases
Contrasté cada frase con `values.promote`, `demote` y `restore`, con `mark_active` y con la guía (escenarios 3 y 4): ninguna es falsa. Hay dos huecos que vería quien fusiona en la demo D2:
1. **Nota de promoción.** No avisa de que, si la versión ya se marcó activa, revertir el PR hace que Argo CD retire su `isvc-…` mientras governance la sigue teniendo `activo` y `serving-config` sigue apuntando a ella. El camino correcto es `rollback-pr` de la anterior y después `mark-active`.
2. **Nota de rollback.** Omite el «espera los pods de M1 en `READY`» que la guía (`paso-20-kind.md:279`) pone antes de `mark-active`. Además, «ese estado se cambia con `promotion-tool`» generaliza de más: `aprobado` se fija por la API con `cro-1` (guía, 5.3). Para `activo` e `inactivo` sí es exacto.

### F-02 · AMARILLO · test_promotion_tool.py:219-220 · La guarda descarta todo lo que va detrás de `--body`, no solo su valor
`c[: c.index("--body")]` corta toda la cola. Hoy `--body` es el último argumento de `gh pr create`, así que no tiene efecto. Sería más preciso quitar solo `c[i+1]`.

### F-03 · AMARILLO · gitops.py:102-111,116 · Búsqueda por `[kind]` y un literal de la Application
- Una clase desconocida da `KeyError` y no `PromotionError`. Hoy no es alcanzable: solo se llama con las tres clases de `commands.py`.
- `argocd app sync model-serving` es un literal en texto, no en un punto de decisión. El nombre coincide en los tres entornos y no es configurable, a diferencia de `--gitops` y `--chart`.

## Tareas candidatas (defectos reales fuera de alcance)
- U1, `platform/tests/rollback_note.py`. `COMMENT` y `HEADING` ignoran los bloques de código. Un `<!--` en cualquier línea del `kubectl diff` (aunque empiece por `+`) borra el resto del cuerpo y da rc 1, un falso negativo. A la inversa, un `## Rollback` dentro de un bloque de código cuenta como nota válida: `has_rollback_note` devuelve `True`, comprobado en Python.

## Observaciones sobre el bucle
- Al final, el worktree quedó con `git status --short` vacío y HEAD en `150908c`. Quité los enlaces de `platform/.tools` y `node_modules` y la copia de `platform/.charts`, y borré las copias del scratchpad.
- Efecto secundario de enlazar `platform/.tools`: los objetivos `policy-chart` y `policy-job` escribieron sus artefactos de integración en `platform/.tools/integration/u4*` del **árbol principal** (es caché ignorada, no fuentes). Para futuras revisiones conviene copiar `.tools` en vez de enlazarlo, o asumirlo.

## Rutas de transcripciones largas
- Ninguna persistente: la salida de CA-3 estaba en el scratchpad y la borré.

```
VEREDICTO: VERDE
AMARILLO|gitops.py:100-119|El texto de la nota es cierto pero incompleto (revertir la promoción tras mark-active; READY antes de mark-active; «estado» generalizado)
AMARILLO|test_promotion_tool.py:219-220|La guarda descarta todo lo que va detrás de --body, no solo su valor
AMARILLO|gitops.py:102-111,116|Búsqueda [kind] con KeyError y nombre de la Application como literal
INFORME: revisiones/U04-T13/ronda-1.md
```
