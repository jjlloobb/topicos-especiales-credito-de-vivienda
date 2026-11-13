# Changelog de `contracts`

## 0.1.0 (etiqueta `contracts-v0.1.0`, pendiente de crear al integrar)

Version inicial: tipos del contrato, invariante en dos fases, finanzas, etiquetas, registro de rutas,
middleware comun, specs OpenAPI y cliente TypeScript.

## Sin publicar — la audiencia de la aserción de servicio (2026-11-13, U00-T04)

Sin etiqueta ni cambio de versión: ningún esquema cambia (la línea base 0.1.0 sigue sin etiquetar).

- `ServiceTokenProvider` recibe `assertion_audience` (solo por nombre, sin valor por omisión; vacía es `ValueError`) y firma esa `aud`; la petición sigue yendo a `token_url`. Keycloak rechaza con 400 `Invalid token audience` la `aud` = URL interna de token y acepta el emisor público.
- `provider_from_env` lee `VECTRA_ASSERTION_AUDIENCE` (obligatoria; sin ella falla al construir). Todo workload que pide token la rinde, derivada de `keycloak.issuer`.

## Sin publicar — revisión de consistencia entre unidades (2026-11-01)

Sin etiqueta `contracts-v*` todavía: estos cambios forman parte de la línea base 0.1.0.

- `POST /v1/explanations` devuelve `Explanation`, y `POST /v1/entries`, `RegistryAck`.
- Parámetros de consulta en los specs: `CaseFilter`, `ModelFilter`, `EntryFilter`, `DisparityFilter`; `Idempotency-Key`, `If-None-Match` y los estados 202 y 304.
- `GET /v1/entries` publica las proyecciones (`EntryProjection`).
- `AffectedVolume`, `PrePostDelta`, `PolicyDecisionIn`; `CaseDetail.recommendation` tipado; `Principal.client_id`; `registry.idempotency_conflict`; `verification-reader` en el catálogo.
- `vectra_common`: `ops_server.run_service` (8080 y 8081), `service_token` (`private_key_jwt`), `token_source` y reintento por 401 en `deps.call`, `window_seconds` en el breaker, timeout de dependencia = 504, muestreo real, ids de span únicos y métricas de proceso.
- El cliente TypeScript exporta todos los enumerados del catálogo.

## Sin publicar — la política activa viaja en `serving-config` (2026-11-10, U04-T09)

Decisión del usuario del 2026-11-10. Sin subir la versión mayor: añadir propiedades obligatorias a una respuesta no es un cambio incompatible para `oasdiff` (BR-U0-91 y 92).

- `ServingConfig` gana `cutoff`, `low_confidence_threshold` y `channel_rules` (`list[ChannelRule]`), obligatorios, con los tipos de `PolicyDraft`. Los copia governance de la política `activa`; scoring los usa para `PolicyEvaluationInput` sin otra llamada.
- Regenerados `contracts/openapi/governance-service.yaml` y el cliente TypeScript.
