# console (U10)

La consola de Vectra Risk: la pantalla donde el analista, el ingeniero de riesgo, el CRO y cumplimiento ven los casos, leen la explicación de la recomendación, registran la decisión y gobiernan modelos y congelamientos. Son dos piezas que se despliegan por separado:

- **`console-spa`** (`spa/`): la aplicación de una sola página (React y Vite). En el clúster la sirve un nginx sin privilegios, en el 8080 de `vectra-edge`. No tiene lógica de servidor.
- **`console-bff`** (`bff/`): la API única de la SPA (`/api/console/**`, 30 endpoints). Valida el token del usuario, comprueba rol y MFA, llama a cinco servicios de `vectra-app` y traduce sus errores. No tiene base de datos ni estado y no guarda secretos: usa el token del usuario. Escucha en el 8080 (la API) y en el 8081 (`/metrics`, `/healthz`, `/readyz`).

## Arquitectura

```text
navegador ──F02──> api-gateway ──F02──> console-spa (nginx, vectra-edge, 8080)      /, /callback, /stepup-callback, assets
    │                  │
    └────────F03──────>└──F03──> console-bff (vectra-app, 8080) ──F10──> case-service
                                       │                        ──F11──> governance-service
                                       │                        ──F12──> explainability-service
                                       │                        ──F13──> decision-registry-service
                                       │                        ──F14──> bias-monitoring-service
                                       └─F50─> keycloak (JWKS)      F60: Prometheus raspa el 8081      F61: OTLP
```

- El gateway de U2 (`identity-edge/gateway/routes.yaml`) es el único cliente de las dos piezas: la ruta `spa` (el prefijo `/`) va a `console-spa` y la ruta `console` (`/api/console`) va a `console-bff`. Las cabeceras de seguridad (HSTS, CSP, marcos, referrer, COOP, tipos) las pone el gateway; nginx no pone ninguna.
- Los flujos, las cuentas de servicio y los casos bloqueados son los de `platform/network/flows.yaml` y `forbidden.yaml` (U1). Los `Server` de Linkerd los genera U1; los charts de esta unidad no declaran ninguna política de red.
- La matriz rol × endpoint es [`contracts/openapi/role-endpoint-matrix.md`](../contracts/openapi/role-endpoint-matrix.md) (las filas `console-bff`); `bff/tools/role_matrix.py --check` la compara con C03 y con el registro de contratos.

## Documentos de diseño

| Etapa | Documentos |
|---|---|
| Diseño funcional | [`business-logic-model.md`](../aidlc-docs/construction/console/functional-design/business-logic-model.md), [`business-rules.md`](../aidlc-docs/construction/console/functional-design/business-rules.md), [`domain-entities.md`](../aidlc-docs/construction/console/functional-design/domain-entities.md), [`frontend-components.md`](../aidlc-docs/construction/console/functional-design/frontend-components.md) |
| Requisitos no funcionales | [`nfr-requirements.md`](../aidlc-docs/construction/console/nfr-requirements/nfr-requirements.md), [`tech-stack-decisions.md`](../aidlc-docs/construction/console/nfr-requirements/tech-stack-decisions.md) |
| Diseño no funcional | [`nfr-design-patterns.md`](../aidlc-docs/construction/console/nfr-design/nfr-design-patterns.md), [`logical-components.md`](../aidlc-docs/construction/console/nfr-design/logical-components.md) |
| Infraestructura | [`infrastructure-design.md`](../aidlc-docs/construction/console/infrastructure-design/infrastructure-design.md), [`deployment-architecture.md`](../aidlc-docs/construction/console/infrastructure-design/deployment-architecture.md) |
| Código | [`bff-api.md`](../aidlc-docs/construction/console/code/bff-api.md), [`bff-logic.md`](../aidlc-docs/construction/console/code/bff-logic.md), [`spa.md`](../aidlc-docs/construction/console/code/spa.md) |
| Cierre | [`cierre-demo.md`](../aidlc-docs/construction/console/evidence/cierre-demo.md) |

**Runbooks:** no hay ninguno. Los de la unidad (el Paso 19 del plan: alertas, runbooks y dashboard) están diferidos por la demo (T2); esa mitad de «un enlace por runbook» se cumple vacía.

## Correr el BFF con dobles y la SPA con Vite

Desde `vectra-risk/`, en serie (la máquina se comparte). Los detalles, los puertos y los dobles están en [`spa.md` §2](../aidlc-docs/construction/console/code/spa.md); aquí solo la forma:

