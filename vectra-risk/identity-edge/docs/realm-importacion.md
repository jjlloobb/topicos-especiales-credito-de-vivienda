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
