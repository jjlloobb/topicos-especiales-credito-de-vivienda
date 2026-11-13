# U10-T05 — Imágenes, charts, Applications, trazabilidad, documentación y cierre acotado de `console`

**Unidad:** U10 `console`
**Historias que implementa:** US-609 (HPA del BFF en su chart, Paso 18), según la trazabilidad del plan (§3). Los Pasos 17, 21, 23 y 24 no tienen historia propia: empaquetan, despliegan por GitOps y cierran lo que implementan los Pasos 1 a 16.
**Depende de:**
- **U10-T04 fusionada en `main`** (PR: **por completar al fusionar**; hash de fusión: **por completar al fusionar**): las vistas de la demo, la tabla de rutas por rol, el build de Vite con `build.manifest` y `aidlc-docs/construction/console/code/spa.md`, cuya §11 dice lo que queda para esta tarea;
- en `main`, como contratos (comprobado al redactar, sobre `82c1718`):
  - U0: `vectra_common.ops_server` (`/metrics`, `/healthz` y `/readyz` en 8081; la API en 8080); `vectra_common.authn.authenticator_from_env` lee `VECTRA_OIDC_ISSUER` y `VECTRA_JWKS_URL` y fija `audience=service_name` (`authn.py`, líneas 79 a 87); `vectra_common.telemetry.ENDPOINT_ENV` = `VECTRA_OTLP_ENDPOINT`;
  - U1, red (`platform/network/flows.yaml`): las identidades `console-spa` (línea 83: `vectra-edge`, SA `console-spa`) y `console-bff` (línea 89: `vectra-app`, SA `console-bff`); F02 y F03 (líneas 150 y 151); F10 a F14 (líneas 160 a 164), todos al 8080; F50 con `console-bff` (línea 220); F60 a `ns:vectra-app` y `ns:vectra-edge` en 8081 (línea 221); F61 (línea 227); las rutas `model-list` y `console` de `http_routes.governance-service` (líneas 51 a 62). Los `Server` `console-spa-8080` (`platform/network/generated/kind/vectra-edge.yaml`) y `console-bff-8080` (`vectra-app.yaml`) ya están generados, con selector `app.kubernetes.io/name`. X09 y los cuatro casos `U10` están en `platform/network/forbidden.yaml` (líneas 20 y 22 a 25);
  - U1, cuota (`platform/policies/quotas/quotas.yaml`): `U10: { requests: [3.19, 2.4], limits: [13.7, 5.7] }` en `vectra-app` (línea 12) y `U10: { requests: [0.78, 0.26], limits: [3.64, 0.97] }` en `vectra-edge` (línea 17);
  - U1, Kyverno: el fixture `console-spa` (`platform/policies/kyverno/fixtures/resources.yaml`, línea 309) y sus dos casos en `kyverno-test.yaml` (líneas 113 y 331: `exempt-needs-two-replicas` y `require-pdb`, los dos `pass`);
  - U1, pruebas: `FIXED_WAVES` fija `console-bff` y `console-spa` en 5 (`platform/tests/test_waves.py`, líneas 33 y 34); `EXPECTED_WAVES[5]` **sin** ninguna de las dos (`platform/tests/test_platform.py`, línea 285); `BUDGET_GIB = 10.7` (`platform/tests/test_kind_profile.py`, línea 27);
  - GitOps: `vectra-risk-gitops/components.yaml` **sin** entradas de U10; `values/<env>/` existe (hoy solo `model-serving` y `scoring-explainability`); `envs/<env>/values.yaml` trae `imageRegistry`;
  - U2, gateway (`identity-edge/gateway/routes.yaml`): la ruta `spa` (líneas 118 a 129: prefijo `/`, backend `console-spa` en `vectra-edge`, 8080, afinidad por la cookie `vectra-spa-route`) y la ruta `console` (líneas 130 a 147: `/api/console`, backend `console-bff` en `vectra-app`, 8080, `azp = vectra-console`); el perfil `spa` con su CSP (líneas 73 a 76); `jwt.issuer_path` y `jwt.jwks_uri` (líneas 59 y 60); `hostname` por entorno en `identity-edge/gateway/values/<env>.yaml` (línea 2: `vectra.localtest.me`, `vectra.staging.banco.internal` y `vectra.banco.internal`); el `ReferenceGrant` `edge-routes` ya nombra el Service `console-bff` (`generated/kind/referencegrants.yaml`);
  - U2, realm (`identity-edge/keycloak/realm/realm.kind.yaml`): el cliente **público** `vectra-console` (línea 834), con PKCE S256, `redirectUris` `https://$(env:PUBLIC_HOSTNAME)/callback` y `/stepup-callback` (líneas 849 a 851) y el mapper `aud-console-bff` (líneas 857 a 861). `PUBLIC_HOSTNAME` sale de `vectra.publicHostname` de `identity-edge/keycloak/values/<env>.yaml` (línea 6 del de kind). **No existe** un cliente `console-bff` ni ninguna entrada de la consola en `platform/kind/vault_paths.py`: el BFF usa el token del usuario y no tiene secretos (`deployment-architecture.md` §3: «`ExternalSecret`: Ninguno»);
  - U3, U4, U7, U8 y U9: `decision-registry-service` (F13), `governance-service` (F11), `explainability-service` (F12), `case-service` (F10) y `bias-monitoring-service` (F14), los cinco en 8080.

Sin clúster (AUTONOMIA-01). Todo se verifica con `hadolint`, `docker build`, `helm template`, `kubeconform`, `conftest`, `kyverno test`, Docker local contra dobles y las pruebas de `platform/`. **Nada de `kubectl apply`, `helm install`, `argocd` ni sync.**
**Rama:** `tarea/U10-T05`, desde `origin/main`.

Bloque F del plan de U10 (`aidlc-docs/construction/plans/console-code-generation-plan.md`) más el cierre: la tarea «F+cierre (17, 18, 21, 23, 24)» de `aidlc-docs/construction/plans/demo-recorte-funcional.md` §8, la quinta y última de U10. La enmienda rige donde difiera del alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 17 Imágenes | **E\*** | Entran las dos imágenes (base por digest, `runAsNonRoot`, `readOnlyRootFilesystem`), `nginx.conf`, `hadolint` y la prueba de `nginx.conf`. Se difieren el escaneo, el SBOM y la firma (T1) y, con `version`, las etapas `no-previous` y `previous`, la copia de los recursos anteriores, la etiqueta `vectra.io/previous-digest` y la prueba con `PREVIOUS_IMAGE` | Alcance §3 U10, fila «16 Resumen del frontend · 17 Imágenes: E · E\*, T1 en el 17»; enmienda §3 U10, fila «17 · 18: T1 (más las etapas `previous` si se difiere `version`) · T6». `version` **está** diferido: enmienda §3 U10, fila «12», y §6 P-15 («Diferir `version`»), aplicado en U10-T03 |
| 18 Chart, cuotas y flujos | **E\*** | Entra completo, con el perfil de DD-3 b: sin `values-kind-demo.yaml` y con 2 réplicas. El único ajuste de kind fuera del plan es el request de memoria del BFF (P-1) | Alcance §3 U10, fila «18: E\*, T6»; enmienda §3 U10, fila «17 · 18»; DD-3; `DECISIONES-LOOP.md` §7 |
| 19 Alertas, runbooks y dashboard | **D** | Entero fuera. Queda `[ ]` con «diferido por la demo (T2)» | Alcance §3 U10, fila «19: D, T2»; enmienda §3 U10, fila «19 · 20: D» |
| 20 Workflows de CI y de release | **D** | Entero fuera. Queda `[ ]` con «diferido por la demo (T4)». Sus comprobaciones corren en `make -C console check` | Alcance §3 U10, fila «20: D, T4»; enmienda §3 U10, fila «19 · 20: D» |
| 21 Applications, carga y trazabilidad | **E\*** | Entran las dos Applications y la trazabilidad con la lista «Diferido por la demo». Se difieren el script k6 y Lighthouse CI | Alcance §3 U10, fila «21: E\*, Carga (T3)»; enmienda §3 U10, fila «21: k6 y Lighthouse CI (T3); trazabilidad con lista», y §2 regla 3 |
| 22 Verificación en kind | — | Queda `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)». La fila de §3 dice que entran el escenario 1 (PoC y Playwright con Keycloak real: login y step-up de `cumplimiento-1`) y el 2 (conectividad F03, F10, F11, F14), y que se difieren aprobador ≠ proponente, el 3 a 6 y NVDA. §8 pasa los que entran a U12 | Enmienda §3 U10, fila «22 Kind», y §8 |
| 23 Documentación | **E** | Completo | Enmienda §3 U10, fila «23 · 24: E · E\*» |
| 24 Cierre de la unidad | **E\*** | Cierre acotado, con `evidence/cierre-demo.md`. Se difiere la evidencia de kind en el PR | Enmienda §3 U10, fila «23 · 24», y §8; alcance §2.4 |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda del 2026-11-09.

Lo que la consola sostiene en las demos (enmienda §1):
- **Flujo base:** el presentador decide en la SPA (`CasesInbox`, `CaseDetail`, `ExplanationPanel`, `DecisionForm`) y el BFF llama a U8 por F10 (§1.0, punto 4). El arranque de la política y del modelo pasa por `POST /api/console/policies` y `POST /api/console/models` (§1.0, punto 1).
- **D1:** `ingeniero-1` → BFF `POST /api/console/models` → 422; la SPA muestra `en_sincronizacion` con refresco de 3 s (§1.1).
- **D2:** `cumplimiento-1` abre `Freezes` y `FreezeContextView` (F14) y resuelve con `ResolveFrozenDialog` y step-up MFA (F11) (§1.2). Sin `/stepup-callback` servido por nginx no hay reactivación en vivo.
- **D3 y D4:** no pasan por la consola (§1.3 y §1.4).

U10-T01 a U10-T04 escribieron el código. Esta tarea escribe **lo que lo lleva al clúster**: las dos imágenes, los charts, las Applications y el cierre.

---

**Dos lecciones que esta tarea aplica:**
- **U04-T06 y U04-T08** (`revisiones/U04-T06/ronda-1.md`, F-01) y U11-T03 (CA-4): un chart que renderiza bien no prueba que el contenedor arranque. Aquí los **dos** contenedores reales arrancan con las variables y los archivos **que pone el chart** (CA-4): el BFF con su `ConfigMap`, y nginx sin root, con el sistema de archivos de solo lectura y el `config.json` que monta el chart.
- **Enmienda §8**: los revisores encontraron cuatro defectos que habrían roto el flujo base en kind sin que ninguna prueba fallara. En U10 los equivalentes son cuatro, y los cuatro dejan la pantalla en blanco o toda la API en 401:
  1. un `config.json` con una clave de más o de menos: `parseConfig` lanza `ConfigError` y la SPA no arranca (`console/spa/src/config/load.ts`);
  2. un `authority`, un `client_id` o un `redirect_uri` que no es el del realm de U2: el login falla en Keycloak;
  3. un `VECTRA_OIDC_ISSUER` del BFF distinto del `iss` de los tokens del navegador: todas las llamadas dan 401;
  4. el `ConfigMap` montado encima de la raíz de nginx (tapa `index.html`) o con `subPath` (no se actualiza), o un fallback que no sirve `/stepup-callback`.

  Por eso CA-3 exige el **mundo cerrado** chart → SPA → realm de U2 → gateway de U2.

---

## Alcance

**Dentro:** los Pasos 17, 18, 21, 23 y 24 del plan. Texto del plan, sin recortes salvo lo que la tabla de arriba difiere, que va ~~tachado~~ con su cita y en «Fuera»:

### Bloque F — Despliegue y operación

- [ ] **Paso 17 — Imágenes** (E\*)
  - BFF: Python oficial por digest, `runAsNonRoot`, `readOnlyRootFilesystem`.
  - SPA (INF-U10-02): etapas `build`, ~~`no-previous` (`FROM scratch`, manifiesto vacío), `previous` (`FROM ${PREVIOUS_IMAGE}`, por omisión `no-previous`)~~ y final `nginx-unprivileged` por digest; ~~copia los recursos de `previous` listados en su `manifest.json`; etiqueta OCI `vectra.io/previous-digest` (`none` en el primer release).~~ (enmienda §3 U10, fila «17 · 18»: «más las etapas `previous` si se difiere `version`»; §6 P-15)
  - `nginx.conf`: `no-store` en `index.html`, `version.json` y `config.json`; `immutable` en `assets/`; fallback a `index.html` solo para rutas sin extensión; sin `server_tokens`.
  - Construidas, ~~escaneadas, con SBOM y firmadas con `sign-image.yml` de U1; el escaneo y el SBOM son de `supply-chain.yml`~~; `npm ci --ignore-scripts`. (T1; alcance §3 U10, fila «17»)
  - Diseño: INF-U10-02; NFR-U10-44, 45; P-U10-06.
  - **Aceptación**: `hadolint console/bff/Dockerfile console/spa/Dockerfile`; ~~prueba sobre la imagen de la SPA construida con un `PREVIOUS_IMAGE` de fixture (contiene los recursos de las dos versiones y ninguno más viejo; la etiqueta tiene el digest) y sin él (etiqueta `none`, sin recursos anteriores)~~; prueba de `nginx.conf` con `nginx -t` y `curl` en un contenedor local (`/cases/123` → `index.html`; `/assets/no-existe.js` → 404; cabeceras de caché). (La prueba con `PREVIOUS_IMAGE`: enmienda §3 U10, fila «17 · 18», y §6 P-15)

- [ ] **Paso 18 — Chart, cuotas y flujos** (E\*)
  - BFF: `Deployment` con HPA de 2 a 6 (en kind, `minReplicas = maxReplicas = 2`), `maxSurge: 1` y `maxUnavailable: 0`, PDB, spread por zona, `vectra-high`, `ServiceMonitor` 8081, `ConfigMap` de URLs y audiencias.
  - SPA: 2 réplicas fijas con `vectra.io/hpa-exempt`, `maxSurge: 100%` y `maxUnavailable: 0`, PDB, spread, `vectra-normal`, `ConfigMap` de `config.json` montado sin `subPath` y anotación `checksum/config`.
  - Aporte a las cuotas de `vectra-app` y `vectra-edge` con los pods del rollout y el proxy (INF-U10-01) en `platform/policies/quotas/` de U1.
  - Flujos a verificar en `platform/network/flows.yaml`, donde ya están (revisión de consistencia entre unidades, 2026-11-01): F02, F03, F10–F14, F50 y F60, con los casos bloqueados de INF-U10-04.
  - Diseño: INF-U10-01, 03, 04; NFR-U10-10..12, 20, 22.
  - **Aceptación**: `helm template` con cada values + `kubeconform` + `conftest test console/policies/conftest/` (réplicas, HPA de kind, exención, estrategias, PDB, spread, PriorityClass, sin `subPath`, `checksum/config`, `config.json` sin secretos y con los `redirect_uri` del realm del entorno); `kyverno test` de U1 (`require-hpa-bounds`); `conftest test platform/policies/quotas/`; `uv run python platform/network/generate.py --check`.

- [ ] ~~**Paso 19 — Alertas, runbooks y dashboard**~~ — **no entra**: D (T2; alcance §3 U10, fila «19»; enmienda §3 U10, fila «19 · 20»). Va en «Fuera».

- [ ] ~~**Paso 20 — Workflows de CI y de release**~~ — **no entra**: D (T4; alcance §3 U10, fila «20»; enmienda §3 U10, fila «19 · 20»). Va en «Fuera».

- [ ] **Paso 21 — Applications, especificaciones de carga y trazabilidad** (E\*)
  - Entradas `console-bff` y `console-spa` en `vectra-risk-gitops/components.yaml` con `wave: 5`; `generate.py` escribe una Application por entorno, sin auto-sync (revisión de consistencia entre unidades, 2026-11-01).
  - ~~Script k6 con el perfil por rol de P-U10-11 (200 usuarios, 30 min) y configuración de Lighthouse CI con el perfil de red del banco.~~ (T3; enmienda §3 U10, fila «21»)
  - Trazabilidad de cada BR-U10 a una prueba.
  - Diseño: P-U1-12; P-U10-11; NFR-U10-01, 02, 04.
  - **Aceptación**: `uv run python vectra-risk-gitops/generate.py --check`; `uv run python platform/tests/test_waves.py`; `kyverno test` de `disallow-argocd-auto-sync`; ~~`k6 inspect console/bff/tests/load/console.js`; `npx lhci healthcheck --config console/spa/lighthouserc.json`~~; `uv run python platform/tests/test_traceability.py --unit console --all`. (`k6 inspect` y `lhci`: T3)

### Bloque G — Verificación en kind (con aprobación humana)

- [ ] ~~**Paso 22 — Puerta de aprobación y escenarios en kind**~~ — **no entra**: consolidado en U12 Paso 18 (enmienda §8). Va en «Fuera» y en «Pendiente en U12» del cierre.

### Bloque H — Documentación y cierre

- [ ] **Paso 23 — Documentación** (E)
  - `console/README.md`: arquitectura, cómo correr el BFF con dobles y la SPA con Vite, constantes, flujo de release de la SPA y el rollback de emergencia; referencia a `role-endpoint-matrix.md`.
  - **Aceptación**: `test -s console/README.md`; un enlace por runbook y por documento de diseño, comprobado por `platform/tests/test_links.py`.

- [ ] **Paso 24 — Cierre de la unidad** (E\*)
  - **Aceptación**: `make -C console check`, que corre en orden las verificaciones estáticas, las propiedades, las pruebas de integración y las de Playwright con dobles de los Pasos 1–21 y termina en 0. ~~Las de kind (Paso 22) se revisan como evidencia en el PR.~~ (enmienda §8)

### Estructura de destino (§1 del plan): lo que esta tarea crea

```text
vectra-risk/console/
|-- Makefile                                  # se amplía: image-bff, image-spa, image-test, policy-chart, policy-chart-u1, quota-flows, gitops, links, traceability
|-- README.md                                 # nuevo (Paso 23), con la sección «Imágenes» (build, push, digest y PR de values, sin ejecutarlos)
|-- bff/
|   |-- Dockerfile  Dockerfile.dockerignore   # nuevos (Paso 17)
|   `-- tests/
|       |-- unit/test_chart.py                # nuevo: los dos charts, los values, la cuota, los flujos y el mundo cerrado
|       |-- integration/test_image.py         # nuevo (CA-4): las dos imágenes con lo que pone el chart
|       `-- integration/test_clients.py       # se modifica: solo la candidata C-1
|-- spa/
|   |-- Dockerfile  Dockerfile.dockerignore   # nuevos (Paso 17): etapas `build` y final
|   |-- nginx.conf                            # nuevo (Paso 17)
|   `-- tests/unit/chart-config.test.ts       # nuevo: el `config.json` rendido pasa por el `parseConfig` real
|-- chart/
|   |-- bff/  Chart.yaml  values.yaml  values-kind.yaml  templates/   # nuevo (P-2 y P-3)
|   `-- spa/  Chart.yaml  values.yaml  templates/                     # nuevo (P-2 y P-3)
`-- policies/conftest/  *.rego                # nuevo (Paso 18): reglas del render y de `config.json`
```

