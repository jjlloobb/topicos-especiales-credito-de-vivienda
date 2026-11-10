# Ronda 1 — U09-T02

VEREDICTO: VERDE

Revisor, 2026-11-10, punta `b021c5c`, base `31e12c0`. El revisor entregó el informe en su respuesta; el orquestador lo transcribe.

## Criterios (corridos por el revisor)

| # | Resultado |
|---|---|
| CA-1 | 23 passed (`ci`, semilla 3805923219) |
| CA-2 | 13 passed: 40/6 pp sin freeze; 2 000/6 pp sin freeze (0,0315); 2 000/12 pp freeze (0,0918); F-03 congela por `sexo` (0,0768) con `trigger_attribute=region`; proxy 0,2282; base 0,0042 |
| CA-3 | 32 + 1 passed |
| CA-4 | 24 passed; `run_machine_stats={'examples': 144, 'runs': 2419, 'max_runs': 40}`; corrida de 3 versiones 0,95 s, `tracemalloc` 4,8 MiB, RSS 138 MiB |
| CA-5 | 7 passed sin xfail ni skip: falsos 0,01 % / 0 % con ≥ 500; base 0,80 / 1,28 / 1,07 %; proxy 100 %; D\* t = 0,69 → 95,58 % |
| CA-6 | la fecha 2026-11-10 en los cinco archivos; BR-U9-11 con 46 comparaciones y z = 3,14 |
| CA-7 | 4 contratos KEPT, 2 passed |
| CA-8 | `--all`: 0 ids nuevos frente a la base y a main; se resuelven NFR-U9-01, 04, 20, 21, 22, 33, P-U9-01 y P-U9-07 |
| CA-9 | `make -C bias-monitoring check` rc 0, cobertura de ramas 100 % |
| CA-10 | Pasos 6, 7 y 8 en `[x] (U09-T02)` |

`make -C platform check`: 802 pytest pasan; solo falla `check-tools` por falta de `platform/.tools` en el worktree (entorno, sin relación con el diff, que no toca `pyproject.toml` ni `uv.lock`).

## Dictamen

1. PBT-U9-05 con 120 × 80: **ajuste de escala, no recorte**: conserva todos los comandos e invariantes de la BLM §3, explora más que U3 (50 × 15) y U4 (25 × 40). Contradice al pie de la letra NFR-U9-52 (F-01).
2. R4 sobre todos los atributos: correcto; el paquete F-03 pasa `FreezeContext` (U0), `fit_freeze_package` (U4) con `implicated` intacto y `FreezeRecord` (U3).
3. Re-medición y D\* reproducidos con las semillas 777 y 4242 (10 000 repeticiones): el cruce del 95 % está entre t = 0,68 y 0,69 en las tres semillas; `DSTAR_T = 0,69` bien calibrado, con margen fino (95,28 % con 4242).
4. Enmienda de diseño coherente; 46 = 1 + 15 + 15 + 15 verificado con los catálogos de U0.
5. Cambios fuera de la lista aceptables; los códigos de salida 0/1/2, la solicitud de `versions` con `unattributable_range` y las variables de `run` no contradicen P-U9-01, P-U9-02, P-U9-07 ni BR-U9-20.

## Hallazgos (candidatas)

- **F-01 · NARANJA** · `test_run_machine.py:228`: 120 ejemplos incrustados contra NFR-U9-52; nombrarlo en el diseño o atarlo al perfil.
- **F-02 · NARANJA** · `freeze_client.py:46`, `registry_client.py:26-27`, `run.py:59-62`: rutas y scopes literales en vez de `vectra_contracts.routes` y `Scope`.
- **F-03 · AMARILLO** · `test_run_machine.py:233`: la prueba guardiana depende del orden (falla sola).
- **F-04 · AMARILLO** · comentario «30 × 60» del `Makefile` desactualizado; margen fino de D\* sin documentar en `library.md`.
- **F-05 · AMARILLO** · `_rewrite`: la máquina no genera «datos viejos altos y nuevos bajos» tras reactivar (lo cubre una prueba de integración).
- **F-06 · AMARILLO** · `plan_queries`: el parámetro `unattributable` no lo usa `run`.
