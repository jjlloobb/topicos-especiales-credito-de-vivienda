# Changelog de `contracts`

## 0.1.0 (etiqueta `contracts-v0.1.0`, pendiente de crear al integrar)

Version inicial: tipos del contrato, invariante en dos fases, finanzas, etiquetas, registro de rutas,
middleware comun, specs OpenAPI y cliente TypeScript.

## Sin publicar — revisión de consistencia entre unidades (2026-11-01)

Sin etiqueta `contracts-v*` todavía: estos cambios forman parte de la línea base 0.1.0.

- `POST /v1/explanations` devuelve `Explanation`, y `POST /v1/entries`, `RegistryAck`.
- Parámetros de consulta en los specs: `CaseFilter`, `ModelFilter`, `EntryFilter`, `DisparityFilter`; `Idempotency-Key`, `If-None-Match` y los estados 202 y 304.
- `GET /v1/entries` publica las proyecciones (`EntryProjection`).
- `AffectedVolume`, `PrePostDelta`, `PolicyDecisionIn`; `CaseDetail.recommendation` tipado; `Principal.client_id`; `registry.idempotency_conflict`; `verification-reader` en el catálogo.
- `vectra_common`: `ops_server.run_service` (8080 y 8081), `service_token` (`private_key_jwt`), `token_source` y reintento por 401 en `deps.call`, `window_seconds` en el breaker, timeout de dependencia = 504, muestreo real, ids de span únicos y métricas de proceso.
- El cliente TypeScript exporta todos los enumerados del catálogo.
