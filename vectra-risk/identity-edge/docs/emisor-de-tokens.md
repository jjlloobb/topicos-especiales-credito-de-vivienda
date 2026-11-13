# El emisor (`iss`) de los tokens entre unidades: medición con un Keycloak real (U02-T21)

**Resultado: R2.** H1 cierta (todo token sale con el emisor público, también el pedido por el host interno) y H2 cierta
(Keycloak rechaza la aserción `private_key_jwt` cuya `aud` es la URL de token interna, que es la que firma
`vectra_common.service_token`). La medida extra M-e (P-2 a, `KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true`) **no** corrige H2.

Esta evidencia no lleva tokens, aserciones, llaves ni contraseñas: solo los claims `iss`, `azp` y `aud` decodificados sin firma.

## Cómo se midió

- **Guion:** `uv run python identity-edge/tools/measure_issuer.py` (con `--backchannel-dynamic` para M-e). Levanta **un** contenedor
  `u02t21-<azar>` y lo borra (con sus volúmenes) al terminar. No entra en `make check`.
- **Imagen:** `quay.io/keycloak/keycloak:26.8.1@sha256:3f3c5f8e03c614774b4bd9173b88391fefa4153bfc010d8012d59ad825377332`, leída de la línea `FROM` de
  `identity-edge/keycloak/Dockerfile`.
- **Igual que el render de kind** (`identity-edge/keycloak/rendered/kind/keycloak.yaml`, leído por el guion): `KC_HOSTNAME=https://vectra.localtest.me/auth`,
  `KC_HOSTNAME_ADMIN=https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth`, `KC_PROXY_HEADERS=xforwarded`, `KC_HTTP_RELATIVE_PATH=/auth`, sin
  `KC_HOSTNAME_BACKCHANNEL_DYNAMIC` (salvo M-e).
- **Diferencias con kind (todas permitidas por la tarea):** orden `start` (construye al arrancar) en lugar de `start --optimized` sobre la imagen de
  U2 (que añade `--db=postgres` en el build); base de datos y caché locales (valores por omisión de `start`, sin PostgreSQL ni `jdbc-ping`);
  certificado autofirmado desechable con los SAN de `keycloak-tls` (`keycloak.vectra-identity.svc`, `keycloak-admin.vectra-identity.svc.cluster.local`);
  administrador de arranque con contraseña al azar; realm `vectra` mínimo (cliente público `probe-public` con *direct grant*, cliente `probe-svc`
  `client-jwt` ES256 con llave generada al momento, usuario `probe`), no el realm de U2; contenedor con 1,5 GiB de memoria.
- **Host dinámico:** puerto libre publicado solo en `127.0.0.1`. Toda orden va a `127.0.0.1:<puerto>`, o al nombre interno desviado con
  `curl --connect-to` (M-b) o con SNI y `Host` (httpx, M-c y M-d). El nombre público solo viaja en `KC_HOSTNAME` y en `X-Forwarded-Host`.
- **Máquina (`/proc/loadavg`):** corrida base `10.62 6.28 5.77` al final; corrida M-e `12.02 7.52 6.23`; `uptime` previo `00:52:36 up 13:59, load average: 4.55, 4.44, 5.18`.

## Medidas (configuración de kind, sin M-e)

| Id | Orden | HTTP | Claims decodificados (`iss`, `azp`, `aud`) o error |
|---|---|---|---|
| M-a | `POST /auth/realms/vectra/protocol/openid-connect/token` a `127.0.0.1:<puerto>` con `X-Forwarded-Proto: https` y `X-Forwarded-Host: vectra.localtest.me` (grant `password`, cliente público) | 200 | `iss` = `https://vectra.localtest.me/auth/realms/vectra`; `azp` = `probe-public`; `aud` = `account` |
| M-b | `curl --cacert <ca> --connect-to keycloak-admin.vectra-identity.svc.cluster.local:8443:127.0.0.1:<puerto> --data-urlencode grant_type=client_credentials --data-urlencode client_assertion_type=<jwt-bearer> --data-urlencode client_assertion@<archivo> https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/realms/vectra/protocol/openid-connect/token`, sin `X-Forwarded-*`; la aserción lleva `aud` = la URL interna de token | 400 | `invalid_client: Invalid token audience`. Con `aud` = la URL de token pública, la misma orden da 200 y `iss` = `https://vectra.localtest.me/auth/realms/vectra`; `azp` = `probe-svc`; `aud` = `account` |
| M-c | `ServiceTokenProvider("probe-svc", <URL interna de token>, …).token()` (U0 importado; la aserción lleva `aud` = esa URL), transporte httpx con `Host` y SNI internos hacia `127.0.0.1:<puerto>` | 400 | `invalid_client: Invalid token audience` (H2 cierta) |
| M-d | `GET /auth/realms/vectra/.well-known/openid-configuration`, de dos formas: con `X-Forwarded-*` (como M-a) y con `Host` interno (como M-b) | 200 y 200 | Ambas: `issuer` = `https://vectra.localtest.me/auth/realms/vectra`, `token_endpoint` y `jwks_uri` bajo `https://vectra.localtest.me/auth/realms/vectra/protocol/openid-connect/`. Idénticas |

### Qué `aud` acepta Keycloak en la aserción (M-b, prueba de las cuatro variantes)

| `aud` de la aserción | HTTP |
|---|---|
| URL de token interna (`keycloak-admin…:8443/auth/realms/vectra/protocol/openid-connect/token`) | 400 `Invalid token audience` |
| URL de token pública (`vectra.localtest.me/auth/realms/vectra/protocol/openid-connect/token`) | 200 |
| emisor público (`vectra.localtest.me/auth/realms/vectra`) | 200 |
| emisor interno (`keycloak-admin…:8443/auth/realms/vectra`) | 400 `Invalid token audience` |

En todos los 200 el token trae `iss` = `https://vectra.localtest.me/auth/realms/vectra`.

## M-e: P-2 (a), `KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true` (mismo guion, `--backchannel-dynamic`)

| Medida | HTTP | Resultado |
|---|---|---|
| M-e: a | 200 | `iss` = `https://vectra.localtest.me/auth/realms/vectra` (sin cambio) |
| M-e: b, `aud` = URL de token interna | 400 | `invalid_client: Invalid token audience` (**sigue rechazada**) |
| M-e: b, `aud` = URL de token pública / emisor público | 200 / 200 | `iss` público |
| M-e: b, `aud` = emisor interno | 400 | `Invalid token audience` |
| M-e: c (U0, `aud` interna) | 400 | `invalid_client: Invalid token audience` |
| M-e: d con `Host` interno | 200 | `issuer` público, pero `token_endpoint` y `jwks_uri` bajo `https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/realms/vectra/protocol/openid-connect/` |

Con el modo dinámico Keycloak anuncia las URL internas en el *discovery* pero **no** las acepta como `aud` de la aserción, y el `iss` sigue
siendo el público. La opción (a) de P-2 no resuelve H2; la (b) sí es consistente con lo medido: una `aud` igual al emisor público (o a
la URL de token pública) se acepta, y `service_token` solo tendría que firmar esa `aud`.

## Lo que se concluye

- Circula **un** emisor, el público (`KC_HOSTNAME` + `/realms/vectra`), para usuarios y para servicios, pidan por donde pidan. No hay dos emisores (R3 descartado).
- Por eso el `keycloak.issuer` de cada servicio que valida debe ser el público de su entorno (corregido en esta tarea).
- Ningún servicio puede obtener hoy un token de servicio: la aserción de `vectra_common.service_token` se firma con la URL interna y se rechaza (P-2, abierto: ver `CANDIDATAS.md`).