```bash
npm ci --ignore-scripts
uv run pytest console/bff/tests -q -p no:cacheprovider --rootdir=console/bff        # el BFF contra los dobles de los cinco destinos
VECTRA_E2E_PORT=47180 VECTRA_E2E_ORIGIN=http://127.0.0.1:47173 uv run python console/bff/tests/doubles/bff_e2e_server.py   # el BFF real, los dobles y un emisor OIDC de prueba en un solo proceso
npm run -w console/spa build && npm exec -w console/spa -- size-limit                # el build y el presupuesto del JavaScript inicial
make -C console check                                                                  # todo lo de abajo, en orden
```

[`bff_e2e_server.py`](bff/tests/doubles/bff_e2e_server.py) nunca usa el 8080 ni el 8081. `make -C console e2e-spa` corre Playwright (Chromium y Firefox) contra el build servido con `vite preview` y falla, diciendo cómo instalarlos, si faltan los navegadores.

## Constantes y configuración

Hay dos clases de valores y no se mezclan (INF-U10-01, INF-U10-03):

- **Constantes del código**: los plazos, el *breaker*, las conexiones por réplica y los refrescos. Viven en [`bff/src/console_bff/config.py`](bff/src/console_bff/config.py) y en [`spa/src/config/constants.ts`](spa/src/config/constants.ts). Cambiarlas es un cambio de código con su PR; **ninguna** es una variable de entorno ni una clave de `config.json` (una prueba y una regla de `conftest` lo comprueban).
- **Configuración por entorno**: lo que cambia de un clúster a otro.
  - **`config.json` de la SPA** (lo genera el chart `console/chart/spa` desde sus values y lo monta como `ConfigMap` en `/etc/vectra/console-spa/`, sin `subPath`): exactamente `oidc.authority`, `oidc.client_id`, `redirect_uri`, `stepup_redirect_uri` y `grafana.bias_dashboard_uid`. El único valor por entorno es el `hostname` (el de `identity-edge/gateway/values/<env>.yaml`). No lleva secretos: el cliente `vectra-console` es público (PKCE).
  - **Variables del BFF** (las pone el `ConfigMap` de `console/chart/bff`): `VECTRA_CASE_URL`, `VECTRA_GOVERNANCE_URL`, `VECTRA_REGISTRY_URL`, `VECTRA_EXPLAINABILITY_URL`, `VECTRA_BIAS_URL`, `VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL`, `VECTRA_CA_BUNDLE` y `VECTRA_OTLP_ENDPOINT`. Si falta una obligatoria, o hay una URL `https` sin `VECTRA_CA_BUNDLE`, el proceso sale con código 2 antes de escuchar.
  - **El emisor.** `VECTRA_OIDC_ISSUER` es el `iss` de los tokens que emite el navegador, el mismo `authority` de la SPA y el que valida el gateway: `https://<hostname>/auth/realms/vectra`. El JWKS va por el host interno de Keycloak (`jwt.jwks_uri` de `routes.yaml`) con la CA de `vectra-internal-ca`. Los dos son values separados del chart del BFF para poder cambiar uno sin tocar el otro.

## Charts y Applications

- `chart/bff` (`vectra-app`): `Deployment` con HPA de 2 a 6 (en kind, 2 y 2), `maxSurge: 1` y `maxUnavailable: 0`, PDB, reparto por zona, `vectra-high`, `ServiceMonitor` en el 8081 y el `ConfigMap` de variables. En kind, `chart/bff/values-kind.yaml` baja solo el máximo del HPA y el request de memoria a 128 MiB (decisión del usuario, 2026-11-13); staging y producción siguen en 256 MiB.
- `chart/spa` (`vectra-edge`): 2 réplicas fijas con `vectra.io/hpa-exempt`, `maxSurge: 100%` y `maxUnavailable: 0`, PDB, reparto por zona, `vectra-normal`, el `ConfigMap` de `config.json` y `checksum/config` en el pod.
- Los valores de cada entorno están en `vectra-risk-gitops/values/<env>/console-bff.yaml` y `console-spa.yaml`. `components.yaml` tiene una entrada por pieza (wave 5) y `vectra-risk-gitops/generate.py` escribe su `Application` por entorno, sin auto-sync.
- Las comprobaciones sin clúster: `make -C console policy-chart policy-chart-u1 quota-flows gitops` (render, `kubeconform`, `conftest`, las políticas de admisión de U1, la cuota y los flujos).

## Imágenes

