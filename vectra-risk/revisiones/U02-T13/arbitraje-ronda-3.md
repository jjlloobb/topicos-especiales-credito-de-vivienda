# U02-T13 — Arbitraje de la ronda 3 (orquestador, 2026-11-05)

Informe: `ronda-3.md`, NO-VERDE. CA-1 a CA-6 pasan. De lo que pedía la ronda 2 quedan cerrados la expresión B11, `KeycloakMetricsDown`, F-02 y F-03.

La tarea llega a la ronda 4, así que se paró y se llevó a la persona. El patrón se repite desde F-01 de la ronda 2: lo difícil es describir con exactitud los límites de B11, no el código. **Decisión del usuario (2026-11-05): ronda 4 acotada. B11 no se reabre.**

| Hallazgo | Decisión |
|---|---|
| F-04 ROJO: la bitácora cita para CA-2 `--operational` una salida («4») de otro comando | **Entra en la ronda 4** |
| F-05 NARANJA: los límites del runbook se presentan como medidos y no coinciden con la medición | **Entra en la ronda 4** |
| F-06 AMARILLO: falta en promtool un caso de login fallido sobre una serie nueva en la rama 3 | **Entra en la ronda 4** |
| F-07 AMARILLO: literal de diseño en `test_alert_rules.py:234` | **Entra en la ronda 4** |
| F-08 AMARILLO: docstring obsoleto en `theme_checks.py:88` | **Entra en la ronda 4** |
| Candidata: omisión y retraso de `BreakGlassLogin` tras un reinicio del pod | **Va a `CANDIDATAS.md`**. B11 no cambia en esta tarea; la vía es el ruler de Loki o una revisión de B11 |

## Lo que se espera de la ronda 4

- **F-04**: la bitácora cita la salida real de `uv run python platform/tests/test_runbooks.py --root identity-edge --operational`, que es la corrida de esta ronda, no una copia.
- **F-05**: `break-glass-login.md`, la entrada de `CANDIDATAS.md` y los comentarios de `b11_scenarios.py` describen los límites así:
  - con el modelo de *staleness* explícito en cada escenario: qué serie lleva marca de stale (`X`, `up`, las dos o ninguna) y por qué ocurre eso en Prometheus;
  - con lo que se mide, sin generalizar desde un solo punto. Para el falso positivo, la duración por tamaño de hueco. Para la omisión, el hueco desde el que empieza en cada modelo;
  - incluida la omisión de un login que cae en el scrape en que vuelve el pod tras un reinicio normal, y el retraso de un login 1 min después.

  Cada cifra del runbook la produce un escenario versionado de `b11_scenarios.py probe`. La bitácora cita la salida.
- **F-06**: un caso de promtool con un login fallido (`error` distinto de `""`) sobre una serie nueva en la rama 3. Debe matar la mutación «sin `error=""` en la `N` de la rama 3» y la de `offset 10m`. Esas dos mutaciones se añaden a `mutaciones.py` y su salida se regenera en `revisiones/U02-T13/`.
- **F-07**: `SEV2` y `5m` se leen del diseño, no de literales.
- **F-08**: el docstring dice lo que la función devuelve hoy.
- Las reglas (`identity-edge-rules.yaml` y el CR) no cambian.
- **CA-1 a CA-6** se vuelven a correr; CA-5 y CA-6 en serie.
