# Ronda 1: U10-T05

VEREDICTO: VERDE (con RL-2: no hay ningún ROJO; un NARANJA y tres AMARILLO pasan a CANDIDATAS.md)

Base de la rama: 76cee36 (merge-base con origin/main). HEAD: 99a4fec. Hash de la tarea: 12a21702c1a47b5c7b700ca2fa75d314b19236c5, coincide. El diff tiene 61 archivos, todos dentro de lo nombrado. La orden de CA-15 da `rc=1` y no imprime nada. `git diff base..HEAD -- platform/policies platform/network identity-edge` sale vacío y `console/bff/src` y `console/spa/src` no tienen diff.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Imágenes | `hadolint`; `make -C console image-bff image-spa`; los `inspect`/`run` de CA-1 | pasa: `65532:65532` y `101:101`; sin `previous-digest`; FROM 2/2 y 2/2; OK-bff, OK-entrada; `nginx -t` ok; OK-spa; `1`; los grep sin salida |
| 2 | Render, esquema y conftest | render de los 6 casos (en `platform/.tools/integration/rev-u10-r1`) + `kubeconform`; `policy-chart` dentro de `check` | pasa: Valid 7/7 ×3 y 5/5 ×3; inventario idéntico al pedido; conftest 469 y 335 por documento, 10 en conjunto; `test_chart.py` 180 passed |
| 3 | Mundo cerrado | `pytest -k "config_json or realm or …"` (46 passed); `chart-config` (10 passed); comparación a mano y 5 mutaciones | pasa (detalle abajo) |
| 4 | Contenedores reales | `pytest test_image.py -v -s` (8 passed, 14,6 s) y sondeo manual del contenedor de la SPA | pasa: el BFF sale con código 0 en 0,5 s al `stop -t 20`; nginx sale con 0 en 0,2 s |
| 5 | Admisión de U1 | `policy-chart-u1` dentro de `check`; los `grep` | pasa: `pass: 10, fail: 0` ×6; rego 49/35 y hpa 3 ×6; `kyverno test` 81/0; sin PolicyException; diff vacío |
| 6 | Cuota y flujos | `quota-flows` dentro de `check`; los `grep` | pasa: sin «falta»; `5`; `4`; las dos líneas de `quotas.yaml`; 17 passed |
| 7 | Values por entorno | `test -s`; `grep` de secretos | pasa (la ejecución de `-k values…` va dentro de las 180) |
| 8 | Applications | `gitops` dentro de `check`; los `grep`; `test_platform -k …` (2 passed); `wave: 4` con las Applications regeneradas | pasa: seis con wave '5' y sin `automated`; `1` ×6; `values-kind` 1/0/0; vectra-app y vectra-edge; la mutación de wave imprime «wave 4, se esperaba 5» ×3 |
| 9 | Trazabilidad | `traceability` (48 con trazabilidad); bucle de BR; `--all \| grep -c U10-` | pasa: ningún «sin prueba»; `0`; 9 filas de diferidos; el grep de los seis da `rc=1` |
| 10 | Memoria de kind | `requested_gib` sin y con las dos líneas de `components.yaml` | pasa: 10.6328 → 11.0234 (+0,3906); BUDGET 11.1; `test_kind_profile` 6 passed; el diff solo toca la constante y su comentario |
| 11 | C-1 | `test_clients -k "pool or connections"` con las mutaciones M11 (1000), M12 (21) y `Upstreams` con 20 fijo | pasa: 3 passed en limpio; cada mutación da 1 failed |
| 12 | Documentación | `test_links.py` (535 archivos sin enlaces rotos); los 16 `grep -qF`; `diferid` = 4; `forbidden_phrases` | pasa |
| 13 | Cierre | `time make -C console check` | pasa: rc 0 en 9 min 58 s (01:47 con carga 2,50 → 01:56 con carga 7,47); cuatro secciones; ningún «falta» |
| 14 | RL-4 | `make -C platform check-local` | pasa: rc 0 en 4 min 27 s, 802 passed (01:58 con carga 7,24 → 02:03 con carga 6,90). **`check-tools` no lo corrí.** |
| 15 | Plan y diferidos | los `git diff` del plan y el resto de las órdenes | pasa: 17, 18, 21, 23 y 24 en `[x]`; 19, 20 y 22 en `[ ]` con su nota; `17`; OK-diferidos; 0 workflows |

