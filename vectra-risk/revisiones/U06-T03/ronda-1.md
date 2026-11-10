# Ronda 1 — U06-T03

VEREDICTO: VERDE

Revisor, 2026-11-10, punta `63f1f5e`, base `9c01e46`. El revisor entregó el informe en su respuesta; el orquestador lo transcribe. Ninguna orden contra el clúster: solo `helm template` local, pruebas y `make`.

| # | Comando | Resultado |
|---|---|---|
| CA-1 | `uv run pytest platform/tests/test_kind_profile.py -v` | 6 passed (renderiza los charts de verdad) |
| CA-2 | `test -s model-serving/docs/paso-11-kind.md` | pasa |
| CA-3 | `shellcheck` (vía `uvx`), `test_kind_scripts.py` y el `grep` de órdenes prohibidas | rc 0; 13 passed; sin coincidencias |
| CA-4 | `test ! -d model-serving/migrations && test ! -d model-serving/frontend` | pasa |
| CA-5 | `make -C model-serving check`, `make -C platform check`, `--all` en la rama y en `git archive 9c01e46` | rc 0; rc 0 (pass 335); `--all` sin fallos nuevos (39 de U4 y U9, los mismos de la base) |
| CA-6 | Evidencia del operador | pendiente del operador |

## Dictamen

1. **Override de kind y esquema:** el esquema declara `profiles` en el nivel superior. `helm template … -f envs/kind/values.yaml -f values/kind/model-serving.yaml` (los `valueFiles` de `apps/kind/model-serving.yaml`) da rc 0; con un overlay de `prod`, `inactive` y `staging`, todos piden 256Mi en kind, y en staging y prod siguen en INF-U6-01. `promotion-tool` solo reemplaza `inferenceServices` y conserva `profiles`. No es ROJO.
2. **Presupuesto:** `requested_gib()` toma las cifras del render real; solo el conjunto del pico está proyectado (kind declara `[]`). El pico (M1 y M2 en `prod` más el predictor de staging, 9 pods de 276 MiB) es el peor momento. 8,4375 ≤ 8,5, conforme a §7. El proxy se cuenta; el storage initializer no (ya es candidata) y no cambia lo que reserva el planificador.
3. **Guía y scripts:** escenarios 1, 2 y 3 y memoria con comando, salida esperada y evidencia. El escenario 3 es ejecutable (RT-3 derivado del base; `PREDICTOR_FILES` incluye `explainer.json`; render de staging con `s3://model-store/adversarial/rt3/RT3-a/` rc 0). `init-order` exige `linkerd-proxy` antes que `storage-initializer`. `traffic.sh` sale con rc 1 ante una versión fuera del conjunto.
4. **Cierre:** `cierre-demo.md` con sus tres secciones y 8 filas «pendiente del operador»; Paso 11 `[ ]`, 12 `[x]`, 13 `[x] (U06-T03, acotado a la demo)`.

## Hallazgos (todos AMARILLO, candidatas)

- **F-01** · `model-serving/docs/kind/memory.sh:29`: la suma de `kubectl top` solo entiende `Mi`.
- **F-02** · `model-serving/docs/paso-11-kind.md:162`: `propagation ${I1}` con M1 inactivo, cuando tras el escenario 2 M1 vuelve a `prod`.
- **F-03** · `platform/tests/test_kind_profile.py`: reformateo de líneas ajenas al cambio.
- **F-04** · `platform/tests/test_kind_profile.py`: la prueba de conteo no pasa por el archivo de values de kind y compara floats con `==`.

Candidata nueva: agregar `shellcheck` a `platform/install-tools.sh`.
