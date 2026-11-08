# Guía del operador: Paso 16 de U2 en kind

Paso 16 del plan de U2 (`aidlc-docs/construction/plans/identity-edge-code-generation-plan.md`): instalar U2 en `kind-vectra` y ejecutar sus pruebas con evidencia. Lo ejecuta **un operador** después de un PR aprobado (AUTONOMIA-01).

Alcance de la demo (`aidlc-docs/construction/plans/demo-kind-alcance.md`): el Paso 16 entra completo, salvo la prueba de carga k6 (ítem 2), que se difiere (T3). Al terminar se mide la memoria para DD-3.

Estado de esta guía (2026-11-08): **todavía no se puede ejecutar de punta a punta.** B-1, B-2 y B-4 los resuelve U02-T19; quedan B-3 (imágenes) y B-5 (salud de U1), que son del operador. La sección 1 lista cada bloqueo y quién lo resuelve.

## 1. Bloqueos antes de empezar

| Id | Bloqueo | Por qué impide el Paso 16 | Lo resuelve |
|---|---|---|---|
| B-1 | **Resuelto por U02-T19.** (Antes: no había forma de importar el realm.) `keycloak-config-cli` está bloqueado: ningún release admite `private_key_jwt` (enmienda Q1 del 2026-11-03, INF-U2-05a). Los values de Keycloak no usan `--import-realm`, y el realm usa la sintaxis `$(env:…)` de `keycloak-config-cli`, que la importación nativa de Keycloak no resuelve | Sin realm `vectra` no hay clientes, roles ni usuarios sintéticos. Todas las pruebas e2e fallan | Decisión del usuario (opción a, ver §1.1) e implementación en U02-T19: Job `keycloak-config-cli` v6.5.1 como hook `PostSync`, solo en kind (§5) |
| B-2 | **Resuelto por U02-T19.** (Antes: `platform/kind/seed-vault.sh` no sembraba las rutas `identity/`.) `vault_paths.py` solo lee `platform/secrets/`, y los valores al azar no sirven para estas rutas | Los `ExternalSecret` de Keycloak, de los Jobs y del rate limit quedan sin datos. Además, `identity/clients/*` necesita pares ES256 reales (`private-key` y `jwks`), `identity/ca` el certificado de `vectra-internal-ca` y `identity/synthetic-users` las contraseñas y las semillas TOTP | U02-T19: `seed-vault.sh identity` (§4) |
| B-3 | **Las imágenes de U2 no están en el registro local.** `kind-registry` solo tiene `restore-drill`, `grafana-folder-permissions`, `minio` y `mc`. `keycloak` e `identity-jobs` tienen digest de ceros en `values/kind.yaml`, y la de Envoy apunta a un digest que no está publicado | Argo CD despliega lo que hay en `main`, y los pods quedan en `ImagePullBackOff` | El operador construye y publica, y un PR cambia los digests (§3) |
| B-4 | **Resuelto por U02-T19.** (Antes: el backend de eco no respondía 503.) `tests/e2e/echo/server.py` no tiene un modo de error | El ítem 8 (un `POST` a un backend que da 503 recibe exactamente 1 llamada, P-U2-02) no tiene contra qué correr | U02-T19: el eco tiene un modo 503 con contador y el caso e2e `test_post_to_a_backend_with_503_gets_exactly_one_call` (§6, ítem 8) |
| B-5 | **U1 no está sano hoy en kind.** `postgres`, `restore-drill`, `grafana-config` y `grafana-secrets` están `Degraded`. Linkerd, la observabilidad y `minio` están `Progressing` | Keycloak necesita `keycloak-db` (postgres) y Linkerd. Loki es la fuente de dos pruebas (H6) | El operador, con `platform/runbooks/install.md` §7 y los runbooks de cada alerta, antes del Paso 16 |

### 1.1 Opciones para B-1 (decisión del usuario)

