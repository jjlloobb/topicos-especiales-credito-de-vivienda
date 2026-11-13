# Ronda 1 — U02-T21

VEREDICTO: VERDE

Reproduje la medición tres veces y sale igual que en la evidencia: **R2 confirmado**. No encontré ninguna configuración fiel a kind en la que Keycloak acepte la aserción con `aud` interna. Queda un hallazgo AMARILLO y no hay ni ROJO ni NARANJA.

## Medición reproducida

Antes de ejecutar el guion `identity-edge/tools/measure_issuer.py` lo leí entero. Todas las peticiones de httpx van a `https://127.0.0.1:<puerto>`. Las de curl van a `https://keycloak-admin…:8443` y `--connect-to` las desvía a `127.0.0.1:<puerto>`. El nombre `vectra.localtest.me` solo aparece en `KC_HOSTNAME` y en `X-Forwarded-Host`. El guion no llama a `kubectl` ni se conecta al kind.

Comprobaciones de fidelidad:
- **Imagen:** se lee de la línea `FROM` del Dockerfile y es `keycloak:26.8.1@sha256:3f3c5f8e…7332`, presente en local por digest. No descargué nada.
- **Variables:** `KC_HOSTNAME`, `KC_HOSTNAME_ADMIN`, `KC_PROXY_HEADERS=xforwarded` y `KC_HTTP_RELATIVE_PATH=/auth` se leen del StatefulSet de `rendered/kind/keycloak.yaml` y coinciden con sus líneas 240-269.
- **Build de la imagen:** el `kc.sh build` del Dockerfile no activa ninguna función que afecte al nombre de host.
- **Cliente de prueba:** `client-jwt` con `token.endpoint.auth.signing.alg: ES256` y `use.jwks.string`. Es lo mismo que llevan `case-service`, `scoring-service` y los demás en `realm.kind.yaml:1069-1246`. El realm no define `frontendUrl` ni ningún atributo que toque la `aud`.
- **M-c:** importa de verdad `vectra_common.service_token.ServiceTokenProvider` y solo sustituye el `poster`, que hace el transporte con `Host` y SNI internos. La aserción la firma `_assertion()` de U0.

| Corrida (con `uptime`) | M-a `iss` | M-b `aud` = URL token interna / pública / emisor público / emisor interno | M-c | M-d `issuer` (como M-a / como M-b) |
|---|---|---|---|---|
| Base: `uv run python identity-edge/tools/measure_issuer.py`. Carga 3,14 al empezar y 5,91 al acabar | 200, `https://vectra.localtest.me/auth/realms/vectra`, `azp` = `probe-public` | 400 `invalid_client: Invalid token audience` / 200 / 200 / 400. En los dos 200, `iss` público | 400 `Invalid token audience` | público / público; `token_endpoint` y `jwks_uri` públicos en las dos |
| M-e: `… --backchannel-dynamic`. Carga 6,08 al empezar y 15,23 al acabar | 200, `iss` público | 400 / 200 / 200 / 400 | 400 | público / público, pero con `token_endpoint` y `jwks_uri` en `keycloak-admin…:8443` |
| Variante mía: host interno = Service `keycloak.vectra-identity.svc` en vez de `keycloak-admin` (le cambié `urlhost` al módulo desde `python -c`). Carga 13,49 al empezar y 20,63 al acabar | 200, `iss` público | 400 / 200 / 200 / 400 | 400 | público |

Qué confirmo:
- Hay un solo emisor, el público, tanto para el token de usuario como para el de servicio, se pida por donde se pida.
- Keycloak rechaza la `aud` interna con los dos Services, con y sin `KC_HOSTNAME_BACKCHANNEL_DYNAMIC`.
- La petición M-b es la que llegaría dentro del clúster: `Host` y SNI internos, TLS, sin `X-Forwarded-*`.
- `KC_HOSTNAME_STRICT` no aplica, porque `KC_HOSTNAME` es una URL completa.

Qué no reproduje:
- El arranque `start --optimized` con PostgreSQL y el realm real cargado por keycloak-config-cli. La tarea admite esas diferencias y nada en ellas afecta a la `aud`.

Tras cada corrida, `docker ps -a | grep -c u02t21` dio 0. No toqué ningún contenedor ajeno.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Medición completa y sin secretos | los tres `grep` de CA-1 | `4`, `0`, línea 3 `Resultado: R2` → pasa |
| 2 | Nada apunta al kind; Docker limpio | `grep` de CA-2; `docker ps -a … grep -ci u02t21` | sin salida; `0` → pasa |
| 3 | Inventario | `grep` sobre `vectra-risk-gitops/values` y `envs` | solo los 8 `keycloak.issuer` nuevos → pasa |
| 4 | Rojo primero | valores de 5be01dc con `git checkout 5be01dc -- <M>` y `rm <A>`, luego pytest | `15 failed, 46 passed`: los 5 validadores × 3 entornos → pasa. Restaurado con `git checkout HEAD` |
| 5 | Verde | pytest `-v` sobre HEAD | `61 passed`; 9 workloads por entorno (los 5 validadores y los 4 que solo piden token) → pasa |
| 6 | Mutaciones (ver abajo) | mutaciones reales en los values y en una plantilla | todas caen nombrando `<env>/<workload>` → pasa |
| 7 | Cambio mínimo | las dos órdenes de CA-7 | sin salida → pasa |
| 8 | Regresión | `generate.py --check`; `policy-chart policy-chart-u1` ×4; `test_chart.py` ×4; `check-local`; `test_links.py` | rc 0; rc 0 ×4; 136, 125, 104 y 146 passed; `863 passed in 232.51s`, rc 0, 238 s (carga de 5,21 a 7,88), `TMPDIR` por omisión; `542 archivos sin enlaces rotos` → pasa |
| 9 | `CANDIDATAS.md` | `grep -n U02-T21 CANDIDATAS.md` | líneas 644-646: Resuelta, P-2 Abierta y la nota para U12-T02 → pasa |

