# 03 — Identidad y acceso

**Estado: completa.** Llenada el 2026-11-20 con lo que se obtuvo contra `kind-vectra`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F3 (Identidad y acceso).
- Fecha: 2026-11-20 (jornada 1), entre las 12:27 y las 13:00 UTC.
- Operador: jjlloobb, con Claude Code ejecutando las ordenes.
- Commit de `main` desplegado: 9dc027f.
- Duración real de la fase: unos 10 min (sin la parte a mano) (estimada: 40 min; la guía pide anotarla).

Entradas de esta fase: K-27, K-28, K-29, K-30, K-31, K-32, K-33, K-34, K-35, K-36, K-37.

### K-27 — Si el kind tiene el realm viejo

- Demo: Base. Fuentes: `identity-edge/docs/realm-importacion.md:23-29`, `CANDIDATAS.md:712`, `CANDIDATAS.md:715`, `revisiones/U02-T22/ronda-1.md:50`, `revisiones/U02-T22/ronda-1.md:68`, `tareas/U12-T05-imagen-y-documentacion.md:358`.

**Resultado esperado.** Si el kind tiene el realm viejo: tras resincronizar U2 quedan 26 de 26 ejecuciones enlazadas; config-cli avisa que no reaplica contrasenas y anade una segunda credencial OTP con la misma semilla

**Comando.** Previsto: `identidad.sh`; `humo login`.

```bash
system-verification/docs/kind/identidad.sh
```

**Salida.**

```text
OK   K16 get pods en vectra-app: yes
OK   K16 get pods en vectra-edge: yes
OK   K16 get pods en vectra-serving: yes
OK   K16 get pods en vectra-identity: yes
OK   K16 get pods en vectra-data: yes
OK   K16 get pods en vectra-observability: yes
OK   K16 get jobs en vectra-app: yes
OK   K16 get pods/log en vectra-app: yes
OK   K16 create pods/portforward en vectra-app: yes
OK   K16 create pods/portforward en vectra-observability: yes
OK   K16 get inferenceservices.serving.kserve.io en vectra-serving: yes
OK   K16 get pods en vectra-mock: no
OK   K16 get pods en vectra-staging: no
OK   K16 get pods/log en vectra-staging: no
OK   K16 get secrets en vectra-app: no
OK   K16 get networkpolicies en vectra-serving: no
OK   Job keycloak-config-cli terminado
AVISO el log trae 'Password policy violation ... NOT updated': esperado, config-cli no reaplica contrasenas (K-27)
OK   el log de config-cli sin lineas ERROR
identity/synthetic-users: 20 claves (solo nombres)
identidad: sin hallazgos
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Si el kind tiene el realm viejo: tras resincronizar U2 quedan 26 de 26 ejecuciones enlazadas; config-cli avisa que no reaplica contrasenas y anade una segunda credencial OTP con la misma semilla | el kind no tiene el realm viejo (los cinco logins pasan): no hizo falta resincronizar; el log de config-cli trae el aviso esperado de contrasenas | si (las 26 ejecuciones enlazadas no se contaron) |

### K-28 — Bloqueos por fuerza bruta

- Demo: Base. Fuentes: `DECISIONES-LOOP.md:122`, `DECISIONES-LOOP.md:128`, `CANDIDATAS.md:715`, `identity-edge/docs/realm-importacion.md:29`.

**Resultado esperado.** Bloqueos por fuerza bruta: el login fallido por el error interno del realm viejo no cuenta (numFailures 0); si cuentan las contrasenas mal tecleadas (60 s al quinto fallo, permanente al 20)

**Comando.** Previsto: `humo login`.

```bash
no ejecutado
```

**Salida.**

```text
no ejecutado
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Bloqueos por fuerza bruta: el login fallido por el error interno del realm viejo no cuenta (numFailures 0); si cuentan las contrasenas mal tecleadas (60 s al quinto fallo, permanente al 20) | no ejecutado: no hubo realm viejo ni logins fallidos que medir | no ejecutado |

### K-29 — Login por rol por el gateway real, con el emisor publico

