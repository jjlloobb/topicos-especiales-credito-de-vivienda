# 02 — Sync y arranque de cada unidad

**Estado: pendiente del operador.** Plantilla de U12-T06: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada _pendiente_ con lo que obtuvo —el comando, la salida **sin tokens, cookies, contraseñas ni semillas** y el cumplimiento— y cambia este estado a `completa` (o `fallida`, con el hallazgo). Quien llena una plantilla no inventa la salida: lo que no se corrió queda `no ejecutado`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F2 (Sync y arranque de cada unidad).
- Fecha: _pendiente_.
- Operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.
- Duración real de la fase: _pendiente_ (estimada: 2 a 3 h; la guía pide anotarla).

Entradas de esta fase: K-10, K-11, K-12, K-13, K-14, K-15, K-16, K-17, K-18, K-19, K-20, K-21, K-22, K-23, K-24, K-25, K-26.

### K-10 — U2 arranca: Envoy con la raiz de solo lectura, las sondas de Valkey co…

- Demo: Base. Fuentes: `CANDIDATAS.md:95`, `CANDIDATAS.md:111`, `CANDIDATAS.md:115`, `identity-edge/docs/paso-16-kind.md:87-100`.

**Resultado esperado.** U2 arranca: Envoy con la raiz de solo lectura, las sondas de Valkey contestan, el Job keycloak-config-cli termina

**Comando.** Previsto: `arranque.sh vectra-edge vectra-identity`; `kubectl --context kind-vectra get job keycloak-config-cli -n vectra-identity`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| U2 arranca: Envoy con la raiz de solo lectura, las sondas de Valkey contestan, el Job keycloak-config-cli termina | _pendiente_ | _pendiente_ |

### K-11 — decision-registry

- Demo: Base. Fuentes: `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md:71`, `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md:72`.

**Resultado esperado.** decision-registry: Application Synced y Healthy; /readyz responde 200

**Comando.** Previsto: `kubectl --context kind-vectra get applications.argoproj.io decision-registry -n argocd`; `arranque.sh vectra-app`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| decision-registry: Application Synced y Healthy; /readyz responde 200 | _pendiente_ | _pendiente_ |

### K-12 — ESO materializa las llaves de cada unidad (scoring, explainability, ca…

