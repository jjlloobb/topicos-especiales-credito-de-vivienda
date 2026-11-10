# SLO de `governance` (NFR-U4-01)

`governance-service` es **dependencia del SLO de la ruta de recomendación** (99,5 %, P-U1-11 de U1): si no responde, scoring falla cerrado en todas las evaluaciones. Este documento dice qué se promete, qué se mide y qué cubre la demo. La alerta de disponibilidad (`ServingConfigUnavailable`, NFR-U4-07) y las demás de P-U4-08 están diferidas (T2); aquí solo existe `CompensationEventPending`.

## Qué cuenta contra el SLO

| Lectura | Objetivo | Por qué |
|---|---|---|
| `GET /v1/serving-config` (incluido el 304) | p95 ≤ 20 ms con 12 clientes cada 5 s (NFR-U4-10) | Scoring y `case-worker` la leen continuamente |
| Transiciones con firma | p95 ≤ 500 ms, incluido el append al registro (NFR-U4-11) | |
| Frescura de la configuración | Nunca vencida: scoring no usa una `serving-config` de más de 5 s (NFR-U4-02, BR-U4-14); a los 30 s sin confirmar contra la base, el servicio responde 503 | Sin modo «última conocida» |
| Propagación del congelamiento | ≤ 6 s: 1 s de convergencia entre réplicas más 5 s de la caché de scoring (NFR-U4-06) | |

`governance` cuenta como **dentro del SLO** mientras la lectura de `serving-config` responda dentro de esos objetivos. Las **escrituras** (transiciones, políticas, fuentes) pueden responder 503 con la base o el registro caídos sin que eso viole el SLO de la ruta de recomendación: las lecturas siguen (NFR-U4-03).

## Cómo se sostiene

- 2 réplicas o más (HPA de 2 a 6 al 70 % de CPU), repartidas por zona, con PDB `minAvailable: 1` y `vectra-high` (INF-U4-01; `governance/chart/`).
- La readiness (`/readyz`, puerto 8081) es «la copia de `serving-config` está cargada», no «la base responde»: con `governance-db` caída el pod sigue en el balanceo, `serving-config` responde y las escrituras dan 503 (NFR-U4-03).
- El reconciliador completa las transiciones que quedaron sin ack del registro; una compensación pendiente dispara `CompensationEventPending` (runbook: `governance/runbooks/compensation-event-pending.md`).

## Qué mide la demo y qué no

- **Medido en esta tarea:** forma del despliegue (réplicas, HPA, PDB, prioridad, recursos) con `conftest` y `test_chart.py`; la alerta de compensaciones con `promtool test rules` (`make -C governance rules`).
- **No medido (diferido):** la carga k6 de NFR-U4-10 y NFR-U4-11 (T3), la prueba de propagación de ≤ 6 s y la de la base pausada (verificación en kind, consolidada en U12) y las alertas `ServingConfigUnavailable`, `ServingConfigStale` y `ServingConfigConvergenceSlow` (T2). Están en la lista «Diferido por la demo» de `aidlc-docs/construction/governance/evidence/cierre-demo.md`.