- Demo: Base. Fuentes: `aidlc-docs/construction/console/evidence/cierre-demo.md:65`, `CANDIDATAS.md:42`, `CANDIDATAS.md:44`, `CANDIDATAS.md:48`, `DECISIONES-LOOP.md:110`, `tareas/U12-T05-imagen-y-documentacion.md:367`, `tareas/U12-T05-imagen-y-documentacion.md:373`.

**Resultado esperado.** Login por rol por el gateway real, con el emisor publico: analista-1, analista-2, ingeniero-1, cro-1 y cumplimiento-1; cada token con acr = mfa, amr, aud con console-bff y su rol

**Comando.** Previsto: `humo login`.

```bash
humo login
```

**Salida.**

```text
OK    analista-1: iss=https://vectra.localtest.me/auth/realms/vectra aud=['bias-monitoring-service', 'governance-service', 'console-bff', 'case-service', 'explainability-service', 'decision-registry-service'] acr=mfa amr=['pwd', 'otp'] roles=['analista'] auth_time=2026-11-20T12:30:23+00:00
OK    analista-2: iss=https://vectra.localtest.me/auth/realms/vectra aud=['bias-monitoring-service', 'governance-service', 'console-bff', 'case-service', 'explainability-service', 'decision-registry-service'] acr=mfa amr=['pwd', 'otp'] roles=['analista'] auth_time=2026-11-20T12:30:23+00:00
OK    ingeniero-1: iss=https://vectra.localtest.me/auth/realms/vectra aud=['bias-monitoring-service', 'governance-service', 'console-bff', 'case-service', 'explainability-service', 'decision-registry-service'] acr=mfa amr=['pwd', 'otp'] roles=['ingeniero_riesgo'] auth_time=2026-11-20T12:30:24+00:00
OK    cro-1: iss=https://vectra.localtest.me/auth/realms/vectra aud=['bias-monitoring-service', 'governance-service', 'console-bff', 'case-service', 'explainability-service', 'decision-registry-service'] acr=mfa amr=['pwd', 'otp'] roles=['cro'] auth_time=2026-11-20T12:30:25+00:00
OK    cumplimiento-1: iss=https://vectra.localtest.me/auth/realms/vectra aud=['bias-monitoring-service', 'governance-service', 'console-bff', 'case-service', 'explainability-service', 'decision-registry-service'] acr=mfa amr=['pwd', 'otp'] roles=['cumplimiento'] auth_time=2026-11-20T12:30:25+00:00
login: 5 de 5 usuarios bien; espera 30 s antes de repetir un comando con los mismos usuarios (reuso del TOTP)
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Login por rol por el gateway real, con el emisor publico: analista-1, analista-2, ingeniero-1, cro-1 y cumplimiento-1; cada token con acr = mfa, amr, aud con console-bff y su rol | 5 de 5 usuarios con el emisor publico, acr=mfa, amr pwd y otp, aud con console-bff y su rol | si |

### K-30 — El iss de los tokens del navegador es el que valida el BFF y cada dest…

- Demo: Base. Fuentes: `aidlc-docs/construction/console/evidence/cierre-demo.md:69`, `CANDIDATAS.md:692`, `CANDIDATAS.md:702`, `identity-edge/docs/emisor-de-tokens.md:64-66`.

**Resultado esperado.** El iss de los tokens del navegador es el que valida el BFF y cada destino (F10 a F14): 200 en bandeja, detalle, modelos y congelamientos, ningun 401

**Comando.** Previsto: `humo flujo --delivery /verification/reference-model/.out`.

```bash
humo flujo --delivery /verification/reference-model/.out
```

**Salida.**

```text
solicitud aceptada: caso 6a33a846-04bf-4f4e-b919-69bfa73d2390 (la cabecera de escenario se acepto: K-36)
OK   caso listo con registry_entry_id 30
OK   decision registrada con ack: registry_entry_id 32
OK   /api/console/models con ingeniero-1: 1 versiones
OK   /api/console/freezes con cumplimiento-1
estado HTTP de cada llamada:
  200 GET /api/console/cases/{id} x2
  200 GET /api/console/freezes
  200 GET /api/console/models
  200 POST /api/console/cases/{id}/decision
  204 POST /api/console/cases/{id}/explanation-views
  200 POST /api/intake/v1/intake/applications
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| El iss de los tokens del navegador es el que valida el BFF y cada destino (F10 a F14): 200 en bandeja, detalle, modelos y congelamientos, ningun 401 | 200 en casos, detalle, modelos y congelamientos; ningun 401 | si |

