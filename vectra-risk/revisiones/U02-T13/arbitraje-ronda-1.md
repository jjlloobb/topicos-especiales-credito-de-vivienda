# U02-T13 — Arbitraje de la ronda 1 (orquestador, 2026-11-05)

Informe: `ronda-1.md`, NO-VERDE.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 NARANJA: falso SEV1 de `BreakGlassLogin` tras un hueco de scrape | **Entra en la ronda 2** | Es un defecto de la regla que introduce el propio diff. Un SEV1 falso en la alerta más grave de U2 no se acepta como riesgo |
| F-02 NARANJA: casos de promtool que no detectan mutaciones | **Entra en la ronda 2** | CA-1 pide que promtool demuestre el disparo y el no-disparo de cada alerta, «antes de cumplir el `for`» incluido |
| F-03 AMARILLO: literales en pytest de valores que fija el diseño | **Entra en la ronda 2** | La nota de la tarea lo prohíbe expresamente, y el arreglo es acotado. El 19001 inyectado en el modelo del data plane se lee de una fuente versionada |
| F-04 AMARILLO: candidata obsoleta | **Entra en la ronda 2** | Se retira la entrada de `error=""` de `CANDIDATAS.md` |
| F-05 AMARILLO: `GatewayHighLatency` sin filtro de listener ni de cluster | **Pasa a `CANDIDATAS.md`** | La aproximación es la que fija P-U2-09. Acotarla es un cambio de diseño |

## Lo que se espera de la ronda 2

- **F-01**:
  - la rama de primera muestra solo dispara si el target se raspó sin hueco en la ventana, por ejemplo con `up` del job de Keycloak y la cuenta de muestras;
  - un caso de promtool con la serie del revisor (`'1x5 stale _x8 1x10'`) que **no** dispara;
  - el caso de primera muestra real **sí** sigue disparando;
  - si queda algún riesgo residual, va escrito en el runbook `break-glass-login.md`.
- **F-02**: cada mutación que sobrevivió en el informe del revisor (`for` de `KeycloakDown` y `RateLimitBackendDown`, ventanas de `RoleConflict` y `LdapUnavailable`, umbral de `GatewayHighLatency`, `realm` en la rama de `increase`, bordes de los dos stale) tiene un caso de promtool que la detecta.
  - El codificador registra en la bitácora la corrida de sus propias mutaciones de la regla, con el resultado de cada una.
- **F-03**: las pruebas de pytest leen del diseño o de una fuente versionada los valores que fija el diseño.
- **F-04**: se retira la candidata.
- **CA-1 a CA-6** se vuelven a correr; CA-5 y CA-6 en serie.
