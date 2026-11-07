# Revisión de código del PR 75 (2026-11-07, `/code-review 75`, a pedido del usuario)

La revisión no corrió nada (sin pase de verificación). El orquestador comprobó C-02 leyendo el código.

| Id | Archivo | Hallazgo |
|---|---|---|
| C-01 | `platform/tests/test_integration.py:107` | `EXTERNAL_ISSUERS = {"banco-ca"}` tapa que ninguna Application crea el `ClusterIssuer` `banco-ca` de staging y prod. En la wave 3 los `Certificate` de Keycloak y del gateway no se emitirían |
| C-02 | `identity-edge/keycloak/values/kind.yaml:51` y `platform/tests/test_kind_profile.py` | **Comprobado por el orquestador:** `requested_gib()` cuenta `spec.replicas` o 1. El StatefulSet de Keycloak no tiene `replicas` y su HPA pide `minReplicas: 2`, así que en kind corren 2 pods y la prueba cuenta 1. Tampoco cuenta los pods que crea el controlador: el data plane de Envoy (`EnvoyProxy` con `replicas: 2`, HPA con mínimo 2), `envoy-ratelimit` (`replicas: 2`) ni el controlador de Envoy Gateway (chart OCI, que `render_env` deja vacío). El «cabe en 4,97 GiB» de M4 no es real: 2 × 512 Mi de Keycloak piden lo mismo que el 1 × 1 Gi que se contaba antes |
| C-03 | `identity-edge/keycloak/values/kind.yaml:49` | Con 512 Mi de request, 2 Gi de limit y `MaxRAMPercentage=70`, el pod queda muy sobrecomprometido; con presión de memoria en el nodo, es el primero que se desaloja |
| C-04 | `identity-edge/keycloak/policy/keycloak.rego:347` | La excepción de kind sale del hostname y no del entorno. Coincide con F-01 del revisor |
| C-05 | `platform/tests/test_integration.py:132` | Omitir el grupo `gateway.networking.k8s.io` deja sin validar también el `BackendTLSPolicy` de la Application `keycloak` |
| C-06 | `platform/tests/test_platform.py:171` | `resource_owners` no mira las Applications de chart ni de Helm, solo lee `*.yaml` y usa `None` como namespace. Coincide con F-03 del revisor |
| C-07 | `platform/tests/test_platform.py:158` | Reimplementa la selección `include`/`exclude` que ya existe en `integration.directory_docs` |