### K-31 — La aud de la asercion de servicio la acepta el Keycloak del cluster (n…

- Demo: Base. Fuentes: `identity-edge/docs/emisor-de-tokens.md:81`, `CANDIDATAS.md:65`, `CANDIDATAS.md:703`, `tareas/U12-T05-imagen-y-documentacion.md:359`.

**Resultado esperado.** La aud de la asercion de servicio la acepta el Keycloak del cluster (nunca medido en kind con el realm real)

**Comando.** Previsto: `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=case-worker`; `humo flujo --delivery /verification/reference-model/.out`.

```bash
kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=case-worker --all-containers --since=20m --tail=2000 | grep -c invalid_client
```

**Salida.**

```text
0
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| La aud de la asercion de servicio la acepta el Keycloak del cluster (nunca medido en kind con el realm real) | 0 lineas invalid_client en case-worker en los ultimos 20 min, y el caso llego a listo | si |

### K-32 — Camino a la boveda desde la estacion (no lo da K16)

- Demo: Base. Fuentes: `CANDIDATAS.md:640`, `CANDIDATAS.md:647`, `CANDIDATAS.md:673`, `CANDIDATAS.md:678`, `tareas/U12-T05-imagen-y-documentacion.md:365`.

**Resultado esperado.** Camino a la boveda desde la estacion (no lo da K16): lectura de las 5 credenciales y las 2 llaves; el token root de kind no rompe el filtro de evidencias

**Comando.** Previsto: `humo login`; `vectra-verification prepare`.

```bash
humo login
```

**Salida.**

```text
OK    analista-1: iss=https://vectra.localtest.me/auth/realms/vectra aud=['bias-monitoring-service', 'governance-service', 'console-bff', 'case-service', 'explainability-service', 'decision-registry-service'] acr=mfa amr=['pwd', 'otp'] roles=['analista'] auth_time=2026-11-20T12:30:23+00:00
OK    analista-2: iss=https://vectra.localtest.me/auth/realms/vectra aud=['bias-monitoring-service', 'governance-service', 'console-bff', 'case-service', 'explainability-service', 'decision-registry-service'] acr=mfa amr=['pwd', 'otp'] roles=['analista'] auth_time=2026-11-20T12:30:23+00:00
OK    ingeniero-1: iss=https://vectra.localtest.me/auth/realms/vectra aud=['bias-monitoring-service', 'governance-service', 'console-bff', 'case-service', 'explainability-service', 'decision-registry-service'] acr=mfa amr=['pwd', 'otp'] roles=['ingeniero_riesgo'] auth_time=2026-11-20T12:30:24+00:00
OK    cro-1: iss=https://vectra.localtest.me/auth/realms/vectra aud=['bias-monitoring-service', 'governance-service', 'console-bff', 'case-service', 'explainability-service', 'decision-registry-service'] acr=mfa amr=['pwd', 'otp'] roles=['cro'] auth_time=2026-11-20T12:30:25+00:00
OK    cumplimiento-1: iss=https://vectra.localtest.me/auth/realms/vectra aud=['bias-monitoring-service', 'governance-service', 'console-bff', 'case-service', 'explainability-service', 'decision-registry-service'] acr=mfa amr=['pwd', 'otp'] roles=['cumplimiento'] auth_time=2026-11-20T12:30:25+00:00
login: 5 de 5 usuarios bien; espera 30 s antes de repetir un comando con los mismos usuarios (reuso del TOTP)
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Camino a la boveda desde la estacion (no lo da K16): lectura de las 5 credenciales y las 2 llaves; el token root de kind no rompe el filtro de evidencias | `humo login` leyo de la boveda, por el port-forward, las credenciales de los cinco usuarios; la salida no trae tokens | parcial: las 2 llaves y el filtro de evidencias se comprueban con `prepare` en F5 |

