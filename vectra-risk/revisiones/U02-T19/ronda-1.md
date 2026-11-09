# Ronda 1 — U02-T19

VEREDICTO: NO-VERDE

Entrego ahora porque el veredicto ya está decidido por un ROJO (F-01). Ese ROJO no depende de CA-5. **CA-5 queda sin terminar.** Cuando entregué, `make -C identity-edge check` había pasado todas las etapas anteriores a pytest y pytest iba por el 36 % sin fallos. `make -C platform check` todavía no había empezado. Como F-01 obliga a cambiar código, CA-5 se tiene que correr completo en la ronda 2 de todos modos.

Lo que corrí:
- Commit `2bd8b974`, blob de la tarea `006b9589…` (coincide).
- Copias con `git archive` en el scratchpad del orquestador (`U02-T19-revisor-r1/`).
- No toqué el clúster. El worktree del codificador quedó limpio (`git status --porcelain` vacío).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Job y administrador de arranque solo en kind | `make -C identity-edge check-keycloak-rendered policy-keycloak policy-keycloak-u1`; `grep -c` | pasa: exit 0, kind da 20, staging y prod dan 0 y 0 |
| 1-rojo | Job en los values de staging | copio el bloque `configCli` de kind a `staging.yaml`, renderizo y corro conftest | falla como debe: 3 por documento y `config-cli-only-kind` en el combinado |
| 1-rojo | `PreSync`, `HookSucceeded`, etiqueta sin digest, `VARSUBST=false` | sed sobre el render de kind y conftest | falla en las 4 mutaciones, con la regla correcta |
| 2 | Rutas `identity/` y `edge/valkey` | `vault_paths.py list \| grep …` | pasa: 15 `jwks` (incluido `grafana`), 14 `private-key`, `ca`, `synthetic-users` (20 propiedades), `break-glass`, `keycloak-admin` y `edge/valkey` |
| 3 | Modo `identity` con dobles | `uv run pytest platform/kind/tests -v` | pasa: 59 en 178 s, 0 omitidas |
| 3-rojo | Siembra que regenera pares | `client_pair(path, {}, …)` | 5 fallos, la idempotencia los detecta |
| 4 | Eco 503 y caso e2e | `pytest identity-edge/tests/unit -k echo -v`; `collect-e2e \| grep` | pasa: 55 en 93 s; aparecen los 2 casos de `test_e2e_retries.py` |
| 4-rojo | Eco sin el 503 / eco que cuenta doble | sed sobre `server.py` | 2 y 4 fallos |
| 5 | `check` de U2 y de U1 | `make -C identity-edge check && make -C platform check` | **sin terminar**: U2 parcial (abajo), U1 sin correr |

Estado parcial de CA-5:
- Pasó: lint, `check-keycloak-rendered`, `policy-keycloak` (4320/4320 y 11/11 por entorno), `policy-keycloak-u1`, jobs, gateway (133), kubeconform, xds, `load-inspect`.
- pytest estaba al 36 % sin fallos.

Staging y prod:
- `git diff --quiet de70f35 2bd8b974 -- rendered/staging rendered/prod` da 0 bytes: no cambian.
- No hay material de llaves en el diff. El único `BEGIN PRIVATE KEY` es una aserción de prueba.

Alcance:
- El diff no toca `decision-registry/`, `reference-model/`, `flows.yaml` ni el plan.

## Hallazgos

### F-01 · ROJO · `identity-edge/keycloak/values/common.yaml` (Job) y `policy/config_cli.rego` (`config-cli-security`) · Recursos y prioridad del Job fuera del diseño
- **Recursos.** INF-U2-06 fija para `keycloak-config-cli` 100m / 256 MiB de requests y 500m / 512 MiB de limits. El Job pide 100m / **384Mi** y limita a **1 CPU / 1Gi**. El init container `truststore` pide 50m/64Mi y limita a 500m/256Mi, cifras que el diseño no tiene.
- **Prioridad.** `nfr-design/logical-components.md:14` asigna `vectra-normal`, y `CANDIDATAS.md:57` lo repite para esta tarea («recursos de INF-U2-06, prioridad `vectra-normal`»). El Job usa `vectra-low`.
- **La política fija la desviación.** La regla exige `vectra-low`, así que las pruebas pasan sobre el valor equivocado.
- **No está justificado.** La bitácora solo dice «recursos, `vectra-low`», sin medición ni enmienda.
- **Por qué importa.** La cuota de `vectra-identity` (`quotas.yaml`) se calcula con las cifras del diseño.
- **Arreglo:** alinear los valores con el diseño, o traer una enmienda de diseño con la medición de memoria de la JVM. Ajustar la regla en cualquiera de los dos casos.

### F-02 · NARANJA (no bloquea con RL) · `values/common.yaml` y `platform/kind/vault_paths.py` · Literales en el template y en la siembra
Valores ajustables escritos como literales en el template en lugar de `vectra.configCli.*`:
- `backoffLimit: 3`, `activeDeadlineSeconds: 900`
- `KEYCLOAK_AVAILABILITYCHECK_TIMEOUT 300s`
- los recursos
- `NOMBRE=NOMBRE`