Los nombres de las plantillas y de los paquetes Rego son orientativos; los demás son los que nombran los criterios. Sale `chart/templates/.gitkeep` (P-2). **No** se crean `spa/lighthouserc.json`, `bff/tests/load/console.js`, `spa/stryker.conf.json`, nada en `observability/` ni ningún workflow. Fuera de `console/`, uno por uno:

- `vectra-risk-gitops/components.yaml` (las entradas `console-bff` y `console-spa`) y lo que `generate.py` escribe (`apps/<env>/console-bff.yaml`, `apps/<env>/console-spa.yaml` y lo que cambie en `apps/<env>/`);
- `vectra-risk-gitops/values/<env>/console-bff.yaml` y `values/<env>/console-spa.yaml`, para kind, staging y prod (seis archivos nuevos; Paso 18);
- `platform/tests/test_platform.py`: **solo** `console-bff` y `console-spa` en `EXPECTED_WAVES[5]`. Sin ellas `make -C platform check` falla (C-7);
- `platform/tests/test_kind_profile.py`: **solo** `BUDGET_GIB` y su comentario, y solo si la cifra medida no cabe en el tope de la base (sección «Presupuesto»);
- `aidlc-docs/construction/console/evidence/cierre-demo.md` (nuevo), `aidlc-docs/construction/console/code/spa.md` (solo §11, que pasa a decir lo que se hizo), el plan (casillas y una línea en las notas de §1), `CANDIDATAS.md` y `bitacoras/U10-T05.md`.

Nada más de `platform/`: ni `flows.yaml`, ni `forbidden.yaml`, ni `quotas.yaml`, ni `kyverno-test.yaml`. **Nada de `identity-edge/`**: ni `routes.yaml`, ni los realms, ni lo generado.

### Precisiones

#### Paso 17 — Imágenes

- Contexto de construcción: la raíz de `vectra-risk/`, como `product-metrics/Dockerfile`. Cada imagen lleva su `Dockerfile.dockerignore` (deja fuera `.venv`, `**/node_modules`, `**/dist`, `.git`, `platform/.tools`, `platform/.charts` y la documentación): el contexto se envía entero y la máquina está cargada.
- Cada `FROM` va fijado por digest. `USER` numérico en las dos imágenes, igual al `runAsUser` y `runAsGroup` de su chart.
- **Imagen `console-bff`**: multi-stage como `product-metrics/Dockerfile`; solo el runtime y sus dependencias del workspace (`vectra_contracts`, `vectra_common`), sin dependencias de desarrollo ni `tests/`. Usuario `65532:65532`. Orden: `python -m console_bff.app` (8080 y 8081).
- **Imagen `console-spa`**, dos etapas:
  - `build`: Node oficial por digest. El lockfile es el `package-lock.json` raíz y `console/spa` depende del workspace `contracts/ts` (P-2 de U10-T01): se copian `package.json` y `package-lock.json` de la raíz, `contracts/ts/` y `console/spa/`; después `npm ci --ignore-scripts` y `npm run -w console/spa build`. Elige un Node 22 que cumpla el rango de las dependencias (≥ 22.22.2), para que el build de la imagen no dependa del Node de la máquina (C-11);
  - final: `nginxinc/nginx-unprivileged` por digest, con `dist/` **sin** `.vite/` (C-2: `build.manifest` deja `dist/.vite/manifest.json` y solo lo lee `.size-limit.mjs`) y con `nginx.conf`. Sin Node, sin `node_modules`, sin fuentes y sin mapas de código.
  - No hay `ARG PREVIOUS_IMAGE`, ni etapa `previous`, ni etiqueta `vectra.io/previous-digest` (diferidas). No se genera `version.json` (`version` está diferido): la línea de `nginx.conf` que lo nombra se queda, y una petición a `/version.json` da 404.
- **`nginx.conf`** (INF-U10-02):
  - escucha en 8080; `server_tokens off`; el `pid` y los directorios temporales en `/tmp` (el chart pone `emptyDir`; INF-U10-03);
  - `location = /healthz`: 200 estático (las sondas de INF-U10-01);
  - `index.html`, `version.json` y `config.json` con `Cache-Control: no-store`. **También cuando `index.html` sale por el fallback**: la respuesta a `/casos/<uuid>` lleva `no-store`;
  - `config.json` **no** está en la raíz de nginx: lo sirve desde el directorio donde el chart monta el `ConfigMap` (por ejemplo, con `alias`). Montar el volumen sobre la raíz taparía `index.html`;
  - `assets/` con `public, max-age=31536000, immutable`;
  - fallback a `index.html` **solo** para rutas sin extensión (`location ~ ^[^.]*$`): `/callback`, `/stepup-callback` y las rutas de `src/views/shared/routes.ts`. Un archivo con extensión que no existe da 404, nunca HTML con 200;
  - compresión `gzip` para JavaScript, CSS y JSON: `.size-limit.mjs` mide con gzip «porque es lo que sirve nginx» (`spa.md` §9);
  - **ninguna cabecera de seguridad**: las pone el gateway de U2 (NFR-U10-45; perfiles `common` y `spa` de `routes.yaml`). Una prueba lee esos nombres de `routes.yaml` y comprueba que `nginx.conf` no los fija.
- Targets `image-bff`, `image-spa` e `image-test` en `console/Makefile`, con los tags `localhost:5001/vectra/console-bff:dev` y `localhost:5001/vectra/console-spa:dev`. `check` construye las dos **antes** de `test_image.py` (candidata de U09-T04, F-03: la prueba no puede pasar con una imagen vieja).
- La sección «Imágenes» de `console/README.md` (como `scoring-explainability/docs/imagenes.md`): build, comprobaciones locales, y el push, el digest real y el PR de `values/kind/console-bff.yaml` y `console-spa.yaml` **sin ejecutarlos**. Los hace el operador en U12 Paso 18.
- En cada `values.yaml`, el digest es de ejemplo y distinto de los que ya usan los otros charts (hoy van del `…0001` al `…0007`): los dos siguientes libres en la base de la rama. No pueden ser 64 ceros (`test_placeholder_digests_are_only_on_images_we_build`).

#### Paso 18 — Charts

- **Dos charts** (P-2): `console/chart/bff` (namespace `vectra-app`) y `console/chart/spa` (namespace `vectra-edge`), uno por Application.
- **Nombres** (los de `flows.yaml`, líneas 83 y 89, y los backends de `routes.yaml`): `Deployment`, `Service` y `ServiceAccount` `console-bff` y `console-spa`, con `app.kubernetes.io/name` igual. Una prueba los lee de los dos archivos.
- **`console-bff`** (INF-U10-01):
  - `replicas: 2` (`test_kind_profile.py` cuenta `spec.replicas`, 1 si falta); HPA de 2 a 6, CPU al 70 %, estabilización 60 s hacia arriba y 300 s hacia abajo. **En kind**, `minReplicas = maxReplicas = 2`, con el HPA presente (INF-U10-06);
  - `maxSurge: 1` y `maxUnavailable: 0`; PDB `minAvailable: 1` por `app.kubernetes.io/name`; spread por zona; `vectra-high`; `vectra.io/criticality: high` (NFR-U10-20);
  - recursos: 250m / 256 MiB y 1 CPU / 512 MiB. El request de memoria de kind es P-1;
  - sondas: readiness `/readyz` y liveness `/healthz`, las dos en 8081, sin `startupProbe`. Una prueba compara las rutas con las de `vectra_common.ops_server`, importadas (como `scoring-explainability/tests/unit/test_chart.py::test_probes_the_paths_are_routes_that_ops_server_serves`);
  - `preStop.sleep.seconds: 5` y `terminationGracePeriodSeconds: 20` (P-5 (a) de U10-T02; `bff-api.md`);
  - `Service` con 8080 y 8081; `ServiceMonitor` en 8081 con `honorLabels: true`;
  - **`ConfigMap` de variables**: exactamente `console_bff.app.REQUIRED` (`VECTRA_CASE_URL`, `VECTRA_GOVERNANCE_URL`, `VECTRA_REGISTRY_URL`, `VECTRA_EXPLAINABILITY_URL`, `VECTRA_BIAS_URL`, `VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL`), más `VECTRA_CA_BUNDLE` y `VECTRA_OTLP_ENDPOINT` (F61, como U7). La prueba importa `REQUIRED` y `OPTIONAL`; no los copia. Las cinco URL son `http://<Service>.<namespace>.svc.cluster.local:8080`, con el Service y el puerto de F10 a F14 leídos de `flows.yaml`. El emisor y el JWKS son P-4. El `Deployment` lleva `checksum/config` del `ConfigMap`, para que un cambio reinicie los pods;
  - «audiencias»: el plan dice «`ConfigMap` de URLs y audiencias», pero el BFF no lee ninguna variable de audiencia. U0 valida `aud = console-bff` (el nombre del servicio) y el realm la pone con el mapper `aud-console-bff`. No inventes una variable: déjalo dicho en la bitácora y como candidata de corrección del plan;
  - la CA: el `ConfigMap` `vectra-internal-ca` montado de solo lectura, como `scoring-explainability/chart` (`keycloak.caConfigMap` y `keycloak.caMountPath`). El JWKS va por `https`, y sin `VECTRA_CA_BUNDLE` el proceso sale con código 2;
  - **ninguna constante de `console_bff/config.py`** como variable de entorno (INF-U10-01; `deployment-architecture.md` §3). La prueba recorre los nombres públicos de `config.py`, importado;
  - sin `Secret`, `ExternalSecret`, `PrometheusRule`, `ConfigMap` de dashboard, `Server`, `AuthorizationPolicy`, `HTTPRoute` ni `NetworkPolicy` en el render.
