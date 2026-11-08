# Código de U2 `identity-edge`

Generado el 2026-11-08 (U02-T18, Paso 15). Código en `vectra-risk/identity-edge/`. Verificación estática de toda la unidad: `make -C identity-edge check`. Las pruebas que necesitan un clúster las ejecuta el operador en kind (Paso 16) y no entran en `check`.

Raíces de código: `identity-edge/`

Cada sección: componente → archivos → verificación → identificadores de diseño que cumple. El diseño está en [Functional Design](../functional-design/), [NFR Requirements](../nfr-requirements/), [NFR Design](../nfr-design/) e [Infrastructure Design](../infrastructure-design/); el plan, en [identity-edge-code-generation-plan.md](../../plans/identity-edge-code-generation-plan.md).

## Keycloak y realm

- Archivos: `identity-edge/keycloak/realm/realm.kind.yaml` (también `realm.staging.yaml` y `realm.prod.yaml`), `identity-edge/keycloak/Dockerfile`, `identity-edge/keycloak/values/common.yaml`, `identity-edge/keycloak/themes/vectra/login/theme.properties` (tema de login), `identity-edge/keycloak/policy/keycloak.rego`.
- Verificación: `make -C identity-edge check-keycloak-rendered policy-keycloak policy-keycloak-u1`; `identity-edge/tests/unit/test_keycloak_deploy.py`, `identity-edge/tests/unit/test_keycloak_image.py`, `identity-edge/tests/unit/test_theme.py`, `identity-edge/tests/unit/test_realm_files.py`.
- Cumple: BR-U2-03, BR-U2-12, BR-U2-16, INF-U2-01, INF-U2-05, INF-U2-05a, INF-U2-05b, INF-U2-06, INF-U2-08, NFR-U2-01, NFR-U2-02, NFR-U2-23, NFR-U2-25 (digest, en `keycloak.rego`), NFR-U2-26, P-U2-08, P-U2-09.

## `realm-lint`

- Archivos: `identity-edge/tools/realm_lint.py`, `identity-edge/tools/realm_diff.py`.
- Verificación: `identity-edge/tests/unit/test_realm_lint.py`, `identity-edge/tests/unit/test_realm_diff.py`, `identity-edge/tests/property/test_realm_roles.py` (más `test_realm_scopes.py`, `test_realm_ldap.py`, `test_realm_normalize.py`); `make -C identity-edge test` con `HYPOTHESIS_PROFILE=ci` (NFR-U2-40, en `identity-edge/Makefile`).
- Cumple: BR-U2-01, BR-U2-03, BR-U2-05, BR-U2-09, BR-U2-12, BR-U2-15, INF-U2-05a, NFR-U2-24, NFR-U2-40, P-U2-05.

## Jobs `realm-drift` y `signing-key-age`

- Archivos: `identity-edge/jobs/realm_drift.py`, `identity-edge/jobs/signing_key_age.py`, `identity-edge/jobs/keycloak_admin.py`, `identity-edge/jobs/chart/templates/identity-jobs.yaml`, `identity-edge/jobs/policy/jobs.rego`.
- Verificación: `make -C identity-edge check-jobs-rendered policy-jobs policy-jobs-u1`; `identity-edge/tests/unit/test_identity_jobs.py`.
- Cumple: BR-U2-03, BR-U2-12, INF-U2-05a, INF-U2-06, INF-U2-09, P-U2-05.

## Gateway y `route-gen`

- Archivos: `identity-edge/gateway/routes.yaml` (fuente), `identity-edge/tools/route_gen.py`, `identity-edge/tools/crd_schemas.py`, `identity-edge/tools/xds_gateway.py`, `identity-edge/gateway/generated/kind/httproutes.yaml` (también `staging/` y `prod/`), `identity-edge/gateway/policy/edge.rego`, `identity-edge/gateway/policy/gateway.rego`, `identity-edge/docs/adr-envoy-gateway.md`.
- Verificación: `make -C identity-edge check-route-gen kubeconform-gateway policy-gateway xds-gateway render-envoy-gateway` (NFR-U2-41, en `identity-edge/Makefile`); `identity-edge/tests/unit/test_route_gen.py`, `identity-edge/tests/unit/test_gateway_xds.py`, `identity-edge/tests/property/test_routes_closed.py`.
- Cumple: BR-U2-08, BR-U2-10, BR-U2-11, BR-U2-13, BR-U2-14, INF-U2-01, INF-U2-02, INF-U2-06, INF-U2-10, NFR-U2-03, NFR-U2-04 (ADR §1; la prueba es del Paso 16), NFR-U2-20, NFR-U2-21, NFR-U2-22, NFR-U2-23, NFR-U2-41, P-U2-01, P-U2-02, P-U2-03, P-U2-06, P-U2-07.

## Rate limit y Valkey

