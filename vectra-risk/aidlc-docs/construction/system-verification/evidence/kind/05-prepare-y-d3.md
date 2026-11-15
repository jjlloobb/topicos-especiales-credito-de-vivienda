# 05 — `prepare` y D3 (RT-5)

**Estado: pendiente del operador.** Plantilla de U12-T06: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada _pendiente_ con lo que obtuvo —el comando, la salida **sin tokens, cookies, contraseñas ni semillas** y el cumplimiento— y cambia este estado a `completa` (o `fallida`, con el hallazgo). Quien llena una plantilla no inventa la salida: lo que no se corrió queda `no ejecutado`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F5 (`prepare` y D3 (RT-5)).
- Fecha: _pendiente_.
- Operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.
- Duración real de la fase: _pendiente_ (estimada: 20 min; la guía pide anotarla).

Entradas de esta fase: K-39, K-40, K-41, K-42, K-43.

### K-39 — prepare fija runId y started_at; con el PR de runId fusionado, make -C…

- Demo: D3. Fuentes: `tareas/U12-T04-demos-cli-y-manifiesto.md:584`, `aidlc-docs/construction/plans/demo-recorte-funcional.md:376`, `aidlc-docs/construction/plans/demo-recorte-funcional.md:407`.

**Resultado esperado.** prepare fija runId y started_at; con el PR de runId fusionado, make -C case-management policy-chart sigue en verde sobre main

**Comando.** Previsto: `vectra-verification prepare`; `make -C case-management policy-chart`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| prepare fija runId y started_at; con el PR de runId fusionado, make -C case-management policy-chart sigue en verde sobre main | _pendiente_ | _pendiente_ |

### K-40 — El Job rt5-demo-<runId> termina despues de started_at; su log trae el …

- Demo: D3. Fuentes: `aidlc-docs/construction/case-management/evidence/cierre-demo.md:68`, `tareas/U12-T05-imagen-y-documentacion.md:370`.

**Resultado esperado.** El Job rt5-demo-<runId> termina despues de started_at; su log trae el 403 del proxy y el valor real de l5d-proxy-error

**Comando.** Previsto: `rt-5.sh`; `kubectl --context kind-vectra get jobs -n vectra-app`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| El Job rt5-demo-<runId> termina despues de started_at; su log trae el 403 del proxy y el valor real de l5d-proxy-error | _pendiente_ | _pendiente_ |

### K-41 — La serie inbound_http_authz_deny_total existe con sus etiquetas reales…

- Demo: D3. Fuentes: `aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md:28`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:69`, `CANDIDATAS.md:719`, `tareas/U12-T05-imagen-y-documentacion.md:369`.

**Resultado esperado.** La serie inbound_http_authz_deny_total existe con sus etiquetas reales (namespace vectra-mock, route_name core-mock-catch-all; la prueba de U1 declara otras)

**Comando.** Previsto: `observabilidad.sh serie inbound_http_authz_deny_total`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| La serie inbound_http_authz_deny_total existe con sus etiquetas reales (namespace vectra-mock, route_name core-mock-catch-all; la prueba de U1 declara otras) | _pendiente_ | _pendiente_ |

### K-42 — CoreWriteAttempt llega a firing y cuanto dura (no tiene for

- Demo: D3. Fuentes: `tareas/U12-T04-demos-cli-y-manifiesto.md:143`, `tareas/U12-T04-demos-cli-y-manifiesto.md:169`, `tareas/U12-T05-imagen-y-documentacion.md:370`, `tareas/U12-T05-imagen-y-documentacion.md:374`.

**Resultado esperado.** CoreWriteAttempt llega a firing y cuanto dura (no tiene for:; la expresion mira 5 min)

**Comando.** Previsto: `observabilidad.sh consulta ALERTS{alertname="CoreWriteAttempt"}`; `rt-5.sh`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| CoreWriteAttempt llega a firing y cuanto dura (no tiene for:; la expresion mira 5 min) | _pendiente_ | _pendiente_ |

### K-43 — vectra_core_write_attempts_total en 0 desde el arranque

- Demo: D3. Fuentes: `aidlc-docs/construction/case-management/evidence/cierre-demo.md:68`, `DECISIONES-LOOP.md:100`.

**Resultado esperado.** vectra_core_write_attempts_total en 0 desde el arranque

**Comando.** Previsto: `vectra-verification rt5`; `rt-5.sh`; `observabilidad.sh consulta sum(vectra_core_write_attempts_total)`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| vectra_core_write_attempts_total en 0 desde el arranque | _pendiente_ | _pendiente_ |

## Hallazgos

_Ninguno todavía._ Cada hallazgo dice **a qué unidad apunta** (la tabla de síntomas de la guía da la primera pista) y abre una tarea en esa unidad; un defecto del chart o de las imágenes de una unidad no se arregla aquí.