- **`console-spa`** (INF-U10-01, 03):
  - `replicas: 2`, `vectra.io/hpa-exempt` con su justificación (no vacía), sin HPA; `maxSurge: 100%` y `maxUnavailable: 0`; PDB `minAvailable: 1`; spread por zona; `vectra-normal`; `vectra.io/criticality: medium` (NFR-U10-20);
  - recursos: 50m / 32 MiB y 200m / 64 MiB;
  - sondas: readiness y liveness `GET /healthz` en 8080;
  - `Service` con 8080 y nada más. Sin `ServiceMonitor` (la SPA no expone métricas; INF-U10-05);
  - `readOnlyRootFilesystem` con `emptyDir` en `/tmp` y en el directorio de caché temporal de nginx;
  - **`ConfigMap` de `config.json`**, generado desde los values, montado como volumen completo (**sin `subPath`**) de solo lectura en el directorio que nombra `nginx.conf`, y `checksum/config` en el pod template con el hash de `config.json`;
  - **las claves de `config.json` son las de `SCHEMA` de `console/spa/src/config/load.ts`**, ni una más: `oidc.authority`, `oidc.client_id`, `redirect_uri`, `stepup_redirect_uri` y `grafana.bias_dashboard_uid` (P-5). Ninguna constante de tiempo (`TIME_CONSTANTS`);
  - valores: `oidc.authority` = `https://<hostname>` + `jwt.issuer_path` de `routes.yaml`; `oidc.client_id` = `vectra-console`; `redirect_uri` = `https://<hostname>/callback`; `stepup_redirect_uri` = `https://<hostname>/stepup-callback`. El `<hostname>` es un value por entorno y debe ser el de `identity-edge/gateway/values/<env>.yaml` y el `vectra.publicHostname` de `identity-edge/keycloak/values/<env>.yaml`. Sin puerto: kind publica el 443 (`platform/kind/cluster.yaml`, líneas 38 y 39);
  - sin `Secret`, `ExternalSecret`, `Server`, `HTTPRoute` ni cabeceras: son de U1 y de U2.
- **Values por entorno** (P-3):
  - `chart/bff/values.yaml` y `chart/spa/values.yaml`: los defaults son los de producción. Un render sin values de entorno es el de producción;
  - `chart/bff/values-kind.yaml`, por `kind_values`: lo que las pruebas de U1 deben ver en kind (`maxReplicas: 2` y el request de P-1). Nada más;
  - `vectra-risk-gitops/values/<env>/console-bff.yaml`: el emisor del entorno (P-4) y, después, el digest;
  - `vectra-risk-gitops/values/<env>/console-spa.yaml`: el `<hostname>` del entorno y, después, el digest.
- **`conftest`** en `console/policies/conftest/`, con las reglas del plan, sobre el render de cada entorno:
  - BFF: réplicas, HPA de 2 a 6 (en kind, 2 y 2), estrategia, PDB, spread, `priorityClassName`, recursos, `preStop` y plazo de gracia, ninguna constante como variable;
  - SPA: 2 réplicas, exención con justificación, sin HPA, estrategia, PDB, spread, `priorityClassName`, **sin `subPath`**, `checksum/config` presente y **igual** al hash del `config.json` rendido;
  - `config.json`: ninguna clave con nombre de secreto (`secret`, `password`, `token`, `key`) ni valor con forma de llave; los dos `redirect_uri` son los del cliente `vectra-console` del realm del entorno. `conftest` no lee el realm: los valores esperados le llegan por `--data`, generados por el target desde `realm.<env>.yaml` y los values de Keycloak, sin versionarlos.

  Cada regla tiene en `test_chart.py` un caso que falla con una mutación.
- **Cuota (INF-U10-01).** Los aportes ya están en `quotas.yaml`. Una prueba los recalcula desde el render de prod: BFF, 7 pods (HPA al máximo más 1 de `maxSurge`); SPA, 4 pods (2 más el 100 %); el proxy de 100m / 20 MiB y 500m / 128 MiB; y el 30 %. Resultado esperado (calculado al redactar):

  | Namespace | Recalculado (CPU, GiB) | `quotas.yaml` |
  |---|---|---|
  | `vectra-app`, requests | 3,185 · **2,4527** | 3.19 · **2.4** |
  | `vectra-app`, limits | 13,65 · 5,6875 | 13.7 · 5.7 |
  | `vectra-edge`, requests | 0,78 · 0,2641 | 0.78 · 0.26 |
  | `vectra-edge`, limits | 3,64 · 0,975 | 3.64 · 0.97 |

  INF-U10-01 da cifras con «≈». El request de memoria del BFF queda 0,05 GiB por encima de lo declarado: ver P-6. El plan dice `conftest test platform/policies/quotas/`, pero en el repositorio esa comprobación es `platform/policies/quotas/render.py --check` y `test_integration.py::test_every_workload_declares_requests_and_limits_and_fits_the_quota`. Usa esas y regístralo, como U7, U9 y U11. **No edites U1.**
- **Flujos.** F02, F03, F10 a F14, F50 y F60 ya están en `flows.yaml`, y los casos bloqueados de INF-U10-04 en `forbidden.yaml`. Sin flujos nuevos. Si algo falta, **repórtalo**: no edites U1. La suite de conectividad en kind es de U12.
- **Admisión** (reglas del plan): imagen por digest, `runAsNonRoot`, `readOnlyRootFilesystem`, sin `privileged` ni `hostPath`, recursos, `priorityClassName`, `vectra.io/criticality`, 2 réplicas, spread, PDB por `app.kubernetes.io/name`, y HPA o `vectra.io/hpa-exempt`.
- **Perfil demo (T6):** DD-3 b. Sin `values-kind-demo.yaml` y sin 1 réplica.

#### Presupuesto de memoria de kind (`DECISIONES-LOOP.md` §7)

La máquina de la demo tiene 14 GiB. En `main`, `BUDGET_GIB` está en 10,7 (`requested_gib()` = 10,6328 GiB con U11). U08-T05, en curso, suma 0,7422 GiB (128 MiB solo en kind; `DECISIONES-LOOP.md` §9). §7 ya dio por inviable un pico de ≈ 13 GiB. Por eso esta tarea **no sube `BUDGET_GIB` sin más**:

1. **Mide primero.** Antes de tocar `components.yaml`, anota la cifra de la base de la rama con la orden de CA-10. Con las dos Applications agregadas, mídela otra vez.
2. **Aporte de U10**, réplicas × (request + 20 MiB de proxy). Los dos namespaces están mallados (`MESHED`, `test_kind_profile.py`).

   | Componente | Por diseño (INF-U10-01) | Con P-1 = (b) |
   |---|---|---|
   | `console-bff` | 2 × (256 + 20) = 552 MiB | 2 × (128 + 20) = 296 MiB |
   | `console-spa` | 2 × (32 + 20) = 104 MiB | 104 MiB (no cambia) |
   | **Total** | **656 MiB = 0,6406 GiB** | **400 MiB = 0,3906 GiB** |

   La diferencia entre las dos mediciones debe ser esa cifra (± 0,001). Si no lo es, algo más cambió o `render_env("kind")` no ve lo que Argo CD despliega (P-3): **detente y repórtalo**.
3. **El request de kind** va en `console/chart/bff/values-kind.yaml`, que entra por `kind_values` (como `product-metrics`). `render_env` sí pasa `kind_values`; **no** pasa `vectra-risk-gitops/values/kind/<nombre>.yaml` (C-9). Las réplicas, los limits (512 MiB) y los PDB no cambian, y staging y prod siguen en INF-U10-01 (una prueba lo fija).
4. `BUDGET_GIB` sube a la cifra medida con U10, redondeada hacia arriba a 0,1 GiB, con el comentario de la decisión y la cita de §7. Nunca más arriba.

   | Base de la rama | Cifra de la base | Con (a), 256 MiB | Con (b), 128 MiB |
   |---|---|---|---|
   | `main` de hoy, sin U8 | 10,6328 | 11,2734 → `11.3` | 11,0234 → `11.1` |
   | con U08-T05 fusionada | 11,3750 | 12,0156 → `12.1` | 11,7656 → `11.8` |

   **La base cambiará cuando se fusione U08-T05.** Parte siempre de la cifra de la base de tu rama; si las dos tareas tocan `BUDGET_GIB` a la vez, el orquestador resuelve el conflicto al integrar.
5. **Proyección, que no decide el codificador.** Suma a la cifra medida lo que todavía no tenga Application (U8, si no está en `main`: 0,7422 GiB). U12 no despliega `Deployment` en kind. Al redactar da **≈ 12,02 GiB con (a)** y **≈ 11,77 GiB con (b)**. Recalcúlala con lo que haya en `main` y déjala en la bitácora y en el cierre.
6. **Detención.** Si la cifra medida no cuadra (punto 2), o si la proyección llega a **13,0 GiB**, no subas `BUDGET_GIB`: **detente y repórtalo** con la cifra, el desglose por unidad y las opciones. Es una detención, no un ROJO del codificador. No cambies réplicas, limits ni requests fuera de lo que P-1 fija.
7. En la prueba de los contenedores reales (CA-4), anota la memoria del BFF y de nginx en reposo (`docker stats --no-stream`). Es el dato que justifica o desmiente P-1 = (b), sin umbral.

#### Paso 21 — Applications y trazabilidad

- Entradas en `components.yaml`, con un comentario como el de las otras unidades:
  - `{ name: console-bff, wave: 5, namespace: vectra-app, path: console/chart/bff, env_values: true, kind_values: [console/chart/bff/values-kind.yaml] }`;
  - `{ name: console-spa, wave: 5, namespace: vectra-edge, path: console/chart/spa, env_values: true }`.

  `generate.py` escribe una Application por entorno, sin `syncPolicy.automated`, y agrega solo `values/<env>/<nombre>.yaml` a sus `valueFiles` (`generate.value_files`).
- **Trazabilidad.** `python3 -B platform/tests/test_traceability.py --unit console --all` marca hoy **15** identificadores (comprobado al redactar, sobre `8ed696f` de `tarea/U10-T04`). Destino de cada uno:

  | Identificador | Destino | Dónde se traza (o por qué se difiere) |
  |---|---|---|
  | INF-U10-02 | **Trazar** | `console/spa/Dockerfile` y la prueba de `nginx.conf` de `test_image.py`. Las etapas `previous` van en el cierre como diferidas, sin fila |
  | INF-U10-04 | **Trazar** | La prueba de `test_chart.py` que ata nombres, `ServiceAccount`, etiquetas y puertos a `flows.yaml` y a `routes.yaml` |
  | INF-U10-06 | **Trazar** | La regla de `conftest` del HPA de kind (2 y 2) y la de los values por entorno |
  | NFR-U10-10 | **Trazar** | La regla de `conftest` del HPA de 2 a 6 al 70 %. La medida con carga va en el cierre como «no comprobado», sin fila |
  | NFR-U10-12 | **Trazar** | La regla de `conftest` de las 2 réplicas fijas con la exención |
  | NFR-U10-20 | **Trazar** | La regla de `priorityClassName` y de `vectra.io/criticality` |
  | NFR-U10-22 | **Trazar** | La regla de spread y PDB. El simulacro de zona va en el cierre como «no comprobado», sin fila |
  | NFR-U10-44 | **Trazar** | `console/spa/Dockerfile` (`npm ci --ignore-scripts`) y su comprobación en `test_image.py`. `npm audit`, Trivy, SBOM y firma van en el cierre como diferidos (T1), sin fila |
  | NFR-U10-45 | **Trazar** | `console/spa/Dockerfile` y las pruebas de `test_image.py` (sin root, solo lectura, cabeceras de caché, sin cabeceras de seguridad) |
  | INF-U10-05 | **Diferir** | Paso 19 (reglas, runbooks y dashboard); enmienda §3 U10, fila «19 · 20»; T2 |
  | NFR-U10-01 | **Diferir** | Paso 21 (k6 con el perfil por rol) y Paso 22, punto 5; enmienda §3 U10, fila «21»; T3 |
  | NFR-U10-04 | **Diferir** | Paso 21 (Lighthouse CI) y Paso 22, punto 5; enmienda §3 U10, fila «21», y §2 regla 3; T3 |
  | NFR-U10-21 | **Diferir** | Paso 19 (regla de grabación del SLO y alerta de *burn rate*); enmienda §3 U10, fila «19 · 20»; T2 |
  | P-U10-06 | **Diferir** | Paso 12 (`version`) y Paso 17 (etapas `previous`); enmienda §3 U10, filas «12» y «17 · 18»; §6 P-15 |
  | P-U10-10 | **Diferir** | Paso 19 (las seis alertas); enmienda §3 U10, fila «19 · 20»; T2 |

  - La lista «Diferido por la demo» de `cierre-demo.md` tiene **exactamente** esas seis filas más las de **BR-U10-14** (`DecideDataSourceDialog` y `PrePostReportView`; Paso 14; enmienda §3 U10, fila «14 Gobierno y sesgo»), **BR-U10-16** (`GrafanaEmbed`; Paso 14; misma fila) y **BR-U10-21** (`version` y `VersionBanner`; Paso 12; enmienda §3 U10, fila «12», y §6 P-15): nueve filas. Cada fila lleva el identificador, el paso y la cita. La herramienta acepta las filas de BR porque no cuenta las BR entre los identificadores de la unidad (`DEFINITION` solo lee encabezados y filas de tabla; candidata de U03-T02): que `constants.ts` y `reporter/version.ts` citen BR-U10-21 no estorba.
  - Cada identificador que se traza se cita en el artefacto que lo implementa o en la prueba que lo verifica. Citarlo solo en `console/README.md` no cuenta.
  - **Ningún archivo de `console/` escribe** `INF-U10-05`, `NFR-U10-01`, `NFR-U10-04`, `NFR-U10-21`, `P-U10-06` ni `P-U10-10`: la herramienta rechaza una fila diferida cuyo identificador «ya tiene código o prueba». Cuidado con `nginx.conf` y con el README: citan INF-U10-02, no P-U10-06.
  - La herramienta solo lee archivos con sufijo conocido, `Makefile` y `Dockerfile` (`SUFFIXES` y `NAMES`, `test_traceability.py`, líneas 32 y 33): **no lee `nginx.conf` ni los `.mjs`**. Una cita puesta solo allí no cuenta.
  - Corre la prueba al empezar, registra lo que marca y justifica cada identificador en la bitácora. Si la lista difiere de las 15 de arriba, dilo.
