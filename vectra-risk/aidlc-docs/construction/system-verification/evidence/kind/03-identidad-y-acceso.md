# 03 — Identidad y acceso

**Estado: pendiente del operador.** Plantilla de U12-T06: nadie ha ejecutado esto contra el clúster (AUTONOMIA-01). El operador reemplaza cada _pendiente_ con lo que obtuvo —el comando, la salida **sin tokens, cookies, contraseñas ni semillas** y el cumplimiento— y cambia este estado a `completa` (o `fallida`, con el hallazgo). Quien llena una plantilla no inventa la salida: lo que no se corrió queda `no ejecutado`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F3 (Identidad y acceso).
- Fecha: _pendiente_.
- Operador: _pendiente_.
- Commit de `main` desplegado: _pendiente_.
- Duración real de la fase: _pendiente_ (estimada: 40 min; la guía pide anotarla).

Entradas de esta fase: K-27, K-28, K-29, K-30, K-31, K-32, K-33, K-34, K-35, K-36, K-37.

### K-27 — Si el kind tiene el realm viejo

- Demo: Base. Fuentes: `identity-edge/docs/realm-importacion.md:23-29`, `CANDIDATAS.md:712`, `CANDIDATAS.md:715`, `revisiones/U02-T22/ronda-1.md:50`, `revisiones/U02-T22/ronda-1.md:68`, `tareas/U12-T05-imagen-y-documentacion.md:358`.

**Resultado esperado.** Si el kind tiene el realm viejo: tras resincronizar U2 quedan 26 de 26 ejecuciones enlazadas; config-cli avisa que no reaplica contrasenas y anade una segunda credencial OTP con la misma semilla

**Comando.** Previsto: `identidad.sh`; `humo login`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Si el kind tiene el realm viejo: tras resincronizar U2 quedan 26 de 26 ejecuciones enlazadas; config-cli avisa que no reaplica contrasenas y anade una segunda credencial OTP con la misma semilla | _pendiente_ | _pendiente_ |

### K-28 — Bloqueos por fuerza bruta

- Demo: Base. Fuentes: `DECISIONES-LOOP.md:122`, `DECISIONES-LOOP.md:128`, `CANDIDATAS.md:715`, `identity-edge/docs/realm-importacion.md:29`.

**Resultado esperado.** Bloqueos por fuerza bruta: el login fallido por el error interno del realm viejo no cuenta (numFailures 0); si cuentan las contrasenas mal tecleadas (60 s al quinto fallo, permanente al 20)

**Comando.** Previsto: `humo login`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Bloqueos por fuerza bruta: el login fallido por el error interno del realm viejo no cuenta (numFailures 0); si cuentan las contrasenas mal tecleadas (60 s al quinto fallo, permanente al 20) | _pendiente_ | _pendiente_ |

### K-29 — Login por rol por el gateway real, con el emisor publico

- Demo: Base. Fuentes: `aidlc-docs/construction/console/evidence/cierre-demo.md:65`, `CANDIDATAS.md:42`, `CANDIDATAS.md:44`, `CANDIDATAS.md:48`, `DECISIONES-LOOP.md:110`, `tareas/U12-T05-imagen-y-documentacion.md:367`, `tareas/U12-T05-imagen-y-documentacion.md:373`.

**Resultado esperado.** Login por rol por el gateway real, con el emisor publico: analista-1, analista-2, ingeniero-1, cro-1 y cumplimiento-1; cada token con acr = mfa, amr, aud con console-bff y su rol

**Comando.** Previsto: `humo login`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Login por rol por el gateway real, con el emisor publico: analista-1, analista-2, ingeniero-1, cro-1 y cumplimiento-1; cada token con acr = mfa, amr, aud con console-bff y su rol | _pendiente_ | _pendiente_ |

### K-30 — El iss de los tokens del navegador es el que valida el BFF y cada dest…

- Demo: Base. Fuentes: `aidlc-docs/construction/console/evidence/cierre-demo.md:69`, `CANDIDATAS.md:692`, `CANDIDATAS.md:702`, `identity-edge/docs/emisor-de-tokens.md:64-66`.

**Resultado esperado.** El iss de los tokens del navegador es el que valida el BFF y cada destino (F10 a F14): 200 en bandeja, detalle, modelos y congelamientos, ningun 401

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
| El iss de los tokens del navegador es el que valida el BFF y cada destino (F10 a F14): 200 en bandeja, detalle, modelos y congelamientos, ningun 401 | _pendiente_ | _pendiente_ |

### K-31 — La aud de la asercion de servicio la acepta el Keycloak del cluster (n…

- Demo: Base. Fuentes: `identity-edge/docs/emisor-de-tokens.md:81`, `CANDIDATAS.md:65`, `CANDIDATAS.md:703`, `tareas/U12-T05-imagen-y-documentacion.md:359`.

**Resultado esperado.** La aud de la asercion de servicio la acepta el Keycloak del cluster (nunca medido en kind con el realm real)

**Comando.** Previsto: `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=case-worker`; `humo flujo --delivery /verification/reference-model/.out`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| La aud de la asercion de servicio la acepta el Keycloak del cluster (nunca medido en kind con el realm real) | _pendiente_ | _pendiente_ |

