# 09 — D4 (día D + 1 UTC): `u11` y Grafana

**Estado: pendiente del operador.** Plantilla de U12-T06: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada _pendiente_ con lo que obtuvo —el comando, la salida **sin tokens, cookies, contraseñas ni semillas** y el cumplimiento— y cambia este estado a `completa` (o `fallida`, con el hallazgo). Quien llena una plantilla no inventa la salida: lo que no se corrió queda `no ejecutado`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F9 (D4 (día D + 1 UTC): `u11` y Grafana).
- Fecha: _pendiente_.
- Operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.
- Duración real de la fase: _pendiente_ (estimada: 15 min, tras la espera; la guía pide anotarla).

Entradas de esta fase: K-62, K-63.

### K-62 — North Star, sostenida, tasa de consulta y ProductMetricsStale con dato…

- Demo: D4. Fuentes: `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:47`, `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:48`, `aidlc-docs/construction/plans/demo-recorte-funcional.md:117`, `tareas/U12-T05-imagen-y-documentacion.md:372`, `tareas/U12-T05-imagen-y-documentacion.md:374`.

**Resultado esperado.** North Star, sostenida, tasa de consulta y ProductMetricsStale con datos reales, dentro del dia D + 1 UTC (la herramienta espera hasta las 02:40 UTC; desde las 00:00 UTC de D + 2 el ayer no tiene decisiones)

**Comando.** Previsto: `vectra-verification u11`; `dashboard.sh`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| North Star, sostenida, tasa de consulta y ProductMetricsStale con datos reales, dentro del dia D + 1 UTC (la herramienta espera hasta las 02:40 UTC; desde las 00:00 UTC de D + 2 el ayer no tiene decisiones) | _pendiente_ | _pendiente_ |

### K-63 — Grafana por port-forward con grafana-admin; el dashboard Producto carg…

- Demo: D4. Fuentes: `DECISIONES-LOOP.md:132`, `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:48`, `tareas/U12-T04-demos-cli-y-manifiesto.md:161`, `tareas/U12-T04-demos-cli-y-manifiesto.md:586`, `tareas/U12-T05-imagen-y-documentacion.md:373`, `platform/observability/grafana/external-secrets.yaml:31-36`, `CANDIDATAS.md:82`.

**Resultado esperado.** Grafana por port-forward con grafana-admin; el dashboard Producto carga con sus cuatro paneles. Los permisos por carpeta y rol no se ensenan

**Comando.** Previsto: `kubectl --context kind-vectra port-forward -n vectra-observability`; a mano: el navegador, en el dashboard Producto.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Grafana por port-forward con grafana-admin; el dashboard Producto carga con sus cuatro paneles. Los permisos por carpeta y rol no se ensenan | _pendiente_ | _pendiente_ |

## Hallazgos

_Ninguno todavía._ Cada hallazgo dice **a qué unidad apunta** (la tabla de síntomas de la guía da la primera pista) y abre una tarea en esa unidad; un defecto del chart o de las imágenes de una unidad no se arregla aquí.