**Desviación 6 (forma de `check`):** `test-bff` ignora `test_image.py` y `test_chart.py`, y `test-spa` excluye `chart-config`. Las tres corren dentro de `check`: `image-test` (8 passed), `policy-chart` (10 + 180 passed) y `quota-flows` (17). Ninguna prueba queda sin objetivo y no apareció ningún `skipped`.

**Mundo cerrado (prioridad 1), comparado a mano:**
- **`config.json` en los tres entornos:** trae exactamente las claves de `SCHEMA` de `load.ts`.
- **Valores del cliente:** `authority` = `https://<hostname>/auth/realms/vectra` y `client_id` = `vectra-console`, el cliente público de los tres `realm.<env>.yaml`. Los redirect `/callback` y `/stepup-callback` son iguales a sus `redirectUris` una vez sustituido `PUBLIC_HOSTNAME`.
- **Hostnames:** coinciden el `hostname` del gateway y el `publicHostname` de Keycloak (localtest.me, staging.banco.internal y banco.internal).
- **URL base del BFF:** la SPA llama a `/api/console/**` sobre su propio origen (`wiring.ts`, `baseUrl: origin`), y esa es la ruta `console` del gateway hacia `console-bff:8080` (F03).
- **Mutaciones:** cada una hizo caer las pruebas.
  - otro host en kind: 3 failed
  - `clientId` distinto: 9 failed
  - barra final en el emisor del BFF: 2 failed
  - barra final en `issuerPath`: 6 failed
  - sin `grafana`: 9 failed, y `parseConfig` real lanza `ConfigError: missing:grafana`

**Emisor y JWKS (prioridad 2).** `test_token_issuer.py` no existe en esta rama, así que la comparación es a mano.
- **Emisor:** `VECTRA_OIDC_ISSUER` = `KC_HOSTNAME + /realms/vectra` del render de Keycloak en los tres entornos, que es el emisor público medido en U02-T21.
- **JWKS:** apunta a `keycloak.vectra-identity.svc:8443`. Ese nombre está en los `dnsNames` del Certificate y F50 permite `console-bff → keycloak:8443`. La CA (`vectra-internal-ca`) llega por el Bundle a los namespaces de la malla, y `vectra-app` está en esa lista.
- **Servicios que llama el BFF:** las cuatro URL de servicios que ya están en main dan con un Service real en `http:8080`, y F10 a F14 los permiten: governance, decision-registry, explainability y bias-monitoring. `case-service` no tiene chart en main (U8 aún no está fusionada).
- **Telemetría:** `otel-collector:4317` existe, con `fullnameOverride`, y F61 lo cubre.

**Kind (prioridad 4).** El HPA del BFF en kind queda con `minReplicas = maxReplicas = 2`. El render de kind difiere del de staging solo en tres cosas:
- lo que declara `values-kind.yaml`: `maxReplicas` 2 y la memoria en 128Mi;
- el hostname y el emisor;
- el registro de la imagen.

Staging y prod siguen en 256Mi. P-1 (b) está anotado en `values-kind.yaml`, en `components.yaml` y en `BUDGET_GIB`.

## Hallazgos
### F-01 · NARANJA · console/spa/nginx.conf:64-67 · un 404 de `/assets/` sale con caché inmutable de un año
`add_header Cache-Control "public, max-age=31536000, immutable" always` también se aplica al 404. Durante un despliegue nuevo (2 réplicas, `maxSurge 100%`), si un navegador pide un asset nuevo a un pod viejo, guarda ese 404 un año, y recargar no lo arregla. Reproducción, contra mi contenedor: `curl -D - http://127.0.0.1:<p>/assets/no.js` devuelve `HTTP/1.1 404` y `Cache-Control: public, max-age=31536000, immutable`. No rompe ningún criterio ni la demo en kind. Arreglo sugerido: quitar `always` en esa location. Pasa a CANDIDATAS.

