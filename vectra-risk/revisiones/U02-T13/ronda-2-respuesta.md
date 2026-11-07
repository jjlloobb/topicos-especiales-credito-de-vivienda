# U02-T13, respuesta del codificador a la ronda 1

F-01: Corregido en el commit de la ronda 2 (ver SHA en el mensaje final): la rama de primera muestra de `BreakGlassLogin` lleva `and on(namespace, pod) (up{job="keycloak"} offset 5m == 1)`; casos de promtool con la serie del revisor (up=0 y up ausente en el hueco) que no disparan, y el de primera muestra real que sigue disparando; riesgo residual escrito en `break-glass-login.md` y en `CANDIDATAS.md`.
F-02: Corregido en el commit de la ronda 2: casos nuevos para `for` de KeycloakDown y RateLimitBackendDown, ventanas de RoleConflict y LdapUnavailable, umbral de GatewayHighLatency (4.95 y 14.5 ms), realm en la rama de `increase`, y bordes de los dos stale; mi corrida: 10 de 30 mutaciones sobrevivian y con los casos nuevos 35 de 35 se detectan (bitacora, Ronda 2).
F-03: Corregido en el commit de la ronda 2: los literales de `test_alert_rules.py`, `test_keycloak_deploy.py` y `test_keycloak_image.py` se leen del diseno; el 19001 sale de F60 de `flows.yaml`.
F-04: Corregido en el commit de la ronda 2: entrada de `error=""` retirada de `CANDIDATAS.md`.
F-05: Fuera de alcance: pasa a `CANDIDATAS.md` por el arbitraje (agregada).