- **BR-U10 a una prueba.** `test_traceability.py` no ve las BR. Por eso hay un `git grep` por cada una (CA-9), como en U7, U8, U9 y U11. Hoy quedan **7 sin prueba**: BR-U10-02, 09b, 11, 14, 16, 18 y 21. Destino:
  - BR-U10-02 (sin estado): se cita en la prueba de `test_chart.py` que comprueba que el BFF no tiene volúmenes persistentes ni afinidad de sesión en su `Service`;
  - BR-U10-09b (decisión sin step-up), BR-U10-11 (datos del solicitante en pantalla) y BR-U10-18 (frases prohibidas): se citan en la prueba que **ya** las ejerce (la matriz rol × endpoint o los ejemplos de la API; `tests/unit/views/cases/`; la prueba de `i18n` que corre las frases). Si ninguna lo hace, se escribe. Sin cambio de comportamiento;
  - BR-U10-14, 16 y 21 van en la lista y el `git grep` las exceptúa.

#### Paso 23 — `console/README.md`

- Arquitectura (las dos piezas, los dos namespaces, F02, F03 y F10 a F14); cómo correr el BFF con dobles y la SPA con Vite (lo de `spa.md` §2, enlazado, no copiado); las constantes (`console_bff/config.py` y `src/config/constants.ts`) frente a `config.json`; las variables del BFF; la sección «Imágenes»; y la referencia a `contracts/openapi/role-endpoint-matrix.md`.
- **Flujo de release de la SPA y rollback de emergencia:** se describen como los fija INF-U10-02 (un rollback es un release nuevo; revertir el digest es solo de emergencia), y el README dice **qué está diferido**: el workflow `console-spa-release.yml` y `spa-previous-digest-check` (Paso 20, T4), las etapas `previous` (P-15) y el runbook `console-spa-emergency-rollback` (Paso 19, T2).
- «Un enlace por runbook y por documento de diseño»: no hay runbooks (Paso 19, D), así que esa mitad se cumple vacía y el README lo dice. Sí lleva un enlace relativo por cada documento de `aidlc-docs/construction/console/` (los nueve de diseño y los tres de `code/`).
- Ningún texto falla `contracts/tools/forbidden_phrases.py`.

#### Candidatas que se atienden aquí (`CANDIDATAS.md`)

Los números de línea son los del `CANDIDATAS.md` de `main` (`82c1718`); las de U10-T04 todavía no están en `main` y se citan por su texto (rama `tarea/U10-T04`, `8ed696f`). Si se mueven al fusionar, busca por el texto. El codificador marca cada una («~~…~~ **Atendida en U10-T05:** …»).

- **C-1 · «Pool agotado» (línea 565; U10-T02, ronda 1, F-01, NARANJA; destino U10-T05).** `console/bff/tests/integration/test_clients.py` (`test_an_exhausted_pool_ends_in_a_timeout_within_the_deadline`) pasa igual sin límite de conexiones. Dos cambios, solo de pruebas:
  - la llamada 21 va a una ruta que responde al instante: con las 20 conexiones ocupadas termina en `DependencyTimeout` a ≈ 1,5 s, y con 19 ocupadas responde 200;
  - una prueba fija que `Upstreams` pasa `CONNECTIONS_PER_REPLICA[name]` a cada `DependencyClient`.

  Las mutaciones M11 (1 000 conexiones) y M12 (21) deben hacerla fallar (rojo en la bitácora). `console/bff/src` no cambia.
- **C-2 · `.vite/manifest.json` fuera de la imagen (U10-T04, «`console/spa/dist/.vite/manifest.json`»).** La imagen no lo copia y nginx no lo sirve (CA-1 y CA-4).
- **C-3 · `config.json` del chart (`spa.md` §2 y §11: «no hay `config.json` de desarrollo: lo sirve el `ConfigMap` del chart»).** El chart lo genera y CA-3 cierra el mundo.
- **C-4 · `nginx.conf` (`spa.md` §11; `routes.yaml`, línea 118: «las rutas de la SPA sin extensión llegan a nginx»).** `/callback` y `/stepup-callback` devuelven `index.html` (CA-4).
- **C-5 · La CSP del gateway real (línea 607; y U10-T04, «`tests/e2e/vite.e2e.config.ts` y `playwright.config.ts`»).** Aquí solo lo que se puede probar sin clúster: el `authority` del `config.json` es del **mismo origen** que la SPA (`https://<hostname>/auth/realms/vectra`), así que `connect-src 'self'` y `form-action 'self'` lo admiten, y nginx no añade ninguna CSP propia. La prueba con el gateway y Keycloak reales va en «Pendiente en U12». La candidata **no** se cierra.
- **C-6 · `ServiceAccount` `console-bff` (líneas 402 y 412).** El chart del BFF la crea. El runbook de U4 que la crea de forma temporal ya no hace falta cuando U10 esté sincronizada: va en «Pendiente en U12» (retirarla antes del sync).
- **C-7 · `EXPECTED_WAVES` (líneas 303 y 517).** Nombrado arriba entre los archivos de U1 que esta tarea toca. La candidata de la plantilla (`loop/plantilla-tarea.md`) sigue abierta: es del loop.
- **C-8 · `check-chart` y el PDB repetido (líneas 345, 400, 467 y 594).** No se arregla U1: `make -C console policy-chart-u1` rinde un entorno y un chart por directorio, como `product-metrics/Makefile`. Ver CA-5 y «Restricciones del entorno».
- **C-9 · `render_env` sin los values de la unidad (líneas 466 y 512).** No se arregla U1; se rodea con P-3 y una prueba que compara los dos renders de kind.
- **C-10 · `crd_to_schema.py` duplicado (líneas 468 y 516).** Aquí **no** se copia: U10 solo necesita el esquema de `ServiceMonitor`, y `kubeconform` lo toma de `scoring-explainability/tests/fixtures/crds/`. La bitácora lo anota.
- **C-11 · Node y `jsdom` (líneas 573 y 603).** Solo la parte de la imagen: la etapa `build` fija un Node por digest que cumple el rango. El Node de la máquina y de `platform/tools.env` no se toca; la candidata sigue abierta.

**No se atienden** (con su porqué; van también en «Fuera»):

- `version` y `VersionBanner` (P-15): diferidos. Con ellos, las etapas `previous`.
- `sslmode` (línea 236): U10 no tiene base de datos.
- `AuthProvider` sin `silentRenewError` (línea 606), `/callback` que vuelve siempre a `/` (U10-T04) y el sondeo del foco del step-up (U10-T04): cambian `console/spa/src`; no afectan al despliegue.
- El `override` de `minimatch`, la etiqueta de `FeatureContribution`, el catálogo de canales, el `disclaimer` de `FreezeRecord` y el código de `ClientErrorReport` (U10-T04): son de U0 o de diseño.
- Los puertos fijos de `test_service_shutdown.py` (línea 566): U0. Aquí solo se evita chocar.
- `playwright.config.ts` con los `webServer` globales (línea 576) y el instrumento de la PoC (línea 574): pruebas de U10-T03, sin efecto en D1 a D4.
- El eco de U2 con el nombre `console-bff` (línea 259): es de U2; aquí solo se anota en «Pendiente en U12».
- Paquetes de prueba con `--import-mode=importlib` (línea 549): `console/bff/tests` no está dentro de un paquete llamado `console_bff`; no aplica.

### Plan

