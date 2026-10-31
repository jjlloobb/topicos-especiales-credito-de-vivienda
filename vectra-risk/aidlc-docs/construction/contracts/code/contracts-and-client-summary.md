# Resumen de las specs y del cliente — U0

- `tools/codegen.py` genera desde el registro de rutas: `openapi/{servicio}.yaml` (8 servicios), `openapi/scopes-catalog.json` para el realm de U2, `openapi/role-endpoint-matrix.md` (US-602) y `ts/src/enums.generated.ts`.
- `contracts/ts`: tipos con `openapi-typescript` en `src/generated/`, cliente `openapi-fetch`, `decimal.js` para `Decimal4` y regla de ESLint contra `Number()` y `parseFloat`.
- Pruebas con fast-check y Vitest: `Decimal4` como cadena, `RecommendResult` por `kind` y `FeatureValue`.
- `tools/version_gate.py` y `oasdiff` comprueban la compatibilidad en CI contra la última etiqueta `contracts-vX.Y.Z`.