### K-32 — Camino a la boveda desde la estacion (no lo da K16)

- Demo: Base. Fuentes: `CANDIDATAS.md:640`, `CANDIDATAS.md:647`, `CANDIDATAS.md:673`, `CANDIDATAS.md:678`, `tareas/U12-T05-imagen-y-documentacion.md:365`.

**Resultado esperado.** Camino a la boveda desde la estacion (no lo da K16): lectura de las 5 credenciales y las 2 llaves; el token root de kind no rompe el filtro de evidencias

**Comando.** Previsto: `humo login`; `vectra-verification prepare`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Camino a la boveda desde la estacion (no lo da K16): lectura de las 5 credenciales y las 2 llaves; el token root de kind no rompe el filtro de evidencias | _pendiente_ | _pendiente_ |

### K-33 — Credenciales de los usuarios -2 (analista-2 o cro-2 en D1; cumplimient…

- Demo: D1, D2. Fuentes: `tareas/U12-T05-imagen-y-documentacion.md:365`, `tareas/U12-T05-imagen-y-documentacion.md:374`, `tareas/U12-T04-demos-cli-y-manifiesto.md:585`, `identity-edge/docs/paso-16-kind.md:67`, `identity-edge/docs/paso-16-kind.md:75`.

**Resultado esperado.** Credenciales de los usuarios -2 (analista-2 o cro-2 en D1; cumplimiento-2 en D2) en la boveda, y sus semillas TOTP en el telefono del presentador

**Comando.** Previsto: `identidad.sh`; a mano: login manual de cumplimiento-2 en la consola.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Credenciales de los usuarios -2 (analista-2 o cro-2 en D1; cumplimiento-2 en D2) en la boveda, y sus semillas TOTP en el telefono del presentador | _pendiente_ | _pendiente_ |

### K-34 — K16 de verdad

- Demo: D1, D2, D3. Fuentes: `tareas/U12-T05-imagen-y-documentacion.md:366`, `tareas/U12-T04-demos-cli-y-manifiesto.md:127-135`, `platform/rbac/verification-operator/k16.yaml:1-20`.

**Resultado esperado.** K16 de verdad: lo que cada verify lee lo permite el grupo vectra-verification-operators; que pasa en vectra-staging y vectra-mock (K16 no da nada)

**Comando.** Previsto: `identidad.sh`.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| K16 de verdad: lo que cada verify lee lo permite el grupo vectra-verification-operators; que pasa en vectra-staging y vectra-mock (K16 no da nada) | _pendiente_ | _pendiente_ |

### K-35 — Consola en el navegador por el gateway real

- Demo: Base. Fuentes: `aidlc-docs/construction/console/evidence/cierre-demo.md:65`, `aidlc-docs/construction/console/evidence/cierre-demo.md:66`, `aidlc-docs/construction/console/evidence/cierre-demo.md:73`, `CANDIDATAS.md:631`, `CANDIDATAS.md:659`, `tareas/U12-T05-imagen-y-documentacion.md:371`.

**Resultado esperado.** Consola en el navegador por el gateway real: redireccion, /callback, recarga con prompt=none; cero securitypolicyviolation con la CSP real; la cookie vectra-spa-route llega a los pods

**Comando.** Previsto: `humo consola`; a mano: la consola del navegador del presentador.

```bash
_pendiente: el comando exacto que se ejecutó_
```

**Salida.**

```text
_pendiente: la salida real, sin tokens_
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Consola en el navegador por el gateway real: redireccion, /callback, recarga con prompt=none; cero securitypolicyviolation con la CSP real; la cookie vectra-spa-route llega a los pods | _pendiente_ | _pendiente_ |

### K-36 — CASE_ALLOW_TEST_SCENARIOS activo en kind (la cabecera de escenario de …

- Demo: Base. Fuentes: `vectra-risk-gitops/values/kind/case-management.yaml:3`, `tareas/U12-T05-imagen-y-documentacion.md:368`.

**Resultado esperado.** CASE_ALLOW_TEST_SCENARIOS activo en kind (la cabecera de escenario de U12 se acepta)

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
| CASE_ALLOW_TEST_SCENARIOS activo en kind (la cabecera de escenario de U12 se acepta) | _pendiente_ | _pendiente_ |

### K-37 — Limites del gateway con el volumen real

- Demo: D2, D4. Fuentes: `identity-edge/gateway/routes.yaml:87-107`, `tareas/U12-T05-imagen-y-documentacion.md:368`.

**Resultado esperado.** Limites del gateway con el volumen real: 30/s para el simulador, 20/s por usuario en /api/console, 600/min en auth-login y auth-token (cero 429)

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
| Limites del gateway con el volumen real: 30/s para el simulador, 20/s por usuario en /api/console, 600/min en auth-login y auth-token (cero 429) | _pendiente_ | _pendiente_ |

## Hallazgos

_Ninguno todavía._ Cada hallazgo dice **a qué unidad apunta** (la tabla de síntomas de la guía da la primera pista) y abre una tarea en esa unidad; un defecto del chart o de las imágenes de una unidad no se arregla aquí.