- Paso 17: `[x]` con «(U10-T05; firma, SBOM y escaneo diferidos por la demo (T1); etapas `previous` diferidas con `version` (P-15))», en el estilo del Paso 4.
- Paso 18: `[x] (U10-T05)`.
- Paso 21: `[x]` con «(U10-T05; k6 y Lighthouse CI diferidos por la demo (T3))».
- Paso 23: `[x] (U10-T05)`.
- Paso 24: `[x]` con «(U10-T05; cierre acotado a la demo)».
- Paso 19: `[ ]` con «diferido por la demo (T2)». Paso 20: `[ ]` con «diferido por la demo (T4)».
- Paso 22: `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)».
- Una línea nueva en «Notas de U10-T01 a la estructura de destino» (§1), como las de U10-T02 y U10-T03: los dos charts (`chart/bff` y `chart/spa`), `values-kind.yaml`, los dos `Dockerfile.dockerignore` y las pruebas nuevas.

### Cierre acotado (Paso 24)

`aidlc-docs/construction/console/evidence/cierre-demo.md`, con el formato de `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md`:

- **Comprobado:** cada paso que entra (también los de U10-T01 a U10-T04, en una fila cada tarea), con su comando y su resultado; la memoria de kind con y sin U10 y la proyección; las cifras de CA-13 y CA-14.
- **Decisiones:** P-1 a P-6, con la opción que rigió y quién la decidió; lo «no comprobado» de NFR-U10-10 y NFR-U10-22.
- **Pendiente en U12** (lo que solo se ve en kind; U12 Paso 18, enmienda §8):
  - el **login por el gateway real con Keycloak real**: redirección, `/callback` y la recarga con `prompt=none`, con `analista-1` (escenario 1 del Paso 22);
  - **la CSP del gateway**: cero `securitypolicyviolation` con el perfil `spa` real y con la política de `/auth/**` (`frame-ancestors 'self'`), que el servidor de pruebas no reproduce (C-5);
  - el **step-up de `cumplimiento-1`**: ventana emergente, `/stepup-callback`, `acr = mfa` y `ResolveFrozenDialog` (D2);
  - la **conectividad F03, F10, F11 y F14** (escenario 2) y los casos bloqueados de INF-U10-04;
  - que el `iss` de los tokens del navegador sea el `VECTRA_OIDC_ISSUER` del BFF (P-4) **y el de cada destino**, que recibe ese mismo token por F10 a F14;
  - el push de las dos imágenes y los digests reales en `values/kind/console-bff.yaml` y `console-spa.yaml`;
  - retirar, antes del sync, el eco de U2 (`identity-edge/tests/e2e/echo/manifests.yaml`, que usa el nombre `console-bff`) y la `ServiceAccount` temporal del runbook de U4 (C-6);
  - que el `ConfigMap` `vectra-internal-ca` exista en `vectra-app` y el JWKS responda por `https`;
  - que Prometheus raspe el `ServiceMonitor` del BFF y que la afinidad `vectra-spa-route` llegue a los pods reales;
  - la memoria real del BFF frente al request de kind de P-1.
- **Diferido por la demo:** las nueve filas de la lista y, sin identificador propio, cada uno con su destino:
  - firma, SBOM, escaneo, `npm audit` y Trivy (Paso 17, T1);
  - las etapas `no-previous` y `previous`, la etiqueta `vectra.io/previous-digest` y la prueba con `PREVIOUS_IMAGE` (Paso 17; P-15);
  - el Paso 19 entero (seis alertas, cinco runbooks y `console.json`; T2) y el Paso 20 entero (`console.yml`, el nocturno, `console-spa-release.yml` y `spa-previous-digest-check`; T4);
  - el script k6, Lighthouse CI, `k6 inspect` y `lhci` (Paso 21, T3); `mutmut` y Stryker (Pasos 4 y 16, T3);
  - del Paso 22: aprobador ≠ proponente, los escenarios 3 a 6 y NVDA (enmienda §3 U10, fila «22 Kind»);
  - las vistas diferidas de los Pasos 13 y 14, que ya lista `spa.md` §4.

**Fuera** (rechazar aunque se vea roto o tentador):

- **Las etapas `previous`:** `ARG PREVIOUS_IMAGE`, `no-previous`, la copia de recursos anteriores, la etiqueta OCI y su prueba. **`version`, `version.json` y `VersionBanner`.**
- **Paso 19 completo:** `PrometheusRule`, reglas de grabación, runbooks, `console.json` y su `ConfigMap`, `promtool` y `test_runbooks.py --root console`.
- **Paso 20 completo:** cualquier archivo en `.github/workflows/`, `actionlint` y `test_previous_digest_check.py`.
- **Paso 22 completo:** guía, scripts y escenarios de kind; cualquier `kubectl`, `helm install`, `argocd` o sync; el push de las imágenes y los digests reales (AUTONOMIA-01; enmienda §8).
- Firma, SBOM, escaneo, `sign-image.yml` y `supply-chain.yml` (T1).
- `console/bff/tests/load/console.js`, `console/spa/lighthouserc.json`, `k6 inspect` y `lhci` (T3). `mutmut` y Stryker (T3).
- `values-kind-demo.yaml` o 1 réplica (DD-3 eligió la b).
- Un `Server`, una `HTTPRoute`, una `AuthorizationPolicy` o una `NetworkPolicy` en los charts; un `Secret` o un `ExternalSecret`; cabeceras de seguridad en `nginx.conf`.
- **Cambios en U0, U1 y U2.** En U1, solo lo nombrado en «Estructura de destino». En U2, nada. En particular:
  - `render_env` (C-9), el pánico de `check-chart` (C-8), `crd_to_schema.py` en `platform/` (C-10), `EXPECTED_WAVES` y `FIXED_WAVES` solapadas (línea 170) y la línea de U10 en `quotas.yaml` (P-6) → U1;
  - los puertos configurables de `run_service` (línea 566) → U0;
  - el `VECTRA_OIDC_ISSUER` de los charts de U3, U4, U7, U8, U9 y U11 (P-4) → cada unidad, tras U12 Paso 18.
- **Cambios de comportamiento en `console/bff/src` y `console/spa/src`.** Esta tarea no toca `src/`. Si el chart o las imágenes revelan un defecto del código de U10-T01 a U10-T04, **repórtalo** y no lo arregles aquí. Las candidatas listadas en «No se atienden».
- Editar el texto de los diseños o del plan, salvo las casillas y la nota de §1.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/console-code-generation-plan.md`: §1, Pasos 17 a 24, §3, §4 y «Reglas de admisión».
- `aidlc-docs/construction/plans/demo-recorte-funcional.md`: §1 (§1.0 a §1.4), §2, §3 U10, §6 (P-14, P-15, P-16 y P-17) y §8.
- `aidlc-docs/construction/plans/demo-kind-alcance.md`: §2 (T1 a T6), §3 U10, §5 (DD-3) y §6.
- `DECISIONES-LOOP.md` §6, §7, §8 y §9.
- `aidlc-docs/construction/console/`: `infrastructure-design/infrastructure-design.md` (INF-U10-01 a 06) y `deployment-architecture.md`; `nfr-design/nfr-design-patterns.md` (P-U10-06, 10 y 11); `nfr-requirements/nfr-requirements.md`; `functional-design/domain-entities.md` §4 y `business-rules.md`.
- `aidlc-docs/construction/console/code/`: `bff-api.md` (arranque, apagado y P-5), `bff-logic.md` y `spa.md` (§2, §4, §8, §9 y §11).
- `console/`: `Makefile`; `bff/src/console_bff/app.py` (`REQUIRED`, `OPTIONAL`, `EXIT_CONFIG`) y `config.py`; `bff/tests/doubles/` (`bff_oidc.py`, `bff_tokens.py`, `bff_doubles.py`, `bff_e2e_server.py`) y `bff/tests/integration/test_clients.py` y `test_service_shutdown.py`; `spa/src/config/load.ts` y `constants.ts`, `spa/src/entry.ts`, `spa/src/views/shared/routes.ts`, `spa/vite.config.ts`, `spa/.size-limit.mjs`, `spa/index.html` y `spa/tests/e2e/vite.e2e.config.ts`.
- `bitacoras/U10-T04.md`, `revisiones/U10-T04/` y `tareas/U10-T04-spa-vistas-y-e2e.md` («Fuera»).
- La misma tarea hecha en otras unidades: `tareas/U11-T03-despliegue-y-cierre.md`, `tareas/U08-T05-despliegue-y-cierre.md`, `tareas/U07-T04-despliegue-y-cierre.md` y `revisiones/U11-T03/ronda-1.md`.
- `product-metrics/`: `Dockerfile`, `Dockerfile.dockerignore`, `chart/` (`values-kind.yaml`, `templates/deployment.yaml` con `checksum/config`), `policies/conftest/`, `Makefile` (`policy-chart`, `policy-chart-u1`, `quota-flows`, `gitops`), `tests/unit/test_chart.py` y `tests/integration/test_image.py`.
- `scoring-explainability/`: `chart/` (HPA de 2 a 6, `servicemonitors.yaml`, la CA de Keycloak), `policies/conftest/`, `docs/imagenes.md`, `tests/unit/test_chart.py` y `tests/fixtures/crds/servicemonitor.json`.
- `platform/`: `network/flows.yaml`, `network/forbidden.yaml`, `network/generated/<env>/vectra-edge.yaml` y `vectra-app.yaml`, `policies/quotas/quotas.yaml` y `render.py`, `policies/kyverno/` (`require-hpa-bounds.yaml`, `kyverno-test.yaml`, `fixtures/resources.yaml`), `policies/rego/`, `kind/cluster.yaml`, `tools.env`, `charts.sh` y `Makefile`.
- `platform/tests/`: `integration.py` (`render_env` y `chart_renders`), `test_integration.py`, `test_kind_profile.py`, `test_platform.py`, `test_waves.py`, `test_traceability.py` y `test_links.py`.
- `vectra-risk-gitops/`: `components.yaml`, `generate.py` (`value_files`), `envs/<env>/values.yaml` y `values/<env>/`.
- `identity-edge/`: `gateway/routes.yaml`, `gateway/values/<env>.yaml`, `gateway/generated/kind/` (`httproutes.yaml`, `referencegrants.yaml`, `securitypolicies.yaml`), `keycloak/realm/realm.<env>.yaml` (cliente `vectra-console`), `keycloak/values/` (`common.yaml`, líneas 137 a 141, y `<env>.yaml`) y `tests/e2e/echo/manifests.yaml`.
- `contracts/python/vectra_common/src/vectra_common/`: `ops_server.py`, `authn.py` y `telemetry.py`. `contracts/openapi/role-endpoint-matrix.md`. `contracts/tools/forbidden_phrases.py`.
- `CANDIDATAS.md`: las líneas citadas en «Candidatas que se atienden aquí» y en «No se atienden».

---

## Criterios de aceptación

Desde `vectra-risk/`, con las herramientas de `platform/install-tools.sh` y `npm ci --ignore-scripts` hecho **dentro del worktree**. Ninguno toca el clúster. Los renders van a `platform/.tools/integration/u10/`, **no a `/tmp`** (ver «Restricciones del entorno»); las órdenes usan `OUT=platform/.tools/integration/u10`. Tras cada criterio va lo que pasa **hoy** en `tarea/U10-T04` (`8ed696f`), que es lo que queda en `main` al fusionarla.

- [ ] **CA-1** — Paso 17: las dos imágenes.
  ```bash
  platform/.tools/bin/hadolint console/bff/Dockerfile console/spa/Dockerfile
  uptime; make -C console image-bff image-spa
  for i in console-bff console-spa; do docker image inspect localhost:5001/vectra/$i:dev --format '{{.Config.User}} {{json .Config.Cmd}} {{json .Config.Labels}}'; done
  for f in console/bff/Dockerfile console/spa/Dockerfile; do grep -c '^FROM ' $f; grep -cE '^FROM .*@sha256:[0-9a-f]{64}' $f; done
  docker run --rm --entrypoint sh localhost:5001/vectra/console-bff:dev -c '! pip list 2>/dev/null | grep -iE "^(pytest|hypothesis|ruff|mypy|hatchling|mutmut) " && echo OK-bff'
  docker run --rm --entrypoint python localhost:5001/vectra/console-bff:dev -c 'import console_bff.app; print("OK-entrada")'
  docker run --rm --entrypoint nginx localhost:5001/vectra/console-spa:dev -t
  docker run --rm --entrypoint sh localhost:5001/vectra/console-spa:dev -c 'cd /usr/share/nginx/html && test -s index.html && ls assets/*.js >/dev/null && ! test -e .vite && ! test -e config.json && ! test -e version.json && ! ls assets/*.map 2>/dev/null && ! command -v node && echo OK-spa'
  grep -c "npm ci --ignore-scripts" console/spa/Dockerfile
  ! grep -nE "PREVIOUS_IMAGE|no-previous|previous-digest" console/spa/Dockerfile console/spa/nginx.conf
  ! grep -niE "content-security-policy|x-frame-options|strict-transport-security|referrer-policy|cross-origin-opener-policy|x-content-type-options" console/spa/nginx.conf
  ```
  Esperado: `hadolint` en 0; un usuario numérico distinto de 0 en las dos (`65532:65532` en el BFF) y el `Cmd` de cada una; ninguna etiqueta `vectra.io/previous-digest`; los dos conteos de `FROM` iguales en cada archivo; `OK-bff`; `OK-entrada`; `nginx -t` con «syntax is ok» y «test is successful»; `OK-spa` (sin `.vite/`, sin `config.json` ni `version.json` en la imagen, sin mapas y sin Node); al menos `1`; los dos últimos `grep` no imprimen nada. Si `nginx -t` necesita `/tmp` escribible, córrelo con `--tmpfs /tmp` y anótalo. Si `hadolint` no está en `platform/.tools/bin` del worktree, ver «Restricciones del entorno».
  **Hoy falla:** no hay `Dockerfile`, `nginx.conf` ni targets de imagen (`test -f console/spa/Dockerfile` da 1).

- [ ] **CA-2** — Paso 18: render, esquema y `conftest` de los dos charts.
  ```bash
  OUT=platform/.tools/integration/u10
  for c in bff:vectra-app spa:vectra-edge; do for env in kind staging prod; do rm -rf $OUT/${c%%:*}/$env && uv run python platform/tests/integration.py --chart console/chart/${c%%:*} --namespace ${c##*:} --env $env --out $OUT/${c%%:*}/$env || echo "FALLA $c $env"; done; done
  for c in bff spa; do for env in kind staging prod; do platform/.tools/bin/kubeconform -strict -summary -schema-location default -schema-location 'scoring-explainability/tests/fixtures/crds/{{.ResourceKind}}.json' $OUT/$c/$env/*.yaml || echo "FALLA $c $env"; done; done
  make -C console policy-chart
  for c in bff spa; do for env in kind staging prod; do echo "== $c $env"; grep -h "^kind:" $OUT/$c/$env/*.yaml | sort | uniq -c; done; done
  uv run pytest console/bff/tests/unit/test_chart.py -p no:cacheprovider --rootdir=console/bff -v
  ```
  Esperado: código 0, ninguna línea «FALLA» e `Invalid: 0` en los seis renders. `policy-chart` corre `conftest test --policy console/policies/conftest` sobre cada render, con los datos del realm por `--data`, y **falla** si falta una herramienta. El inventario, igual en los tres entornos:
  - **`console-bff`:** 1 `Deployment`, 1 `Service`, 1 `HorizontalPodAutoscaler`, 1 `PodDisruptionBudget`, 1 `ServiceAccount`, 1 `ConfigMap` y 1 `ServiceMonitor`;
  - **`console-spa`:** 1 `Deployment`, 1 `Service`, 1 `PodDisruptionBudget`, 1 `ServiceAccount` y 1 `ConfigMap`.

  `test_chart.py` tiene un caso por regla que falla con una mutación del render. Como mínimo:
  - BFF: HPA con mínimo ≠ 2, máximo ≠ 6 en staging o prod, máximo ≠ 2 en kind, CPU ≠ 70 % o estabilización ≠ 60 / 300 s; sin HPA; `replicas` ≠ 2; estrategia distinta de `maxSurge: 1` y `maxUnavailable: 0`;
  - SPA: con HPA; sin `vectra.io/hpa-exempt` o con la justificación vacía; `replicas` ≠ 2; estrategia distinta de `maxSurge: 100%` y `maxUnavailable: 0`; un `subPath` en el montaje; sin `checksum/config`, o con un hash que no es el del `config.json` rendido; el `ConfigMap` montado en la raíz de nginx; sin `emptyDir` en `/tmp`;
  - las dos: sin PDB o con `minAvailable` ≠ 1; sin spread por zona; `priorityClassName` ≠ `vectra-high` (BFF) o ≠ `vectra-normal` (SPA); sin `vectra.io/criticality`; requests o limits distintos de INF-U10-01 en staging o prod; en kind, un request de memoria del BFF distinto del de P-1; `values-kind.yaml` con algo más que lo que P-1 y P-3 fijan; imagen sin digest; sin `runAsNonRoot` o sin `readOnlyRootFilesystem`;
  - BFF sin `preStop.sleep` de 5 s o con `terminationGracePeriodSeconds` < 20; liveness que no es `/healthz` en 8081; readiness que no es `/readyz` en 8081; el `Service` sin el 8080 o sin el 8081;
  - SPA con sondas que no son `GET /healthz` en 8080; el `Service` con otro puerto;
  - un `Secret`, un `ExternalSecret`, una `PrometheusRule`, un `Server`, una `HTTPRoute`, una `AuthorizationPolicy` o una `NetworkPolicy` en cualquiera de los dos renders.

  **Hoy falla:** `console/chart/` solo tiene `templates/.gitkeep`, y `console/policies/conftest/` solo `.gitkeep`.

- [ ] **CA-3** — Paso 18: **mundo cerrado** del `config.json`, de las variables del BFF y de los nombres.
  ```bash
  uv run pytest console/bff/tests/unit/test_chart.py -p no:cacheprovider --rootdir=console/bff -k "config_json or realm or gateway or env or issuer or flows or names or constants or kind_render" -v
  VECTRA_CHART_RENDER=$PWD/platform/.tools/integration/u10/spa npm run -w console/spa test -- chart-config
  OUT=platform/.tools/integration/u10
  for env in kind staging prod; do uv run python -c "import sys, json, yaml; d = [x for x in yaml.safe_load_all(open(sys.argv[1])) if x and x['kind'] == 'ConfigMap'][0]; c = json.loads(d['data']['config.json']); print(sys.argv[2], sorted(c), sorted(c['oidc']), sorted(c['grafana']), c['oidc']['authority'], c['oidc']['client_id'], c['redirect_uri'], c['stepup_redirect_uri'])" "$(grep -l '^kind: ConfigMap' $OUT/spa/$env/*.yaml | head -1)" $env; done
  grep -nE "clientId: vectra-console$" identity-edge/keycloak/realm/realm.kind.yaml identity-edge/keycloak/realm/realm.staging.yaml identity-edge/keycloak/realm/realm.prod.yaml
  grep -n "^hostname:" identity-edge/gateway/values/kind.yaml identity-edge/gateway/values/staging.yaml identity-edge/gateway/values/prod.yaml
  ! grep -n "clientId: console-bff" identity-edge/keycloak/realm/realm.kind.yaml
  ```
  Esperado: código 0. Para kind, la tercera orden imprime las claves `['grafana', 'oidc', 'redirect_uri', 'stepup_redirect_uri']`, `['authority', 'client_id']`, `['bias_dashboard_uid']`, y los valores `https://vectra.localtest.me/auth/realms/vectra`, `vectra-console`, `https://vectra.localtest.me/callback` y `https://vectra.localtest.me/stepup-callback`; para staging y prod, lo mismo con su hostname. Tres líneas del realm, tres de hostname, y el último `grep` no imprime nada. Las pruebas comprueban, sobre el render **de los tres entornos**:
  - **`parseConfig` real:** `chart-config.test.ts` pasa el `config.json` rendido de cada entorno por `parseConfig` de `console/spa/src/config/load.ts` (importado, no una copia del esquema) y no lanza. Con una clave de más lanza `unknown`; con una de menos, `missing`; con una constante de `TIME_CONSTANTS`, `constant`. Sin `VECTRA_CHART_RENDER`, o sin los tres archivos, la prueba **falla**; no se salta;
  - **realm de U2:** `oidc.client_id` es el `clientId` del cliente público de `realm.<env>.yaml`; el conjunto `{redirect_uri, stepup_redirect_uri}` es **igual** al de sus `redirectUris`, con `$(env:PUBLIC_HOSTNAME)` sustituido por `vectra.publicHostname` de `identity-edge/keycloak/values/<env>.yaml`. Todo leído de los archivos;
  - **gateway de U2:** el host de los tres valores es el `hostname` de `identity-edge/gateway/values/<env>.yaml`; `oidc.authority` es `https://<hostname>` más `jwt.issuer_path` de `routes.yaml`; el `authority` y los dos URI tienen el mismo origen;
  - **BFF:** los nombres de las variables del `ConfigMap` son exactamente `REQUIRED` ∪ `OPTIONAL` de `console_bff.app` más `ENDPOINT_ENV` de `vectra_common.telemetry`, importados; `VECTRA_OIDC_ISSUER` es **igual** al `oidc.authority` de la SPA del mismo entorno (P-4); `VECTRA_JWKS_URL` es `jwt.jwks_uri` de `routes.yaml`; `VECTRA_CA_BUNDLE` apunta a un archivo del volumen de `vectra-internal-ca`, montado de solo lectura; las cinco URL apuntan al Service, al namespace y al puerto de F10 a F14 de `flows.yaml`; ninguna variable lleva el nombre de una constante pública de `console_bff.config`;
  - **nombres:** el `Service`, la `ServiceAccount`, el namespace, la etiqueta `app.kubernetes.io/name` y el puerto de cada pieza son los de `flows.yaml` (identidades `console-bff` y `console-spa`) y los de los backends `spa` y `console` de `routes.yaml`; el `mountPath` del `ConfigMap` de la SPA es el directorio que `console/spa/nginx.conf` usa para `config.json`;
  - **`kind_render`:** los `Deployment` de U10 que ve `integration.render_env("kind")` (nombre, namespace, réplicas y request de memoria) son los mismos que rinde la orden de CA-2 para kind (P-3).

  Rojo de cada caso en la bitácora: añadir `version_poll_seconds` al `config.json`; quitar `grafana`; `client_id: console`; `redirect_uri` con `/auth/callback`; el hostname de staging en los values de kind; `VECTRA_OIDC_ISSUER` con `keycloak-admin`; `VECTRA_BIAS_URL` fuera del `ConfigMap`; `VECTRA_CASE_URL` al puerto 8081; `CASE_READ_TIMEOUT_SECONDS` como variable.
  **Hoy falla:** no existe `test_chart.py`, `chart-config.test.ts` ni el chart. Los tres `grep` ya pasan.

- [ ] **CA-4** — Pasos 17 y 18: los dos contenedores reales arrancan con lo que pone el chart.
  ```bash
  uptime
  uv run pytest console/bff/tests/integration/test_image.py -p no:cacheprovider --rootdir=console/bff -v
  ```
  Esperado: código 0. La prueba toma de **el render de kind** (CA-2) la orden, las variables, los montajes, el usuario y los `emptyDir` de cada contenedor. Cada contenedor corre con `docker run --read-only` y el `--user` del chart.
  1. **`console-bff`.** Variables: las del `ConfigMap` rendido. Solo cambian los hosts de las cinco URL y del JWKS por los de los dobles de `console/bff/tests/doubles/` (y `https` por `http` si el doble no tiene TLS; anótalo), y el archivo de la CA por uno de prueba **en la misma ruta**. `VECTRA_OIDC_ISSUER` es el del emisor de prueba (`bff_oidc.py`).
     - `/healthz` y `/readyz` responden 200 en el puerto publicado del 8081, **con los cinco destinos caídos**;
     - `/metrics` trae las seis series de `vectra_console_client_errors_total` en 0;
     - el 8080 responde 401 a `GET /api/console/me` sin token, y **200** con un token del emisor de prueba (`bff_tokens.py`): prueba el emisor, el JWKS y la audiencia juntos;
     - `docker stop -t 20` (el plazo de gracia del chart): sale con **0**, nunca 137, y la bitácora anota los segundos;
     - sin `VECTRA_BIAS_URL`: sale con **2**, antes de escuchar, y el mensaje nombra la variable;
     - con el JWKS en `https` y sin `VECTRA_CA_BUNDLE`: sale con **2**.
  2. **`console-spa`.** El `config.json` es el del `ConfigMap` rendido, escrito en un directorio del worktree y montado de solo lectura en el `mountPath` del chart; un `--tmpfs` por cada `emptyDir` del chart, en su ruta; ningún otro volumen.
     - `GET /healthz` → 200;
     - `GET /` y `GET /index.html` → 200, el `index.html` del build, `Cache-Control: no-store`;
     - `GET /config.json` → 200, **byte a byte** el del chart, `Cache-Control: no-store`;
     - `GET /cases/123`, `GET /casos/<uuid>`, `GET /callback` y `GET /stepup-callback` → 200, el mismo `index.html`, `Cache-Control: no-store`;
     - un archivo real de `assets/` → 200 con `Cache-Control: public, max-age=31536000, immutable`; con `Accept-Encoding: gzip`, `Content-Encoding: gzip`;
     - `GET /assets/no-existe.js` → **404**, y el cuerpo no es `index.html`;
     - `GET /.vite/manifest.json` y `GET /version.json` → 404;
     - ninguna respuesta trae `Content-Security-Policy`, `X-Frame-Options`, `Strict-Transport-Security`, `Referrer-Policy`, `Cross-Origin-Opener-Policy` ni `X-Content-Type-Options` (los nombres salen de los perfiles `common` y `spa` de `routes.yaml`), y la cabecera `Server` no trae versión;
     - el proceso no corre como root (`docker exec … id -u` distinto de 0) y `docker stop` sale sin 137;
     - sin el `--tmpfs` de `/tmp`, nginx **no** arranca: prueba que el `emptyDir` del chart hace falta.

  Si Docker no está disponible, la prueba **falla**; no se salta. Ningún contenedor usa el 8080 ni el 8081 **del host** como puerto fijo: publica puertos libres, como `product-metrics/tests/integration/test_image.py`. Registra en la bitácora cada `docker run`, su salida, el tiempo de cada apagado y la memoria en reposo de los dos (`docker stats --no-stream`).
  **Hoy falla:** no hay imágenes ni prueba.

- [ ] **CA-5** — Paso 18: admisión de U1 en los tres entornos.
  ```bash
  make -C console policy-chart-u1
  platform/.tools/bin/kyverno test platform/policies/kyverno
  ! grep -rn "PolicyException" platform/policies console/chart
  ! grep -nE "console-bff|console-spa" platform/policies/kyverno/require-spread-and-pdb.yaml
  git diff --exit-code origin/main -- platform/policies platform/network identity-edge
  ```
  Esperado: código 0, Kyverno con `fail: 0` y `conftest` de `platform/policies/rego` (incluido `--combine --namespace hpa`, que admite la exención de la SPA y exige el HPA del BFF) en 0, en kind, staging y prod y para los dos charts. Los casos `console-spa` de `kyverno-test.yaml` siguen en `pass`. Ningún `PolicyException` y ninguna exclusión de U10 (los dos `grep` no imprimen nada), y el `diff` vacío. `policy-chart-u1` rinde **un chart y un entorno por directorio** dentro de `platform/.tools/integration/u10/`, como `product-metrics/Makefile`: `make -C platform check-chart` entra en pánico con el PDB repetido entre entornos (C-8) y además borra `platform/.tools/integration/chart`. No la uses con `platform/.tools` enlazado al árbol principal.
  **Hoy falla** la primera orden (no hay target ni chart). La segunda ya pasa.

- [ ] **CA-6** — Paso 18: cuota y flujos.
  ```bash
  uv run python platform/policies/quotas/render.py --check \
    && uv run pytest "platform/tests/test_integration.py::test_every_workload_declares_requests_and_limits_and_fits_the_quota" -v \
    && uv run python platform/network/generate.py --check && uv run pytest platform/network/tests -q \
    && for id in F02 F03 F10 F11 F12 F13 F14 F50 F60; do grep -q "id: $id," platform/network/flows.yaml || echo "falta $id"; done \
    && grep -n "id: F02, from: \[api-gateway\], to: \[console-spa\], port: 8080" platform/network/flows.yaml \
    && grep -n "id: F03, from: \[api-gateway\], to: \[console-bff\], port: 8080" platform/network/flows.yaml \
    && grep -cE "id: F1[0-4], from: \[console-bff\], to: \[[a-z-]+\], port: 8080" platform/network/flows.yaml \
    && grep -cE "id: U10, from: console-(spa|bff)" platform/network/forbidden.yaml \
    && grep -n "U10: { requests: \[3.19, 2.4\], limits: \[13.7, 5.7\] }" platform/policies/quotas/quotas.yaml \
    && grep -n "U10: { requests: \[0.78, 0.26\], limits: \[3.64, 0.97\] }" platform/policies/quotas/quotas.yaml
  uv run pytest console/bff/tests/unit/test_chart.py -p no:cacheprovider --rootdir=console/bff -k "quota or flows or forbidden" -v
  ```
  Esperado: código 0, ninguna línea «falta», `5` en el conteo de F10 a F14 y `4` en el de los casos bloqueados. Las pruebas de `test_chart.py`:
  - recalculan el aporte de U10 desde el render de prod (7 y 4 pods, el proxy y el 30 %) y lo comparan con las dos líneas de `quotas.yaml`, leídas del archivo, según P-6;
  - leen `forbidden.yaml` y comprueban que están los casos de INF-U10-04: SPA → un servicio de `vectra-app`, BFF → `vectra-data` y BFF → `vectra-serving`;
  - leen `platform/network/generated/kind/` y comprueban que existen los `Server` `console-spa-8080` y `console-bff-8080`, con el selector que llevan los pods del chart.

  **Hoy:** la primera orden completa ya pasa (los `grep` se comprobaron al redactar). Falla la segunda: no existe `test_chart.py`.

- [ ] **CA-7** — Paso 18: los values por entorno.
  ```bash
  for env in kind staging prod; do for n in console-bff console-spa; do test -s vectra-risk-gitops/values/$env/$n.yaml || echo "falta $env/$n"; done; done
  ! grep -rniE "secret|password|private|BEGIN " vectra-risk-gitops/values/*/console-bff.yaml vectra-risk-gitops/values/*/console-spa.yaml console/chart/bff/values.yaml console/chart/spa/values.yaml console/chart/bff/values-kind.yaml
  grep -c "" console/chart/bff/values-kind.yaml
  test ! -e console/chart/spa/values-kind-demo.yaml && test ! -e console/chart/bff/values-kind-demo.yaml
  uv run pytest console/bff/tests/unit/test_chart.py -p no:cacheprovider --rootdir=console/bff -k "values or secrets or checksum" -v
  ```
  Esperado: código 0, ninguna línea «falta» y el `grep` de secretos sin salida. Las pruebas:
  - un `config.json` con una clave `client_secret`, o con un valor con forma de llave (PEM o JWT), hace fallar `conftest`;
  - cambiar el hostname en `values/kind/console-spa.yaml` cambia `config.json` **y** el `checksum/config` del pod template;
  - cambiar una URL en los values del BFF cambia su `ConfigMap` y su `checksum/config`;
  - `values-kind.yaml` solo fija el máximo del HPA y el request de memoria; staging y prod rinden 256 MiB y HPA de 2 a 6.

  **Hoy falla:** los seis archivos no existen.

- [ ] **CA-8** — Paso 21: Applications.
  ```bash
  uv run python vectra-risk-gitops/generate.py --check && uv run python platform/tests/test_waves.py \
    && for env in kind staging prod; do for n in console-bff console-spa; do platform/.tools/bin/kyverno apply platform/policies/kyverno/disallow-argocd-auto-sync.yaml --resource vectra-risk-gitops/apps/$env/$n.yaml || echo "FALLA $env/$n"; done; done \
    && platform/.tools/bin/kyverno test platform/policies/kyverno \
    && grep -n "sync-wave" vectra-risk-gitops/apps/*/console-bff.yaml vectra-risk-gitops/apps/*/console-spa.yaml \
    && ! grep -rn "automated" vectra-risk-gitops/apps/*/console-bff.yaml vectra-risk-gitops/apps/*/console-spa.yaml
  for env in kind staging prod; do for n in console-bff console-spa; do grep -c "values/$env/$n.yaml" vectra-risk-gitops/apps/$env/$n.yaml; done; done
  grep -c "values-kind.yaml" vectra-risk-gitops/apps/kind/console-bff.yaml vectra-risk-gitops/apps/staging/console-bff.yaml vectra-risk-gitops/apps/prod/console-bff.yaml
  grep -n "namespace: vectra-" vectra-risk-gitops/apps/kind/console-bff.yaml vectra-risk-gitops/apps/kind/console-spa.yaml
  uv run pytest platform/tests/test_platform.py -k "every_component_is_in_its_wave or gitops_manifests_match_components" -v
  git diff origin/main -- platform/tests/test_platform.py | grep -E "^[-+]" | grep -vcE "^(\+\+\+|---) "
  ```
  Esperado: código 0 y ninguna línea «FALLA». Seis Applications (dos por entorno), todas con wave `'5'`, sin `syncPolicy.automated` y con su `values/<env>/<nombre>.yaml` (`1` seis veces). `values-kind.yaml`: `1` en kind y `0` en staging y prod. Destino `vectra-app` para el BFF y `vectra-edge` para la SPA. El `diff` de `test_platform.py` tiene `2` líneas: la de `EXPECTED_WAVES[5]`, quitada y puesta. Con `wave: 4` en `components.yaml` **y las Applications regeneradas**, `test_waves.py` da rc 1 (`FIXED_WAVES`; lección de U11-T03, F-01: sin regenerar no falla).
  **Hoy:** `generate.py --check` y `test_waves.py` pasan, pero no existe ninguna de las seis Applications y los `grep` fallan.

- [ ] **CA-9** — Paso 21: trazabilidad (P-4 de la enmienda).
  ```bash
  uv run python platform/tests/test_traceability.py --unit console --all \
    && for n in 01 02 03 04 05 06 07 08 09 09b 10 11 12 13 15 17 18 19 20 22; do git grep -qiE "BR-U10-$n([^0-9b]|$)" -- console/bff/tests console/spa/tests || echo "BR-U10-$n sin prueba"; done
  uv run python platform/tests/test_traceability.py --all | grep -c "U10-"
  grep -n "^## Diferido por la demo" -A16 aidlc-docs/construction/console/evidence/cierre-demo.md
  grep -rnE "(INF-U10-05|NFR-U10-01|NFR-U10-04|NFR-U10-21|P-U10-06|P-U10-10)([^0-9]|$)" console/ --exclude-dir=node_modules --exclude-dir=dist; echo "rc=$?"
  ```
  Esperado: código 0 y ninguna línea «sin prueba» (BR-U10-14, 16 y 21 no están en el bucle: van en la lista); `0` en el conteo de `--all` (y `--all`, sin `--unit`, cumple la regla «sin fallos nuevos» de `DECISIONES-LOOP.md` §6 frente a la base); la lista tiene exactamente nueve filas (INF-U10-05, NFR-U10-01, NFR-U10-04, NFR-U10-21, P-U10-06, P-U10-10, BR-U10-14, BR-U10-16 y BR-U10-21); la última orden no imprime nada y da `rc=1`.
  **Hoy falla:** 15 identificadores sin trazabilidad (INF-U10-02, 04, 05 y 06; NFR-U10-01, 04, 10, 12, 20, 21, 22, 44 y 45; P-U10-06 y 10) y 7 BR sin prueba (BR-U10-02, 09b, 11, 14, 16, 18 y 21). No existe `evidence/cierre-demo.md`.

- [ ] **CA-10** — Presupuesto de memoria de kind.
  ```bash
  uptime
  uv run python -c "import sys; sys.path.insert(0, 'platform/tests'); import test_kind_profile as t; print(round(t.requested_gib([*t.declared_inference_services(), *t.PEAK_INFERENCE_SERVICES]), 4), t.BUDGET_GIB)"
  uv run pytest platform/tests/test_kind_profile.py -v
  git diff origin/main -- platform/tests/test_kind_profile.py
  grep -nE "Proyecci[oó]n" aidlc-docs/construction/console/evidence/cierre-demo.md
  ```
  Esperado: la segunda orden se corre **dos veces**, antes y después de agregar las Applications, y las dos cifras quedan en la bitácora. La diferencia es el aporte de U10: **0,3906 GiB** con P-1 = (b) o **0,6406 GiB** con (a). Las pruebas pasan. El `diff` solo cambia `BUDGET_GIB` y su comentario, con la cifra medida redondeada hacia arriba a 0,1 GiB y la cita de `DECISIONES-LOOP.md` §7 (la tabla de «Presupuesto», punto 4, da el valor para cada base). El cierre lleva la proyección total. Si la cifra no cuadra o la proyección llega a 13,0 GiB, es una **detención** (sección «Presupuesto»), no un ROJO del codificador.
  **Hoy:** en `main` la orden debe imprimir `10.6328 10.7` (la cifra del comentario de `test_kind_profile.py` y de la revisión de U11-T03; no se volvió a correr al redactar, porque el worktree de preparación no tiene `platform/.charts`). Con las Applications agregadas y sin tocar el tope, `test_the_profile_requests_fit_the_budget` falla: es el rojo esperado.

- [ ] **CA-11** — Candidata C-1 y registro de candidatas.
  ```bash
  uv run pytest console/bff/tests/integration/test_clients.py -p no:cacheprovider --rootdir=console/bff -k "pool or connections" -v
  git diff origin/main --stat -- console/bff/src console/spa/src
  git diff origin/main -- CANDIDATAS.md | grep -c "Atendida en U10-T05"
  ```
  Esperado: código 0; el `diff` de `console/bff/src` y `console/spa/src` **vacío**; al menos `4` en el conteo (C-1, C-2, C-3 y C-4; las demás se atienden sin cerrarse). La bitácora lleva el rojo: con `CONNECTIONS_PER_REPLICA["case"]` en 1 000 (M11) o en 21 (M12), la prueba del pool falla; y con `Upstreams` sin pasar el límite, falla la prueba nueva.
  **Hoy falla:** las dos mutaciones sobreviven (`revisiones/U10-T02/ronda-1.md`, F-01).

- [ ] **CA-12** — Paso 23: documentación.
  ```bash
  test -s console/README.md
  uv run python platform/tests/test_links.py --root console
  for s in "role-endpoint-matrix.md" "infrastructure-design.md" "deployment-architecture.md" "nfr-design-patterns.md" "nfr-requirements.md" "business-rules.md" "bff-api.md" "bff-logic.md" "spa.md" "bff_e2e_server.py" "config.json" "VECTRA_OIDC_ISSUER" "constants.ts" "config.py" "rollback" "Imágenes"; do grep -qF "$s" console/README.md || echo "falta $s"; done
  grep -ciE "diferid" console/README.md
  uv run python contracts/tools/forbidden_phrases.py console/README.md
  ```
  Esperado: código 0, ninguna línea «falta», al menos `3` en el conteo de «diferid» (el workflow de release, las etapas `previous` y el runbook de rollback) y `forbidden_phrases.py` sin salida. `test_links.py` no encuentra enlaces rotos.
  **Hoy falla:** no existe `console/README.md`.

- [ ] **CA-13** — Paso 24: cierre.
  ```bash
  uptime; time make -C console check
  grep -nE "^## (Comprobado|Decisiones|Pendiente en U12|Diferido por la demo)" aidlc-docs/construction/console/evidence/cierre-demo.md
  for s in "Keycloak real" "CSP" "cumplimiento-1" "F03" "F10" "F11" "F14" "iss" "echo/manifests.yaml"; do grep -qF "$s" aidlc-docs/construction/console/evidence/cierre-demo.md || echo "falta $s"; done
  grep -n "^check:" console/Makefile
  ```
  Esperado: código 0, las cuatro secciones y ninguna línea «falta». El `check` de U10 corre, en orden: `lint` (BFF y SPA), `test-bff`, `test-spa`, `e2e-spa` (con `build-spa`), `image-bff` e `image-spa`, `image-test`, `policy-chart` (con `chart-config`), `policy-chart-u1`, `quota-flows`, `gitops`, enlaces y trazabilidad. **Falla** si falta una herramienta (`helm`, `kubeconform`, `conftest`, `kyverno`, `hadolint`, Docker, los navegadores de Playwright): no se salta con rc 0. Registra la duración y el `uptime`.
  **Hoy:** `make -C console check` pasa con `lint` y `test` (bitácora de U10-T04). Falla el `grep` del cierre.

- [ ] **CA-14** — RL-4: el `make check` de las unidades que el diff toca.
  ```bash
  uptime; time make -C platform check-local
  mkdir -p platform/.tools/tmp && uptime && time env TMPDIR=$PWD/platform/.tools/tmp make -C platform check-tools
  ```
  Esperado: código 0 en las dos. Van porque el diff toca `test_platform.py`, `test_kind_profile.py` y `components.yaml`. **Por separado**: `check-local` con el `TMPDIR` por omisión (con `TMPDIR` dentro del repositorio da falsos rojos: `test_identity_seed` rechaza claves dentro del repo y `test_traceability` salta `.tools`), y `check-tools` con `TMPDIR` en el worktree (`promtool` escribe en `TMPDIR` y `/tmp` está casi lleno). Es lo que hizo el revisor de U11-T03 (`revisiones/U11-T03/ronda-1.md`, «Notas del entorno»). Si un fallo también ocurre en `origin/main`, regístralo con la salida y su causa: no es de esta tarea. El cierre cita las cifras (lección de U09-T04, F-02).
  **Hoy:** pasan en `main`.

- [ ] **CA-15** — Estado del plan y nada de lo diferido.
  ```bash
  git diff origin/main -- aidlc-docs/construction/plans/console-code-generation-plan.md | grep -E "^\+- \[.\] \*\*Paso (17|18|19|2[0-4]) "
  git diff origin/main -- aidlc-docs/construction/plans/console-code-generation-plan.md | grep -E "^[-+]" | grep -vcE "^(\+\+\+|---) "
  test ! -e console/spa/lighthouserc.json && test ! -e console/bff/tests/load/console.js && test ! -e console/spa/stryker.conf.json && echo OK-diferidos
  git diff origin/main --name-only -- ../.github | wc -l
  ! grep -rnE "kind: PrometheusRule|grafana_folder" console/chart
  git diff origin/main --name-only | grep -vE "^vectra-risk/(console/|vectra-risk-gitops/|platform/tests/test_(platform|kind_profile)\.py$|aidlc-docs/construction/console/(evidence/cierre-demo|code/spa)\.md$|aidlc-docs/construction/plans/console-code-generation-plan\.md$|CANDIDATAS\.md$|bitacoras/U10-T05\.md$|package-lock\.json$)"; echo "rc=$?"
  ```
  Esperado: Pasos 17, 18, 21, 23 y 24 en `[x]` con `(U10-T05…)` y su nota; Pasos 19 y 20 en `[ ]` con «diferido por la demo (T2)» y «(T4)»; Paso 22 en `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)». El segundo conteo es `17`: ocho líneas quitadas y nueve puestas (la novena es la nota de §1). `OK-diferidos`; `0` archivos de workflows; el `grep` de reglas sin salida; y la última orden no imprime nada (`rc=1`): el diff no toca nada fuera de lo nombrado. `package-lock.json` solo cambia si una dependencia nueva lo exige, y entonces la bitácora dice cuál.
  **Hoy:** los ocho pasos están en `[ ]` sin nota.

---

## Plan de pruebas

Se escriben en esta tarea: `console/bff/tests/unit/test_chart.py`; `console/bff/tests/integration/test_image.py`; `console/spa/tests/unit/chart-config.test.ts`; las reglas de `console/policies/conftest/`; y las dos pruebas de C-1 en `test_clients.py`.

**Rojo primero**, con cada par falla-pasa en `bitacoras/U10-T05.md`:

- `replicas: 1` en `console-spa`, o sin `vectra.io/hpa-exempt` (`conftest` o el `rego` de U1 falla);
- HPA de 1 a 6 en el BFF; HPA de 2 a 6 en kind; el BFF sin HPA;
- `maxSurge: 1` en la SPA; `maxUnavailable: 1` en el BFF;
- el `ConfigMap` de `config.json` con `subPath`; montado en `/usr/share/nginx/html` (CA-2 falla, y en CA-4 `GET /` da 403 o 404);
- sin `checksum/config`;
- una clave de más en `config.json` (CA-3 falla en `parseConfig`);
- `client_id` distinto del realm; `redirect_uri` que el realm no registra;
- `VECTRA_OIDC_ISSUER` distinto del `authority` (CA-3 falla, y en CA-4 el token del emisor da 401);
- `VECTRA_BIAS_URL` fuera del `ConfigMap` (CA-3 falla, y en CA-4 el contenedor sale con 2);
- `/livez` como liveness del BFF;
- `terminationGracePeriodSeconds: 10` en el BFF; el BFF sin `preStop`;
- la SPA sin `emptyDir` en `/tmp` (en CA-4 nginx no arranca con `--read-only`);
- `nginx.conf` con el fallback para **toda** ruta (`/assets/no-existe.js` da 200: CA-4 falla);
- `nginx.conf` sin `no-store` en el fallback (`/stepup-callback` sin la cabecera);
- `nginx.conf` con `add_header Content-Security-Policy` (CA-1 y CA-4 fallan);
- `COPY dist` sin excluir `.vite/` (CA-1 y CA-4 fallan);
- `FROM node:22` sin digest (el conteo de CA-1 no cuadra);
- `npm ci` sin `--ignore-scripts`;
- `syncPolicy.automated` en `apps/kind/console-spa.yaml` (Kyverno falla);
- `wave: 4` en `components.yaml`, con las Applications regeneradas (`test_waves.py` falla);
- `NFR-U10-45` en la lista de diferidos, y `P-U10-06` citado en `console/spa/Dockerfile` (`test_traceability.py` falla las dos veces);
- M11 y M12 de C-1.

---

## Preguntas abiertas

**P-1 necesita la decisión del usuario antes de despachar.** En las demás, si nadie responde, rige la recomendación.

- **P-1 · Request de memoria de `console-bff` en kind (necesita al usuario).** INF-U10-01 fija 256 MiB por réplica («la prueba de carga de P-U10-11 confirma o ajusta los valores») y `deployment-architecture.md` dice que kind es como staging salvo el HPA. La prueba de carga está diferida (T3) y la máquina tiene 14 GiB.
  - (a) 256 MiB también en kind, la letra del diseño: U10 suma **0,6406 GiB**. Total con U8: 12,0156 GiB (`BUDGET_GIB` 12,1).
  - (b) **128 MiB solo en kind** para el BFF (recomendada), en `console/chart/bff/values-kind.yaml`: U10 suma **0,3906 GiB**. Total con U8: 11,7656 GiB (`BUDGET_GIB` 11,8). Mismo patrón que la opción (c) de `DECISIONES-LOOP.md` §7 para U6 y que las decisiones del usuario del 2026-11-12 para U11 y U8 (§9: «128 MiB **solo en kind**»): solo el request, sin tocar réplicas, HPA, PDB ni limits (512 MiB), y staging y prod siguen en el diseño. El BFF no tiene base ni caché; su memoria en reposo se anota en CA-4 y la real se comprueba en U12.
  - (c) Otra cifra que el usuario indique.

  La SPA no cambia en ninguna opción (32 MiB). Es una desviación del diseño para un entorno, como las de U6, U8 y U11: por eso la decide el usuario. Ninguna de las dos opciones llega al tope de detención de 13,0 GiB; la (b) deja 0,25 GiB más de margen y mantiene una sola regla para los servicios de Python de la demo. Un request más bajo que el uso real no rompe el pod (el limit sigue en 512 MiB), pero deja al planificador contar menos memoria de la que se usa.

- **P-2 · Un chart o dos.** §1 del plan tiene un solo `chart/` con `templates/` y `values.yaml`. El Paso 21, `FIXED_WAVES` (`console-bff` y `console-spa`), INF-U10-02 (`values/prod/console-spa.yaml`) y `deployment-architecture.md` («una por componente») piden **dos** Applications, en dos namespaces.
  - (a) **Dos charts, `console/chart/bff` y `console/chart/spa`** (recomendada): cada entrada de `components.yaml` tiene su `path`, y `render_env`, `integration.py --chart` y `test_kind_profile.py` funcionan sin trucos. «Reglas de admisión» del plan ya habla de «cada chart de esta unidad». Costo: §1 queda con una nota.
  - (b) Un chart y dos entradas con el mismo `path`, que eligen la pieza con un value. No sirve: `render_env` no pasa `values/<env>/<nombre>.yaml` ni la clave `values` de un componente `path` (C-9), así que las pruebas de U1 rendirían las dos piezas dos veces y contarían el doble de memoria y de cuota.
  - (c) Una sola Application `console`, con el namespace explícito en los recursos de la SPA (como `governance`). Contradice el Paso 21, `FIXED_WAVES` y el archivo de values que el flujo de release lee.

- **P-3 · Dónde van los values de cada entorno para que `render_env` los vea.** El plan los pone en `vectra-risk-gitops/values/<env>/console-bff.yaml` y `console-spa.yaml`, y `generate.py` los pasa a Argo CD. `platform/tests/integration.py` `render_env` **no** los pasa (C-9).
  - (a) **Defaults de producción en cada `values.yaml`; `chart/bff/values-kind.yaml` por `kind_values` con lo que las pruebas de U1 deben ver (HPA y request); y el hostname y el emisor en `values/<env>/`** (recomendada). Un chart con `required` y sin default no rendiría en `test_integration.py`. Una prueba compara los dos renders de kind (CA-3, `kind_render`). Costo: el `render_env("kind")` de U1 ve el hostname de producción en `config.json`; no lo mira ninguna prueba de U1, y el render de Argo CD (`--chart`) sí es el correcto.
  - (b) Todo en `values/<env>/`, y `render_env` pasa los values de la unidad. Es el arreglo correcto, pero cambia una herramienta de U1 que usan todas las unidades.
  - (c) El hostname en `vectra-risk-gitops/envs/<env>/values.yaml`. Duplica un dato de U2 en un archivo compartido de U1.

- **P-4 · Emisor y JWKS del BFF.** Los charts de U3, U4, U7, U9 y U11 usan `https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/realms/vectra` como `VECTRA_OIDC_ISSUER`. Keycloak corre con `KC_HOSTNAME=https://<hostname público>/auth` (`identity-edge/keycloak/values/common.yaml`, líneas 138 y 139) y el gateway valida `issuer: https://vectra.localtest.me/auth/realms/vectra` (`identity-edge/gateway/generated/kind/securitypolicies.yaml`). El BFF recibe **el token del navegador**, emitido por esa URL pública.
  - (a) **El emisor público, igual al del gateway y al `authority` de la SPA; JWKS en `jwt.jwks_uri` de `routes.yaml`** (`https://keycloak.vectra-identity.svc:8443/…`, F50), con la CA `vectra-internal-ca` (recomendada). Una prueba ata los tres valores.
  - (b) `keycloak-admin`, como los otros charts. Si el `iss` real es el público, toda la API de la consola da 401.

  No se puede comprobar sin clúster: va en «Pendiente en U12». **Riesgo fuera de esta tarea:** el BFF reenvía ese mismo token a U3, U4, U7, U8 y U9, cuyos charts esperan el emisor `keycloak-admin`. Si rechazan el `iss` público, F10 a F14 dan 401 en kind. No lo arregles: déjalo como candidata, con las cinco rutas de los `values.yaml`.

- **P-5 · `grafana.bias_dashboard_uid` sin `bias.json`.** `parseConfig` exige la clave, no vacía. El dashboard `bias.json` de U9 está diferido (cierre de `bias-monitoring`, fila INF-U9-05) y `GrafanaEmbed` también: nadie lee el valor.
  - (a) **`vectra-bias`**, con el patrón de los dashboards de U1 (`vectra-slo`, `vectra-seguridad`, `vectra-resiliencia`), y una candidata para que U9 use ese `uid` (recomendada).
  - (b) Hacer la clave opcional en `load.ts`. Cambia `console/spa/src` y el diseño (domain-entities §4): fuera de esta tarea.

- **P-6 · El aporte de memoria del BFF en `quotas.yaml`.** Recalculado da 2,4527 GiB; `quotas.yaml` e INF-U10-01 dicen 2,4 («≈»). Los otros siete valores coinciden al redondear.
  - (a) **La prueba admite la diferencia del redondeo del diseño** (cada valor recalculado dista menos de 0,06 del declarado) y queda una candidata para que U1 suba la línea a 2,46 (recomendada). La cuota real del namespace no se excede: `test_every_workload_declares_requests_and_limits_and_fits_the_quota` lo comprueba con el render.
  - (b) Corregir `quotas.yaml` y regenerar `generated.yaml` aquí. Toca U1 fuera de lo nombrado.

Decidido por el recorte, no es pregunta: **las etapas `previous` no entran.** La fila «17 · 18» las ata a `version`, y `version` está diferido (fila «12», P-15; U10-T03). `spa.md` §11 y `tareas/U10-T04-spa-vistas-y-e2e.md` dicen «con las etapas `previous`»: esta tarea corrige §11 y lo deja en la bitácora.

---

## Restricciones del entorno

- **`/tmp` es un tmpfs con cuota y está casi lleno.** No copies el repositorio ni corras `npm ci` allí: **`npm ci --ignore-scripts` va dentro del worktree**. Los renders van a `platform/.tools/integration/u10/`. `promtool` y `check-tools` escriben en `TMPDIR`: usa `TMPDIR=$PWD/platform/.tools/tmp` **solo** para `check-tools`. Con `TMPDIR` dentro del repositorio, `check-local` da falsos rojos: córrelos por separado (CA-14).
- **Máquina compartida, cargada y con poca memoria** (hasta 3 codificadores, RL-5). Corre las suites **en serie**. Anota `uptime` junto a cada medida de tiempo o de memoria. `docker build` de la SPA instala todo el workspace de npm: no lo lances a la vez que Playwright. Una prueba con límite de tiempo que falla con carga alta se repite en frío antes de darla por rota, y se anotan las dos corridas.
- **Puertos 8080 y 8081 fijos.** `run_service` de U0 abre esos puertos en el host durante `console/bff/tests/integration/test_service_shutdown.py`, y las suites de U8, U9 y U11 hacen lo mismo. No lances dos `make check` a la vez. Los contenedores de CA-4 publican puertos libres. Los servidores de Playwright usan 47173, 47174, 47180 y 47181.
- **`platform/.tools` y `platform/.charts` no están versionados.** En un worktree nuevo, `make -C platform check` y las órdenes con `platform/.tools/bin/` fallan. **No enlaces esos directorios enteros al árbol principal**: en U11-T03, un `make -C platform check-chart` corrido en un worktree con el enlace borró `platform/.tools/integration/chart` del árbol principal. Crea `platform/.tools/` real en el worktree y enlaza o copia **solo** `platform/.tools/bin`; `integration/` y `tmp/` son del worktree. Compara las versiones con `platform/tools.env`. Regístralo en la bitácora.
- **Charts de U1.** `platform/.charts` se llena con `platform/charts.sh` (`make -C platform charts`), que baja también los charts OCI (`envoy-gateway`, `kserve*`). Sin ellos `render_env` no rinde los charts upstream (CA-10 no corre) y fallan pruebas de `platform/network/tests/test_edge_selectors.py`. O cópialo del árbol principal, sin enlazarlo.
- **Navegadores de Playwright.** `make -C console e2e-spa` falla si faltan y dice cómo instalarlos (`npx playwright install chromium firefox`, a `~/.cache`, sin sudo).
- **Docker** está disponible para construir y correr las dos imágenes. Hace falta red para bajar las imágenes base por digest.
- **Sin clúster.** Nada de `kubectl`, `helm install`, `argocd` ni `kind`.
- **No toques** el árbol principal, otros worktrees ni la raíz del scratchpad compartido. **No uses `git stash`.**
- **Otros codificadores en paralelo** (U8 y U12): no toques sus directorios. Si otra tarea toca a la vez `components.yaml`, `test_kind_profile.py`, `EXPECTED_WAVES` o los digests de ejemplo, el orquestador resuelve el conflicto al integrar; tú partes de la base de tu rama.

---

## Notas

- **Orden sugerido**, para que lo que sostiene las demos quede primero: imágenes y `nginx.conf` (Paso 17) → chart de la SPA con `config.json` y mundo cerrado (CA-3) → chart del BFF → contenedores reales (CA-4) → values por entorno y `conftest` → Applications y memoria de kind → C-1 → README → trazabilidad y cierre.
- **Nombres que rompen las herramientas:** nada de directorios `generated`, `rendered` ni `dist` nuevos dentro de `console/` (`test_traceability.py` los salta; `spa/dist/` ya está en `.gitignore`).
- **Enlaces:** `test_links.py` lee como enlace cualquier corchete cerrado seguido de un paréntesis fuera de un bloque de código. Cuidado con los patrones de `grep` en los Markdown nuevos.
- **`/healthz` de la SPA** queda expuesto por el gateway (la ruta `spa` es el prefijo `/`). Es un 200 estático sin datos; no añadas una ruta ni una regla en U2.
- Archivos que se modifican en su sitio:
  - en `console/`: `Makefile`, `bff/tests/integration/test_clients.py` (C-1) y las pruebas que reciben una cita de BR. **Nada de `bff/src/` ni de `spa/src/`**;
  - `vectra-risk-gitops/components.yaml` y lo generado;
  - `platform/tests/test_platform.py` (solo `EXPECTED_WAVES[5]`) y `platform/tests/test_kind_profile.py` (solo `BUDGET_GIB`);
  - `aidlc-docs/construction/console/code/spa.md` (§11), el plan (casillas y nota de §1) y `CANDIDATAS.md`.
- Archivos nuevos: los de «Estructura de destino», los seis `values/<env>/console-*.yaml` y `aidlc-docs/construction/console/evidence/cierre-demo.md`.
- **Candidatas nuevas que la tarea debe dejar en `CANDIDATAS.md`:** «audiencias» en el Paso 18 del plan, sin variable en el código; §1 del plan con un solo `chart/` (P-2); el aporte de 2,4 GiB de `quotas.yaml` (P-6); el `uid` de `bias.json` (P-5); el emisor `keycloak-admin` de los otros charts frente al `iss` público (P-4); el `manifest.json` que las etapas `previous` necesitarán en la imagen, fuera de la raíz servida, cuando vuelvan; `test_traceability.py` no lee `.conf` ni `.mjs`; y lo que CA-4 revele del arranque de nginx con otro usuario o del código de salida del BFF dentro de un contenedor.
- **Bitácora:** `bitacoras/U10-T05.md`, con:
  - los pares falla-pasa;
  - la lista de diferidos razonada y la justificación de cada identificador trazado;
  - cada `docker run` de CA-4, su salida, el tiempo de cada apagado y la memoria en reposo;
  - la memoria de kind (dos mediciones y proyección);
  - la decisión de P-1 a P-6;
  - la duración de cada `make check` con su `uptime`.