### K-33 — Credenciales de los usuarios -2 (analista-2 o cro-2 en D1; cumplimient…

- Demo: D1, D2. Fuentes: `tareas/U12-T05-imagen-y-documentacion.md:365`, `tareas/U12-T05-imagen-y-documentacion.md:374`, `tareas/U12-T04-demos-cli-y-manifiesto.md:585`, `identity-edge/docs/paso-16-kind.md:67`, `identity-edge/docs/paso-16-kind.md:75`.

**Resultado esperado.** Credenciales de los usuarios -2 (analista-2 o cro-2 en D1; cumplimiento-2 en D2) en la boveda, y sus semillas TOTP en el telefono del presentador

**Comando.** Previsto: `identidad.sh`; a mano: login manual de cumplimiento-2 en la consola.

```bash
system-verification/docs/kind/identidad.sh
```

**Salida.**

```text
OK   K16 get pods en vectra-app: yes
OK   K16 get pods en vectra-edge: yes
OK   K16 get pods en vectra-serving: yes
OK   K16 get pods en vectra-identity: yes
OK   K16 get pods en vectra-data: yes
OK   K16 get pods en vectra-observability: yes
OK   K16 get jobs en vectra-app: yes
OK   K16 get pods/log en vectra-app: yes
OK   K16 create pods/portforward en vectra-app: yes
OK   K16 create pods/portforward en vectra-observability: yes
OK   K16 get inferenceservices.serving.kserve.io en vectra-serving: yes
OK   K16 get pods en vectra-mock: no
OK   K16 get pods en vectra-staging: no
OK   K16 get pods/log en vectra-staging: no
OK   K16 get secrets en vectra-app: no
OK   K16 get networkpolicies en vectra-serving: no
OK   Job keycloak-config-cli terminado
AVISO el log trae 'Password policy violation ... NOT updated': esperado, config-cli no reaplica contrasenas (K-27)
OK   el log de config-cli sin lineas ERROR
identity/synthetic-users: 20 claves (solo nombres)
identidad: sin hallazgos
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Credenciales de los usuarios -2 (analista-2 o cro-2 en D1; cumplimiento-2 en D2) en la boveda, y sus semillas TOTP en el telefono del presentador | identity/synthetic-users tiene 20 claves, con las de los usuarios -2; el login manual de cumplimiento-2 y de ingeniero-2 y las semillas en el telefono quedan para el presentador | parcial: la parte a mano esta pendiente |

### K-34 — K16 de verdad

- Demo: D1, D2, D3. Fuentes: `tareas/U12-T05-imagen-y-documentacion.md:366`, `tareas/U12-T04-demos-cli-y-manifiesto.md:127-135`, `platform/rbac/verification-operator/k16.yaml:1-20`.

**Resultado esperado.** K16 de verdad: lo que cada verify lee lo permite el grupo vectra-verification-operators; que pasa en vectra-staging y vectra-mock (K16 no da nada)

**Comando.** Previsto: `identidad.sh`.

```bash
system-verification/docs/kind/identidad.sh
```

**Salida.**

```text
OK   K16 get pods en vectra-app: yes
OK   K16 get pods en vectra-edge: yes
OK   K16 get pods en vectra-serving: yes
OK   K16 get pods en vectra-identity: yes
OK   K16 get pods en vectra-data: yes
OK   K16 get pods en vectra-observability: yes
OK   K16 get jobs en vectra-app: yes
OK   K16 get pods/log en vectra-app: yes
OK   K16 create pods/portforward en vectra-app: yes
OK   K16 create pods/portforward en vectra-observability: yes
OK   K16 get inferenceservices.serving.kserve.io en vectra-serving: yes
OK   K16 get pods en vectra-mock: no
OK   K16 get pods en vectra-staging: no
OK   K16 get pods/log en vectra-staging: no
OK   K16 get secrets en vectra-app: no
OK   K16 get networkpolicies en vectra-serving: no
OK   Job keycloak-config-cli terminado
AVISO el log trae 'Password policy violation ... NOT updated': esperado, config-cli no reaplica contrasenas (K-27)
OK   el log de config-cli sin lineas ERROR
identity/synthetic-users: 20 claves (solo nombres)
identidad: sin hallazgos
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| K16 de verdad: lo que cada verify lee lo permite el grupo vectra-verification-operators; que pasa en vectra-staging y vectra-mock (K16 no da nada) | `identidad.sh` sale 0: lo que lee cada verify da yes; vectra-mock y vectra-staging dan no | si |

