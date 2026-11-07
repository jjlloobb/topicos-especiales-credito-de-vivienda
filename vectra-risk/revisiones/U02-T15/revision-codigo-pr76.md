# Revisión de código del PR 76 (2026-11-07, `/code-review 76`, a pedido del usuario)

No se verificó con ejecución.

| Id | Archivo | Hallazgo |
|---|---|---|
| D-01 | `identity-edge/tests/load/identity.js:259` | Con la espera de 30 s, un solo fallo de token deja 30 s de checks `hay token` fallidos. El executor `arrival-rate` sigue lanzando iteraciones, así que en un VU de `console-burst` se acumulan de 150 a 1200 checks fallidos, y uno solo puede romper `checks: rate>0.99` |
| D-02 | `identity-edge/tests/load/seed_users.py:81` | `create` hace DELETE y luego POST. Si el POST falla, el usuario se pierde, cuando antes se conservaba |
| D-03 | `identity-edge/tests/load/identity.js:67` | `PUBLIC_ORIGIN` quita siempre el puerto, y con una URL IPv6 queda mal formado. En kind no aplica: `KC_HOSTNAME` no lleva puerto |
| D-04 | `identity-edge/tests/unit/test_load_spec.py:156` | El `aud` esperado repite el supuesto del script. Es el mismo que F-03 de la ronda 5 |
| D-05 | `identity-edge/tests/load/identity.js:306` | El comentario dice «issuer», pero el valor es el token endpoint |
| D-06 | `identity-edge/tests/load/seed_users.py:88` | El GET de `role-mappings` ya no sirve, porque el usuario siempre es nuevo |
| D-07 | `identity-edge/tests/strategies/fake_admin.py:82` | El modelo de `passwordHistory` del falso ya no lo usa `seed_users` |
| D-08 | `identity-edge/tests/unit/test_load_seed_users.py:64` | La docstring de `pollute` miente, y la prueba de idempotencia ya no comprueba lo que hace la segunda corrida |
| D-09 | `identity-edge/tests/unit/test_load_spec.py:228` | La prueba hereda `**os.environ`, así que se le cuelan las `K6_*` del desarrollador |
