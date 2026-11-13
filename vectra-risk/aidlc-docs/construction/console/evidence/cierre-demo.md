# Cierre de U10 con alcance acotado a la demo

**Estado: pendiente de revisión; verificación en kind pendiente de U12 Paso 18.** U10 queda cerrada **para kind** (`demo-kind-alcance.md` §3, U10), no para staging ni prod. U10-T01 a U10-T04 escribieron el BFF y la SPA; U10-T05 escribe lo que los lleva al clúster: las dos imágenes, los dos charts, las dos Applications, el README y este cierre. Lo que la consola sostiene en las demos (enmienda §1): el flujo base (`CasesInbox`, `CaseDetail`, `ExplanationPanel`, `DecisionForm`; el BFF llama a U8 por F10), D1 (`POST /api/console/models` da 422 y la SPA muestra `en_sincronizacion`) y D2 (`cumplimiento-1` abre `Freezes` y `FreezeContextView` y resuelve con `ResolveFrozenDialog` y el step-up MFA). D3 y D4 no pasan por la consola.

## Comprobado

Lo del codificador, sin clúster, desde `vectra-risk/` (la salida de cada comando está en `bitacoras/U10-T01.md` a `bitacoras/U10-T05.md`):

| Tarea / Paso | Punto | Comando | Resultado |
|---|---|---|---|
| U10-T01, Pasos 1 a 4 | Funciones puras del BFF (`object_rules`, `errors`), cobertura de ramas del 100 %; `mutmut` diferido (T3) | `make -C console test-bff` (segundo comando) | rc 0 |
| U10-T02, Pasos 5 a 9 | Los cinco clientes con *breaker*, las 30 rutas, métricas, errores del navegador, matriz rol × endpoint (270 celdas) y el proceso real con `SIGTERM` → 0; cobertura ≥ 90 % | `make -C console test-bff` | rc 0 |
| U10-T03, Pasos 10 a 12 | La SPA: configuración, autenticación, step-up (PoC en Chromium y Firefox), inactividad; `version` diferido (P-15) | `make -C console test-spa e2e-spa` | rc 0; 100 % de ramas en `src/stepup/**` |
| U10-T04, Pasos 13 a 16 | Las vistas de la demo, la tabla de rutas por rol, el build con presupuesto de JavaScript inicial, la CSP de U2 con Trusted Types y `axe` | `make -C console test-spa e2e-spa` | rc 0 |
| U10-T05, 17 | Imágenes: `hadolint`; usuario `65532:65532` (BFF) y `101:101` (SPA); sin `pytest`/`hypothesis`/`ruff`/`mypy`/`hatchling` en el BFF; `nginx -t`; sin `.vite/`, `config.json`, `version.json`, mapas ni Node en la SPA; cada `FROM` por digest (2 de 2 en cada `Dockerfile`); sin etiqueta `vectra.io/previous-digest` | `make -C console image-bff image-spa` y los comandos de CA-1 | `65532:65532 ["python","-m","console_bff.app"]`; `101:101 ["nginx","-g","daemon off;"]`; `OK-bff`; `OK-entrada`; `OK-spa` |
| U10-T05, 17 y 18 | Los dos contenedores reales con lo que pone el chart (`--read-only`, el usuario del chart, puertos libres): `/healthz` y `/readyz` 200 con los cinco destinos caídos; 401 sin token y 200 con un token del emisor del chart (JWKS por `https` con la CA de prueba en la ruta del chart); sin `VECTRA_BIAS_URL` → 2; `https` sin CA → 2; `docker stop -t 20` → 0 en 0,5 s; nginx: fallback sin extensión (`/callback`, `/stepup-callback`, `/casos/<uuid>`) con `no-store`, `config.json` byte a byte, `immutable` y `gzip` en `assets/`, 404 para lo demás, sin cabeceras de seguridad, sin `/tmp` no arranca | `make -C console image-test` | `8 passed`; **memoria en reposo:** BFF 90,79 MiB, nginx 9,41 MiB |
| U10-T05, 18 | Render, esquema y `conftest` de los dos charts en kind, staging y prod: BFF 7 documentos y SPA 5 por entorno | `make -C console policy-chart` | `Valid: 7, Invalid: 0` y `Valid: 5, Invalid: 0` ×3; `conftest` 469 y 335 pruebas por documento y 10 en conjunto, sin fallos |
| U10-T05, 18 | **Mundo cerrado** chart → SPA → realm de U2 → gateway de U2: `config.json` con las claves de `SCHEMA` (pasa por el `parseConfig` real), `client_id` y los dos `redirect_uri` del realm de cada entorno, `authority` = `https://<hostname>` + `jwt.issuer_path`, `VECTRA_OIDC_ISSUER` = `authority`, `VECTRA_JWKS_URL` = `jwt.jwks_uri`, las cinco URL de F10 a F14, nombres y puertos de `flows.yaml` y `routes.yaml`; una mutación del render por regla | `uv run pytest console/bff/tests/unit/test_chart.py`; `npm run -w console/spa test -- chart-config` | `180 passed`; `10 passed` |
| U10-T05, 18 | Admisión de U1 (Kyverno, `rego` y `--namespace hpa`) por chart y entorno, y las pruebas de Kyverno | `make -C console policy-chart-u1` | ver «Cifras» abajo |
| U10-T05, 18 | Cuota recalculada desde el render de prod (BFF 7 pods, SPA 4 pods, proxy y 30 %) frente a `quotas.yaml`, flujos F02, F03, F10 a F14, F50 y F60, casos bloqueados de INF-U10-04 y `Server` generados | `make -C console quota-flows` | ver «Cifras» abajo |
| U10-T05, 21 | Applications `console-bff` y `console-spa` (wave 5, sin `syncPolicy.automated`) en los tres entornos | `make -C console gitops` | ver «Cifras» abajo |
| U10-T05, 21 | Trazabilidad con la lista «Diferido por la demo»; cada BR-U10 con una prueba | `make -C console traceability`; `git grep` de cada BR | ver «Cifras» abajo |
| U10-T05, 23 | README (arquitectura, cómo correr, constantes frente a `config.json`, variables, imágenes, flujo de release y rollback, lo diferido) | `make -C console links`; `forbidden_phrases.py` | ver «Cifras» abajo |
| U10-T05, 24 | `make -C console check` (todo lo anterior, en orden) | `make -C console check` | ver «Cifras» abajo |
| U10-T05, candidata C-1 | «Pool agotado»: la llamada 21 va a una ruta que responde al instante; con 19 conexiones ocupadas responde 200; `Upstreams` pasa el límite de cada destino | `pytest console/bff/tests/integration/test_clients.py -k "pool or connections"` | `3 passed`; M11, M12 y «sin pasar el límite» hacen fallar una prueba cada una (`bitacoras/U10-T05.md`) |
| U10-T05, presupuesto de memoria de kind | **Con y sin U10:** `requested_gib()` = 10,6328 GiB en la base (sin U10) y **11,0234 GiB** con U10; diferencia 0,3906 GiB = 2 × (128 + 20) MiB + 2 × (32 + 20) MiB (± 0,001). `BUDGET_GIB` 10,7 → 11,1 | `uv run pytest platform/tests/test_kind_profile.py` | `6 passed` |
| U10-T05, presupuesto de memoria de kind | **Proyección** con lo que aún no tiene Application: U8 (`case-service`, `case-worker` y `core-banking-mock`) 0,7422 GiB (`DECISIONES-LOOP.md` §9) | suma sobre la cifra medida | **Proyección: 11,0234 + 0,7422 = 11,7656 GiB (≈ 11,77)**, por debajo de los 13,0 GiB de parada (con (a), 256 MiB, habría sido 12,0156). U12 no despliega `Deployment` en kind |

