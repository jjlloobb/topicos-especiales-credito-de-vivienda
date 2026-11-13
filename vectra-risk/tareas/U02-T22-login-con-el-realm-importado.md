# U02-T22 — El login con el realm importado: reproducirlo con Keycloak y config-cli reales, corregir el realm y atarlo con pruebas

**Unidad:** U2 `identity-edge`.
**Historias:** ninguna nueva. Corrige dos defectos del realm que impiden todo login (US-601; las cuatro demos empiezan con uno).
**Depende de:** nada. Todo lo que toca está en `main` (comprobado al redactar, sobre `da15a07`).
**Se coordina con:** U12-T02 (rama `tarea/U12-T02`, en ronda 2, sin fusionar: repara estos defectos dentro de su prueba y también levanta un Keycloak; ver «Ramas en curso» y «Restricciones del entorno»).
**Rama:** `tarea/U02-T22`, desde `origin/main`.

**Por qué.** `DECISIONES-LOOP.md` §10 («U12-T02, defectos del realm de kind»): el codificador de U12-T02 los halló y el revisor los **reprodujo** (`revisiones/U12-T02/ronda-1.md`, sección «Realm de kind», en la rama `tarea/U12-T02`) con la imagen de Keycloak por digest, el config-cli por digest (etiqueta `6.5.1-26.5.5`, hecha para Keycloak 26.5.5, sobre Keycloak 26.8.1), el YAML sin editar y las variables del Job:

- **(a) Alias de configuración compartidos.** Tras importar, solo la primera ejecución que cita `loa-mfa`, `amr-otp` o `amr-hwk` queda con su `authenticationConfig`; las otras 15 quedan sin él. Todo login falla con «Unexpected error when handling authentication request to identity provider» y, en el log, `KC-SERVICES0013 … NullPointerException … "loaConditionConfig" is null`. Keycloak registra además `LOGIN_ERROR … invalid_user_credentials`: **cada intento cuenta para la fuerza bruta**.
- **(b) Perfil de usuario.** Con (a) reparado, la contraseña y el TOTP pasan y el login termina en la acción `VERIFY_PROFILE` («Please specify this field.», campos `email`, `firstName` y `lastName`). Nunca llega al `redirect_uri`.