- **a. (Elegida el 2026-11-08; resuelta por U02-T19.) `keycloak-config-cli` v6.5.1 solo en kind, con la credencial de administración de INF-U2-05a** (contraseña, no `private_key_jwt`). Se ejecuta como hook `PostSync` de `keycloak` y solo con los values de kind. Staging y prod siguen bloqueados. Es una desviación de seguridad acotada a kind y queda registrada. *Recomendada:* usa el mismo realm y la misma herramienta del diseño, y solo cambia cómo se autentica.
- **b. Importación nativa de Keycloak** (`kc.sh start --import-realm`) con un realm renderizado para kind. Obliga a traducir `$(env:…)` a valores literales o a la sintaxis de Keycloak, y genera un segundo realm que hay que mantener.
- **c. Esperar** un release de `keycloak-config-cli` con aserciones de cliente. Bloquea el Paso 16 y, con él, la demo.

## 2. Requisitos previos

- `kubectl config current-context` es `kind-vectra`, y `argocd login` funciona (`platform/runbooks/install.md` §6).
- U1 sano: `kubectl get applications -n argocd` sin `Degraded` (B-5).
- Herramientas en `platform/.tools/bin`, con `bash platform/install-tools.sh`, y charts con `bash platform/charts.sh`. El chart `keycloakx` hay que copiarlo a `platform/.charts/keycloakx`, porque `charts.sh` no lo descarga (candidata en `CANDIDATAS.md`).
- B-1, B-2 y B-4 (U02-T19) fusionados en `main`. B-3 y B-5 los resuelve el operador antes de empezar.
- `docker` (para el espejo de imágenes) y `uv`.

## 3. Imágenes (B-3)

Igual que `platform/runbooks/install.md` §5:

```bash
docker build -t localhost:5001/vectra/keycloak:dev identity-edge/keycloak
docker build -t localhost:5001/vectra/identity-jobs:dev -f identity-edge/jobs/Dockerfile .   # contexto: la raíz de vectra-risk/
for image in keycloak identity-jobs; do
  docker push localhost:5001/vectra/$image:dev
  docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/vectra/$image:dev
done
```

- **Envoy, Valkey y `redis-exporter`:** son imágenes de terceros fijadas por digest. Haz `docker pull` de cada una por su digest de `identity-edge/gateway/values/kind.yaml` y `identity-edge/charts/valkey/values.yaml`, luego `docker tag` y `docker push` a `localhost:5001` con el mismo nombre.
- **`keycloak-config-cli` (U02-T19, solo kind):** imagen de terceros fijada por digest en `identity-edge/keycloak/values/kind.yaml`. Es `adorsys/keycloak-config-cli:6.5.1-26.5.5`, la etiqueta de la línea 26 de Keycloak (no existe una `6.5.1-26.8.x`; el README del proyecto dice que sigue las últimas versiones de Keycloak y que `a.b.c-x.y.z` es la versión `a.b.c` compilada contra Keycloak `x.y.z`). El digest es el del **índice multi-arquitectura** de esa etiqueta, así que se copia el índice entero y no una sola plataforma:

  ```bash
  digest=sha256:0955d98c8a341898b7aa177477edf8a1e90569ae50bbe7598141c1270b773274
  docker buildx imagetools create --tag localhost:5001/vectra/keycloak-config-cli:6.5.1-26.5.5 docker.io/adorsys/keycloak-config-cli@$digest
  docker buildx imagetools inspect localhost:5001/vectra/keycloak-config-cli:6.5.1-26.5.5 | grep -i '^Digest'   # debe ser $digest
  ```

  Si el `inspect` da otro digest, **no** cambies los values en silencio: el Job de `keycloak` apunta a `kind-registry:5000/vectra/keycloak-config-cli@$digest` y no arrancaría. Corrige el digest en `values/kind.yaml` con un PR (`make -C identity-edge render-keycloak`).
- **Comprobación:** cada digest debe coincidir; un mirror no cambia el digest.
- **PR de digests:** los de `keycloak` e `identity-jobs` van en `identity-edge/{keycloak,jobs}/values/kind.yaml`. Regenera con `make -C identity-edge render-keycloak render-jobs` y verifica con `make -C identity-edge check`.

## 4. Secretos (B-2)