### Cifras de la corrida final

Se completan al final de la ronda, con las salidas de `bitacoras/U10-T05.md`.

## Decisiones

- **P-1 = (b), decidida por el usuario el 2026-11-13:** el request de memoria de `console-bff` en kind es de **128 MiB** por réplica (`chart/bff/values-kind.yaml`, por `kind_values`); staging y prod siguen en los 256 MiB de INF-U10-01 y los limits (512 MiB), las réplicas, el PDB y la estrategia no cambian en kind. **Se aparta de «kind igual a staging»** de `deployment-architecture.md`, solo en ese request y por decisión del usuario (mismo patrón que la opción (c) de `DECISIONES-LOOP.md` §7 para U6 y que U8 y U11). La SPA no cambia (32 MiB). Dato de CA-4: el BFF en reposo usa 90,79 MiB y nginx 9,41 MiB; la medida con el pod real y el proxy es de U12.
- **P-2 = (a), por omisión:** dos charts, `console/chart/bff` y `console/chart/spa`, uno por `Application` (el plan §1 tenía uno; queda una nota en §1 y una candidata).
- **P-3 = (a), por omisión:** defaults de producción en cada `values.yaml`; `values-kind.yaml` por `kind_values` con lo que las pruebas de U1 deben ver; hostname y emisor en `vectra-risk-gitops/values/<env>/`. Una prueba compara los dos renders de kind (`render_env` no pasa `values/<env>/<nombre>.yaml`, C-9).
- **P-4 = (a), por omisión:** `VECTRA_OIDC_ISSUER` es el emisor **público** (`https://<hostname>/auth/realms/vectra`), igual al del gateway y al `authority` de la SPA; el JWKS es `jwt.jwks_uri` de `routes.yaml`, con la CA de `vectra-internal-ca`. Son dos values separados y fáciles de cambiar. **Riesgo abierto:** U02-T21 medirá qué emisor publica Keycloak de verdad y corregirá los charts de las demás unidades; el cambio, si hace falta, es el value `oidc.issuer` de `values/<env>/console-bff.yaml` (y `authority` si fuese el de la SPA).
- **P-5 = (a), por omisión:** `grafana.bias_dashboard_uid` = `vectra-bias` (patrón de los dashboards de U1); nadie lo lee mientras `GrafanaEmbed` esté diferido.
- **P-6 = (a), por omisión:** la prueba admite la diferencia del redondeo del diseño (cada valor recalculado dista menos de 0,06 del declarado; el request de memoria del BFF recalculado da 2,4527 GiB y `quotas.yaml` dice 2,4); candidata para que U1 suba la línea a 2,46.
- **Etapas `previous` y `version`:** no entran (recorte funcional, P-15). `spa.md` §11 decía «con las etapas `previous`»; se corrigió.
- **«Audiencias» del Paso 18:** el plan dice «`ConfigMap` de URLs y audiencias», pero el BFF no lee ninguna variable de audiencia: U0 valida `aud = console-bff` (el nombre del servicio) y el realm lo pone con el mapper `aud-console-bff`. No se inventó una variable (candidata de corrección del plan).
- **Un solo `emptyDir` en la SPA:** el plan pide `emptyDir` en `/tmp` y «en el directorio de caché temporal de nginx»; `nginx.conf` pone el `pid` y todos los temporales en `/tmp` (INF-U10-02), así que un solo `emptyDir` basta. Sin él, nginx no arranca (lo prueba `image-test`).
- **Usuario de la SPA:** `101:101` (el de `nginx-unprivileged`) y no `65532`; el chart y la imagen coinciden.
- **No comprobado (NFR-U10-10):** que el HPA escale de 2 a 6 con carga real al 70 % de CPU; la medida con carga es la prueba de P-U10-11 (k6, diferido, T3). Lo que hay es la regla de `conftest` sobre el render.
- **No comprobado (NFR-U10-22):** el simulacro de pérdida de una zona; solo el reparto por zona y el PDB (`minAvailable: 1`) del render.

