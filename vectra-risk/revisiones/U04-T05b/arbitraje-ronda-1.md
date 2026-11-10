# Arbitraje de la ronda 1 — U04-T05b

Orquestador, 2026-11-10. Informe: `revisiones/U04-T05b/ronda-1.md`. NO-VERDE por F-01, que rompe el flujo base (RL-2: un NARANJA que rompe una demo no va a candidatas).

## Qué entra en la ronda 2 (la última por RL-2)

1. **F-01.** `redirect_uri = f"http://127.0.0.1:{port}"`, sin ruta, como el diseño de U2 y el realm. El handler del loopback acepta la raíz. El doble del IdP de las pruebas comprueba la forma **exacta** del diseño (esquema, host `127.0.0.1`, cualquier puerto, **sin ruta**) y rechaza `…/callback`. Rojo primero: con el código actual, la prueba nueva falla.
2. **F-03.** Declarar `pyyaml` en `governance/pyproject.toml` (la versión del lock, sin cambiar otras) y `uv lock --check` en 0.
3. **Candidatas:** reescribir la candidata de U2 sobre el `redirectUri` (el desajuste era la ruta, de U4, y queda resuelto aquí); agregar F-02, F-04 y F-05.

Nada más. El revisor de la ronda 2 comprueba esos puntos, CA-1, CA-3 y `--all`.
