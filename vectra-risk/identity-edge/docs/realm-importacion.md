# Importar el realm: lo medido con Keycloak y keycloak-config-cli reales (U02-T22)

Antes de esta tarea ninguna prueba importaba el realm en un Keycloak: el login en kind estaba roto sin que nada lo viera. Esta guía deja lo medido, lo corregido y lo que hace el operador. La prueba es `identity-edge/tests/integration/` (`make -C identity-edge integration`; arranca Docker, no entra en `check`) y la guarda rápida es `tests/unit/test_realm_importable.py` (entra en `make test`).

## Medición

- Keycloak 26.8.1 (imagen de la línea `FROM` de `keycloak/Dockerfile`, por digest) y keycloak-config-cli `6.5.1-26.5.5` (digest de `keycloak/values/kind.yaml`; hecha para Keycloak 26.5.5). Variables `IMPORT_*` leídas de `values/common.yaml`, `KEYCLOAK_SSLVERIFY=true`, el YAML sin editar.
- Diferencias con kind: imagen base con `start` y base embebida (kind: la construida, `--db=postgres`, `start --optimized`); host `127.0.0.1:<puerto aleatorio>` con una CA desechable (kind: `vectra.localtest.me` con la CA interna, detrás del gateway); administrador `bootstrap` con contraseña al azar; config-cli con `network_mode=host` y truststore PKCS12 generado (kind: pod con initContainer); el tema `vectra` se monta pero el realm no lo activa, como en kind. **No se probó**: PostgreSQL, Infinispan, el gateway, el tema, `realm.prod.yaml` (necesita el LDAP).
- Cargas de la máquina durante las corridas: 8 a 13 (`uptime` en la bitácora, `bitacoras/U02-T22.md`). Corrida completa: 12 casos en 4 min 47 s.
- **Defecto (a), reproducido sobre `origin/main` 23e8d73:** tras importar `realm.kind.yaml`, 11 de 26 ejecuciones tienen `authenticationConfig`; las 15 que faltan son las citas repetidas de `loa-mfa`, `amr-otp` y `amr-hwk` (config-cli solo enlaza un alias a la primera ejecución que lo cita). Todo login falla con «Unexpected error when handling authentication request to identity provider» y, en el log, `KC-SERVICES0013: Failed authentication: java.lang.NullPointerException ... "loaConditionConfig" is null`. Falla incluso el de `ingeniero_riesgo`, que sí tiene las suyas: Keycloak evalúa también los subflujos de los otros roles. No es del desfase de versiones: se corrigió sin cambiar de config-cli.
- **Defecto (b):** sin `VERIFY_PROFILE` declarada, Keycloak la deja activa tras importar (`enabled: true`, prioridad 100) y los usuarios sin `email`, `firstName` ni `lastName` terminan el login en esa acción. La nota H12 de `business-rules.md` (config-cli borra las acciones que Git no declara) **no se cumple** para esta: sigue activa. El diseño lo enmienda el orquestador.
- Cada login fallido por (a) cuenta para la fuerza bruta (`LOGIN_ERROR ... invalid_user_credentials`).

## Corrección

- P-1 (a): un alias de `authenticatorConfig` por ejecución, con el sufijo del subflujo `vectra-mfa-<rol>`: `loa-mfa-<rol>`, `amr-otp-<rol>` y `amr-hwk-<rol>` para `ingeniero_riesgo`, `cro`, `cumplimiento`, `operacion`, `break-glass` y `analista`. Los tres realms, el mismo cambio: 26 citas, 26 declarados, 0 compartidos. Importado: **26 de 26** ejecuciones enlazadas, con los valores del YAML.
- P-2 (c, decisión del usuario): `VERIFY_PROFILE` declarada en `requiredActions` con `enabled: false`. **Bastó**: tras importar, los 10 sintéticos entran sin `email` ni nombres; `break-glass` y los usuarios de LDAP quedan cubiertos por el mismo mecanismo (en prod nada lo aplica hoy: el Job está bloqueado). Con esto el claim `name` del ID token sigue vacío para los sintéticos (nadie lo lee).
- Medido tras importar, por rol: `acr = mfa`, `amr = [pwd, otp]`, `roles` = su rol, `aud` con `console-bff`, sin `preferred_username`, `email` ni `name` en el access token (`operacion`: `acr = mfa`, sin `roles`, porque `vectra-console` no tiene ese rol en `scopeMappings`). Step-up con `acr = mfa` y `auth_time` ≤ 900 s; un código TOTP reusado no da código de autorización; un usuario efímero queda `disabled` en el fallo 5 (temporal, 60 s) y no antes.
- Idempotencia: aplicar el realm dos veces deja las 26 enlazadas y 30 `authenticatorConfig` en `partial-export` (26 del YAML y 4 de los flujos predefinidos de Keycloak). La segunda pasada de config-cli no escribe líneas de actualización (solo `Importing file`): es compatible con que la omita por suma de control, pero el log no lo dice.