- Demo: Base. Fuentes: `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md:44`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:73`, `aidlc-docs/construction/bias-monitoring/evidence/cierre-demo.md:40`, `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:51`, `tareas/U12-T05-imagen-y-documentacion.md:370`.

**Resultado esperado.** ESO materializa las llaves de cada unidad (scoring, explainability, case-service, case-worker, las dos de bias, product-metrics) y existen los cuatro pg-role-case-*

**Comando.** Previsto: `kubectl --context kind-vectra get externalsecret -n vectra-app`; `arranque.sh vectra-app`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| ESO materializa las llaves de cada unidad (scoring, explainability, case-service, case-worker, las dos de bias, product-metrics) y existen los cuatro pg-role-case-* | _pendiente_ | _pendiente_ |

### K-13 — Ningun contenedor sale con codigo 0 y sin mensaje (falta una variable …

- Demo: Base. Fuentes: `CANDIDATAS.md:616`, `CANDIDATAS.md:624`, `revisiones/U08-T05/ronda-1.md:66`.

**Resultado esperado.** Ningun contenedor sale con codigo 0 y sin mensaje (falta una variable o la llave private_key_jwt)

**Comando.** Previsto: `arranque.sh vectra-app`; `kubectl --context kind-vectra logs --previous -n vectra-app`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Ningun contenedor sale con codigo 0 y sin mensaje (falta una variable o la llave private_key_jwt) | _pendiente_ | _pendiente_ |

### K-14 — U8: el hook de migracion corre antes de que los Deployment queden Read…

- Demo: Base. Fuentes: `aidlc-docs/construction/case-management/evidence/cierre-demo.md:74`, `CANDIDATAS.md:625`, `CANDIDATAS.md:236`.

**Resultado esperado.** U8: el hook de migracion corre antes de que los Deployment queden Ready; sslmode=verify-full conecta de verdad con case-db

**Comando.** Previsto: `kubectl --context kind-vectra get jobs -n vectra-app`; `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=case-service`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| U8: el hook de migracion corre antes de que los Deployment queden Ready; sslmode=verify-full conecta de verdad con case-db | _pendiente_ | _pendiente_ |

### K-15 — U7 arranca con la raiz de solo lectura y sin emptyDir; los hosts <isvc…

- Demo: Base. Fuentes: `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md:43`, `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md:45`, `CANDIDATAS.md:520`.

**Resultado esperado.** U7 arranca con la raiz de solo lectura y sin emptyDir; los hosts <isvc>-predictor.vectra-serving y -explainer resuelven desde vectra-app

**Comando.** Previsto: `arranque.sh vectra-app`; `humo flujo --delivery /verification/reference-model/.out`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| U7 arranca con la raiz de solo lectura y sin emptyDir; los hosts <isvc>-predictor.vectra-serving y -explainer resuelven desde vectra-app | _pendiente_ | _pendiente_ |

### K-16 — vectra-internal-ca existe en vectra-app y el JWKS responde por https

- Demo: Base. Fuentes: `aidlc-docs/construction/console/evidence/cierre-demo.md:72`.

**Resultado esperado.** vectra-internal-ca existe en vectra-app y el JWKS responde por https

**Comando.** Previsto: `kubectl --context kind-vectra get configmap vectra-internal-ca -n vectra-app`; `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=console-bff`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| vectra-internal-ca existe en vectra-app y el JWKS responde por https | _pendiente_ | _pendiente_ |

### K-17 — El eco de U2 y la ServiceAccount temporal console-bff de U4 no existen…

- Demo: Base. Fuentes: `aidlc-docs/construction/console/evidence/cierre-demo.md:71`, `CANDIDATAS.md:402`, `CANDIDATAS.md:412`, `CANDIDATAS.md:259`, `tareas/U12-T05-imagen-y-documentacion.md:361`.

**Resultado esperado.** El eco de U2 y la ServiceAccount temporal console-bff de U4 no existen antes del sync de U10

**Comando.** Previsto: `kubectl --context kind-vectra get deploy,sa -n vectra-app`; `kubectl --context kind-vectra get sa console-bff -n vectra-app`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| El eco de U2 y la ServiceAccount temporal console-bff de U4 no existen antes del sync de U10 | _pendiente_ | _pendiente_ |

### K-18 — product-metrics arranca despues del registro; si no, 503 hasta 30 min …

- Demo: D4. Fuentes: `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:54`, `CANDIDATAS.md:598`.

**Resultado esperado.** product-metrics arranca despues del registro; si no, 503 hasta 30 min y dashboard vacio

**Comando.** Previsto: `kubectl --context kind-vectra get pods -l app.kubernetes.io/name=product-metrics -n vectra-app`; `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=product-metrics`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| product-metrics arranca despues del registro; si no, 503 hasta 30 min y dashboard vacio | _pendiente_ | _pendiente_ |

### K-19 — Prometheus carga las PrometheusRule de U8 y U11 y raspa los ServiceMon…

- Demo: D1, D3, D4. Fuentes: `aidlc-docs/construction/case-management/evidence/cierre-demo.md:75`, `aidlc-docs/construction/console/evidence/cierre-demo.md:73`, `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:52`, `tareas/U12-T05-imagen-y-documentacion.md:372`.

**Resultado esperado.** Prometheus carga las PrometheusRule de U8 y U11 y raspa los ServiceMonitor de U8 (tres), del BFF y de U11; Grafana descubre el ConfigMap del dashboard en Vectra / Producto

**Comando.** Previsto: `observabilidad.sh reglas`; `observabilidad.sh targets`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Prometheus carga las PrometheusRule de U8 y U11 y raspa los ServiceMonitor de U8 (tres), del BFF y de U11; Grafana descubre el ConfigMap del dashboard en Vectra / Producto | _pendiente_ | _pendiente_ |

### K-20 — Selectores y puertos de partida

- Demo: Base. Fuentes: `CANDIDATAS.md:671`, `tareas/U12-T04-demos-cli-y-manifiesto.md:141`, `tareas/U12-T05-imagen-y-documentacion.md:367`.

**Resultado esperado.** Selectores y puertos de partida: Prometheus (app.kubernetes.io/name=prometheus, 9090) y el registro (decision-registry-service, 8080)

**Comando.** Previsto: `kubectl --context kind-vectra get pods -l app.kubernetes.io/name=prometheus -n vectra-observability`; `kubectl --context kind-vectra get pods -l app.kubernetes.io/name=decision-registry-service -n vectra-app`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Selectores y puertos de partida: Prometheus (app.kubernetes.io/name=prometheus, 9090) y el registro (decision-registry-service, 8080) | _pendiente_ | _pendiente_ |

### K-21 — Proxy de Linkerd en vectra-mock

- Demo: D3. Fuentes: `aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md:28`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:69`, `DECISIONES-LOOP.md:118`, `tareas/U12-T05-imagen-y-documentacion.md:369`.