Sobre CA-8: en el primer intento, `policy-chart` de scoring-explainability falló con rc 2 por un timeout de DNS de kubeconform al bajar los esquemas desde `raw.githubusercontent.com`. Es un problema del entorno. Al repetirlo dio rc 0 con `Valid: 14` en los tres entornos.

**Mutaciones reales**, cada una deshecha con `git checkout HEAD`:

| Mutación | Archivo | Caso que falla |
|---|---|---|
| Emisor con barra final | `values/kind/decision-registry.yaml` | `kind/decision-registry-service` |
| Otro host | `governance/chart/values.yaml` | `prod/governance-service` |
| `http` | `values/staging/bias-monitoring.yaml` | `staging/bias-monitoring-service` |
| Emisor de staging en kind | `values/kind/scoring-explainability.yaml` | `kind/scoring-service` y `kind/explainability-service` |
| `jwksUrl` al nombre público | `governance/chart/values.yaml` | `{kind,staging,prod}/governance-service`, mensaje «no es un Service de Keycloak» |
| CronJob nuevo `rogue-job` que pide token, sin flujo | plantilla temporal en `bias-monitoring` | `{kind,staging,prod}/rogue-job`, mensaje «su ServiceAccount vectra-app/rogue-job no es un workload de flows.yaml» |

**Vacuidad:** forcé que `integration.chart_renders` no devolviera nada con un plugin de pytest puesto en el scratchpad. Resultado: `28 failed`, entre ellos `test_the_workloads_are_discovered[kind|staging|prod]`. La prueba no pasa en vacío.

**Alcance y secretos:**
- `git diff --name-only origin/main` no toca `contracts/`, ningún `src/`, `chart/templates/`, `identity-edge/keycloak|gateway|jobs` ni `flows.yaml`.
- Busqué en el diff JWT con firma (`eyJ….`), `PRIVATE KEY` y contraseñas: sin salida.
- `ruff check` y `ruff format --check` de los dos archivos nuevos pasan.

**Workloads que la prueba no ve:**
- `grep` de `OIDC_ISSUER` y de `keycloak-admin` (sin contar docs ni pruebas): todas las apariciones en charts o renders son de workloads que la prueba descubre.
- `KEYCLOAK_ADMIN_URL` de identity-jobs no es un emisor.
- `case-management/chart` solo tiene `templates/.gitkeep` y `console/chart/templates` está vacío: U8 y U10 no están en `main`.
- `model-serving` no usa JWT.
- `model-validation-job` queda cubierto a través de `GOVERNANCE_JOB_TOKEN_URL`.
- No queda ningún workload con el emisor viejo.

## Hallazgos

### F-01 · AMARILLO · platform/tests/test_token_issuer.py:74 · Un emisor que llega por `valueFrom` o `envFrom` no se comprueba
`_env_of` solo lee los `env` que traen `value` literal. Lo probé con un Deployment temporal `rogue-validator` que lleva `VECTRA_OIDC_ISSUER` desde un `configMapKeyRef` y `VECTRA_JWKS_URL` literal: pasó en los tres entornos (`3 failed, 64 passed`, y los tres fallos son de `rogue-job`). Además, la regla de coherencia solo detecta emisor sin JWKS, no JWKS sin emisor. Hoy ningún chart pasa el emisor así, por eso no bloquea. Mejora posible: que falle si una variable vigilada llega sin `value`, o si hay `VECTRA_JWKS_URL` sin `VECTRA_OIDC_ISSUER` literal.

## Tareas candidatas (defectos reales fuera de alcance)
- P-2 sigue abierta y bloquea todo flujo de servicio. Esta revisión la confirma con un dato nuevo: la `aud` interna también se rechaza con el Service `keycloak.vectra-identity.svc`, así que cambiar de Service no lo arregla. La opción (b), una `aud` igual al emisor público, se aceptó (200) en las tres corridas.

## Estado final
- Worktree: `git status --short` vacío y HEAD en `5b405e672444075a0fea1befb1fa350487faa175`.
- No quedan contenedores `u02t21`.
- Hash de la tarea comprobado: `8f333b459f54415500e0105a6e5f33bb2407a0ac`.

## Rutas de transcripciones largas
Todo en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u02t21/`:
- Medición: `measure-base.log`, `measure-me.log`, `measure-svc-keycloak.log`
- Prueba: `test-green.log`, `test-red.log`, `mut-*.log`
- Regresión: `checklocal.log`, `policy-*.log`, `tc-*.log`

```
VEREDICTO: VERDE
AMARILLO|platform/tests/test_token_issuer.py:74|Un emisor que llega por valueFrom/envFrom no se comprueba
INFORME: revisiones/U02-T21/ronda-1.md
```
