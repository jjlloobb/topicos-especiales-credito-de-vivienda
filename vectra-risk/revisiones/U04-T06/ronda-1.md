# Ronda 1 — U04-T06

VEREDICTO: NO-VERDE

Revisor, 2026-11-10, punta `57d8cd6`. El revisor entregó el informe en su respuesta; el orquestador lo transcribe.

## Criterios (corridos por el revisor)

CA-1 a CA-11 pasan: conftest 876/876 y 114 pruebas de `test_chart.py`; admisión de U1 en los tres entornos (bucle por entorno, sin `check-chart` por el pánico conocido); flujos (211 pruebas); runbook con `cro-2`/`cro-1`; `slo.md`, runbook de `CompensationEventPending` y `promtool` SUCCESS; Application wave 5 sin auto-sync; cobertura 95,77 % y 100 % en `evidence`, `model_fsm` y `policy` (476 pruebas); trazabilidad rc 0; imagen `65532:65532` y `OK`; `make -C platform check` rc 0 (802); plan correcto. Presupuesto: 8,9766 GiB, `BUDGET_GIB` 9,0.

## Hallazgos

- **F-01 · NARANJA, rompe las cuatro demos** · `governance/Dockerfile:31` y `chart/templates/service.yaml:50`: `docker run localhost:5001/vectra/governance:dev` sale con `No module named vectra_governance.service`. No hay `service.py`, `build_app` ni `__main__`; `api.py` solo exporta `create_governance_app(deps, …)`. Nada arma desde el entorno `Pools`, `Evidence`, `ServingConfigCache`, el `PackageStore` S3 de F47, `KubernetesJobs`, los clientes del registro y de F25 ni `Background`. **El origen es el Paso 10 (U04-T04)**, no el 16: U3 tuvo su `service.py` en U03-T03, y la candidata de U04-T04 (`build_app` y S3 de F47) ya lo anunciaba. U04-T06 no podía escribirlo: `governance/src` no está en sus archivos.
- **F-02 · NARANJA** · `governance/runbooks/kind-politica-de-referencia.md:44-79`: el camino sin BFF (pod efímero con la identidad `console-bff`) es viable, pero tal como está no corre: `localhost:5001/mc:dev` no tiene `curl`; el paso 3 está elidido con «…»; la verificación hace `curl` al nombre interno desde la máquina del operador (no resuelve y la malla lo rechazaría); y la `ServiceAccount` `console-bff` no existe hasta U10.
- **F-03 · AMARILLO** · `evidence.py:917`: el `# pragma: no cover` de la rama `blocked` de `_recover` cubre lógica de negocio que un doble del registro podría alcanzar en un solo proceso. Los de `:425` y `:768` son legítimos.
- **F-04 · AMARILLO** · `cierre-demo.md`: NFR-U4-02, 06, 12 y 13 citan el recorte §8, pero §8 conserva la guía de kind de U4; son pendientes de U04-T07, no diferidos. Además §8 no está en la base `d1d2c48`.

Lo demás (`EXPECTED_WAVES`, el ajuste de `test_validation_job_template.py`, una sola Application con namespaces explícitos, DSN sin credenciales) es correcto.