Además, el nombre de usuario `"admin"` está fijado en `identity_value`. Es visible para el operador como `VECTRA_E2E_ADMIN_USER`.

### F-03 · AMARILLO · Job (`NOMBRE=NOMBRE`) · El rodeo es aceptable, no tapa un error
- La causa está bien diagnosticada: el comentario de la línea 3 del realm usa la sintaxis de sustitución. La tarea pide justo esto: candidata en `CANDIDATAS.md` y no corregir el realm aquí.
- El rodeo es inocuo: solo reescribe un comentario. Una prueba fija que esa es la única variable dentro de un comentario.
- Debe salir cuando se corrija el realm.

### F-04 · AMARILLO · Imagen `6.5.1-26.5.5` · Compatibilidad con Keycloak 26.8.1 sin probar
- La fuente está citada (README y etiquetas de Docker Hub).
- El digest del índice `sha256:0955d98c…` está fijado en el Job y en el init, y la regla `config-cli-image` lo exige.
- La compatibilidad con 26.8.1 se declara pero no se probó contra un Keycloak real. La tarea lo admite y el riesgo queda en `CANDIDATAS.md`. Lo cierra el Paso 16.

### F-05 · AMARILLO · `set.rego` (`metadata-annotations`) · La excepción es más amplia que su comentario
- La regla exime a todo `kind == "Job"`, no solo a `keycloak-config-cli`.
- `documents-exact` compensa: en kind no se admite otro Job, y en staging y prod ninguno.

### F-06 · AMARILLO · `vault_paths.py` (`write_private`) · El 0600 se aplica después de escribir
- Si `env` o un `.pem` ya existían con permisos más amplios, el contenido se escribe antes del `chmod`.
- El directorio queda en 0700 antes de escribir, así que la exposición real es nula. Mejor hacer `chmod` antes o reemplazar con `os.replace`.

## Lo que verifiqué y está bien
- **B-1 · `toJson`:** el JWKS entra al realm (`jwks.string: $(env:…)`) como una cadena JSON con comillas, que es YAML válido. La política exige ese template exacto.
- **B-1 · F94:** cubre al Job. La ServiceAccount `keycloak-config-cli` y la etiqueta `app.kubernetes.io/name: keycloak-config-cli` coinciden con `flows.yaml:122,264`.
- **B-1 · Seguridad del Job:**
  - URL de administración con la CA de `identity-ca`, sin saltar la verificación;
  - `runAsNonRoot`, raíz de solo lectura y `drop ALL`;
  - sidecar nativo de Linkerd;
  - ninguna credencial en claro.
- **B-2 · Llaves:** PKCS#8 P-256. El `kid` sigue RFC 7638 (`crv, kty, x, y` ordenados y sin espacios).
- **B-2 · CA:** se lee solo `tls.crt` de `cert-manager/vectra-internal-ca`, que es raíz autofirmada (`isCA`).
- **B-2 · TOTP:** base32 de 160 bits.
- **B-2 · Idempotencia:** nunca regenera un par. Un `jwks` que no corresponde a su llave detiene la siembra.
- **B-2 · `seed` de U1:** solo usa `platform_external_secrets()` (prueba `test_u1_seed_does_not_write_identity_paths`).
- **B-2 · Sin secretos expuestos:** los valores van a Vault por stdin y no salen por stdout. Directorio 0700, archivos 0600, y la escritura se rechaza dentro del repositorio.
- **B-4 · Contraste con P-U2-02:** `/api/console/**` reintenta solo ante `connect-failure` y «sin reintento ante 503», así que 1 llamada en el `GET` es lo correcto. El `POST` de intake no se reintenta nunca.
- **B-4 · Cabeceras:** el gateway no quita `X-Echo-*` (solo quita los prefijos `x-envoy-` y `x-vectra-`).
- **B-4 · Suma por réplicas:** la clave es única por caso y la suma cubre todas las URLs. Un reintento daría 2 y un 503 de Envoy daría 0, y los dos casos fallan.

## Tareas candidatas (defectos reales fuera de alcance)
- `identity/ca` se conserva entre corridas. `vectra-internal-ca` usa `rotationPolicy: Always` y se renueva cada año, así que tras la renovación la bóveda queda con la CA vieja. Hace falta un modo que la refresque.
- La detección de outliers expulsa tras 5 respuestas 5xx seguidas en intake. Repetir el ítem 8 muchas veces seguidas podría sacar del balanceo un pod del eco.

```
VEREDICTO: NO-VERDE
ROJO|identity-edge/keycloak/values/common.yaml (Job keycloak-config-cli) y policy/config_cli.rego (config-cli-security)|Recursos (384Mi/1CPU/1Gi) y prioridad vectra-low contra INF-U2-06 (100m/256Mi-500m/512Mi) y logical-components (vectra-normal)
INFORME: revisiones/U02-T19/ronda-1.md
```
