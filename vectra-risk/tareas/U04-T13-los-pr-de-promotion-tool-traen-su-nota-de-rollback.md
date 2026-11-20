# U04-T13 — Los PR que abre `promotion-tool` traen su nota de rollback

**Unidad:** U4 — `governance` (`promotion-tool`)
**Historias que implementa:** ninguna nueva; corrige un defecto medido el 2026-11-18 (candidata de `CANDIDATAS.md`, propuesta por U01-T20).
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> **Medido por el orquestador:**
>
> - `.github/workflows/platform.yml` corre en cada PR el check `rollback-note`: `python3 vectra-risk/platform/tests/rollback_note.py` con el cuerpo del PR en `BODY`. Sale 1 si el cuerpo no tiene una sección `## Rollback` (o `# Rollback`) con al menos una línea de texto visible (NFR-U1-44).
> - `governance/promotion_tool/vectra_promotion/gitops.py`, `open_pr`, abre el PR con `gh pr create … --body body`, y `body` es solo `self.evidence(...)`: `### Evidencia`, el sha del render, la tabla de recursos, el `kubectl diff` y la frase final. No trae `## Rollback`.
> - El PR #211 (`promotion/promocion-isvc-8a98ab02-kind`) salió con ese cuerpo; el check quedó en rojo hasta editarlo a mano.
> - `promotion-tool` abre tres clases de PR, todas por `open_pr`: `promotion-pr`, `post-activation-pr` y `rollback-pr` (`commands.py`, `cli.py`).
>
> Lo que se quiere:
>
> 1. **El cuerpo de cada PR que abre `promotion-tool` lleva una sección `## Rollback` con texto**, que pasa `platform/tests/rollback_note.py` tal cual está.
> 2. **El texto dice la verdad para cada clase de PR**, sin inventar órdenes: qué se revierte (este PR), qué recoge Argo CD al sincronizar `model-serving`, y qué queda en `governance` (el estado de la versión no lo cambia revertir el PR; se cambia con `promotion-tool`, como dice `governance/docs/paso-20-kind.md`, escenarios 3 y 4). Léelo del código y de esa guía; si algo no lo puedes afirmar, no lo escribas.
> 3. **Pruebas:** el cuerpo que arma `open_pr` para cada una de las tres clases pasa `rollback_note.has_rollback_note`; y una mutación que quite la sección hace fallar la prueba.

**Fuera:**

- El check `rollback-note` y `platform/tests/rollback_note.py` (son de U1): no se relajan.
- Lo demás de `open_pr`: el commit firmado, la rama, el árbol sucio que deja un `git commit -S` fallido (ya es candidata), `mark-active` y su 503 (ya es candidata).
- El presupuesto de memoria de kind con un modelo `inactive` (candidata aparte, decisión del usuario).
- Los values de `model-serving` y cualquier orden contra el clúster o contra GitHub (no abras PR de prueba).

---

## Archivos de contexto

- `governance/promotion_tool/vectra_promotion/gitops.py` (`evidence`, `open_pr`), `commands.py`, `cli.py`
- `governance/tests/unit/test_promotion_tool.py`
- `platform/tests/rollback_note.py` y `.github/workflows/platform.yml` (job `rollback-note`)
- `governance/docs/paso-20-kind.md`, escenarios 3 (promoción) y 4 (rollback)
- `governance/Makefile`

---

## Criterios de aceptación

- [ ] **CA-1** — El cuerpo de las tres clases de PR pasa el comprobador de la CI.
  ```bash
  cd vectra-risk && uv run pytest governance/tests/unit/test_promotion_tool.py -q -p no:cacheprovider -k "rollback_note"
  ```
  Esperado: pasa. **Rojo primero**, pegado en la bitácora: las pruebas nuevas fallan con el `gitops.py` de `main`. Comprueba con `--collect-only` que el filtro recoge las pruebas nuevas (una por clase de PR, o una parametrizada con las tres).

- [ ] **CA-2** — El comprobador real acepta el cuerpo, ejecutado como lo ejecuta la CI.
  Una prueba (o un comando que dejes en la bitácora) escribe el cuerpo generado a un archivo temporal y corre `python3 platform/tests/rollback_note.py <archivo>`. Esperado: rc 0 para las tres clases; rc 1 para el cuerpo de `main`.

- [ ] **CA-3** — La unidad sigue en verde.
  ```bash
  cd vectra-risk && make -C governance check
  ```
  Esperado: rc 0. Una sola vez, al final. Si necesita herramientas que el worktree no tiene (`platform/.tools`, `platform/.charts`, `node_modules`), dilo como «no medido» con el objetivo que falló; no las instales.

---

## Plan de pruebas

- Unitarias en `test_promotion_tool.py`: el cuerpo de `promotion-pr`, `post-activation-pr` y `rollback-pr` contiene una sección `## Rollback` con texto y pasa `has_rollback_note`.
- Negativa: sin la sección, `has_rollback_note` da falso (mutación).

**Rojo primero:** las pruebas nuevas contra el `gitops.py` de `main`.

---

## Notas

- Archivos que se **modifican en su sitio**: `governance/promotion_tool/vectra_promotion/gitops.py` (y `commands.py` si el texto depende de la clase de PR) y `governance/tests/unit/test_promotion_tool.py`. Nada de duplicados.
- `promotion-tool` se corre desde un clon limpio, no desde una imagen: no hay imagen que reconstruir. Dilo en la bitácora si ves lo contrario.
- Es lo que usa la demo D2 del Paso 18 (promoción y rollback): el texto lo va a leer una persona al fusionar.