## Migración

Sobre un Keycloak con el **realm viejo** ya importado (copia literal en `tests/fixtures/realm-pre-u02t22/`): 11 de 26 enlazadas. Al aplicar el corregido encima: **26 de 26**, **0** configuraciones huérfanas con los alias viejos (`loa-mfa`, `amr-otp`, `amr-hwk`), `VERIFY_PROFILE` queda deshabilitada y el login de `ingeniero-2` da `acr = mfa`. La migración no necesita ningún paso manual sobre el realm.

## Qué hace el operador

1. Si el kind **no** tiene aún el realm, nada especial: el Job lo importa con el YAML corregido.
2. Si el kind **ya** tiene el realm viejo: volver a sincronizar U2 (el Job `keycloak-config-cli` reaplica el realm corregido; sección 5 de `paso-16-kind.md`). No hace falta borrar el realm.
3. Los intentos de login fallidos con el realm viejo contaron para la fuerza bruta: bloqueo temporal de 60 s al quinto fallo y permanente en el 20. Desbloquear por la API de administración a los usuarios que hayan intentado entrar (`DELETE /admin/realms/vectra/attack-detection/brute-force/users/<id>`; o `…/users` para todos), y comprobar con un login por rol.
4. Cada vez que cambie un realm: correr `make -C identity-edge integration` (quién la corre es una candidata).

## Pendiente en U12

`system-verification/tests/doubles/keycloak_tc.py` (rama `tarea/U12-T02`) trae `repair_shared_authenticator_configs` y `complete_user_profiles`, que **esconden** estos defectos: su prueba pasaría aunque el realm volviera a romperse. Cuando U02-T22 esté en `main`, U12 las retira y comprueba que `repaired_configs` y `completed_profiles` valen 0 sin ayuda. Si el kind del operador tiene el realm viejo, el Paso 18 aplica el punto 2 y 3 de arriba antes de la verificación.

## Descubrimiento y segundo login con sesión abierta (U02-T27)

**Defecto, reproducido con el Keycloak real** (`tests/integration/test_login_levels.py`, contra el realm de `origin/main` 524273a): `GET /auth/realms/vectra/.well-known/openid-configuration` da **500** y el segundo login con la cookie de sesión del primero da **400** («Unexpected error when handling authentication request to identity provider»); en ambos el log dice `IllegalStateException: Duplicate key 2 (attempted merging values 36000 and 36000)`. Causa (código de Keycloak 26.8.1, `LoAUtil.getLoaMaxAgesConfiguredInRealmFlow`): arma la tabla nivel → vigencia con `Collectors.toMap` sobre **todas** las condiciones `conditional-level-of-authentication` del flujo de login, en cualquier subflujo; el realm tenía seis de nivel 2 (una por rol) y dos con el mismo nivel no caben. Lo consultan el descubrimiento y la petición de login que llega con sesión SSO abierta; medido: el primer login (sin cookie) pasa, por eso los guiones (`token.sh`, `e2e_support.py`) nunca lo vieron.

**Forma del flujo** (el mismo en `realm.{kind,staging,prod}.yaml`):