### K-35 — Consola en el navegador por el gateway real

- Demo: Base. Fuentes: `aidlc-docs/construction/console/evidence/cierre-demo.md:65`, `aidlc-docs/construction/console/evidence/cierre-demo.md:66`, `aidlc-docs/construction/console/evidence/cierre-demo.md:73`, `CANDIDATAS.md:631`, `CANDIDATAS.md:659`, `tareas/U12-T05-imagen-y-documentacion.md:371`.

**Resultado esperado.** Consola en el navegador por el gateway real: redireccion, /callback, recarga con prompt=none; cero securitypolicyviolation con la CSP real; la cookie vectra-spa-route llega a los pods

**Comando.** Previsto: `humo consola`; a mano: la consola del navegador del presentador.

```bash
humo consola
```

**Salida.**

```text
OK   login por redireccion completa; la SPA quedo en /casos; tras recargar, en /casos (sin volver al formulario)
securitypolicyviolation: 0
cookie vectra-spa-route: presente (solo se dice si esta; nunca su valor)
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Consola en el navegador por el gateway real: redireccion, /callback, recarga con prompt=none; cero securitypolicyviolation con la CSP real; la cookie vectra-spa-route llega a los pods | redireccion completa, /casos tras recargar, 0 securitypolicyviolation y la cookie vectra-spa-route presente; el navegador del presentador queda a mano | si para el Chromium sin interfaz; la parte a mano esta pendiente |

### K-36 — CASE_ALLOW_TEST_SCENARIOS activo en kind (la cabecera de escenario de …

- Demo: Base. Fuentes: `vectra-risk-gitops/values/kind/case-management.yaml:3`, `tareas/U12-T05-imagen-y-documentacion.md:368`.

**Resultado esperado.** CASE_ALLOW_TEST_SCENARIOS activo en kind (la cabecera de escenario de U12 se acepta)

**Comando.** Previsto: `humo flujo --delivery /verification/reference-model/.out`.

```bash
grep -n allowTestScenarios vectra-risk-gitops/values/kind/case-management.yaml
```

**Salida.**

```text
3:allowTestScenarios: true
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| CASE_ALLOW_TEST_SCENARIOS activo en kind (la cabecera de escenario de U12 se acepta) | allowTestScenarios: true en los values de kind y la cabecera de escenario se acepto en el flujo base | si |

### K-37 — Limites del gateway con el volumen real

- Demo: D2, D4. Fuentes: `identity-edge/gateway/routes.yaml:87-107`, `tareas/U12-T05-imagen-y-documentacion.md:368`.

**Resultado esperado.** Limites del gateway con el volumen real: 30/s para el simulador, 20/s por usuario en /api/console, 600/min en auth-login y auth-token (cero 429)

**Comando.** Previsto: `vectra-verification decisions`.

```bash
no ejecutado
```

**Salida.**

```text
no ejecutado
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Limites del gateway con el volumen real: 30/s para el simulador, 20/s por usuario en /api/console, 600/min en auth-login y auth-token (cero 429) | no ejecutado: los limites se prueban con el volumen real en F6 | no ejecutado |

## Hallazgos

- **Pendiente a mano (presentador).** El login manual de `ingeniero-2` y de `cumplimiento-2`, las semillas TOTP en el telefono y la consola en el navegador del presentador (K-33, K-35).
