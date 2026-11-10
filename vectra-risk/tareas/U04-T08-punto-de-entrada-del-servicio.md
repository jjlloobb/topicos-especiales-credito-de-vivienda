# U04-T08 — Punto de entrada de `governance-service` y cliente S3 de F47

**Unidad:** U4 `governance`
**Historias:** ninguna nueva. Completa el Paso 10 (US-201..208 y US-305 en su parte HTTP), que U04-T04 dejó sin arranque.
**Depende de:** U04-T06 (chart con las variables de entorno del Deployment), fusionada en `main`.
**Se despacha** cuando U04-T06 esté en `main`. Va **antes** de U04-T07 (guía de kind).
**Rama:** `tarea/U04-T08`, desde `origin/main`.

**Por qué.** El revisor de U04-T06 (`revisiones/U04-T06/ronda-1.md`, F-01) arrancó la imagen y sale con `No module named vectra_governance.service`. `governance/src/vectra_governance/` no tiene `service.py`, `build_app` ni `__main__`: `api.py` solo exporta `create_governance_app(deps, authenticator=None)` y nadie arma `ApiDeps` desde el entorno. Sin esto el pod no arranca en kind, no hay `serving-config` ni política, y se cae el flujo base de las cuatro demos. Es del Paso 10 (E), que entra completo (`demo-recorte-funcional.md` §3 U4). La candidata de U04-T04 «cliente S3 de F47 y `build_app`» (`CANDIDATAS.md`) ya lo anunciaba. Arbitraje: `revisiones/U04-T06/arbitraje-ronda-1.md`.

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. `--all` según `DECISIONES-LOOP.md` §6, con su enmienda.

---

## Alcance

**Dentro:**

1. **`governance/src/vectra_governance/service.py`**, con el patrón de `decision-registry/src/vectra_registry/service.py` (U3): `config_from_env()`, `build_app()` y `main()`.
   - `config_from_env()` lee **exactamente** las variables que el chart de U04-T06 pone en el Deployment (`governance/chart/templates/service.yaml`): `GOVERNANCE_DATABASE_DSN` con `PGUSER`/`PGPASSWORD`, `GOVERNANCE_S3_*` (F47), `GOVERNANCE_CALLBACK_URL`, `GOVERNANCE_JOB_*`, `GOVERNANCE_VALIDATION_IMAGE`, `GOVERNANCE_VALIDATION_DATASET`, y las de U0 (`VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL`, `VECTRA_CA_BUNDLE`). Si falta una obligatoria, falla al arrancar con un mensaje que la nombra. Si el chart y el código no coinciden en un nombre, gana el chart; si el chart no entrega algo que el servicio necesita, **detente y repórtalo** (no cambies el chart sin decirlo).
   - `build_app()` arma `ApiDeps` y llama a `create_governance_app`: `Pools` y `Evidence` (U04-T03), `ServingConfigCache` y la convergencia (Paso 9), el `PackageStore` sobre S3 de F47 (lectura del model-store con `minio-governance`), `KubernetesJobs` (K01, in-cluster), el cliente del registro (U3, `append`) y el `SourceComparer` de F25 (U9), y `Background` (reconciliador y barridos del Paso 8) con su arranque y apagado ordenado en el ciclo de vida de la app.
   - `main()` sirve en 8080 el contrato y en 8081 `/metrics`, `/healthz` y `/readyz` (`vectra_common.ops_server`), con la readiness de NFR-U4-25 (P-U4-03): `serving-config` responde aunque la base esté pausada.
2. **Cliente S3 de F47** (`PackageStore`): leer `manifest.json` y los archivos del paquete por `*_uri` (la convención `s3://model-store/<model_version_id>/` de `reference-model/docs/release.md` y de `api.py:243`), con firma SigV4, timeouts y la CA interna. Pruebas contra **MinIO real con Testcontainers** (no un doble): registrar un paquete real de U5 subido al MinIO de prueba.
3. **Dockerfile:** el `CMD` de `governance/Dockerfile` apunta a `python -m vectra_governance.service` (o al módulo que crees), y `governance/chart/` sigue igual salvo que haga falta un `emptyDir` en `/tmp` por `readOnlyRootFilesystem` (candidata de U04-T06): agrégalo solo si el arranque lo exige, con su regla de conftest.
4. **Cierra** en `CANDIDATAS.md` las candidatas de `build_app`/S3 de F47 y la de `callback_url`, `DEFAULT_S3_ENDPOINT` y `DEFAULT_TOKEN_URL` (ahora leídos del entorno).

**Fuera:**
- Cualquier cambio en U0, U1, U3, U5, U6 o U9. Si algo falta allí, detente y repórtalo.
- Lo diferido de U4 (Pasos 14 y 15, `retire_inference_service`, modo `source_comparison` del Job, la rama `source_comparison` del barrido).
- Nada contra el clúster (AUTONOMIA-01); el arranque se prueba con Docker local y Testcontainers.

---

## Archivos de contexto

- `revisiones/U04-T06/ronda-1.md` (F-01) y `arbitraje-ronda-1.md`; `revisiones/U04-T04/` y `bitacoras/U04-T04.md` (cómo se probó la API).
- `governance/src/vectra_governance/` (`api.py`, `evidence.py`, `background.py`, `convergence.py`, `pools.py`, `k8s_jobs.py`, `clients.py`).
- `decision-registry/src/vectra_registry/service.py` y `decision-registry/tests/service_harness.py` (patrón de U3).
- `governance/chart/templates/service.yaml`, `governance/Dockerfile`.
- `contracts/python/vectra_common/src/vectra_common/` (`app_factory`, `ops_server`, `deps`, `service_token`).
- `aidlc-docs/construction/governance/` (NFR-U4-03, 05, 25; P-U4-02, 03, 04; INF-U4-01, 04).
- `reference-model/docs/release.md` y los paquetes de U5.

---

## Criterios de aceptación

Desde `vectra-risk/`.

- [ ] **CA-1** — El contenedor arranca. Con Docker local: Postgres (Testcontainers o `docker run`), MinIO con un paquete de U5, y las variables del chart, `docker run … localhost:5001/vectra/governance:dev` deja `/healthz` y `/readyz` en 200 y `GET /v1/serving-config` responde (sin política activa, el código que diga el contrato). Rojo primero: con la imagen actual sale `No module named vectra_governance.service`. Si `docker run -p` está denegado en esta máquina, usa la red de Docker entre contenedores y regístralo.
- [ ] **CA-2** — `config_from_env`: una prueba por variable obligatoria ausente (mensaje que la nombra) y una que compara los nombres con los de `governance/chart/templates/service.yaml` renderizado (ninguna sobra ni falta).
- [ ] **CA-3** — `build_app` + ciclo de vida: prueba de integración (Testcontainers Postgres y MinIO) que arma la app con `build_app()`, registra un paquete real de U5 por `POST /v1/models` leyéndolo de MinIO por F47, y comprueba que `Background` arranca y se detiene ordenadamente al cerrar.
- [ ] **CA-4** — Cliente S3: firma SigV4 contra MinIO real, timeout y error de red → error del contrato, nunca 500 sin cuerpo.
- [ ] **CA-5** — `make -C governance check` y `make -C platform check` en 0; `--all` sin fallos nuevos; `uv lock --check` en 0.
- [ ] **CA-6** — Plan: la nota del Paso 10 cita «arranque completado en U04-T08»; la casilla sigue `[x]`.

---

## Notas

- **Bitácora:** `bitacoras/U04-T08.md`, con el par rojo-verde del arranque.
- No uses `git stash`.
