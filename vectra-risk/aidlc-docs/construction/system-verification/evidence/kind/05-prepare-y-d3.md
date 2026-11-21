# 05 — `prepare` y D3 (RT-5)

**Estado: completa, con hallazgos.** Llenada el 2026-11-21 con lo que se obtuvo contra `kind-vectra`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F5 (`prepare` y D3 (RT-5)).
- Fecha: 2026-11-21 (jornada 2), entre las 01:04 y las 01:20 UTC; `rt5 --redo` a las 03:12 UTC.
- Operador: jjlloobb, con Claude Code ejecutando las ordenes.
- Commit de `main` desplegado: de9f23a al correr `prepare`; 85c267d con el `runId`.
- Duración real de la fase: unos 16 min (de las 01:04 a las 01:20 UTC, con la espera del PR #226) (estimada: 20 min; la guía pide anotarla).

Entradas de esta fase: K-39, K-40, K-41, K-42, K-43.

### K-39 — prepare fija runId y started_at; con el PR de runId fusionado, make -C…

- Demo: D3. Fuentes: `tareas/U12-T04-demos-cli-y-manifiesto.md:584`, `aidlc-docs/construction/plans/demo-recorte-funcional.md:376`, `aidlc-docs/construction/plans/demo-recorte-funcional.md:407`.

**Resultado esperado.** prepare fija runId y started_at; con el PR de runId fusionado, make -C case-management policy-chart sigue en verde sobre main

**Comando.** Previsto: `vectra-verification prepare`; `make -C case-management policy-chart`.

```bash
vectra-verification prepare --commit "$(git rev-parse --short HEAD)" --operator "jjlloobb" --values-file /values/case-management.yaml --delivery /verification/reference-model/.out
make -C case-management policy-chart   # en el clon de promocion, con el parche aplicado (PR #226)
```

**Salida.**

```text
runId: 20261121-0104
started_at: 2026-11-21T01:04:21Z
parche: evidence/case-management-runid.patch
seccion prepare: pasa (0)
policy-chart: termina en 0 con el parche; PR #226 fusionado (85c267d) con toda la CI en verde
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| prepare fija runId y started_at; con el PR de runId fusionado, make -C case-management policy-chart sigue en verde sobre main | runId 20261121-0104 y started_at 2026-11-21T01:04:21Z; `policy-chart` en verde con el parche; PR #226 fusionado | si |

### K-40 — El Job rt5-demo-<runId> termina despues de started_at; su log trae el …

- Demo: D3. Fuentes: `aidlc-docs/construction/case-management/evidence/cierre-demo.md:68`, `tareas/U12-T05-imagen-y-documentacion.md:370`.

**Resultado esperado.** El Job rt5-demo-<runId> termina despues de started_at; su log trae el 403 del proxy y el valor real de l5d-proxy-error

**Comando.** Previsto: `rt-5.sh`; `kubectl --context kind-vectra get jobs -n vectra-app`.

```bash
argocd app sync case-management --prune && argocd app wait case-management --health --timeout 900
system-verification/demos/verify/rt-5.sh 1; system-verification/demos/verify/rt-5.sh 2; system-verification/demos/verify/rt-5.sh 3
kubectl --context kind-vectra logs -n vectra-mock deploy/core-banking-mock -c linkerd-proxy --since=20m
```

**Salida.**

```text
## rt-5.sh 1 01:12:18
OK: existe job/rt5-demo-20261121-0104
rc=0
## rt-5.sh 2 01:12:18
OK: job/rt5-demo-20261121-0104 termino bien
rc=0
## rt-5.sh 3 01:12:18
NO ES LO ESPERADO: el 403 lo dio la aplicacion (l5d-proxy-error: None)
rc=1
NO ES LO ESPERADO: CoreWriteAttempt no esta en firing (pasaron mas de 5 min desde el Job: ensena la evidencia de rt5)
rc=1
OK: el proxy denego y el mock no recibio la escritura
rc=0
--- log del proxy de entrada del mock y series (captura F5-403-sin-cabecera.txt) ---
## 01:20:41 increase deny 20m
{client_id="case-service.vectra-app.serviceaccount.identity.linkerd.cluster.local",route_name="core-mock-catch-all"} 0
## contador del mock
{} 0
## log del mock (ultimos 20 min, sin proxy)
[ 82674.868066s]  INFO ThreadId(01) inbound:server{port=8080}:rescue{client.addr=192.168.204.81:34594}: linkerd_app_core::errors::respond: HTTP/2.0 request failed error=client 192.168.204.81:34594: server: 192.168.204.122:8080: unauthorized request on route error.sources=[unauthorized request on rou
0
--- tras el PR #229 (oraculo corregido; captura F6-rt5-redo.txt) ---
2026-11-21T03:12:53Z
RT-5: pasa
rt-5: pasa
seccion rt5: pasa (0)
rc=0
OK: el log trae el 403 sin l5d-proxy-error: quien lo dio lo decide el paso 5
rc3=0
OK: RT-5 y rt-5 pasan
rc6=0
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| El Job rt5-demo-<runId> termina despues de started_at; su log trae el 403 del proxy y el valor real de l5d-proxy-error | el Job `rt5-demo-20261121-0104` termino (Complete, 17 s) despues de `started_at`; su log trae `403 l5d-proxy-error: None`. El 403 lo dio el proxy de entrada del mock (`unauthorized request on route` en su log), pero la cabecera no llego al cliente | si para el Job y el 403 del proxy; el «valor real de l5d-proxy-error» es que no llega (hallazgo H-5) |

### K-41 — La serie inbound_http_authz_deny_total existe con sus etiquetas reales…

- Demo: D3. Fuentes: `aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md:28`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:69`, `CANDIDATAS.md:719`, `tareas/U12-T05-imagen-y-documentacion.md:369`.

**Resultado esperado.** La serie inbound_http_authz_deny_total existe con sus etiquetas reales (namespace vectra-mock, route_name core-mock-catch-all; la prueba de U1 declara otras)

**Comando.** Previsto: `observabilidad.sh serie inbound_http_authz_deny_total`.

```bash
system-verification/docs/kind/observabilidad.sh serie inbound_http_authz_deny_total
```

**Salida.**

```text
inbound_http_authz_deny_total{client_id="case-service.vectra-app.serviceaccount.identity.linkerd.cluster.local",container="linkerd-proxy",endpoint="linkerd-admin",instance="192.168.204.122:4191",job="linkerd-proxy",namespace="vectra-mock",pod="core-banking-mock-5cd84d7886-wvg8c",route_group="policy.
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| La serie inbound_http_authz_deny_total existe con sus etiquetas reales (namespace vectra-mock, route_name core-mock-catch-all; la prueba de U1 declara otras) | la serie existe con `namespace="vectra-mock"` y `route_name="core-mock-catch-all"`, y con `client_id` de `case-service` | si |

### K-42 — CoreWriteAttempt llega a firing y cuanto dura (no tiene for

- Demo: D3. Fuentes: `tareas/U12-T04-demos-cli-y-manifiesto.md:143`, `tareas/U12-T04-demos-cli-y-manifiesto.md:169`, `tareas/U12-T05-imagen-y-documentacion.md:370`, `tareas/U12-T05-imagen-y-documentacion.md:374`.

**Resultado esperado.** CoreWriteAttempt llega a firing y cuanto dura (no tiene for:; la expresion mira 5 min)

**Comando.** Previsto: `observabilidad.sh consulta ALERTS{alertname="CoreWriteAttempt"}`; `rt-5.sh`.

```bash
system-verification/docs/kind/observabilidad.sh consulta 'ALERTS{alertname="CoreWriteAttempt"}'   # cada 30 s durante 7 min
```

**Salida.**

```text
## 01:12:19
sin resultados
## 01:12:50
{__name__="ALERTS",alertname="CoreWriteAttempt",alertstate="firing",severity="SEV2"} 1
## 01:13:20
{__name__="ALERTS",alertname="CoreWriteAttempt",alertstate="firing",severity="SEV2"} 1
## 01:13:51
{__name__="ALERTS",alertname="CoreWriteAttempt",alertstate="firing",severity="SEV2"} 1
## 01:14:22
{__name__="ALERTS",alertname="CoreWriteAttempt",alertstate="firing",severity="SEV2"} 1
## 01:14:53
{__name__="ALERTS",alertname="CoreWriteAttempt",alertstate="firing",severity="SEV2"} 1
## 01:15:23
{__name__="ALERTS",alertname="CoreWriteAttempt",alertstate="firing",severity="SEV2"} 1
## 01:15:54
{__name__="ALERTS",alertname="CoreWriteAttempt",alertstate="firing",severity="SEV2"} 1
## 01:16:25
{__name__="ALERTS",alertname="CoreWriteAttempt",alertstate="firing",severity="SEV2"} 1
## 01:16:56
{__name__="ALERTS",alertname="CoreWriteAttempt",alertstate="firing",severity="SEV2"} 1
## 01:17:27
sin resultados
## 01:17:58
sin resultados
## 01:18:29
sin resultados
## 01:19:00
sin resultados
## 01:19:31
sin resultados
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| CoreWriteAttempt llega a firing y cuanto dura (no tiene for:; la expresion mira 5 min) | sin resultados a las 01:12:19 UTC; `firing` desde la muestra de las 01:12:50 hasta la de las 01:16:56; apagada en la de las 01:17:27 (unos 4 min 30 s) | si |

### K-43 — vectra_core_write_attempts_total en 0 desde el arranque

- Demo: D3. Fuentes: `aidlc-docs/construction/case-management/evidence/cierre-demo.md:68`, `DECISIONES-LOOP.md:100`.

**Resultado esperado.** vectra_core_write_attempts_total en 0 desde el arranque

**Comando.** Previsto: `vectra-verification rt5`; `rt-5.sh`; `observabilidad.sh consulta sum(vectra_core_write_attempts_total)`.

```bash
vectra-verification rt5 --redo
system-verification/demos/verify/rt-5.sh 5; system-verification/demos/verify/rt-5.sh 6
system-verification/docs/kind/observabilidad.sh consulta 'sum(vectra_core_write_attempts_total)'
```

**Salida.**

```text
## rt-5.sh 5 01:20:02
OK: el proxy denego y el mock no recibio la escritura
2026-11-21T03:12:53Z
RT-5: pasa
rt-5: pasa
seccion rt5: pasa (0)
rc=0
OK: el log trae el 403 sin l5d-proxy-error: quien lo dio lo decide el paso 5
rc3=0
OK: RT-5 y rt-5 pasan
rc6=0
{} 0
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| vectra_core_write_attempts_total en 0 desde el arranque | `vectra_core_write_attempts_total` en 0; `RT-5` y `rt-5` en `pasa` con la imagen de U12 del PR #229 (la primera corrida, con el oraculo anterior, dio `falla` por `rt5_403_de_la_aplicacion`) | si, tras corregir el oraculo (H-5) |

## Hallazgos

- **H-5 (U12, oraculo de RT-5; PR #229).** El Job registra `403 l5d-proxy-error: None` aunque denego el proxy de entrada del mock (su log dice `unauthorized request on route`, la serie de denegaciones sube y el contador del mock sigue en 0): la cabecera no llega al cliente. El oraculo lo leia como «respondio la aplicacion» y dio `falla`. Desde el PR #229 deciden la serie de denegaciones y el contador del mock; `rt5 --redo` dio `pasa`.
- `rt-5.sh 4` salio 1 a las 01:20:02 UTC solo porque se corrio con la alerta ya apagada; la alerta se vio (K-42).
