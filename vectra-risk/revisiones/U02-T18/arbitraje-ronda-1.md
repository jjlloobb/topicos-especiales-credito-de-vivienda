# U02-T18 — Arbitraje de la ronda 1 (orquestador, 2026-11-07)

Sin informe de revisor: el codificador se detuvo antes, con CA-6 en rojo, y lo reportó como bloqueo.

## El bloqueo

`platform/tests/test_kind_profile.py::test_the_profile_requests_fit_the_budget` falla: `5.47265625 <= 5.0`. Ahora que `integration.py` ve los manifiestos de U2, las requests de memoria de kind de Valkey, Keycloak, el data plane de Envoy y `envoy-ratelimit` superan `BUDGET_GIB = 5.0` por 0,47 GiB.

El codificador no tomó ninguna de las dos salidas, y tenía razón: bajar requests toca `identity-edge/`, donde la tarea manda detenerse, y subir el tope cambia el perfil de U1 sin respaldo.

## Decisión del usuario (M4)

**Bajar las requests de memoria de U2 solo en kind**, hasta que el perfil quepa con margen. `BUDGET_GIB` no cambia. Las requests de staging y prod (INF-U2-06) tampoco.

## Lo que se espera de la ronda 2

- Solo M4. CA-1 a CA-5 no se reabren, salvo que M4 los rompa.
- La tarea enmendada dice qué archivos se pueden tocar y qué se comprueba.

## Ronda 2: bloqueo y ampliación de M4

El codificador se detuvo sin cambios: `keycloak.rego:343-346` y `valkey.rego` fijan las requests exactas en todos los entornos, y solo Keycloak puede aportar el recorte. **El usuario amplió M4 a las políticas**: Keycloak baja a 512 Mi solo en kind, y `keycloak.rego` acepta esa request únicamente en el render de kind. El presupuesto de kind para U3–U12 pasa a `CANDIDATAS.md`.
