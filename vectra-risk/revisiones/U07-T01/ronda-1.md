# Ronda 1 — U07-T01

VEREDICTO: NO-VERDE

Revisor, 2026-11-10, punta `690d5ed`, base `a1dc900` (= `origin/main`). El revisor entregó el informe en su respuesta; el orquestador lo transcribe.

## Criterios (corridos por el revisor)

| # | Resultado |
|---|---|
| CA-1 | rc 0: 3 contratos KEPT, ruff y `mypy --strict` limpios, 12 passed. Mutaciones de cada contrato sobre una copia (factuality→narrative, `httpx`, `pybreaker`, `openai`, `google.generativeai`, `from google import genai`): todas BROKEN |
| CA-2 | `test_no_core_client.py`: 3 passed; la lista sale de X01 de `forbidden.yaml` y de `flows.yaml`, con caso negativo |
| CA-3 | `test_config.py`: 9 passed; valores de NFR-U7-10/11, P-U7-02/04/05 y la gracia de 20 s frente a 5,8 s; sin `os.environ` ni `getenv` |
| CA-4 | `make -C platform check` rc 0 (pass 335); `make -C scoring-explainability check` rc 0 |
| CA-5 | solo los Pasos 1 y 2 en `[x] (U07-T01)` |
| — | `uv lock --check` rc 0 |
| `--all` | **no cumple la enmienda de §6** (F-01) |

## Juicio

1. Estructura: cumple el Paso 1 con dos miembros (precedente `bias-monitoring` + `bias-monitoring/disparity`); el `pyproject.toml` de unidad del §1 no hace falta para T02–T04.
2. import-linter efectivo y no prohíbe de más: los imports de `vectra_common.*` y `vectra_contracts` siguen KEPT; OpenTelemetry es externo y no se sigue hasta `google.protobuf`. Un `import google.protobuf` directo en U7 sí rompería, pero el diseño de U7 no lo usa.
3. Presupuestos: todos coinciden con la tarea.
4. `test_no_core_client`: sin copias a mano.
5. Fuera de U7: solo el `pyproject.toml` raíz y `uv.lock` (+36 líneas de los dos miembros).

## Hallazgos

- **F-01 · ROJO** · `--all`: 25 fallos nuevos, todos de U7 (sin `cierre-demo.md`). Cuatro son del Paso 1, que la tarea cubre: **NFR-U7-30, NFR-U7-32, NFR-U7-43 y P-U7-07**. NFR-U7-32 y 43 solo se citan en `.importlinter`, que la herramienta no lee; NFR-U7-30 y P-U7-07 no se citan. La bitácora no registra ninguna corrida de `--all`. Arreglo: citarlos en un archivo que la herramienta lee (docstring de una prueba o comentario del `Makefile`).
- **F-02 · AMARILLO** · `.importlinter`: con `vectra_common` como paquete raíz, un import futuro de `google.*` en U0 rompería el contrato de U7; dejarlo comentado.
- **F-03 · AMARILLO** · la duda del `pyproject.toml` de unidad no se anotó en `CANDIDATAS.md`.

Candidata: que `test_traceability.py` lea `.importlinter` (agregarlo a `NAMES`).
