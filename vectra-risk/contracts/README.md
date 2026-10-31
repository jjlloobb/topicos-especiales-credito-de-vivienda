# `contracts` (U0)

Tipos, invariantes y middleware que comparten los servicios de Vectra Risk. No se despliega: los
servicios lo importan por ruta del workspace `uv`.

## Comandos

```text
uv sync --frozen          # entorno
make -C contracts check   # lint, pruebas ci, cobertura, trazabilidad, benchmark, specs y TS
make -C contracts openapi # regenera contracts/openapi y los enumerados de TS
uv run python contracts/tools/mutation.py   # mutacion (tambien corre de noche)
```

## Crear un servicio

```python
from vectra_common import create_app
from vectra_contracts.routes import REGISTRY

app = create_app("scoring-service", handlers={("POST", "/v1/recommendations"): recommend})
```

- `create_app` es la unica forma de crear una app. Falla al arrancar si falta o sobra un handler, si
  una ruta no declara requisitos o si un `POST` con solo scopes de lectura no es `read_only`.
- El handler recibe un `RequestContext` ya autenticado, autorizado y validado.
- Variables: `VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL`, `VECTRA_CA_BUNDLE` (con https; sin el archivo no
  arranca), `VECTRA_OTLP_ENDPOINT` (sin ella no exporta trazas), `VECTRA_TRACE_RATIO`, `VECTRA_LOG_STRICT`.
- La app de 8081 (`/metrics`, `/healthz`, `/readyz`) queda en `app.state.ops_app`.

## Autorizacion

Cada ruta se declara como `RouteContract` en `vectra_contracts.routes`. `require` autoriza si y solo si
`scopes ⊆ principal.scopes`, `any_scopes` tiene alguno, `roles` tiene alguno y, con `mfa`, `acr = mfa` y
`auth_time` de hace menos de `mfa_max_age`.

## Dependencias

```python
client = DependencyClient("registry", "http://decision-registry:8080",
                          BreakerConfig(open_for=30, window_size=20, failure_ratio=0.5), max_connections=10)
response = await call(client, "POST", "/v1/entries", timeout=2.5, deadline=ctx.deadline, content=body)
```

`timeout` es obligatorio. Solo timeouts, errores de conexion y 5xx cuentan como fallo. Un proceso batch
llama `process.init("batch")` antes de crear clientes, y solo ese proceso puede usar `breaker="disabled"`.

## Invariante de la recomendacion

`check_preconditions` es la unica que construye `Ready` y `build_outcome` la unica que construye
`Recommendation`. Para leer de la red se usa `RecommendResult.from_wire`.

## Versiones (BR-U0-90..93)

Una sola version SemVer para specs, `vectra_contracts`, `vectra_common` y el cliente TS. Eliminar un
campo, cambiar su tipo o endurecer una validacion sube la version mayor, y CI lo comprueba con `oasdiff`
contra la ultima etiqueta `contracts-vX.Y.Z`.

## Actualizar DIVIPOLA

1. Reemplaza `data/divipola.csv` con los datos del DANE (conjunto `gdxc-w37w` de datos.gov.co).
2. Actualiza su `sha256`, `retrieved_on` y `cutoff_date` en `data/MANIFEST.json`.
3. Agregar codigos sube la version menor; quitarlos sube la mayor (NFR-U0-21).

La fecha de corte vigente y la tabla de regiones siguen marcadas `[VERIFICAR]`.
