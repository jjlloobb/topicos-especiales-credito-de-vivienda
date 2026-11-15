# 06 — `decisions` (D4, día D)

**Estado: pendiente del operador.** Plantilla de U12-T06: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada _pendiente_ con lo que obtuvo —el comando, la salida **sin tokens, cookies, contraseñas ni semillas** y el cumplimiento— y cambia este estado a `completa` (o `fallida`, con el hallazgo). Quien llena una plantilla no inventa la salida: lo que no se corrió queda `no ejecutado`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F6 (`decisions` (D4, día D)).
- Fecha: _pendiente_.
- Operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.
- Duración real de la fase: _pendiente_ (estimada: ≈ 45 min; la guía pide anotarla).

Entradas de esta fase: K-44, K-45, K-46, K-47.

### K-44 — 2 000 casos: accepted = sent; cada uno en listo o en un fail-closed do…

- Demo: D4. Fuentes: `CANDIDATAS.md:676`, `aidlc-docs/construction/plans/system-verification-code-generation-plan.md:107`, `aidlc-docs/construction/plans/system-verification-code-generation-plan.md:147`.

**Resultado esperado.** 2 000 casos: accepted = sent; cada uno en listo o en un fail-closed documentado; los ultimos no quedan en not_ready sin decidir

**Comando.** Previsto: `vectra-verification decisions`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| 2 000 casos: accepted = sent; cada uno en listo o en un fail-closed documentado; los ultimos no quedan en not_ready sin decidir | _pendiente_ | _pendiente_ |

### K-45 — Las constantes de la estimacion de guard (1 s por caso, 300 s) frente …

- Demo: D4. Fuentes: `CANDIDATAS.md:634`, `tareas/U12-T05-imagen-y-documentacion.md:375`.

**Resultado esperado.** Las constantes de la estimacion de guard (1 s por caso, 300 s) frente al tiempo real; el ritmo real frente a 10/s

**Comando.** Previsto: `vectra-verification decisions`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Las constantes de la estimacion de guard (1 s por caso, 300 s) frente al tiempo real; el ritmo real frente a 10/s | _pendiente_ | _pendiente_ |

### K-46 — registry-aggregator con atraso 0 y POST /v1/monitoring/daily

- Demo: D2. Fuentes: `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md:74`, `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md:75`.

**Resultado esperado.** registry-aggregator con atraso 0 y POST /v1/monitoring/daily:query con resultado mayor que 0 tras los 2 000 casos

**Comando.** Previsto: `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=registry-aggregator`; `observabilidad.sh consulta vectra_bias_last_run_ok`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| registry-aggregator con atraso 0 y POST /v1/monitoring/daily:query con resultado mayor que 0 tras los 2 000 casos | _pendiente_ | _pendiente_ |

### K-47 — Memoria real con 2 000 decisiones frente a los 128 MiB de request de k…

- Demo: D4. Fuentes: `aidlc-docs/construction/case-management/evidence/cierre-demo.md:76`, `aidlc-docs/construction/console/evidence/cierre-demo.md:74`, `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:53`, `CANDIDATAS.md:619`, `CANDIDATAS.md:696`, `DECISIONES-LOOP.md:102`, `DECISIONES-LOOP.md:104`, `DECISIONES-LOOP.md:108`.

**Resultado esperado.** Memoria real con 2 000 decisiones frente a los 128 MiB de request de kind: case-service, case-worker, el BFF y product-metrics

**Comando.** Previsto: `memoria.sh despues`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Memoria real con 2 000 decisiones frente a los 128 MiB de request de kind: case-service, case-worker, el BFF y product-metrics | _pendiente_ | _pendiente_ |

## Hallazgos

_Ninguno todavía._ Cada hallazgo dice **a qué unidad apunta** (la tabla de síntomas de la guía da la primera pista) y abre una tarea en esa unidad; un defecto del chart o de las imágenes de una unidad no se arregla aquí.