Dos imágenes, una por pieza. Las construye este repositorio; el *push* y el digest real los hace el **operador** en la verificación consolidada de U12 Paso 18. Sin firma, SBOM ni escaneo (diferidos por la demo, T1). **Estos comandos no se ejecutan en la tarea de despliegue más allá del `build` y las comprobaciones locales.**

### Construir (desde `vectra-risk/`)

```bash
make -C console image-bff image-spa
# docker build -t localhost:5001/vectra/console-bff:dev -f console/bff/Dockerfile .   (contexto: la raíz de vectra-risk/)
# docker build -t localhost:5001/vectra/console-spa:dev -f console/spa/Dockerfile .
```

- **`console-bff`**: Python 3.12 por digest, solo el runtime y sus dependencias del workspace (`vectra_contracts`, `vectra_common`), sin `pytest`, `hypothesis`, `ruff`, `mypy` ni `hatchling`. Usuario `65532:65532`, igual que el `runAsUser` del chart. Orden: `python -m console_bff.app`.
- **`console-spa`**: dos etapas. `build` (Node 22 por digest, `npm ci --ignore-scripts` y `npm run -w console/spa build`) y la final, `nginx-unprivileged` por digest con `dist/` **sin** `.vite/`, sin Node, sin fuentes y con [`spa/nginx.conf`](spa/nginx.conf). Usuario `101:101`. nginx corre con el sistema de archivos de solo lectura (`/tmp` es un `emptyDir`) y sirve `config.json` desde el directorio que monta el chart.
- `nginx.conf`: `no-store` en `index.html`, `config.json` y en el fallback; `immutable` en `assets/`; fallback a `index.html` solo para rutas sin extensión (`/callback`, `/stepup-callback`, `/casos/<id>`); un archivo con extensión que no existe es 404; `gzip` para JavaScript, CSS y JSON; ninguna cabecera de seguridad.

### Comprobar (local, sin clúster)

```bash
platform/.tools/bin/hadolint console/bff/Dockerfile console/spa/Dockerfile
make -C console image-test       # los dos contenedores reales con lo que pone el chart (--read-only, el usuario del chart, puertos libres)
docker run --rm --entrypoint nginx localhost:5001/vectra/console-spa:dev -t
```

### Publicar (operador, U12 Paso 18)

```bash
docker push localhost:5001/vectra/console-bff:dev
docker push localhost:5001/vectra/console-spa:dev
docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/vectra/console-bff:dev
docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/vectra/console-spa:dev
```

El digest sale en el `inspect` (`localhost:5001/vectra/<imagen>@sha256:…`). Un PR lo escribe en `image.digest` de `vectra-risk-gitops/values/kind/console-bff.yaml` y `console-spa.yaml` y regenera las Applications con `uv run python vectra-risk-gitops/generate.py`. Hasta entonces los charts renderizan con los digests de ejemplo (`sha256:…0008` y `…0009`) y los pods quedarían en `ImagePullBackOff`.

## Flujo de release de la SPA y rollback de emergencia

Según INF-U10-02: la SPA se publica como una imagen nueva, con su digest, que un PR escribe en `vectra-risk-gitops/values/<env>/console-spa.yaml`; Argo CD sincroniza con `maxSurge: 100%` y `maxUnavailable: 0` y la afinidad `vectra-spa-route` del gateway deja que una pestaña termine de cargar del mismo pod durante el cambio. **Un rollback es un release nuevo** (una imagen nueva con el código anterior). Volver al digest anterior es solo de emergencia: se revierte el PR del digest y se sincroniza.

**Diferido por la demo** (el README lo dice para que nadie lo dé por hecho): el workflow `console-spa-release.yml` y la comprobación `spa-previous-digest-check` (Paso 20, T4); las etapas `previous` de la imagen, con la copia de los recursos de la versión anterior y la etiqueta con su digest, que se difieren junto con `version` y `VersionBanner` (recorte funcional, P-15); y el runbook `console-spa-emergency-rollback` (Paso 19, T2). Sin esas etapas, una pestaña abierta durante un release puede pedir un archivo con hash que ya no existe: recarga la página.

## Qué falta (diferido por la demo)

Firma, SBOM, escaneo, `npm audit` y Trivy (T1); alertas, runbooks y `console.json` (T2); k6, Lighthouse CI, `mutmut` y Stryker (T3); los workflows de CI (T4); y la verificación en kind (Paso 22), que consolida U12. La lista completa y lo pendiente en U12 están en [`cierre-demo.md`](../aidlc-docs/construction/console/evidence/cierre-demo.md).
