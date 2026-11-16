# U01-T16 — Arbitraje de la ronda 1 (orquestador, 2026-11-16)

Informe: `ronda-1.md`. El revisor escribió NO-VERDE **sin ningún ROJO**: tres NARANJA y dos AMARILLO. El veredicto se conserva tal cual en el informe.

**Decisión: hay ronda 2, acotada a los hallazgos de abajo.** RL-2 (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6) permite dos rondas y dice que solo un ROJO bloquea. Aquí abro la segunda sin ROJO, por una razón que no es del revisor sino del orquestador: este guion es lo siguiente que se va a correr contra el clúster real, con la bóveda vacía, y los tres NARANJA cambian lo que pasa en esa corrida.

- F-01: el orquestador esperaría 3 rutas generadas y saldrían 6; `channel-simulator` y `verification-reader` (el simulador y la lectura de U12) dejarían de autenticarse hasta reimportar el realm, y nada escrito lo dice.
- F-02: es el caso «escribir en la bóveda un valor que no es el que había».
- F-03: un error de `kubectl` se leería como «edita `/etc/hosts`», y un fallo de `identity-namespaces` terminaría en rc 0 sin refrescar nada.

| Hallazgo | Decisión | Qué se pide en la ronda 2 |
|---|---|---|
| F-01 NARANJA | Ronda 2 | Las privadas de `channel`, `channel-simulator` y `verification-reader` no están en ningún `Secret`: no se pueden recuperar, y no se pide recuperarlas. Se pide que la prueba use solo los `*-client` que los charts declaran de verdad (sácalos del repositorio, no de una lista), que el informe, la bitácora y `install.md` digan las 6 rutas, y que el runbook tenga el paso concreto para lo generado en identidad (reimportar el realm con `argocd app sync keycloak` y comprobar), marcado como no medido |
| F-02 NARANJA | Ronda 2 | La plantilla solo es literal si es exactamente `{{ .clave }}` sin nada alrededor; lo demás se informa como plantilla. Con su prueba |
| F-03 NARANJA | Ronda 2 | `gateway-address.sh`: un fallo de `kubectl` sale con un código propio, distinto de 1; las pruebas fijan cada código. `seed-vault.sh identity`: si `identity-namespaces` falla, el guion falla |
| F-04 AMARILLO (Valkey) | Ronda 2, solo runbook | Paso propio en «Vault reiniciado», fuera del de Keycloak: si el informe trae `edge/valkey` como generada, reiniciar Valkey, los Sentinel y `envoy-ratelimit` juntos, con las órdenes y qué mirar; marcado como no medido. Invertir las plantillas sigue como candidata |
| F-05 AMARILLO | Ronda 2 | `identity/break-glass` no debe impedir el cierre «nada que realinear» si nadie lee esa ruta (di cómo lo decides); `decode` con un error propio que no cite bytes del valor; devolver la frase medida del 2026-11-14 |

Fuera de la ronda 2: recuperar lo que solo vive en plantillas, persistir el directorio e2e fuera de tmpfs y medir `cloud-provider-kind`. Siguen en `CANDIDATAS.md`.

`shellcheck` (CA-4): el usuario autorizó instalarlo (`uv tool install shellcheck-py`, 0.11.0 en `~/.local/bin`); el orquestador y el revisor lo corrieron sobre los dos guiones, rc 0.

CA-5: el `pytest` sobre `test_runbooks.py` y `test_links.py` da rc 5 porque son guiones, no pruebas. Es un defecto del criterio, escrito por el orquestador; valen las corridas como las hace `make -C platform check`.