**Resultado esperado.** Proxy de Linkerd en vectra-mock: el target linkerd-proxy en up == 1 (no 403) y los pods Ready con el Server del 4191 (las sondas /live y /ready pasan)

**Comando.** Previsto: `observabilidad.sh consulta up{namespace="vectra-mock"}`; `kubectl --context kind-vectra get pods -n vectra-mock`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Proxy de Linkerd en vectra-mock: el target linkerd-proxy en up == 1 (no 403) y los pods Ready con el Server del 4191 (las sondas /live y /ready pasan) | _pendiente_ | _pendiente_ |

### K-22 — Politica activa y modelo de referencia activo

- Demo: Base. Fuentes: `aidlc-docs/construction/governance/evidence/cierre-demo.md:27`, `aidlc-docs/construction/governance/evidence/cierre-demo.md:28`, `aidlc-docs/construction/plans/demo-recorte-funcional.md:43-51`, `aidlc-docs/construction/plans/demo-recorte-funcional.md:401`, `tareas/U12-T05-imagen-y-documentacion.md:362`.

**Resultado esperado.** Politica activa y modelo de referencia activo: serving-config trae policy_version_id y la version

**Comando.** Previsto: `humo flujo --delivery /verification/reference-model/.out`; a mano: plantillas 03 y 04 de U4 (governance/evidence/kind).

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Politica activa y modelo de referencia activo: serving-config trae policy_version_id y la version | _pendiente_ | _pendiente_ |

### K-23 — Con 256 MiB por pod bastan el predictor y el explicador del modelo de …

- Demo: Base. Fuentes: `DECISIONES-LOOP.md:82-84`, `aidlc-docs/construction/model-serving/evidence/cierre-demo.md:34`.

**Resultado esperado.** Con 256 MiB por pod bastan el predictor y el explicador del modelo de referencia (sin OOMKilled)

**Comando.** Previsto: `arranque.sh vectra-serving`; `memoria.sh antes`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Con 256 MiB por pod bastan el predictor y el explicador del modelo de referencia (sin OOMKilled) | _pendiente_ | _pendiente_ |

### K-24 — Paquetes proxy y RT-3 (a, b, c y d) en el model-store, para D1 y D2

- Demo: D1, D2. Fuentes: `model-serving/docs/paso-11-kind.md:42-58`, `tareas/U12-T05-imagen-y-documentacion.md:362`.

**Resultado esperado.** Paquetes proxy y RT-3 (a, b, c y d) en el model-store, para D1 y D2

**Comando.** Previsto: a mano: la salida de mc ls de model-serving/docs/paso-11-kind.md, seccion 2, con RT3-a, RT3-c y RT3-d (rt3 exige los tres); `arranque.sh vectra-data`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Paquetes proxy y RT-3 (a, b, c y d) en el model-store, para D1 y D2 | _pendiente_ | _pendiente_ |

### K-25 — Watchdog recibido, no solo disparado

- Demo: ninguna. Fuentes: `aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md:27`, `tareas/U12-T05-imagen-y-documentacion.md:369`.

**Resultado esperado.** Watchdog recibido, no solo disparado

**Comando.** Previsto: `observabilidad.sh consulta ALERTS{alertname="Watchdog"}`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Watchdog recibido, no solo disparado | _pendiente_ | _pendiente_ |

### K-26 — Flujos negados (suite X01 a X10, casos bloqueados de INF-U10-04, X04)

- Demo: ninguna. Fuentes: `aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md:23`, `aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md:25`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:70`, `aidlc-docs/construction/bias-monitoring/evidence/cierre-demo.md:36`, `aidlc-docs/construction/console/evidence/cierre-demo.md:68`, `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:49`.

**Resultado esperado.** Flujos negados (suite X01 a X10, casos bloqueados de INF-U10-04, X04): no se comprueban porque network y el Paso 9 estan diferidos; los permitidos se ven por el flujo base y las demos

**Comando.** Previsto: `humo flujo --delivery /verification/reference-model/.out`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Flujos negados (suite X01 a X10, casos bloqueados de INF-U10-04, X04): no se comprueban porque network y el Paso 9 estan diferidos; los permitidos se ven por el flujo base y las demos | _pendiente_ | _pendiente_ |

## Hallazgos

_Ninguno todavía._ Cada hallazgo dice **a qué unidad apunta** (la tabla de síntomas de la guía da la primera pista) y abre una tarea en esa unidad; un defecto del chart o de las imágenes de una unidad no se arregla aquí.
