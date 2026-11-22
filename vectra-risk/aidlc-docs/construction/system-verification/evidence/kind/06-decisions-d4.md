# 06 — `decisions` (D4, día D)

**Estado: completa, con hallazgos.** Llenada el 2026-11-21 con lo que se obtuvo contra `kind-vectra`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F6 (`decisions` (D4, día D)).
- Fecha: 2026-11-21 (jornada 2), entre las 01:21 y las 01:38 UTC.
- Operador: jjlloobb, con Claude Code ejecutando las ordenes.
- Commit de `main` desplegado: 85c267d.
- Duración real de la fase: unos 17 min (de las 01:21 a las 01:38 UTC; `decisions` sola, 15 min 28 s) (estimada: ≈ 45 min; la guía pide anotarla).

Entradas de esta fase: K-44, K-45, K-46, K-47.

### K-44 — 2 000 casos: accepted = sent; cada uno en listo o en un fail-closed do…

- Demo: D4. Fuentes: `CANDIDATAS.md:676`, `aidlc-docs/construction/plans/system-verification-code-generation-plan.md:107`, `aidlc-docs/construction/plans/system-verification-code-generation-plan.md:147`.

**Resultado esperado.** 2 000 casos: accepted = sent; cada uno en listo o en un fail-closed documentado; los ultimos no quedan en not_ready sin decidir

**Comando.** Previsto: `vectra-verification decisions`.

```bash
vectra-verification decisions
system-verification/demos/verify/dashboard.sh 5
```

**Salida.**

```text
2026-11-21T01:20:59Z
SIM-NORMAL: pasa
seccion decisions: pasa (0): enviadas 2000, aceptadas 2000, decididas 2000
rc=0
2026-11-21T01:36:29Z
## dashboard.sh 5 01:37:10
OK: decisions paso
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| 2 000 casos: accepted = sent; cada uno en listo o en un fail-closed documentado; los ultimos no quedan en not_ready sin decidir | 2000 enviadas, 2000 aceptadas y 2000 decididas; `SIM-NORMAL` en `pasa`; 0 casos sin decidir, 0 en sincronizacion tras la espera, 0 rechazos | si |

### K-45 — Las constantes de la estimacion de guard (1 s por caso, 300 s) frente …

- Demo: D4. Fuentes: `CANDIDATAS.md:634`, `tareas/U12-T05-imagen-y-documentacion.md:375`.

**Resultado esperado.** Las constantes de la estimacion de guard (1 s por caso, 300 s) frente al tiempo real; el ritmo real frente a 10/s

**Comando.** Previsto: `vectra-verification decisions`.

```bash
vectra-verification decisions   # horas de inicio y fin en el manifiesto
```

**Salida.**

```text
sections.decisions: started_at 2026-11-21T01:21:00Z, finished_at 2026-11-21T01:36:28Z, seconds 928
estimacion de guard: 2000 / 10 + 2000 x 1 s + 300 s = 2500 s (unos 42 min)
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Las constantes de la estimacion de guard (1 s por caso, 300 s) frente al tiempo real; el ritmo real frente a 10/s | 928 s reales (15 min 28 s) frente a los 2500 s estimados: la estimacion sobra por un factor de 2,7. El ritmo de envio no se midio aparte; cero 429 | si (la estimacion es conservadora) |

### K-46 — registry-aggregator con atraso 0 y POST /v1/monitoring/daily

- Demo: D2. Fuentes: `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md:74`, `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md:75`.

**Resultado esperado.** registry-aggregator con atraso 0 y POST /v1/monitoring/daily:query con resultado mayor que 0 tras los 2 000 casos

**Comando.** Previsto: `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=registry-aggregator`; `observabilidad.sh consulta vectra_bias_last_run_ok`.

```bash
kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=registry-aggregator --tail=4
system-verification/docs/kind/observabilidad.sh consulta vectra_bias_last_run_ok
kubectl --context kind-vectra get jobs -n vectra-app
```

**Salida.**