No se comprobó en el clúster real. Rige RL-1 a RL-5 (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Sin clúster (AUTONOMIA-01).

---

## Lo comprobado al redactar (sobre `da15a07`; verifícalo y corrige en la bitácora lo que haya cambiado)

**Cómo se arman los realms.** No hay plantilla ni generador: son tres archivos escritos a mano en `identity-edge/keycloak/realm/`. `realm.staging.yaml` es igual a `realm.kind.yaml` salvo la línea 1 (`diff`). `realm.prod.yaml` difiere en un client scope (`core:read-credit`, líneas 79 a 91 de kind), en los usuarios y en el componente LDAP (líneas 1197 y siguientes). **`authenticationFlows`, `authenticatorConfig` y `requiredActions` son idénticos en los tres** (comparados con `yaml.safe_load`).

| Qué | Dónde (`realm.kind.yaml`; en prod, 13 líneas menos desde la 92) | Estado |
|---|---|---|
| Fuerza bruta | 22 a 29 | `failureFactor: 5`, `permanentLockout: true`, `maxTemporaryLockouts: 15`, `LINEAR` |
| `requiredActions` | 297 a 315 | Solo `CONFIGURE_TOTP`, `webauthn-register` y `UPDATE_PASSWORD`. `VERIFY_PROFILE` no se declara |
| Flujo `vectra-browser` y sus subflujos | 316 a 642 | 26 ejecuciones citan un `authenticatorConfig` |
| `authenticatorConfig` | 643 a 687 | 11 alias declarados para esas 26 citas |
| Citas de `loa-mfa` | 420, 461, 502, 543, 584 y 625 | 6 (una por subflujo `vectra-mfa-<rol>`) |
| Citas de `amr-otp` y `amr-hwk` | 403, 444, 485, 526, 567, 608 y 409, 450, 491, 532, 573, 614 | 6 y 6 (subflujos `… factor`) |
| Usuarios locales | 688 a 818 (kind y staging: 10 sintéticos); prod 676 a 688 (`break-glass`) | Ninguno trae `email`, `firstName` ni `lastName` |
| Perfil de usuario | — | Ningún realm declara `userProfile` ni `unmanagedAttributePolicy`: rige el de Keycloak por omisión |
| Mapper `name` del ID token | 936 a 942 (`oidc-full-name-mapper`, solo en `vectra-console`) | Sin nombre ni apellido, el claim sale vacío |

Los 15 enlaces que faltan son 18 citas menos las 3 primeras. `loa-pwd`, `amr-pwd` y los seis `cond-role-*` se citan una sola vez: no fallan. **Los tres archivos comparten el defecto (a); el (b) afecta a los 10 sintéticos de kind y staging y, en prod, a `break-glass` y a todo usuario de LDAP sin esos atributos.**

**Cómo se aplica.** Solo kind tiene quién lo aplique:

- El Job `keycloak-config-cli` es una plantilla dentro de `identity-edge/keycloak/values/common.yaml` (líneas 398 a 479; variables en 447 a 462: `IMPORT_FILES_LOCATIONS`, `IMPORT_VARSUBSTITUTION_ENABLED`, `IMPORT_VARSUBSTITUTION_UNDEFINEDISERROR`, `PUBLIC_HOSTNAME`, `KEYCLOAK_*` y `JAVA_OPTS`; **ninguna `IMPORT_MANAGED_*` ni de caché**). Solo se rinde con `vectra.configCli.enabled`, que solo activa `values/kind.yaml` (líneas 9 a 17, con el digest `sha256:0955d98c…`). `conftest` fija esas variables (`keycloak/policy/config_cli.rego`, líneas 71 a 98).
- `make render-keycloak` mete `realm.kind.yaml` sin tocarlo en `keycloak/rendered/kind/config-cli-realm.yaml` (`identity-edge/Makefile`, líneas 63 a 75) y `render-jobs` mete el realm de cada entorno en `jobs/rendered/<env>/realm-configmap.yaml` para `realm-drift` (líneas 104 a 111). **Si cambia un realm, cambian esos cuatro archivos** (`check-keycloak-rendered` y `check-jobs-rendered` lo exigen).
- En staging y prod **nada aplica el realm**: el Job está bloqueado hasta que config-cli admita `private_key_jwt` (INF-U2-05a, `infrastructure-design.md`, líneas 181 a 183).
- **Versiones.** El repositorio dice que no existe una etiqueta de config-cli compilada contra Keycloak 26.8: la última es `6.5.1-26.5.5` (`identity-edge/docs/paso-16-kind.md`, línea 47; `CANDIDATAS.md`, líneas 59, 257 y 264). La 257 nombra como alternativa «la etiqueta `maven` del proyecto» o probar la importación en un contenedor local, que es esta tarea. **No se sabe** si el defecto (a) es del desfase de versiones o de config-cli con alias repetidos en cualquier versión: es parte de P-1.

**Por qué ninguna prueba lo vio.** Ninguna importa el realm en un Keycloak real:

- `tests/unit/test_realm_files.py` lee el YAML y resuelve cada cita por alias en un diccionario (líneas 177, 226 y 237): un alias compartido le parece correcto.
- `tests/strategies/fake_keycloak.py` (líneas 86 a 91 y 130-131) devuelve la configuración de cada ejecución **a partir del alias del YAML**: reproduce la suposición, no a Keycloak. Las pruebas de `realm-drift` corren contra ese doble (`CANDIDATAS.md`, línea 66).
- `tests/e2e/` solo corre contra kind (`make e2e`, `Makefile` líneas 55 a 58; `make check` solo la colecta, línea 172) y el Paso 16 **no se ha ejecutado**: sigue pendiente del operador (`docs/paso-16-kind.md`, línea 7; no existe `aidlc-docs/construction/identity-edge/evidence/`).
- Ningún workflow corre `make -C identity-edge check`.

**El diseño que la corrección debe respetar** (`aidlc-docs/construction/identity-edge/functional-design/`):

- BR-U2-03 (`business-rules.md`, líneas 22 a 26): TOTP obligatorio para `ingeniero_riesgo`, `cro` y `cumplimiento`; su token lleva `acr = mfa`. `operacion` y `break-glass` también (`domain-entities.md`, líneas 31 a 36). `analista`, solo si ya tiene el factor.
- BR-U2-04 (líneas 39 a 45): step-up con `prompt=login`, `max_age=0` y `acr_values=mfa` hacia `/stepup-callback`; `acr = mfa` y `auth_time` de ≤ 900 s.
- `domain-entities.md`, línea 45: LoA `pwd` = 1 y `mfa` = 2; referencia `amr` (`pwd`, `otp`, `hwk`) en el `authenticatorConfig` **de cada ejecución**; líneas 165 a 167: `loa-max-age` y `default.reference.maxAge` = 36 000 s.
- BR-U2-05 con la enmienda H10 (líneas 49 a 58): el 5.º fallo da un bloqueo **temporal** de 60 s y el **permanente llega en el fallo 20**. (El informe de U12 dice «cinco intentos bloquean para siempre»: no es lo que fija el diseño. De cualquier modo, cada login fallido por (a) gasta un intento.)
- Usuarios (`domain-entities.md`, líneas 110-111): 2 sintéticos por rol en kind y staging, con contraseña y semilla TOTP desde ESO; en prod, LDAP de solo lectura y `break-glass`. El diseño **no nombra** `email`, `firstName`, `lastName`, el perfil de usuario ni `VERIFY_PROFILE`. Líneas 57-58: el access token va **sin** `preferred_username`, `email` ni `name`; el ID token lleva `name`.
- Nota H12 (`business-rules.md`, líneas 28 a 37): afirma que config-cli borra las acciones requeridas que Git no declara. **Lo medido la contradice**: `VERIFY_PROFILE` sigue activa tras importar. Mídelo (CA-6) y anótalo; el diseño lo enmienda el orquestador.

**Quién más depende de los usuarios y de sus atributos.**

- U2 crea usuarios **sin** esos atributos en sus propias pruebas de kind: los efímeros de la e2e (`tests/e2e/e2e_support.py`, líneas 353 a 357) y los de carga (`tests/load/seed_users.py`, línea 78). Con `VERIFY_PROFILE` activa tampoco podrían entrar.
- `realm-drift` empareja las configuraciones por alias y solo lee las que cuelgan de una ejecución (`jobs/keycloak_admin.py`, líneas 170 a 175; `tools/realm_diff.py`, líneas 35-36). Ignora `VERIFY_PROFILE` si Git no la declara (líneas 128 a 137) y compara los atributos de los usuarios.
- U12 usa `analista-1`, `analista-2`, `ingeniero-1`, `cro-1` y `cumplimiento-1` (`CANDIDATAS.md`, línea 638). U8, U10 y U11 leen del realm solo clientes y scopes (`console/bff/tools/chart_data.py`, línea 23; `platform/kind/vault_paths.py`, línea 50). Nadie lee `email` ni `preferred_username`: `grep` sin resultados en `console/bff/src`, `console/spa/src` y `system-verification/src`.

---

## Alcance

**Dentro**, en este orden:

1. **Reproducir** sin clúster: prueba de integración nueva que importa `realm.kind.yaml` sin editar y **sin reparar nada**, y hace un login completo. Verla fallar sobre `main` (rojo primero).
2. **Prueba unitaria** sobre los tres YAML, sin Docker, que falle con el realm de hoy. También en rojo primero.
3. **Corregir el realm** en los **tres** archivos, con el cambio mínimo, según P-1 y P-2. Regenerar los cuatro renders.
4. **Comprobar tras importar** (misma prueba de integración): configuración de cada ejecución, login por rol, step-up, TOTP reusado y fuerza bruta.
5. **Idempotencia y migración** desde el realm viejo.
6. **Documentar** la medición y lo que debe hacer el operador en `identity-edge/docs/`, y dejar las candidatas (retirar la reparación de U12).

**Fuera** (recházalo aunque lo veas roto):

- Cambiar el comportamiento diseñado: niveles `acr`, TOTP obligatorio por rol, WebAuthn como alternativa, `loa-max-age`, los ocho campos de la fuerza bruta, la política de contraseñas. Ni la estructura de los subflujos, sus prioridades o sus `requirement`.
- `system-verification/` (rama en curso), `console/` y `contracts/`.
- El Job de config-cli, su imagen y su digest, `values/`, las políticas `rego` y el `Dockerfile`: cambiar de config-cli es P-1 (b) y necesita al usuario.
- `tests/e2e/` y `tests/load/`: se leen, no se editan. `tools/realm_diff.py`, `jobs/` y `fake_keycloak.py`: que el doble imite mejor a Keycloak es candidata.
- El comentario de la línea 3 del realm y `commentPlaceholder` (`CANDIDATAS.md`, líneas 255 y 264); activar el tema (línea 51); los mappers de LDAP (línea 38).
- Los diseños y los planes (`aidlc-docs/`). Desplegar, sincronizar o tocar el kind: nada de `kubectl`, `helm install` ni `argocd`.

---

## La prueba de integración

`identity-edge/tests/integration/` (directorio nuevo): `realm_stack.py` (arranque y borrado), `conftest.py` y `test_realm_import.py`. Las dependencias ya están en el workspace (`pyproject.toml`, líneas 44 a 50: `testcontainers`, `pyotp`, `httpx`): **no añadas ninguna**.

- **Keycloak:** la imagen de la línea `FROM` de `identity-edge/keycloak/Dockerfile` (línea 3, por digest), leída del archivo. Con `KC_HTTP_RELATIVE_PATH=/auth`, `KC_HOSTNAME` como URL completa, HTTPS con un certificado desechable y un administrador de arranque con contraseña al azar.
- **config-cli:** `adorsys/keycloak-config-cli@<digest de values/kind.yaml>`, con las variables `IMPORT_*` **leídas de `values/common.yaml`** (no copiadas), `PUBLIC_HOSTNAME=127.0.0.1:<puerto>` y `KEYCLOAK_SSLVERIFY=true` contra la CA de la prueba. Las `$(env:…)` del realm se generan al azar: contraseñas, semillas Base32 y un JWKS ES256 por cliente, **como cadena JSON entre comillas** (`CANDIDATAS.md`, línea 256).
- **Modelo:** `system-verification/tests/doubles/keycloak_tc.py` de la rama `tarea/U12-T02` (léelo en su worktree, solo lectura). Es de otra unidad: **no lo importes**; escribe el tuyo, sin `repair_shared_authenticator_configs` ni `complete_user_profiles`. Anota cada diferencia con kind (imagen base con `start` y base embebida, frente a la construida con `--db=postgres`).
- **Login:** Authorization Code + PKCE con `vectra-console`, con `httpx` y siguiendo el formulario, como `Flow` de `tests/e2e/e2e_support.py` (línea 210). Ese `Flow` arma el `redirect_uri` con el hostname de kind (línea 224): **no lo uses tal cual**. Escribe el flujo en `realm_stack.py` con `redirect_uri = https://127.0.0.1:<puerto>/callback`; puedes importar `form_action`, `hidden_fields` y `decode`. El cliente `httpx` lleva un transporte o una guarda que **rechaza todo host que no sea `127.0.0.1:<puerto>`**. Sin Playwright.
- **TOTP:** un código por ventana y por usuario; un segundo login del mismo usuario espera la ventana siguiente (línea 196 de `e2e_support.py`). Reparte los casos entre usuarios para no esperar de más.
- **Fuerza bruta:** con un usuario **efímero** creado por la API de administración en ese Keycloak, nunca con un sintético: `failureFactor` fallos separados más que el control de login rápido (`tests/e2e/test_e2e_bruteforce.py`, líneas 47 a 57), y lectura de `attack-detection/brute-force/users/<id>`. No llegues al bloqueo permanente.
- **No entra en `make test`** (P-3): objetivo propio `integration` en el `Makefile`, `--ignore` en `test` y `collect-integration` dentro de `check`, igual que `e2e` y `collect-e2e`.

## La prueba unitaria

`identity-edge/tests/unit/test_realm_importable.py`, sobre los tres YAML, dentro de `make test`:

1. Ningún alias de `authenticatorConfig` lo citan dos ejecuciones; toda cita existe; ningún alias declarado queda sin citar.
2. Cada configuración conserva los valores del diseño, leídos con `design_values.py`: nivel y `loa-max-age` en las de `conditional-level-of-authentication`; valor y `maxAge` de `amr` en las de `auth-otp-form`, `webauthn-authenticator` y `auth-username-password-form`.
3. `authenticationFlows`, `authenticatorConfig` y `requiredActions` son iguales en los tres realms.
4. Ningún usuario local (sin `serviceAccountClientId`) queda atrapado por el perfil, según la opción de P-2 que rija, también `break-glass`.
5. Mutaciones sobre copias en memoria, nunca sobre los archivos (CA-3).

---

## Criterios de aceptación

Desde `vectra-risk/`. Logs con el prefijo `u02t22-` en `platform/.tools/tmp/`. `uptime` antes y después de cada orden con Docker o `make`.

- [ ] **CA-1 — Rojo primero, integración.** Con las pruebas escritas y **sin** la corrección (el commit de las pruebas va antes que el del realm):
  ```bash
  uv run pytest identity-edge/tests/integration/test_realm_import.py -v -p no:cacheprovider
  ```
  Esperado: termina en 1. El caso de las ejecuciones informa 15 sin `authenticationConfig` y el del login falla con el texto de la página de error y la línea `loaConditionConfig` del log de Keycloak. La salida y el hash del commit van en la bitácora. Si **no** falla, para y reporta: el defecto no se reproduce y la tarea cambia.
- [ ] **CA-2 — Rojo primero, unitaria.** En ese mismo commit:
  ```bash
  uv run pytest identity-edge/tests/unit/test_realm_importable.py -q -p no:cacheprovider
  ```
  Esperado: termina en 1, en los tres entornos, y el mensaje nombra `loa-mfa`, `amr-otp` y `amr-hwk` con sus ejecuciones, y los usuarios que no cumplen el perfil.
- [ ] **CA-3 — Verde unitaria, con mutaciones.** Tras la corrección:
  ```bash
  uv run pytest identity-edge/tests/unit/test_realm_importable.py identity-edge/tests/unit/test_realm_files.py identity-edge/tests/unit/test_realm_lint.py -q -p no:cacheprovider
  uv run pytest identity-edge/tests/unit/test_realm_importable.py -k mutation -v -p no:cacheprovider
  ```
  Esperado: las dos en 0. La segunda muestra, como mínimo: (a) dos ejecuciones con el mismo alias; (b) una cita a un alias que no existe; (c) un alias declarado que nadie cita; (d) un `loa-condition-level` o un `loa-max-age` distinto del diseño en la configuración de un solo rol; (e) un `amr` cruzado (`otp` en WebAuthn); (f) un realm cuyo flujo difiere de los otros dos; (g) un usuario local que vuelve a quedar atrapado por el perfil (un sintético y `break-glass`).
- [ ] **CA-4 — Cambio mínimo en los realms.**
  ```bash
  mkdir -p platform/.tools/tmp && for e in kind staging prod; do git show origin/main:vectra-risk/identity-edge/keycloak/realm/realm.$e.yaml > platform/.tools/tmp/u02t22-base.$e.yaml; done
  uv run python - <<'EOF'
  import collections, yaml
  def core(path):
      r = yaml.safe_load(open(path, encoding="utf-8"))
      r.pop("authenticatorConfig"); r.pop("userProfile", None)
      r["requiredActions"] = [a for a in r["requiredActions"] if a["alias"] != "VERIFY_PROFILE"]
      for f in r["authenticationFlows"]:
          for x in f["authenticationExecutions"]:
              x.pop("authenticatorConfig", None)
      for u in r["users"]:
          for k in ("email", "firstName", "lastName", "emailVerified"):
              u.pop(k, None)
      return r
  for e in ("kind", "staging", "prod"):
      new = f"identity-edge/keycloak/realm/realm.{e}.yaml"
      assert core(f"platform/.tools/tmp/u02t22-base.{e}.yaml") == core(new), e
      r = yaml.safe_load(open(new, encoding="utf-8"))
      cited = collections.Counter(x["authenticatorConfig"] for f in r["authenticationFlows"] for x in f["authenticationExecutions"] if "authenticatorConfig" in x)
      declared = {c["alias"] for c in r["authenticatorConfig"]}
      print(e, "compartidos:", sum(n - 1 for n in cited.values()), "citados:", sum(cited.values()), "declarados:", len(declared), "iguales:", set(cited) == declared)
  EOF
  ```
  Esperado: sin `AssertionError` y, por entorno, `compartidos: 0 citados: 26 declarados: 26 iguales: True` (hoy: `15`, `26`, `11`). Fuera de los alias, las configuraciones y lo de P-2, los realms no cambian.
- [ ] **CA-5 — Verde integración: login por rol.** `make -C identity-edge integration` termina en 0 y `-v` muestra un caso por rol sintético. Cada uno llega al `redirect_uri` y canjea el código. Para `analista`, `ingeniero_riesgo`, `cro` y `cumplimiento`: `acr = mfa`, `amr` con `otp`, `roles` = su único rol, `aud` con `console-bff`, y **sin** `preferred_username`, `email` ni `name` en el access token. Para `operacion`: `acr = mfa`; lo que traiga `roles` se anota (`vectra-console` no tiene ese rol en `scopeMappings`, línea 267 del realm).
- [ ] **CA-6 — Tras importar, cada ejecución tiene su configuración y es la del diseño.**
  ```bash
  uv run pytest identity-edge/tests/integration/test_realm_import.py -k "executions or required_actions" -v -p no:cacheprovider
  ```
  Esperado: 0. Por la API de administración (`GET …/authentication/flows/<alias>/executions` y `…/authentication/config/<id>`), **cada** ejecución que el YAML cita con configuración la tiene (26 de 26; el número sale del YAML, no de un literal) y sus valores son los del YAML. La prueba también lee `GET …/authentication/required-actions` e imprime el estado de `VERIFY_PROFILE`, que debe ser el que P-2 predice.
- [ ] **CA-7 — Step-up, TOTP reusado y fuerza bruta.**
  ```bash
  uv run pytest identity-edge/tests/integration/test_realm_import.py -k "stepup or reused or brute" -v -p no:cacheprovider
  ```
  Esperado: 0, con tres casos o más: (a) step-up de `ingeniero-1` hacia `/stepup-callback` con `prompt=login`, `max_age=0` y `acr_values=mfa`: `acr = mfa` y `auth_time` de ≤ 900 s (`MFA_MAX_AGE` de `vectra_contracts.routes`); (b) el mismo código TOTP en un segundo login no da código de autorización; (c) un usuario efímero queda `disabled` tras `failureFactor` fallos y **no** antes, y los ocho campos de la fuerza bruta leídos de `GET /admin/realms/vectra` son los de `design_values`.
- [ ] **CA-8 — Idempotencia y migración.**
  ```bash
  uv run pytest identity-edge/tests/integration/test_realm_import.py -k "idempot or migrat" -v -p no:cacheprovider
  ```
  Esperado: 0. (a) Aplicar dos veces el realm corregido deja igual la lectura de CA-6 y el número de `authenticatorConfig` de `POST …/partial-export`; la bitácora dice si config-cli **omitió** la segunda pasada por suma de control o la reaplicó. (b) Sobre un Keycloak con el **realm viejo** ya importado (P-4), aplicar el corregido deja CA-6 en 26 de 26 y un login con `acr = mfa`. La prueba cuenta las configuraciones huérfanas (`loa-mfa`, `amr-otp`, `amr-hwk` viejos) que queden y el valor va a la bitácora y al documento. Si la migración **no** deja el login bien, la prueba queda en rojo, se documenta el paso del operador (CA-11) y **paras y reportas**.
- [ ] **CA-9 — Nunca el kind, y nada queda en Docker.**
  ```bash
  grep -rnE "localtest\.me|:443\b|kubectl|verify=False" identity-edge/tests/integration
  docker ps -a --format '{{.Names}} {{.Image}}' | grep -ciE 'u02t22|keycloak-config-cli'
  for i in "$(sed -n 's/^FROM //p' identity-edge/keycloak/Dockerfile)" "adorsys/keycloak-config-cli@$(grep -oE 'sha256:[0-9a-f]{64}' identity-edge/keycloak/values/kind.yaml | tail -1)"; do docker image inspect --format '{{.Id}}' "$i" > /dev/null && echo presente; done
  ```
  Esperado: sin salida; `0`; `presente` dos veces (las dos imágenes siguen ahí; al redactar lo están). Los contenedores de kind (`vectra-*`, `kind-registry`) no se tocan.
- [ ] **CA-10 — Renders regenerados y solo ellos.**
  ```bash
  make -C identity-edge check-keycloak-rendered check-jobs-rendered
  git diff --name-only origin/main | grep -vE '^vectra-risk/(identity-edge/(keycloak/realm/realm\.(kind|staging|prod)\.yaml|keycloak/rendered/kind/config-cli-realm\.yaml|jobs/rendered/(kind|staging|prod)/realm-configmap\.yaml|tests/integration/[a-z_]+\.py|tests/fixtures/realm-pre-u02t22/[A-Za-z0-9._-]+|tests/unit/test_realm_importable\.py|Makefile|docs/(realm-importacion|paso-16-kind)\.md)|bitacoras/U02-T22\.md|CANDIDATAS\.md)$'
  ```
  Esperado: `make` en 0 y el `grep` sin salida. `keycloak/rendered/kind/keycloak.yaml` no cambia. Si una prueba existente necesita un ajuste (`test_realm_files.py`, `test_realm_diff.py`, `realm_lint.py`), **para y pregunta** antes de tocarla: no debería.
- [ ] **CA-11 — Documento y candidatas.**
  ```bash
  grep -nE "^## (Medición|Corrección|Migración|Qué hace el operador|Pendiente en U12)" identity-edge/docs/realm-importacion.md
  grep -cE 'eyJ[A-Za-z0-9_-]{20,}|PRIVATE KEY|TOTP_SEED=|PASSWORD=' identity-edge/docs/realm-importacion.md bitacoras/U02-T22.md
  grep -n "U02-T22" CANDIDATAS.md identity-edge/docs/paso-16-kind.md
  ```
  Esperado: las cinco secciones; `0` en los dos archivos; y en `CANDIDATAS.md` las entradas de «Candidatas» de abajo.
- [ ] **CA-12 — RL-4.**
  ```bash
  export TMPDIR=$PWD/platform/.tools/tmp && uptime && make -C identity-edge check && uptime
  make -C platform check-local
  uv run python platform/tests/test_links.py
  uv run python platform/tests/test_traceability.py --all
  ```
  Esperado: las tres primeras en 0 (`identity-edge`: ≈ 20 a 30 min según `bitacoras/U11-T03.md` y `bitacoras/U08-T05.md`). `check` incluye `collect-integration` y **no** arranca Docker. `--all`: sin fallos nuevos (`DECISIONES-LOOP.md` §6).

---

## Cambios permitidos, archivo por archivo

| Archivo | Qué |
|---|---|
| `identity-edge/keycloak/realm/realm.{kind,staging,prod}.yaml` | El mismo cambio en los tres: alias por ejecución (P-1) y lo de P-2. Nada más (CA-4) |
| `identity-edge/keycloak/rendered/kind/config-cli-realm.yaml`, `identity-edge/jobs/rendered/<env>/realm-configmap.yaml` | Regenerados con `make -C identity-edge render-keycloak render-jobs`. No a mano |
| `identity-edge/tests/integration/{realm_stack,conftest,test_realm_import}.py` | Nuevos |
| `identity-edge/tests/fixtures/realm-pre-u02t22/realm.kind.yaml` (y un `README.md` corto) | Solo si rige P-4 (a): copia literal del realm de la base, para la migración |
| `identity-edge/tests/unit/test_realm_importable.py` | Nuevo |
| `identity-edge/Makefile` | `integration`, `collect-integration` (en `check`) y el `--ignore` de `test`. Nada más |
| `identity-edge/docs/realm-importacion.md` | Nuevo: medición (versiones y digests, cada diferencia con kind, `uptime`), corrección, migración, qué hace el operador, «Pendiente en U12» |
| `identity-edge/docs/paso-16-kind.md` | Una nota en §5 o §6 que remite al documento nuevo. No reescribas la guía |
| `bitacoras/U02-T22.md`, `CANDIDATAS.md` | Bitácora y candidatas |

---

## Preguntas abiertas

**P-1 — Cómo se logra que cada ejecución quede con su configuración.**
- (a) **Un alias único por ejecución** (recomendada): `loa-mfa-<rol>`, `amr-otp-<rol>` y `amr-hwk-<rol>`, con el mismo sufijo que su subflujo `vectra-mfa-<rol>`; `loa-pwd`, `amr-pwd` y `cond-role-*` no cambian. Solo toca el YAML, vale para los tres entornos y `realm-drift` ya empareja por alias.
- (b) Cambiar de config-cli. El repositorio dice que no hay etiqueta alineada con 26.8 y no se sabe si otra versión corrige esto. Toca imagen, digest, espejo de kind y políticas. **Necesita al usuario.**
- (c) Un paso de reparación tras la importación, en el Job. **La peor:** entre la importación y la reparación todo login falla y cada fallo cuenta para el bloqueo; añade un segundo escritor con `realm-admin`, y `realm-drift` vería alias que Git no declara.

**Rige (a); no necesita al usuario.** Si con (a) la importación **tampoco** enlaza las 26 (CA-6 en rojo), para y reporta con la evidencia: entonces es (b).

**P-2 — El perfil de usuario. Necesita al usuario** (cambia el realm de los tres entornos; el diseño no lo cubre).
- (a) Dar `email`, `firstName` y `lastName` sintéticos a los 10 usuarios semilla. Es lo que hace la reparación de U12 y se sabe que funciona. Pero **solo** cubre a los sintéticos: los efímeros de la e2e y los de carga de U2 seguirían atrapados, y en prod `break-glass` y los usuarios de LDAP (de solo lectura, con mappers sin diseñar: `CANDIDATAS.md`, línea 38) también.
- (b) Declarar en el realm un `userProfile` que no exija esos campos. Cubre a todos en los tres entornos. No está comprobado que config-cli `6.5.1` lo importe ni con qué forma; `realm-drift` no lo lee.
- (c) **Declarar `VERIFY_PROFILE` en `requiredActions` con `enabled: false`** (recomendada). Cubre a todos los usuarios y a los tres entornos, es el mismo mecanismo que H12 ya usa para `UPDATE_PASSWORD`, `realm-lint` lo admite (`tools/realm_lint.py`, líneas 399 a 406: solo exige `UPDATE_PASSWORD`) y `realm-drift` lo compararía por alias. El diseño no usa `email` en ningún token ni evento.

**Recomendación: (c)**, medida en CA-5 y CA-6. Si `VERIFY_PROFILE` deshabilitada **no** basta, prueba (b) en el mismo contenedor, anota las dos medidas y para. **En prod:** con (c) o (b) el realm queda bien para `break-glass` y LDAP, pero nada lo aplica hoy (Job bloqueado); con (a) prod sigue roto. Si no hay respuesta al despachar, rige (c) y el PR lo dice en su primera línea. Con (c) el claim `name` del ID token sigue vacío para los sintéticos: candidata, no defecto (nadie lo lee hoy).

**P-3 — ¿La prueba de integración entra en `make check`?**
- (a) **No: objetivo `integration` aparte y `collect-integration` en `check`** (recomendada). `check` es estático por AUTONOMIA-01 (`Makefile`, línea 171), lo corre toda tarea de U2 y el cierre de cada unidad, y dos Keycloak a la vez no caben en la máquina. La guarda rápida es la unitaria.
- (b) Sí: `check` arranca Docker (≈ 3 a 5 min más).

**Rige (a).** Candidata: quién corre `integration` cuando cambie un realm.

**P-4 — De dónde sale el «realm viejo» de la migración.**
- (a) **Una copia literal del `realm.kind.yaml` de la base**, en `tests/fixtures/realm-pre-u02t22/`, con el hash del commit en su `README.md` (recomendada): es el estado exacto que puede tener el kind del operador.
- (b) Derivarlo en memoria del realm corregido (volver a unir los alias). No añade 1 370 líneas, pero supone la forma de la corrección.

**Rige (a).** Comprueba que ninguna regla (`policy-*`, Trivy `skip-files`, `test_realm_has_no_secret_values`) recorre `tests/fixtures/`; si alguna lo hace, usa (b) y anótalo.

---

## Candidatas

**Entran y se marcan «Resuelta (U02-T22)» o «Atendida (U02-T22), falta kind»**, con lo medido:

- Línea 44: Keycloak lee la semilla TOTP en Base32 (lo prueba el login). La segunda mitad (que config-cli reaplique `credentials` a un usuario que ya existe) se mide en CA-8 (b) si cabe; si no, sigue abierta.
- Líneas 59, 257 y 264 (segunda mitad): compatibilidad de config-cli `6.5.1-26.5.5` con Keycloak 26.8.1, con lo que la importación hizo bien y mal.
- Línea 48, en parte: `acr` y `amr` por rol con tokens reales. Lo demás (`break-glass`, `aud` por scope, Grafana) sigue abierto.
- Las dos de la rama `tarea/U12-T02` (líneas 644 y 645 de su `CANDIDATAS.md`): si ya están en `main`, márcalas resueltas; si no, escribe la entrada de este hallazgo y el orquestador las concilia.

**Nuevas, a escribir:**

- **U12-T03 o T04:** retirar `repair_shared_authenticator_configs` y `complete_user_profiles` de `system-verification/tests/doubles/keycloak_tc.py` cuando U02-T22 esté en `main`. **Mientras existan, esconden el defecto**: la prueba de U12 pasaría aunque el realm volviera a romperse. Tras retirarlas, `repaired_configs` y `completed_profiles` deben ser 0 sin ayuda.
- **U12 Paso 18 (operador):** si el kind ya tiene el realm viejo, lo que diga CA-8 (b); y desbloquear por la API de administración a los usuarios que hayan intentado entrar (cada fallo contó).
- U2: `fake_keycloak.py` da la configuración por el alias del YAML; debería imitar lo medido. Y la nota H12 frente a lo medido de `VERIFY_PROFILE`.
- Lo que aparezca: huérfanas tras migrar, el claim `name` vacío, `roles` de `operacion`, quién corre `integration`.

---

## Ramas en curso

- **U12-T02** (`tarea/U12-T02`, worktree `.claude/worktrees/u12-t02`, **solo lectura**): no toques `system-verification/`. Su `make check` arranca un Keycloak (`u12t02-keycloak-*`): antes de arrancar el tuyo, mira `docker ps`. Si al crear tu rama U12-T02 ya está en `main`, sigue sin tocarla: la retirada de la reparación es de U12.
- **Kind de la máquina:** puede tener ya el realm viejo importado. No lo mires ni lo arregles; lo cubre la migración (CA-8) y el documento.

---

## Restricciones del entorno

Las de U02-T21, más las del Keycloak:

- **Un solo Keycloak a la vez**, también dentro de tu prueba: los escenarios (limpio, idempotencia, migración) van en serie, en el mismo contenedor si puedes (borrar el realm `vectra` por la API de administración y reimportar) o en contenedores sucesivos. Ocupa ≈ 1 GiB: límite de 1,5 GiB al contenedor y 768 MiB a config-cli. Antes de arrancar, `free -g` y `docker ps`: si hay otro Keycloak arriba o quedan menos de 2 GiB, espera.
- **Host dinámico:** `127.0.0.1:<puerto>`, puerto libre al azar publicado **solo** en `127.0.0.1`; nunca el 443, el 8080, el 8081, el 8200 ni el 8443 del host. **Nunca `vectra.localtest.me:443` ni el kind**: ese nombre es el clúster de esta máquina y un login fallido allí gasta intentos de usuarios reales de la demo (`DECISIONES-LOOP.md` §10).
- **Docker se comparte.** Contenedores con el prefijo `u02t22-` y una etiqueta propia; **bórralos con sus volúmenes al terminar, también si la prueba falla** (CA-9). **No borres las imágenes** (ya descargadas y autorizadas, §10; las usa U12) ni descargues otras. No toques `vectra-*`, `kind-registry` ni los contenedores de otros (hay `postgres` viejos en `Exited` que no son tuyos).
- **`/tmp` es un tmpfs con cuota.** No copies el repositorio allí. Certificados, logs y temporales van a `platform/.tools/tmp/u02t22/` (`export TMPDIR=$PWD/platform/.tools/tmp`; sin esto `promtool` falla en `make check`). Los archivos montados en el contenedor necesitan permisos de lectura para otro usuario.
- **Máquina compartida y cargada** (al redactar: carga 4,3; 6 GiB disponibles de 14). `uptime` junto a cada medida y cada `make`; los `make`, en serie. Los plazos de arranque de la prueba, generosos (300 s).
- **Sin clúster.** `helm template` sí (lo usa `render-keycloak`).
- **`platform/.tools` y `platform/.charts` no están versionados.** Crea `platform/.tools/` real en tu worktree y copia o enlaza **solo** `platform/.tools/bin`; llena `platform/.charts` con `make -C platform charts` (y copia `keycloakx`, que `charts.sh` no descarga: `docs/paso-16-kind.md`, línea 29). No enlaces los directorios enteros.
- **No toques el árbol principal ni otros worktrees. No uses `git stash`** (la pila se comparte): para los rojos, ordena los commits.

---

## Notas

- **Orden de commits:** (1) prueba de integración y unitaria, en rojo; (2) realms y renders; (3) `Makefile`; (4) documento, candidatas y bitácora. Los hashes de los rojos van en la bitácora.
- **Bitácora:** `bitacoras/U02-T22.md`, con el acuse (hash de este archivo), «Lo comprobado» verificado, los rojos de CA-1 y CA-2 con su salida, las lecturas de CA-6 antes y después, la respuesta aplicada a cada P-n, las diferencias con kind, la duración y la carga de cada corrida, y `docker ps -a` al terminar. **Sin secretos**: ni tokens, ni contraseñas, ni semillas, ni llaves; de los tokens, solo los claims decodificados.
- **Los nombres de los alias nuevos** siguen al subflujo (`vectra-mfa-<rol>`), incluido `break-glass`. `test_realm_files.py` resuelve las citas por alias y no fija nombres: debe seguir en verde sin tocarlo.
- **Lo que esta tarea no demuestra:** que el login funcione en kind detrás del gateway, con PostgreSQL, la imagen construida y el tema (U12 Paso 18), ni la importación de `realm.prod.yaml` (necesita las variables del LDAP). Aquí queda medido que el realm de Git, importado como lo importa kind, deja entrar a cada rol con su nivel.
- **Si algo de «Lo comprobado» no coincide** con tu `main`, anótalo y sigue si no cambia el alcance; si lo cambia, para y reporta.
- Archivos que se **modifican en su sitio**. Nada de duplicados con sufijo. Otro defecto que veas va a `CANDIDATAS.md`, no al diff.
