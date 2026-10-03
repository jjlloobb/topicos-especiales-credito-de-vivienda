# Decisiones de stack — U0 `contracts`

Decisiones del plan (`contracts-nfr-requirements-plan.md`, Q1–Q11 = A). Las versiones
exactas no se fijan aquí: quedan pinneadas en `uv.lock` y `package-lock.json` (NFR-SEC-10).

---

## 1. Python (`vectra_contracts`, `vectra_common`)

| Área | Decisión | Motivo | Pregunta |
|---|---|---|---|
| Lenguaje | Python 3.12 | Coherente con los servicios FastAPI; soporte vigente | Q2 |
| Workspace | `uv` con un `uv.lock` único en la raíz del monorepo | Resolución reproducible y rápida; un solo lockfile para escanear | Q2 |
| Distribución | Dependencias de ruta del workspace; sin publicar en ningún índice | Coherente con la versión única de Q7 del FD; sin dependencia de un índice externo | Q3 |
| Modelos | Pydantic v2 (`strict`, `extra="forbid"`), **fuente de verdad** | Las validaciones viven junto al tipo; las specs se generan desde aquí | Q1 |
| Decimales | `decimal.Decimal` (contexto con precisión ≥ 28), serializado como cadena | BR-U0-10, BR-U0-15 | FD Q8 |
| JWT | PyJWT con `PyJWKClient` (cache de 10 min, refresco con límite) | Superficie mínima; lista de algoritmos explícita | Q4 |
| Logging | `structlog` con un procesador de allowlist; salida JSON a stdout; `logging` estándar redirigido | BR-U0-50..53 | Q11 |
| Telemetría | OpenTelemetry SDK + exportador OTLP/gRPC hacia el Collector in-cluster (F61); propagador W3C `traceparent` | BR-U0-62, AUTONOMIA-05 | INCEPTION |
| Integración web | Middleware y dependencias de FastAPI (Starlette) | Stack de los servicios | INCEPTION |
| JSON canónico | Implementación de RFC 8785 (JCS) para `feature_vector_hash` | BR del FD (N5) | FD |
| Datos DANE | Snapshot DIVIPOLA versionado como archivo de datos del paquete, con checksum | Sin egress en runtime | Q10 |

## 2. TypeScript (`contracts/ts`)

| Área | Decisión | Motivo | Pregunta |
|---|---|---|---|
| Generación | `openapi-typescript` (solo tipos) | Sin código de runtime generado; bundle pequeño | Q8 |
| Cliente HTTP | `openapi-fetch` | Cliente delgado y tipado sobre `fetch` | Q8 |
| Decimales | `string` en los tipos; `decimal.js` para operar y mostrar | Respeta BR-U0-15; nunca `number` | Q8 |
| Test runner | Vitest | Integración nativa con fast-check y con un SPA basado en Vite. **U10 lo confirma** al definir el stack de la SPA | — |

## 3. Pruebas (PBT-09)

| Lenguaje | Framework PBT | Runner | Generadores | Shrinking y semilla |
|---|---|---|---|---|
| Python | **Hypothesis** | pytest | `contracts/tests/strategies/` (compartidos con las demás unidades) | Nativos; perfiles `ci` (500) y `nightly` (10 000); `print_blob=True` |
| TypeScript | **fast-check** | Vitest | Arbitrarios por tipo del cliente | Nativos; semilla impresa en cada falla |

Complementos:
- `pytest-cov` (cobertura de ramas, NFR-U0-40);
- `mutmut` (mutación en `outcome` y `authz`, NFR-U0-41);
- `pytest-benchmark` (NFR-U0-01..03);
- `import-linter` (pureza y límites entre paquetes, NFR-U0-22 y 44).

## 4. Herramientas de CI de U0

| Herramienta | Uso | Requisito |
|---|---|---|
| Script `make -C contracts openapi` | Genera las specs desde Pydantic; `git diff --exit-code` | NFR-U0-30 |
| `oasdiff` | Cambios incompatibles contra la última etiqueta `contracts-vX.Y.Z` | NFR-U0-33, BR-U0-92 |
| Workflows reutilizables de U1 | Escaneo de dependencias, SBOM, semilla de PBT | NFR-U0-17 |
| Script de trazabilidad | Cada `BR-U0-xx` aparece en las pruebas | NFR-U0-35 |

## 5. Descartado

| Opción | Motivo |
|---|---|
| Spec-first con `datamodel-code-generator` | Dos definiciones (spec y lógica) que pueden divergir (Q1=B descartada) |
| Poetry con un lockfile por servicio | Varios lockfiles que escanear y alinear (Q2=B) |
| Índice interno de paquetes | Innecesario con la versión única y el monorepo (Q3=B) |
| Extender la JWKS vencida ante una caída de Keycloak | Acepta claves posiblemente revocadas; contradice el fail-closed (Q5=B) |
| `openapi-generator` para TS | Genera clases de runtime y convierte los decimales a `number` (Q8=B) |
| Formatter JSON propio sobre `logging` | Más código propio en un control de seguridad (Q11=B) |