| | Antes | Ahora |
|---|---|---|
| `vectra-browser forms` | `vectra-level-pwd` y un `vectra-mfa-<rol>` por rol (6), todos `CONDITIONAL` | `vectra-level-pwd`, `vectra-mfa-exempt` y `vectra-mfa`, `CONDITIONAL` |
| Nivel 1 | `loa-pwd` en `vectra-level-pwd` | igual |
| Nivel 2 | `loa-mfa-<rol>` en cada `vectra-mfa-<rol>` (6 condiciones de nivel 2) | **una**: `loa-level-mfa` en `vectra-mfa` |
| Quién pasa por el nivel 2 | quien cumple la condición de rol de su subflujo (`conditional-user-role`: `ingeniero_riesgo`, `cro`, `cumplimiento`, `operacion`, `realm-management.realm-admin` o `analista`) | quien **no** es «sin ningún rol con MFA»: `vectra-mfa-exempt` junta las seis condiciones de rol **negadas** (usuario sin ninguno de los seis) y no pide nada (`allow-access-authenticator`); `vectra-mfa` lleva `conditional-sub-flow-executed` con `check_result: not-executed` sobre ese subflujo |
| Segundo factor | `vectra-mfa-<rol> factor` (TOTP o WebAuthn) con `amr-otp-<rol>` y `amr-hwk-<rol>` | un `vectra-mfa factor` (TOTP o WebAuthn) con `amr-otp-mfa` y `amr-hwk-mfa`; mismos `amr` (`otp`, `hwk`) y vigencia |

Por qué es equivalente: la condición de rol de cada subflujo antiguo era verdadera para quien tenía ese rol; «tener alguno de los seis» es la negación de «no tener ninguno», y «no tener ninguno» sí se puede escribir con condiciones (un Y de negaciones). Una sola condición de nivel basta porque el segundo factor es el mismo para todos. Rol por rol (medido con el Keycloak real, una prueba por rol): `ingeniero_riesgo`, `cro`, `cumplimiento`, `operacion` y `analista` piden TOTP y no obtienen código sin él; el token trae `acr = mfa`, `amr` con `otp`; `break-glass` (rol de cliente `realm-admin`) no obtiene código sin factor; un usuario sin ninguno de los seis roles entra con la contraseña y su token queda en `acr = pwd`, como antes. TOTP repetido y TOTP erróneo siguen sin dar código.

**Con sesión abierta** (el segundo login con la cookie): sigue en el nivel y la vigencia que dicta `loa-max-age` (36000 s): una sesión en nivel `mfa` vuelve a entrar sin repetir el TOTP; el step-up (`prompt=login`, `max_age=0`, `acr_values=mfa`) sigue pidiéndolo. Nada de eso cambió: solo dejó de fallar.

**No cambia, aunque lo parezca:** `conditional-user-configured` de `vectra-mfa-analista` no filtraba nada (su hermano era un subflujo y Keycloak no lo mira), así que `analista` ya exigía el segundo factor y un `analista` sin factor no entraba (`CANDIDATAS.md`, U02-T22). Ahora tampoco entra; no se arregló aquí porque cambia qué ve ese usuario.

**Migración sobre el realm ya importado** (medida con `test_discovery_migration_from_the_realm_with_one_level_condition_per_role`, que importa el realm de 524273a, comprueba el 500 y aplica el nuevo encima): `keycloak-config-cli` reemplaza los flujos y las configuraciones del realm (los `vectra-mfa-<rol>`, `loa-mfa-<rol>`, `amr-*-<rol>` y `cond-role-<rol>` desaparecen), 12 de 12 ejecuciones con su configuración, el descubrimiento da 200 y el login con sesión abierta pasa. No se tocan usuarios, credenciales (los TOTP ya registrados) ni sesiones: el nivel alcanzado vive en la sesión, no en el flujo.

**Qué hace el operador:** sincronizar `keycloak` (Application de kind, wave 3; el hook `PostSync` ejecuta el Job `keycloak-config-cli`, que aplica `realm.kind.yaml`) y después `identity-jobs` (el ConfigMap del realm que lee `realm-drift`). Comprobar: `curl -s -o /dev/null -w '%{http_code}' https://<host>/auth/realms/vectra/.well-known/openid-configuration` → `200`; entrar desde un navegador, cerrar la pestaña sin cerrar sesión y volver a entrar: llega sin error. Si el Job falla a medias (no medido en kind): la importación es idempotente (medido: una segunda pasada deja el mismo estado), así que se corrige la causa que diga el log del Job y se vuelve a sincronizar `keycloak`; no hace falta borrar el realm.

**`realm-drift` contra Keycloak real:** el lector (`jobs/keycloak_admin.py`) no ve los subflujos (`GET /authentication/flows` solo lista los de primer nivel) y marca diferencia en los `protocolMappers` de los clientes; eso ya era así antes de este cambio (la prueba de migración mide 58 diferencias con el realm anterior contra su propio YAML y 35 con el nuevo). Candidata en `CANDIDATAS.md`.