```text
{"batches": 1, "entries": 1667, "lag_seconds": 0, "purged": 0, "reached_head": true, "watermark": 5085}
bias-monitoring-job-29920382   Complete   1/1           19s        35m
bias-monitoring-job-29920397   Complete   1/1           19s        20m
bias-monitoring-job-29920412   Complete   1/1           21s        5m10s
{__name__="vectra_bias_last_run_ok",container="pushgateway",endpoint="http",group="run",job="bias-monitoring",namespace="vectra-observability",pod="pushgateway-7696594f96-bsgkf",service="pushgateway"} 1
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| registry-aggregator con atraso 0 y POST /v1/monitoring/daily:query con resultado mayor que 0 tras los 2 000 casos | agregador con `lag_seconds: 0` y `reached_head: true`; las corridas de bias posteriores a los 2000 casos terminan `Complete` y `vectra_bias_last_run_ok` vale 1. Antes hubo que arreglar el Job (H-6): desde el primer caso real el Pushgateway rechazaba el grupo `run` | si, tras el PR #225 (H-6) |

### K-47 — Memoria real con 2 000 decisiones frente a los 128 MiB de request de k…

- Demo: D4. Fuentes: `aidlc-docs/construction/case-management/evidence/cierre-demo.md:76`, `aidlc-docs/construction/console/evidence/cierre-demo.md:74`, `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:53`, `CANDIDATAS.md:619`, `CANDIDATAS.md:696`, `DECISIONES-LOOP.md:102`, `DECISIONES-LOOP.md:104`, `DECISIONES-LOOP.md:108`.

**Resultado esperado.** Memoria real con 2 000 decisiones frente a los 128 MiB de request de kind: case-service, case-worker, el BFF y product-metrics

**Comando.** Previsto: `memoria.sh despues`.

```bash
system-verification/docs/kind/memoria.sh antes; system-verification/docs/kind/memoria.sh durante; system-verification/docs/kind/memoria.sh despues
```

**Salida.**

```text
46 pods medidos; fase antes; disponible 3359 MiB (puerta 3072 MiB)
01:25:05
46 pods medidos; fase durante; disponible 3072 MiB (puerta 1536 MiB)
rc=0
vectra-verification-1963283-22302 321.5MiB / 1GiB 2.33%
cloud-provider-kind 27.56MiB / 14.82GiB 0.02%
kindccm-abc7eeb4f506 8MiB / 14.82GiB 0.54%
vectra-app/case-service-77967bf7bc-kc8x6: 76 MiB de trabajo, request 128 MiB
vectra-app/case-service-77967bf7bc-srcwp: 75 MiB de trabajo, request 128 MiB
vectra-app/case-worker-6db85bff7b-lvhh2: 72 MiB de trabajo, request 128 MiB
vectra-app/case-worker-6db85bff7b-mrglk: 71 MiB de trabajo, request 128 MiB
vectra-app/console-bff-6d7df7cb57-rccfb: 68 MiB de trabajo, request 128 MiB
vectra-app/console-bff-6d7df7cb57-x7mgd: 70 MiB de trabajo, request 128 MiB
vectra-app/product-metrics-7dc56bb84c-7nj79: 64 MiB de trabajo, request 128 MiB
vectra-app/product-metrics-7dc56bb84c-nh6zv: 65 MiB de trabajo, request 128 MiB
46 pods medidos; fase despues; disponible 3207 MiB (puerta 0 MiB)
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Memoria real con 2 000 decisiones frente a los 128 MiB de request de kind: case-service, case-worker, el BFF y product-metrics | tras 2000 decisiones: `case-service` 75 y 76 MiB, `case-worker` 71 y 72, BFF 68 y 70, `product-metrics` 64 y 65, todos bajo el request de 128 MiB. El contenedor de la herramienta, 322 MiB de 1 GiB. Disponible en la maquina: 3359 MiB antes, 3072 durante, 3207 despues | si |

## Hallazgos

- **H-6 (U9, `bias-monitoring`; PR #225).** Desde el primer caso real (el ensayo del 2026-11-20, 13:47 UTC) cada corrida del CronJob terminaba `Failed`: el Pushgateway rechazaba con 400 el grupo `run` porque `vectra_bias_cell_size` llevaba una etiqueta `group`, que el Pushgateway pisa con la de la llave del grupo. Se renombro a `cell_group`, se reconstruyo la imagen y la corrida de las 01:02 UTC del 2026-11-21 ya termino `Complete`. Se arreglo antes de `prepare`.
- El modelo de referencia siguio `activo` tras los 2000 casos (`humo modelos`, 01:37:50 UTC).
