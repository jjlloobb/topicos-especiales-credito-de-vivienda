# Revisión de código del PR 72 después de la ronda 4 (2026-11-07, `/code-review 72`, a pedido del usuario)

Sin verificar con ejecución: los hallazgos salen de leer el diff junto con `realm.kind.yaml` y `routes.yaml`. El orquestador comprobó C-01 a medias: `realm.kind.yaml:32` tiene `passwordHistory(5)` y `seed_users.py:84-87` vuelve a poner la misma contraseña.

| Id | Archivo | Hallazgo | Escenario |
|---|---|---|---|
| C-01 | `identity-edge/tests/load/seed_users.py:86` | Si el usuario de carga ya existe, `create` le vuelve a poner el mismo `K6_LOAD_PASSWORD`, y `passwordHistory(5)` rechaza reusar la contraseña vigente. Por eso `create` no es idempotente | La segunda corrida recibe 400 en `reset-password` y se detiene en load-001. `FakeAdmin` no modela el historial |
| C-02 | `identity-edge/tests/load/identity.js:252` | `accessToken()` no espera antes de reintentar: después de un fallo guarda `null`, y cada iteración de `console-burst` (40/s) y `overhead` (5/s) vuelve a hacer un login completo | Un 5xx pasajero supera los 600/min por IP de `/auth`, el 429 alcanza a los 200 VUs y el Paso 16 falla por culpa del script |
| C-03 | `identity-edge/tests/load/seed_users.py:84` | Para un usuario que ya existe no pone `enabled: true` ni limpia `requiredActions` ni las credenciales OTP | Con `permanentLockout: true`, un usuario bloqueado en una corrida anterior sigue bloqueado aunque `create` diga que terminó bien |
| C-04 | `identity-edge/tests/load/identity.js:346` | La pata «directa» de NFR-U2-11 va por un `kubectl port-forward` que pasa por el API server, así que la diferencia gateway−directa queda sesgada hacia abajo | NFR-U2-11 pasaría sin haberse medido |
| C-05 | `identity-edge/tests/load/identity.js:296` | El `aud` de `private_key_jwt` se arma con el `BASE_URL` tal cual, sin normalizar como `REDIRECT_URI` | Con un `BASE_URL` que lleva puerto, todos los `client_credentials` responden 401 |
| C-06 | `identity-edge/tests/load/identity.js:323` | `r.json('keys.#') !== 0` pasa cuando falta `keys` | Un 200 con `{}` pasa el check |
| C-07 | `identity-edge/tests/strategies/load_checks.py:140` | No comprueba que `BASE_RATE` quede por debajo del límite de la consola, ni que existan los umbrales `leg:*` | `load-inspect` pasa con un `BASE_RATE` que da 429 constante |
| C-08 | `identity-edge/Makefile:41` | `load-inspect` corre `k6 inspect` dos veces | Costo sin cobertura extra |
