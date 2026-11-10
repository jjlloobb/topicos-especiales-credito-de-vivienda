# Ronda 1 — U07-T02

VEREDICTO: VERDE

Revisor, 2026-11-10, punta `c08e588`, base `d8eae35`. El revisor entregó el informe en su respuesta; el orquestador lo transcribe. Las mutaciones se hicieron en copias, nunca en el worktree.

| # | Resultado |
|---|---|
| CA-1 | `policy`: 11/11 con 500 ejemplos reales |
| CA-2 | `narrative`: 10/10; `forbidden_phrases.py template_v1.txt` rc 0 |
| CA-3 | `factuality`: 3/3 |
| CA-4 | `applicant`: 4/4; `forbidden_phrases.py applicant_v1.txt` rc 0 |
| CA-5 | cobertura de ramas 100 % en `policy` (44/14), `narrative` (43/8), `factuality` (52/22) y `applicant` (17/0); `logic.md` existe |
| CA-6 | `make -C platform check` rc 0; `make -C scoring-explainability lint` rc 0 (3 contratos) |
| CA-7 | solo las cinco líneas del plan |
| `--all` | la rama quita NFR-U7-40, 41 y 42 y no agrega fallos |

## Dictamen

1. **Mutaciones propias:** 10, de las que mueren 9 (desempate inverso en `narrative` y en `applicant`, `effective_cutoff` sin canal, VIS con `<`, intensidad sobre todo el vector, `factuality` con `>` en 3/10 y sin filtrar ceros, `applicant` con 3 factores que devuelve 2). Sobrevive F9 (F-01).
2. **`factuality` independiente** (BR-U7-11): no importa `narrative` ni `template_files` (import-linter y prueba por AST), usa `Fraction` frente a `Decimal`, y coincide en empates y en SHAP = 0.
3. RT-4 desde `vectra_reference.release` sin copia; normativa nula → `revision_requerida` sin fail-closed (US-207).
4. **US-207/BR-U7-04 no se contradice:** son dos escenarios separados; solo el ejemplo del Paso 3 del plan los mezcla. No afecta a D1 ni al flujo base.
5. **Plantillas:** la rueda de `vectra-explainability` las incluye y `read_template` las encuentra desde `site-packages` en un venv aparte; `forbidden_phrases.py` rc 0.

## Hallazgos (candidatas)

- **F-01 · NARANJA** · PBT-U7-05: ningún operador de mutación toca la numeración; el mutante F9 (aceptar cualquier número de línea) sobrevive.
- **F-02 · NARANJA** · el comentario de `coverage` del `Makefile` traza NFR-U7-41 (mutmut), que está diferido: decidir antes de `cierre-demo.md` de U7.
- **F-03 · AMARILLO** · el oráculo de PBT-U7-06 copia la clave de orden de `applicant.py`.
- **F-04 · AMARILLO** · una corrida verde no imprime la semilla (convención de todos los `conftest.py`).
- **F-05 · AMARILLO** · el ejemplo del factor invertido está fuera del comando de CA-3 (cubierto por el operador «signo»).
