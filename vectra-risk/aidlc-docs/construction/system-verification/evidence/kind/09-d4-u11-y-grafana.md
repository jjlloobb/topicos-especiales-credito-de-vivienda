# 09 — D4 (día D + 1 UTC): `u11` y Grafana

**Estado: completa, con hallazgos.** Llenada el 2026-11-22 (UTC) con lo que se obtuvo contra `kind-vectra`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F9 (D4 (día D + 1 UTC): `u11` y Grafana).
- Fecha: 2026-11-22 UTC (21:33 del 21 de noviembre en Colombia), día D + 1.
- Operador: jjlloobb, con Claude Code ejecutando las ordenes.
- Commit de `main` desplegado: fd33db6.
- Duración real de la fase: unos 5 min (02:33 a 02:34 UTC), más la búsqueda del tablero (estimada: 15 min, tras la espera; la guía pide anotarla).

Entradas de esta fase: K-62, K-63.

### K-62 — North Star, sostenida, tasa de consulta y ProductMetricsStale con dato…

- Demo: D4. Fuentes: `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:47`, `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:48`, `aidlc-docs/construction/plans/demo-recorte-funcional.md:117`, `tareas/U12-T05-imagen-y-documentacion.md:372`, `tareas/U12-T05-imagen-y-documentacion.md:374`.

**Resultado esperado.** North Star, sostenida, tasa de consulta y ProductMetricsStale con datos reales, dentro del dia D + 1 UTC (la herramienta espera hasta las 02:40 UTC; desde las 00:00 UTC de D + 2 el ayer no tiene decisiones)

**Comando.** Previsto: `vectra-verification u11`; `dashboard.sh`.

```bash
system-verification/demos/verify/dashboard.sh 1
vectra-verification u11
system-verification/demos/verify/dashboard.sh 2; system-verification/demos/verify/dashboard.sh 3; system-verification/demos/verify/dashboard.sh 4
```

**Salida.**

```text
2026-11-22T02:33:49Z
OK: Grafana esta Running
rc1=0
dashboard: pasa
seccion u11: pasa (0)
rc_u11=0
OK: las cuatro series tienen valor
rc2=0
OK: ProductMetricsStale no esta en firing
rc3=0
OK: dashboard pasa
rc4=0
2026-11-22T02:33:56Z
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| North Star, sostenida, tasa de consulta y ProductMetricsStale con datos reales, dentro del dia D + 1 UTC (la herramienta espera hasta las 02:40 UTC; desde las 00:00 UTC de D + 2 el ayer no tiene decisiones) | `u11` y `dashboard` en `pasa` a las 02:33:49 UTC del 2026-11-22 (día D + 1; `decisions` fue el 2026-11-21). Las cuatro series con valor (North Star de ayer, sostenidas, tasa de consulta y días bajo el piso) y `ProductMetricsStale` sin `firing`. Se corrió 7 min antes de las 02:40 UTC: la herramienta solo exige que el día UTC sea posterior al de `decisions`, y las series ya estaban publicadas | si |

### K-63 — Grafana por port-forward con grafana-admin; el dashboard Producto carg…

- Demo: D4. Fuentes: `DECISIONES-LOOP.md:132`, `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:48`, `tareas/U12-T04-demos-cli-y-manifiesto.md:161`, `tareas/U12-T04-demos-cli-y-manifiesto.md:586`, `tareas/U12-T05-imagen-y-documentacion.md:373`, `platform/observability/grafana/external-secrets.yaml:31-36`, `CANDIDATAS.md:82`.

**Resultado esperado.** Grafana por port-forward con grafana-admin; el dashboard Producto carga con sus cuatro paneles. Los permisos por carpeta y rol no se ensenan

**Comando.** Previsto: `kubectl --context kind-vectra port-forward -n vectra-observability`; a mano: el navegador, en el dashboard Producto.

```bash
kubectl --context kind-vectra port-forward -n vectra-observability --address=127.0.0.1 pod/<pod de grafana> 13000:3000
curl -s -K <credencial de grafana-admin> http://127.0.0.1:13000/api/dashboards/uid/vectra-producto-panel
curl -s -K <credencial> 'http://127.0.0.1:13000/api/folders?limit=5000'
```

**Salida.**

```text
GET /api/health -> 200
GET /api/search?type=dash-db -> 5 tableros: Operación, Producto (uid vectra-producto-panel, carpeta «Producto»), Resiliencia, Seguridad, SLO de recomendación
tablero Producto: 16 paneles, entre ellos «North Star de ayer», «Recomendaciones sostenidas (aproximación)», «Tasa de consulta de la explicación y piso F» y «Días bajo el piso»
GET /api/folders?limit=5000 -> 5000 carpetas raíz llamadas «Vectra»; search type=dash-folder -> 5000 «Operación»
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Grafana por port-forward con grafana-admin; el dashboard Producto carga con sus cuatro paneles. Los permisos por carpeta y rol no se ensenan | Grafana responde por `port-forward` con `grafana-admin` y el tablero `Producto` existe con sus 16 paneles (leído por la API). El presentador no lo encontró navegando: Grafana tiene al menos 5000 carpetas «Vectra» y 5000 «Operación» duplicadas (hallazgo H-13); se abre con el enlace directo `/d/vectra-producto-panel/producto`. Que los cuatro paneles pinten datos en el navegador queda por confirmar por el presentador | parcial: tablero y series comprobados por API y por `u11`; la vista en el navegador, sin confirmar |

## Hallazgos

- **H-13 (U1, Grafana; sin resolver).** Grafana tiene al menos 5000 carpetas raíz llamadas «Vectra» y 5000 «Operación» (el máximo que se pidió listar; pueden ser más). El tablero `Producto` queda enterrado y no se encuentra navegando. Causa sin comprobar: algo crea la carpeta en cada corrida en vez de reutilizarla (candidato: el Job de permisos por carpeta). No afecta a `u11` ni a las series. Hay que encontrar la causa y limpiar antes de la sustentación.
- D4 se leyó con la consola de la imagen `sha256:af76cdc0…` (idioma, tema y marca de agua; PR #248), distinta de la que había en D3, D1 y D2. D4 no usa la consola.
- Falta la confirmación visual del presentador de que los cuatro paneles pintan datos.
