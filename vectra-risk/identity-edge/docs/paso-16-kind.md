# Guía del operador: Paso 16 de U2 en kind

Paso 16 del plan de U2 (`aidlc-docs/construction/plans/identity-edge-code-generation-plan.md`): instalar U2 en `kind-vectra` y ejecutar sus pruebas con evidencia. Lo ejecuta **un operador** después de un PR aprobado (AUTONOMIA-01).

Alcance de la demo (`aidlc-docs/construction/plans/demo-kind-alcance.md`): el Paso 16 entra completo, salvo la prueba de carga k6 (ítem 2), que se difiere (T3). Al terminar se mide la memoria para DD-3.

Estado de esta guía (2026-11-08): **todavía no se puede ejecutar de punta a punta.** La sección 1 lista lo que falta, y cada bloqueo dice quién lo resuelve.

## 1. Bloqueos antes de empezar

| Id | Bloqueo | Por qué impide el Paso 16 | Lo resuelve |
|---|---|---|---|
| B-1 | **No hay forma de importar el realm.** `keycloak-config-cli` está bloqueado: ningún release admite `private_key_jwt` (enmienda Q1 del 2026-11-03, INF-U2-05a). Los values de Keycloak no usan `--import-realm`, y el realm usa la sintaxis `$(env:…)` de `keycloak-config-cli`, que la importación nativa de Keycloak no resuelve | Sin realm `vectra` no hay clientes, roles ni usuarios sintéticos. Todas las pruebas e2e fallan | **Decisión del usuario** y después una tarea (ver §1.1) |
| B-2 | **`platform/kind/seed-vault.sh` no siembra las rutas `identity/`.** `vault_paths.py` solo lee `platform/secrets/`, y los valores al azar no sirven para estas rutas | Los `ExternalSecret` de Keycloak, de los Jobs y del rate limit quedan sin datos. Además, `identity/clients/*` necesita pares ES256 reales (`private-key` y `jwks`), `identity/ca` el certificado de `vectra-internal-ca` y `identity/synthetic-users` las contraseñas y las semillas TOTP | Tarea de código (propuesta: U02-T19) |
| B-3 | **Las imágenes de U2 no están en el registro local.** `kind-registry` solo tiene `restore-drill`, `grafana-folder-permissions`, `minio` y `mc`. `keycloak` e `identity-jobs` tienen digest de ceros en `values/kind.yaml`, y la de Envoy apunta a un digest que no está publicado | Argo CD despliega lo que hay en `main`, y los pods quedan en `ImagePullBackOff` | El operador construye y publica, y un PR cambia los digests (§3) |
| B-4 | **El backend de eco no responde 503.** `tests/e2e/echo/server.py` no tiene un modo de error | El ítem 8 (un `POST` a un backend que da 503 recibe exactamente 1 llamada, P-U2-02) no tiene contra qué correr | Se suma a la tarea de B-2 o a una propia |
| B-5 | **U1 no está sano hoy en kind.** `postgres`, `restore-drill`, `grafana-config` y `grafana-secrets` están `Degraded`. Linkerd, la observabilidad y `minio` están `Progressing` | Keycloak necesita `keycloak-db` (postgres) y Linkerd. Loki es la fuente de dos pruebas (H6) | El operador, con `platform/runbooks/install.md` §7 y los runbooks de cada alerta, antes del Paso 16 |

### 1.1 Opciones para B-1 (decisión del usuario)

- **a. `keycloak-config-cli` v6.5.1 solo en kind, con la credencial de administración de INF-U2-05a** (contraseña, no `private_key_jwt`). Se ejecuta como hook `PostSync` de `keycloak` y solo con los values de kind. Staging y prod siguen bloqueados. Es una desviación de seguridad acotada a kind y queda registrada. *Recomendada:* usa el mismo realm y la misma herramienta del diseño, y solo cambia cómo se autentica.
- **b. Importación nativa de Keycloak** (`kc.sh start --import-realm`) con un realm renderizado para kind. Obliga a traducir `$(env:…)` a valores literales o a la sintaxis de Keycloak, y genera un segundo realm que hay que mantener.
- **c. Esperar** un release de `keycloak-config-cli` con aserciones de cliente. Bloquea el Paso 16 y, con él, la demo.

## 2. Requisitos previos

- `kubectl config current-context` es `kind-vectra`, y `argocd login` funciona (`platform/runbooks/install.md` §6).
- U1 sano: `kubectl get applications -n argocd` sin `Degraded` (B-5).
- Herramientas en `platform/.tools/bin`, con `bash platform/install-tools.sh`, y charts con `bash platform/charts.sh`. El chart `keycloakx` hay que copiarlo a `platform/.charts/keycloakx`, porque `charts.sh` no lo descarga (candidata en `CANDIDATAS.md`).
- B-1 a B-4 resueltos y fusionados en `main`.

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
- **Comprobación:** cada digest debe coincidir; un mirror no cambia el digest.
- **PR de digests:** los de `keycloak` e `identity-jobs` van en `identity-edge/{keycloak,jobs}/values/kind.yaml`. Regenera con `make -C identity-edge render-keycloak render-jobs` y verifica con `make -C identity-edge check`.

## 4. Secretos (B-2)

Cuando exista la tarea de B-2:

```bash
platform/kind/seed-vault.sh            # rutas de U1, como siempre
platform/kind/seed-vault.sh identity   # rutas identity/ (nombre provisional: lo fija la tarea)
```

## 5. Sincronizar U2

Con la función `sync` de `platform/runbooks/install.md` §7, después de la wave 2 de U1:

```bash
# Wave 2
sync valkey
# Wave 3
sync keycloak gateway ratelimit
kubectl -n vectra-identity wait pod -l app.kubernetes.io/name=keycloakx --for=condition=Ready --timeout=600s
# Importación del realm: según la decisión de B-1
# Wave 4
sync identity-jobs identity-rules identity-monitors
```

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
| 1 | Playwright y PBT-U2-08 | Exporta las variables `VECTRA_E2E_*` (URL base, CA, URL y credencial de la Admin API, Loki, directorio de llaves de cliente) y `SYNTH_*`, que salen de Vault (B-2). Después corre `make -C identity-edge e2e`. El perfil `kind-e2e` de Hypothesis lo registra el `conftest` |
| 2 | Carga k6 | **Diferida por la demo** (T3). La especificación existe (`tests/load/`). Si se corre, sigue `tests/load/README.md` |
| 3 | `testssl.sh` contra el gateway (NFR-U2-22) | Con el contenedor oficial fijado por digest, sobre `vectra.localtest.me:443`. Lo esperado es TLS 1.2 o superior y sin cifrados débiles |
| 4 | Valkey en 0 (P-U2-01) | Escala el StatefulSet de Valkey a 0. `/api/console/**` responde 200 y `/auth/**` responde 503. Después vuelve a escalarlo |
| 5 | Borrar el pod de Keycloak con una sesión activa (NFR-U2-02) | Obtén un token y su refresh, borra un pod de `keycloakx` y haz el refresh: debe seguir funcionando |
| 6 | Controlador de Envoy Gateway en 0 (NFR-U2-04) | Escala `envoy-gateway` en `envoy-gateway-system` a 0. Las rutas siguen respondiendo, y después lo restauras |
| 7 | Rotación de la llave de firma con solapamiento (P-U2-05) | Sigue `identity-edge/runbooks/signing-key-rotation.md`. Los tokens firmados con la llave anterior siguen siendo válidos mientras dura el solapamiento |
| 8 | `POST` contra un backend que da 503, con exactamente 1 llamada (P-U2-02) | Necesita B-4 |

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