- Archivos: `identity-edge/ratelimit/external-secret.yaml`, `identity-edge/ratelimit/policy/ratelimit.rego`, `identity-edge/charts/valkey/templates/valkey.yaml`, `identity-edge/charts/valkey/policy/valkey.rego`, `identity-edge/charts/valkey/values/kind.yaml`.
- Verificación: `make -C identity-edge policy-ratelimit check-valkey-rendered policy-valkey policy-valkey-u1`; `identity-edge/tests/unit/test_ratelimit_config.py`, `identity-edge/tests/unit/test_ratelimit_deployment.py`, `identity-edge/tests/unit/test_valkey_chart.py`.
- Cumple: INF-U2-03, INF-U2-04, INF-U2-06, NFR-U2-20, NFR-U2-27. El modo de fallo por ruta (NFR-U2-21, P-U2-01) está en la sección del gateway.

## Flujos y RBAC

- Archivos: `identity-edge/keycloak/realm/realm.kind.yaml` (clientes, flujos de autenticación, roles y grupos), `identity-edge/tools/realm_lint.py` (reglas de BR-U2-03, 05 y 09), `identity-edge/gateway/routes.yaml` (autorización por `azp` y scope).
- Verificación: `identity-edge/tests/unit/test_realm_lint.py`, `identity-edge/tests/property/test_realm_roles.py`, `identity-edge/tests/unit/test_bruteforce_model.py` (modelo de BR-U2-05 en `identity-edge/tests/strategies/bruteforce_model.py`).
- Cumple: BR-U2-01, BR-U2-03, BR-U2-05, BR-U2-09, BR-U2-12, BR-U2-15 (ya listados en las secciones de Keycloak y `realm-lint`).

## Observabilidad

- Archivos: `identity-edge/observability/rules/identity-edge-rules.yaml`, `identity-edge/observability/rules/identity-edge-rules.prometheusrule.yaml`, `identity-edge/observability/monitors/monitors.yaml`, `identity-edge/runbooks/keycloak-down.md` (y los demás de `identity-edge/runbooks/`).
- Verificación: `make -C identity-edge rules runbooks`; `identity-edge/observability/rules/tests/identity-edge-rules-test.yaml`, `identity-edge/tests/unit/test_alert_rules.py`.
- Cumple: BR-U2-17, INF-U2-04, NFR-U2-05 (`KeycloakDown` SEV1 y su runbook), NFR-U2-11, P-U2-09.

## Pruebas e2e y de carga

- Archivos: `identity-edge/tests/e2e/test_e2e_mfa.py` (y los demás `test_e2e_*.py`), `identity-edge/tests/e2e/echo/server.py`, `identity-edge/tests/strategies/bruteforce_model.py`, `identity-edge/tests/load/identity.js`, `identity-edge/tests/load/seed_users.py`.
- Verificación estática: `make -C identity-edge collect-e2e load-inspect`. La ejecución es del Paso 16 (`make -C identity-edge e2e` y `load`), con la evidencia adjunta al PR.
- Cumple: BR-U2-03 a BR-U2-14 y BR-U2-16 (e2e), NFR-U2-10, NFR-U2-11, NFR-U2-12, NFR-U2-30 (carga), NFR-U2-42 (e2e), P-U2-06, P-U2-08.

## GitOps

- Archivos: `vectra-risk-gitops/components.yaml` (entradas de U2 y sus waves), `vectra-risk-gitops/generate.py`; los manifiestos que sincroniza están en `identity-edge/`.
- Verificación: `uv run python vectra-risk-gitops/generate.py --check` y `uv run python platform/tests/test_waves.py` (U02-T17).
- Cumple: INF-U2-01, INF-U2-05, INF-U2-06 (waves y orden de sincronización; sin `values/<env>/` propios, decisión V1-a del plan).

## Trazabilidad a código de los identificadores sin referencia directa (2026-11-08)

Los siete identificadores que `test_traceability.py` no encontraba al empezar U02-T18 se cumplen en `identity-edge/`; cada uno lleva su id junto al código o la prueba que lo cumple.

| Identificador | Archivo |
|---|---|
| NFR-U2-04 | `identity-edge/docs/adr-envoy-gateway.md` (§1: el data plane es independiente del controlador; la prueba, con el controlador escalado a 0, es del Paso 16) |
| NFR-U2-05 | `identity-edge/observability/rules/identity-edge-rules.yaml` (`KeycloakDown`) y `identity-edge/runbooks/keycloak-down.md` |
| NFR-U2-21 | `identity-edge/gateway/routes.yaml` (`fail_closed`) y `identity-edge/tools/route_gen.py` |
| NFR-U2-25 | `identity-edge/keycloak/policy/keycloak.rego` (regla `image`) |
| NFR-U2-40 | `identity-edge/Makefile` (`test`) y `identity-edge/tests/unit/test_hypothesis_profile.py` |
| NFR-U2-41 | `identity-edge/Makefile` (`kubeconform-gateway`) |
| NFR-U2-42 | `identity-edge/Makefile` (`e2e`) y `identity-edge/tests/e2e/conftest.py` |
