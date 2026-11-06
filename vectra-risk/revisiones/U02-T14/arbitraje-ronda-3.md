# U02-T14 — Arbitraje de la ronda 3 (orquestador, 2026-11-05)

Informe: `ronda-3.md`, NO-VERDE. F-10 a F-13 quedan cerrados y CA-1 a CA-7 pasan.

La tarea llega a la ronda 4, así que se paró y se llevó a la persona. El patrón no apunta a un criterio mal escrito: la regresión de la ronda 2 fue un reemplazo de texto global, y la ronda 3 la protegió con una prueba de forma equivocada. **Decisión del usuario (2026-11-05): ronda 4 acotada a F-14 y F-15, con la forma que propone el revisor.**

| Hallazgo | Decisión |
|---|---|
| F-14 NARANJA: la salvaguarda de F-10 es una foto de los realms enteros | **Entra en la ronda 4**, con los puntos 1 y 2 de la forma que propone el revisor |
| F-15 AMARILLO: margen implícito en la prueba de F-11 | **Entra en la ronda 4** |

## Lo que se espera de la ronda 4

- **Se borran** `identity-edge/tests/fixtures/realm-baseline-8c18021/` y `test_the_realms_only_differ_from_the_baseline_in_the_declared_fields`, junto con lo que el README diga de ellas.
- **Se añade a `test_realm_files.py` una prueba de invariantes de `authenticationFlows`** en los tres realms:
  - en cada flujo, las prioridades son únicas y estrictamente crecientes;
  - en `vectra-browser forms`, el orden es `vectra-level-pwd` primero, luego los roles MFA y `vectra-mfa-analista` al final. El orden se lee de `realm_builders` (o de BR-U2-03 si el diseño lo fija), nunca de una copia del realm;
  - cada `vectra-mfa-<rol>` sigue la plantilla `conditional-level-of-authentication` < `conditional-user-role` (< `conditional-user-configured`) < el factor.
- **La prueba tiene que matar la regresión de F-10.** Si se cambia una `priority: 30` de `authenticationFlows` a 57, falla; si se cambia `accessTokenLifespan`, no falla. Las dos mutaciones se corren y se citan en la bitácora, con su salida.
- No se repiten literales que ya fija `REALM_PARAMETERS` de `realm_lint` (`LINEAR`, 15, 3).
- **F-15**: los 2,0 s y 0,1 s de la prueba de F-11 se derivan de `params.quick_login_check_milliseconds`.
- Los realms y los jobs renderizados no cambian en esta ronda. `git diff d6e1307 -- identity-edge/keycloak/realm identity-edge/jobs/rendered` queda vacío.
- **CA-1 a CA-7** se vuelven a correr; CA-5 y CA-6 en serie.