## Pendiente en U12

Lo que verifica U12 Paso 18 (enmienda §8), más el push de las imágenes:

| Punto | Qué verifica U12 |
|---|---|
| **Login por el gateway real con Keycloak real** | Redirección, `/callback` y la recarga con `prompt=none`, con `analista-1` (escenario 1 del Paso 22) |
| **La CSP del gateway** | Cero `securitypolicyviolation` con el perfil `spa` real y con la política de `/auth/**` (`frame-ancestors 'self'`), que el servidor de pruebas no reproduce. Lo que sí se probó sin clúster: el `authority` es del **mismo origen** que la SPA, así que `connect-src 'self'` y `form-action 'self'` lo admiten, y nginx no añade ninguna CSP propia. La candidata (C-5) sigue abierta |
| **Step-up de `cumplimiento-1`** | Ventana emergente, `/stepup-callback` servido por nginx, `acr = mfa` y `ResolveFrozenDialog` (D2) |
| **Conectividad F03, F10, F11 y F14** (escenario 2) | Y los casos bloqueados de INF-U10-04 |
| **El `iss` de los tokens** | Que el `iss` de los tokens del navegador sea el `VECTRA_OIDC_ISSUER` del BFF (P-4) **y el de cada destino**, que recibe ese mismo token por F10 a F14 (sus charts esperan `keycloak-admin`; candidata) |
| **Push de las dos imágenes y digests reales** | `console/README.md`, sección «Imágenes»: `docker push` y los digests en `vectra-risk-gitops/values/kind/console-bff.yaml` y `console-spa.yaml`, más `generate.py` |
| **Retirar el eco de U2 y la `ServiceAccount` temporal de U4, antes del sync** | `identity-edge/tests/e2e/echo/manifests.yaml` usa el nombre `console-bff`, y el runbook de U4 crea una `ServiceAccount` `console-bff` de forma temporal (C-6): el chart de U10 ya la crea |
| **`vectra-internal-ca` en `vectra-app`** | Que el `ConfigMap` exista en el namespace y el JWKS responda por `https` |
| **Prometheus y la afinidad** | Que Prometheus raspe el `ServiceMonitor` del BFF y que la cookie `vectra-spa-route` del gateway llegue a los pods reales |
| **Memoria real del BFF** | Frente al request de kind de P-1 (128 MiB); el dato de la imagen es 90,79 MiB en reposo |