```bash
platform/kind/seed-vault.sh            # rutas de U1, como siempre (crea también el Secret vault-token)
platform/kind/seed-vault.sh identity   # rutas de U2: identity/… y edge/valkey
```

- Necesita `vectra-internal-ca` listo en cert-manager (U1 sano, B-5): de su Secret toma **solo el certificado público** (`tls.crt`) para `identity/ca`.
- Siembra pares ES256 reales por cliente (`identity/clients/<id>`: `jwks` para los 15 clientes con `client-jwt` del realm y `private-key` PKCS#8 para los 14 con cuenta de servicio), contraseñas alfanuméricas y semillas TOTP en base32 (`identity/synthetic-users`), `identity/break-glass`, `identity/keycloak-admin` (usuario `admin`) y `edge/valkey` al azar.
- **Se puede repetir.** Conserva lo que existe y **nunca regenera un par de llaves** (rompería los tokens vigentes). Si una ruta quedó a medias (por ejemplo un `jwks` que no corresponde a su `private-key`), se detiene con un error en vez de reescribirla.
- Escribe las llaves privadas de los clientes (`<clientId>.pem`), `ca.crt` y un archivo `env` en `${VECTRA_E2E_KEYS_DIR:-${XDG_RUNTIME_DIR:-/tmp}/vectra-e2e-keys}`, fuera del repositorio (0700; archivos 0600). El log no lleva secretos: solo imprime las rutas sembradas y la ruta de ese archivo. Para el ítem 1 y la carga:

```bash
source "${VECTRA_E2E_KEYS_DIR:-${XDG_RUNTIME_DIR:-/tmp}/vectra-e2e-keys}/env"
```

  Define `VECTRA_E2E_BASE_URL`, `VECTRA_E2E_CA_BUNDLE`, `VECTRA_E2E_ADMIN_CA_BUNDLE`, `VECTRA_E2E_CLIENT_KEYS_DIR`, `K6_CLIENT_KEYS_DIR`, `VECTRA_E2E_ADMIN_USER`, `VECTRA_E2E_ADMIN_PASSWORD` (el administrador de arranque) y todas las `SYNTH_<USUARIO>_{PASSWORD,TOTP_SEED}`. Faltan las que dependen de tus port-forwards: `VECTRA_E2E_ADMIN_URL`, `VECTRA_E2E_LOKI_URL` y `VECTRA_E2E_ECHO_URLS` (ítem 8).
- El administrador de arranque es el de la excepción de INF-U2-05a: solo en kind, con todos los permisos del servidor.

## 5. Sincronizar U2

Con la función `sync` de `platform/runbooks/install.md` §7, después de la wave 2 de U1:

```bash
# Wave 2
sync valkey
# Wave 3
sync keycloak gateway ratelimit
kubectl -n vectra-identity wait pod -l app.kubernetes.io/name=keycloakx --for=condition=Ready --timeout=600s
# Importación del realm: la hace sola el hook PostSync de la Application keycloak (Job keycloak-config-cli), cuando la wave 3 está sana.
kubectl -n vectra-identity get job keycloak-config-cli                     # Complete 1/1
kubectl -n vectra-identity logs job/keycloak-config-cli -c keycloak-config-cli | tail -20
# Wave 4
sync identity-jobs identity-rules identity-monitors
```

**Importación del realm (B-1, U02-T19):** `keycloak` lleva, solo en kind, el Job `keycloak-config-cli` v6.5.1 como hook `PostSync` con `BeforeHookCreation`, así que cada `sync keycloak` vuelve a importar `realm.kind.yaml`. El Job se autentica con el administrador de arranque de `master` (`identity/keycloak-admin`) y no con `private_key_jwt`: es una desviación de seguridad acotada a kind. Si el Job falla, mira primero que `kubectl -n vectra-identity get externalsecret` esté `SecretSynced` (si `identity/…` no está sembrado, el pod queda en `CreateContainerConfigError`) y que `identity-ca` exista.

**Comprobaciones:**
- `egctl x status gateway -n vectra-edge` no muestra errores (`egctl` está en `platform/.tools/bin`);
- `curl -sk https://vectra.localtest.me/auth/admin` da 404 (X10);
- el realm `vectra` existe: `GET /auth/realms/vectra/.well-known/openid-configuration` da 200.

**Backend de eco (H1):** lo aplica el operador, solo en kind:

```bash
kubectl apply -f identity-edge/tests/e2e/echo/manifests.yaml
```

## 6. Pruebas, una evidencia por ítem

Cada ítem deja un archivo en `aidlc-docs/construction/identity-edge/evidence/paso-16/<n>-<nombre>.txt`, con el comando, la salida y el resultado esperado contra el obtenido. Ese directorio va adjunto al PR de cierre.

| # | Prueba | Cómo |
|---|---|---|
| 1 | Playwright y PBT-U2-08 | Exporta las variables `VECTRA_E2E_*` (URL base, CA, URL y credencial de la Admin API, Loki, directorio de llaves de cliente) y `SYNTH_*`, que salen de Vault (B-2). Después corre `make -C identity-edge e2e`; esa suite incluye `test_e2e_retries.py`, que además pide `VECTRA_E2E_ECHO_URLS` (ítem 8). El perfil `kind-e2e` de Hypothesis lo registra el `conftest` |
| 2 | Carga k6 | **Diferida por la demo** (T3). La especificación existe (`tests/load/`). Si se corre, sigue `tests/load/README.md` |
| 3 | `testssl.sh` contra el gateway (NFR-U2-22) | Con el contenedor oficial fijado por digest, sobre `vectra.localtest.me:443`. Lo esperado es TLS 1.2 o superior y sin cifrados débiles |
| 4 | Valkey en 0 (P-U2-01) | Escala el StatefulSet de Valkey a 0. `/api/console/**` responde 200 y `/auth/**` responde 503. Después vuelve a escalarlo |
| 5 | Borrar el pod de Keycloak con una sesión activa (NFR-U2-02) | Obtén un token y su refresh, borra un pod de `keycloakx` y haz el refresh: debe seguir funcionando |
| 6 | Controlador de Envoy Gateway en 0 (NFR-U2-04) | Escala `envoy-gateway` en `envoy-gateway-system` a 0. Las rutas siguen respondiendo, y después lo restauras |
| 7 | Rotación de la llave de firma con solapamiento (P-U2-05) | Sigue `identity-edge/runbooks/signing-key-rotation.md`. Los tokens firmados con la llave anterior siguen siendo válidos mientras dura el solapamiento |
| 8 | `POST` contra un backend que da 503, con exactamente 1 llamada (P-U2-02) | Con el eco ya aplicado: un `kubectl -n vectra-app port-forward pod/<cada pod de case-service>` por réplica y de console-bff (los contadores son por pod), `export VECTRA_E2E_ECHO_URLS=http://127.0.0.1:<p1>,http://127.0.0.1:<p2>,…` y `uv run pytest identity-edge/tests/e2e/test_e2e_retries.py -v`. El eco responde 503 si la petición lleva `X-Echo-Fail: 503` y cuenta las llamadas por `X-Echo-Key`; el caso suma los contadores de todas las réplicas (`GET /__echo/calls?key=…`). Esperado: el `POST` a `/api/intake/**` da 503 con 1 llamada, y el `GET` de `/api/console/**` también (solo se reintenta ante `connect-failure`, no ante un 503) |

## 7. Medición de memoria (DD-3)

Al terminar el ítem 1, con U1 y U2 sanos:

```bash
uv run python platform/tests/test_kind_profile.py   # suma de requests de U1 + U2; hoy da 5,47 GiB pedidos
docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' | grep vectra
free -g
```

Hay que registrar el uso real de cada nodo y del host en `aidlc-docs/construction/identity-edge/evidence/paso-16/dd3-memoria.txt`. Con eso se decide DD-3: si el tope provisional de 5,5 GiB sirve y si hace falta el perfil `values-kind-demo.yaml` (T6) para meter U3 a U12.

## 8. Cierre

El PR del Paso 16 lleva la evidencia de §6 y §7. El Paso 18 (`make -C identity-edge check`) cierra la unidad con un `cierre-demo.md`, como el cierre acotado de U1.
