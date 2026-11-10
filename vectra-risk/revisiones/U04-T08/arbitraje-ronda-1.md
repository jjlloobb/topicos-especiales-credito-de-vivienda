# Arbitraje de la ronda 1 — U04-T08

Orquestador, 2026-11-10. Informe: `revisiones/U04-T08/ronda-1.md`. El diff es VERDE, pero el juicio 2 (identidad del servicio fuera del chart) rompe el flujo base de las cuatro demos. Por RL-2, lo que rompe una demo no va a candidatas. Como son los mismos archivos de la misma unidad, **se amplía el alcance de U04-T08 a `governance/chart`** para cerrarlo aquí, antes de U04-T07, en vez de abrir otra tarea.

## Qué entra en la ronda 2 (la última por RL-2)

1. **Identidad del servicio en el chart** (juicio 2 y F-01): `ExternalSecret` `governance-service-client` desde `identity/clients/governance-service`, propiedad `private-key` (con el patrón del `ExternalSecret` del Job en `validation-job.yaml`); volumen montado en solo lectura; variables `VECTRA_CLIENT_ID`, `VECTRA_CLIENT_KEY_PATH`, `GOVERNANCE_REGISTRY_URL` y `GOVERNANCE_BIAS_URL` con los Services de U3 y U9 por entorno. Las cuatro pasan a `REQUIRED` en `service.py` y se quitan los cuatro valores por omisión. Regla de conftest en `governance/chart/policy/` que exija las variables y el montaje, con su caso que falla en `test_chart.py`. La prueba de igualdad con el render (CA-2) sigue pasando. El CA-1 se repite con las variables nuevas (y una llave de prueba montada) y además comprueba que `POST /v1/policies` llega a `confirmada` contra un registro de prueba.
2. **F-03:** el token propio usa `VECTRA_TOKEN_URL`, como `provider_from_env` de U0; el chart la entrega. `GOVERNANCE_JOB_TOKEN_URL` queda solo para el Job.
3. **F-02:** `log.warning` al arrancar si la llave no existe en `VECTRA_CLIENT_KEY_PATH` (con el chart nuevo no debería pasar), y un caso en `test_service_build_app.py` con la llave ausente que lea la fila en `pendiente_registro` y el 503 `problem+json`.
4. **F-04:** cerrar `S3PackageStore` en el `lifespan`.
5. Admisión y presupuesto: `make -C governance policy-chart-u1` en los tres entornos sigue en `fail: 0`; `kyverno apply` de `disallow-plain-secrets` sobre el render pasa (el Secret lo crea ESO); `test_kind_profile.py` sin cambios de cifra.

Nada más.