## Diferido por la demo

Lista que acepta `platform/tests/test_traceability.py --unit console --all` (P-4 de la enmienda, `demo-recorte-funcional.md` §2.4 y §6). Cada fila lleva el identificador, el paso del plan y la cita.

| Identificador | Paso del plan | Cita del recorte | Qué falta |
|---|---|---|---|
| INF-U10-05 | Paso 19 (reglas, runbooks y dashboard) | Enmienda §3 U10, fila «19 · 20»; T2 | Las reglas de grabación, los runbooks y el dashboard |
| NFR-U10-01 | Paso 21 (k6 con el perfil por rol) y Paso 22, punto 5 | Enmienda §3 U10, fila «21»; T3 | La prueba de carga con 200 usuarios |
| NFR-U10-04 | Paso 21 (Lighthouse CI) y Paso 22, punto 5 | Enmienda §3 U10, fila «21», y §2 regla 3; T3 | Lighthouse CI con el perfil de red del banco |
| NFR-U10-21 | Paso 19 (regla de grabación del SLO y alerta de *burn rate*) | Enmienda §3 U10, fila «19 · 20»; T2 | El SLO y su alerta |
| P-U10-06 | Paso 12 (`version`) y Paso 17 (etapas `previous`) | Enmienda §3 U10, filas «12» y «17 · 18»; §6 P-15 | Las etapas con la versión anterior y la etiqueta de su digest |
| P-U10-10 | Paso 19 (las seis alertas) | Enmienda §3 U10, fila «19 · 20»; T2 | Las seis alertas |
| BR-U10-14 | Paso 14 (`DecideDataSourceDialog` y `PrePostReportView`) | Enmienda §3 U10, fila «14 Gobierno y sesgo» | Las dos vistas de gobierno de fuentes y del informe previo y posterior |
| BR-U10-16 | Paso 14 (`GrafanaEmbed`) | Enmienda §3 U10, fila «14 Gobierno y sesgo» | El tablero de sesgo incrustado |
| BR-U10-21 | Paso 12 (`version` y `VersionBanner`) | Enmienda §3 U10, fila «12», y §6 P-15 | El aviso de versión nueva |

Lo diferido sin identificador propio (no lo mira la herramienta; cada uno con su destino):

| Qué | Paso del plan | Cita del recorte | Destino |
|---|---|---|---|
| Firma, SBOM, escaneo, `npm audit` y Trivy | Paso 17 | T1; alcance §3 U10, fila «17» | Fuera de la demo; las imágenes van fijadas por digest, sin firmar |
| Las etapas `no-previous` y `previous`, la etiqueta `vectra.io/previous-digest` y la prueba con `PREVIOUS_IMAGE` | Paso 17 | Enmienda §3 U10, fila «17 · 18»; §6 P-15 | Vuelven con `version`; el `manifest.json` de Vite deberá ir en la imagen, fuera de la raíz servida |
| Las seis alertas, los cinco runbooks y `console.json` | Paso 19 | T2 | Fuera de la demo |
| `console.yml`, el nocturno, `console-spa-release.yml` y `spa-previous-digest-check` | Paso 20 | T4 | Fuera de la demo; las comprobaciones corren en `make -C console check` |
| El script k6, Lighthouse CI, `k6 inspect` y `lhci`; `mutmut` y Stryker | Pasos 21, 4 y 16 | T3 | Fuera de la demo |
| Del Paso 22: aprobador distinto del proponente, los escenarios 3 a 6 y NVDA | Paso 22 | Enmienda §3 U10, fila «22 Kind» | Fuera de la demo; el login, el step-up de `cumplimiento-1` y la conectividad los verifica U12 (arriba) |
| Las vistas diferidas de los Pasos 13 y 14 | Pasos 13 y 14 | `spa.md` §4 | Fuera de la demo |
| `values-kind-demo.yaml` y el perfil de 1 réplica | Paso 18 | T6; DD-3 b | Descartado: kind mantiene las 2 réplicas |
