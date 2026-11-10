# Arbitraje de la ronda 1 — U06-T02

Orquestador, 2026-11-09. Informe: `revisiones/U06-T02/ronda-1.md`. NO-VERDE sin ROJO; los CA-1 a CA-7 pasan. Por RL-2, un NARANJA va a candidatas **salvo que rompa una de las cuatro demos**.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 · el explicador no declara `command`; KServe v0.21.0 le agrega `--model_name`, `--predictor_host` y `--http_port`, que reemplazan el `CMD` → `CrashLoopBackOff` | **Entra en la ronda 2** | Rompe el flujo base y D1: sin explicador no hay `Ready` (BR-U7-10/11) |
| F-02 · la anotación `internal.serving.kserve.io/storage-initializer-sourceuri` no hace nada (KServe la descarta) | **Entra** | Es engañosa y el arreglo es quitarla; documentar que el storage initializer usa `STORAGE_URI`, que dentro del pod vale `/mnt/models` |
| F-03 · la bitácora describe mal la falla de `check-chart` | **Entra** (texto) | Evidencia fiel |
| F-04 · el diseño dice «primeros 8 hex» | Candidata | El chart está bien; es redacción del diseño |
| Ediciones fuera de U6 (`EXPECTED_WAVES`, README, prueba de `package_loader`) | **Ratificadas** por el revisor y el orquestador | Consecuencias necesarias de la tarea; U03-T05 hizo lo mismo |
| Credencial `minio-kserve` sin `AWS_*` ni endpoint; `kserve.yaml` sin `credentials.s3` | Candidata **bloqueante para U06-T03** (U1) | Es de U1 y está fuera del alcance; se le lleva al usuario |
| Presupuesto de kind (hasta 10,17 GiB en la promoción) | Candidata para U06-T03 | No es de esta tarea |

## Qué entra en la ronda 2 (la última por RL-2)

1. **Integrar `origin/main`** (trae U04-T05 y U05-T05). Conflicto esperado en `CANDIDATAS.md`: conservar ambos lados. Si `uv.lock` choca, regenerarlo con `uv lock`.
2. **F-01.** `command: ["python", "-m", "vectra_explainer"]` en el contenedor del explicador de la plantilla (y en el del predictor si la imagen tampoco lo garantiza frente a los `args` que agregue KServe a ese componente; compruébalo en `explainer_custom.go` / el código de v0.21.0 que corresponda y regístralo). Una regla de `policies/conftest/` que lo exija, con su caso de mutación en `test_chart.py`. Una prueba que confirme que el programa ignora argumentos extra en `sys.argv`.
3. **F-02.** Quitar la anotación inerte y dejar en `docs/values.md` (o en la bitácora) cómo llega el paquete al contenedor: `STORAGE_URI` inyectada y montaje en `/mnt/models`. Si el cargador de U06-T01 lee otra ruta, regístralo como riesgo para U06-T03; no cambies U06-T01 salvo que la plantilla lo exija.
4. **F-03.** Corregir en la bitácora la descripción de `check-chart`: pánico por la `ServiceAccount` repetida con los tres entornos juntos; `pass: 0` con un entorno.
5. Candidatas en `CANDIDATAS.md`: F-04, la credencial `minio-kserve` (bloqueante para U06-T03, U1), el presupuesto de kind con la tabla del revisor, `check-chart` con charts de solo CRs y la prueba de sincronía sin explicador en staging.

Nada más. El revisor de la ronda 2 comprueba esos puntos, CA-1, CA-2, CA-5, CA-6 y `--all`.