### F-02 · AMARILLO · console/spa/nginx.conf:38 · `/healthz` de la SPA expuesto por el gateway
La ruta `spa` es un prefijo `/`, así que `/healthz` es público. Mi juicio: es un 200 estático (`ok\n`), sin datos ni versión (`Server: nginx` sin número). No hace daño. Cerrarlo es cosa de `routes.yaml` (U2), y ya está en CANDIDATAS.

### F-03 · AMARILLO · console/spa/nginx.conf:72 · rutas con punto no caen al fallback
`location ~ ^[^.]*$`: `/casos/1.2` da 404. Los ids son UUID, así que no afecta a la demo. `config.json` no tiene problema de caché: nginx lo sirve con `no-store` y `loadConfig` lo pide con `cache: "no-store"`. Tampoco hay CSP duplicada: nginx no pone ninguna de las seis cabeceras de seguridad.

### F-04 · AMARILLO · values/<env>/console-*.yaml · digests de ejemplo
Los charts renderizan con `sha256:…0008` y `…0009`, así que en kind los pods quedan en `ImagePullBackOff` hasta que el operador publique en U12 Paso 18. Está declarado en el README y en el cierre. No es hallazgo de la tarea; lo anoto para quien prepare D1–D4.

## Tareas candidatas (defectos reales fuera de alcance)
- U02-T21: `test_token_issuer.py` (en la rama `tarea/U02-T21`) solo lee `env[].value` (`_env_of`). El BFF toma sus variables por `envFrom` de un ConfigMap y no está en `VALIDATORS`, así que esa prueba no vería un emisor equivocado en `console-bff`.
- El NARANJA F-01 (caché del 404 de assets).
- `case-service` (F10) no tiene chart en main: el BFF de kind arranca, pero sin U8 las vistas de casos dan 503.

## Estado al terminar
- `git status --short` está vacío y HEAD sigue en 99a4fec. Todas las mutaciones se deshicieron con `git checkout --`.
- **Queda un contenedor mío corriendo:** `rev-u10t05-spa`, de `localhost:5001/vectra/console-spa:dev`, publicado en un puerto efímero de 127.0.0.1. Intenté `docker rm -f` y `docker stop` y el permiso me los negó; no lo rodeé. Hay que borrarlo a mano: `docker rm -f rev-u10t05-spa`. No borré ninguna imagen.
- Dejé directorios ignorados nuevos en el worktree: `platform/.tools/integration/rev-u10-r1`, `rev-u10-r1-m5` y `platform/.tools/tmp/rev-r1-cfg`. Una orden con `rm -rf $OUT/...` quedó bloqueada por el control de seguridad y no se ejecutó; por eso rendericé en esos directorios nuevos. `make check` volvió a generar `platform/.tools/integration/u10`.
- Quedaron sin correr: `make -C platform check-tools`, y `test_token_issuer.py` (no existe en esta rama).

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/r1/`:
- `check.log`
- `check-local.log`
- `ca4.log`
- `ca3.log`
- `cc.log`
- `images.log`

```
VEREDICTO: VERDE
NARANJA|console/spa/nginx.conf:64-67|un 404 de /assets/ sale con Cache-Control immutable de un año
AMARILLO|console/spa/nginx.conf:38|/healthz de la SPA expuesto por el gateway (estático, sin datos)
AMARILLO|console/spa/nginx.conf:72|rutas con punto no caen al fallback de index.html
AMARILLO|vectra-risk-gitops/values/*/console-*.yaml|digests de ejemplo hasta U12 Paso 18
INFORME: revisiones/U10-T05/ronda-1.md
```
