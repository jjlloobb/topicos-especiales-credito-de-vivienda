# U02-T13 — Arbitraje de la ronda 2 (orquestador, 2026-11-05)

Informe: `ronda-2.md`, NO-VERDE.

| Hallazgo | Decisión |
|---|---|
| F-01 NARANJA: el riesgo residual documentado de `BreakGlassLogin` es falso y omite el real | **Decisión B11 del usuario. Entra en la ronda 3**: la expresión nueva del revisor, la alerta `KeycloakMetricsDown` y el runbook con los límites medidos (P-U2-09, B11) |
| F-02 AMARILLO: sobreviven las mutaciones `on(pod)` y `up` sin `job` | **Entra en la ronda 3**: un caso de promtool para cada una |
| F-03 AMARILLO: afirmación de mutaciones sin artefacto | **Entra en la ronda 3**: el script de mutaciones y su resultado quedan versionados en `revisiones/U02-T13/` y se citan desde la bitácora |

## Lo que se espera de la ronda 3

- **Reglas**:
  - `BreakGlassLogin` con la expresión de B11, en el archivo de grupos y en el CR;
  - `KeycloakMetricsDown` con su severidad, su `for` y el runbook `keycloak-metrics-down.md`.

  Son 12 alertas. `test_alert_rules.py` sigue leyendo la tabla de P-U2-09. El conjunto de runbooks es la lista del plan, más `valkey-zone-failback` y `keycloak-metrics-down`.
- **promtool**:
  - los escenarios A, A2, B, C y D del informe disparan en los minutos que midió el revisor;
  - los dos casos de hueco de la ronda 2 no disparan;
  - los casos «up de otro pod» y «sin up» se reescriben según B11;
  - `KeycloakMetricsDown` tiene casos de `up` a 0, de `up` ausente y de no disparo, este último antes de cumplir el `for`;
  - hay casos para F-02.
- **Runbook `break-glass-login.md`**: describe los límites de B11 tal como se midieron y remite a `KeycloakMetricsDown`. Se retira de `CANDIDATAS.md` la entrada con el límite falso.
- **Mutaciones**: el script y su salida quedan en `revisiones/U02-T13/` (F-03). Ninguna mutación de las 43 del revisor, ni de la expresión nueva, sobrevive.
- **CA-1 a CA-6** se vuelven a correr; CA-5 y CA-6 en serie.
