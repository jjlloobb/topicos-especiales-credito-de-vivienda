# 10 — Informe y estado final

**Estado: completa, con hallazgos.** Llenada el 2026-11-22 (UTC) con lo que se obtuvo contra `kind-vectra`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F10 (Informe y estado final).
- Fecha: 2026-11-22 UTC (21:33 del 21 de noviembre en Colombia), día D + 1.
- Operador: jjlloobb, con Claude Code ejecutando las ordenes.
- Commit de `main` desplegado: fd33db6.
- Duración real de la fase: unos 5 min (02:34 a 02:36 UTC), sin contar el llenado de plantillas (estimada: 30 min; la guía pide anotarla).

Entradas de esta fase: K-64, K-65.

### K-64 — El informe lista cada RT, demo e historia; salen no ejecutado US-106, …

- Demo: Base. Fuentes: `CANDIDATAS.md:641`, `tareas/U12-T05-imagen-y-documentacion.md:113`, `aidlc-docs/construction/plans/system-verification-code-generation-plan.md:209`.

**Resultado esperado.** El informe lista cada RT, demo e historia; salen no ejecutado US-106, 109, 603, 305, 604, 608, 609 y 610, RT3-b y 'a y d desplegados'; ninguno sale pasa sin evidencia

**Comando.** Previsto: `vectra-verification report`.

```bash
vectra-verification report
```

**Salida.**

```text
2026-11-22T02:34:02Z
informe: evidence/verification-report.md: 16 pasa, 0 falla, 25 no ejecutado
seccion report: pasa (0)
rc_report=0
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| El informe lista cada RT, demo e historia; salen no ejecutado US-106, 109, 603, 305, 604, 608, 609 y 610, RT3-b y 'a y d desplegados'; ninguno sale pasa sin evidencia | informe con 16 `pasa`, 0 `falla` y 25 `no ejecutado`. Pasan RT-2, RT2-LATENCY, RT-3, RT-5, SIM-NORMAL y las cuatro demos (`journey-7-3`, `journey-7-4`, `rt-5`, `dashboard`). `no ejecutado`, con su motivo: RT-1, RT-4 y las secciones diferidas por la demo, entre otros. Ninguno sale `pasa` sin evidencia | si |

### K-65 — El cluster queda como estaba

- Demo: D1, D2. Fuentes: `aidlc-docs/construction/system-verification/functional-design/business-rules.md:130`, `tareas/U12-T04-demos-cli-y-manifiesto.md:587`.

**Resultado esperado.** El cluster queda como estaba: modelo de referencia activo, ninguna version congelado, sin InferenceService de staging, F22 encendido

**Comando.** Previsto: `estado-final.sh`.

```bash
humo modelos | system-verification/docs/kind/estado-final.sh --modelos - --referencia mv-2026-01-01-8a98ab02
system-verification/docs/kind/memoria.sh despues
```

**Salida.**

```text
2026-11-22T02:34:38Z
modelos: 2; activos 1; congelados 0
OK   sin InferenceService de staging
OK   InferenceService en vectra-serving: inferenceservice.serving.kserve.io/isvc-8a98ab02 inferenceservice.serving.kserve.io/isvc-f12bfeaf 
OK   F22: networkpolicy.networking.k8s.io/allow-f22-explainability-service-to-explainer-egress
OK   F22: networkpolicy.networking.k8s.io/allow-f22-to-explainer-ingress
OK   F22: authorizationpolicy.policy.linkerd.io/f22-explainer-8080
OK   F22: meshtlsauthentication.policy.linkerd.io/f22-explainer-8080-mtls
OK   F22: server.policy.linkerd.io/explainer-8080
queda (se anota): casos en fallo persistente (no_disponible de D1) = 10
queda (se anota): alertas en firing = FailClosedPersistente, HPAMaxedOut, PostgresVolumeUsageHigh, RealmDrift, RestoreDrillFailed, Watchdog
estado final: como estaba
rc_estado=0
48 pods medidos; fase despues; disponible 2711 MiB (puerta 0 MiB)
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| El cluster queda como estaba: modelo de referencia activo, ninguna version congelado, sin InferenceService de staging, F22 encendido | `estado-final.sh` en 0, «como estaba»: modelo de referencia `activo`, ninguna versión `congelado`, sin `InferenceService` de staging, los cinco recursos de F22 presentes. Queda, anotado: 10 casos en `no_disponible` (D1), el proxy `isvc-f12bfeaf` declarado e inactivo con 1 réplica, el `runId` 20261121-0104 en los values, el Job `rt5-demo-20261121-0104`, y las alertas `FailClosedPersistente`, `HPAMaxedOut`, `PostgresVolumeUsageHigh`, `RealmDrift`, `RestoreDrillFailed` y `Watchdog` en `firing` | si |

## Hallazgos

- Las alertas `HPAMaxedOut` (en kind el máximo de réplicas es igual al mínimo), `RealmDrift` (35 diferencias conocidas del comparador), `RestoreDrillFailed` y `PostgresVolumeUsageHigh` siguen en `firing`; ninguna entra en las demos. Quedan para explicar en la sustentación.
- El `runId` de RT-5 sigue en `vectra-risk-gitops/values/kind/case-management.yaml`: mientras esté, unas 60 pruebas locales de U12 fallan (la CI no las corre). Retirarlo es un PR y un sync con prune.
