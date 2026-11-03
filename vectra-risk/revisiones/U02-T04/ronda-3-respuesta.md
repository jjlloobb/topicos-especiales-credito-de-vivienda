F-01: Corregido en este commit: `token.endpoint.auth.signing.alg: ES256` en los 13 clientes `client-jwt` de cada realm; `test_realm_files_assertions_are_signed_with_the_algorithm_of_br_u2_09` lo lee de BR-U2-09 y la mutación a RS256 falla (1 failed).
F-02: Corregido en este commit: `test_realm_files_realm_settings_are_those_of_section_1_0` lee los siete ajustes de §1.0 (WebAuthn con ES256 y RS256) y exige que coincidan exactos; cada mutación de un ajuste falla (1 failed cada una).

## Barrido de los tres YAML (valores sin respaldo explícito en el diseño enmendado)
Los tres realms son idénticos en estos puntos. Ninguno lo inventé en esta ronda; son de la ronda 1 y los reporto, sin cambiar:
1. Equivalentes al valor por defecto de Keycloak (sin efecto): `registrationAllowed`, `registrationEmailAsUsername`, `duplicateEmailsAllowed`, `editUsernameAllowed`, `verifyEmail` en false; `implicitFlowEnabled` y `directAccessGrantsEnabled` en false; `enabled` true.
2. Con efecto, no definidos en el diseño:
   - `fullScopeAllowed: false` en todos los clientes (decisión de mínimo privilegio mía; con `scopeMappings` explícitos para los roles de `vectra-console`, `promotion-tool` y `grafana` y `clientScopeMappings` de `realm-management` para las dos cuentas de administración).
   - `scopeMappings` de `grafana` incluye `analista` (para que el claim `roles` lo lleve y Grafana le niegue acceso) y los de `vectra-console` los cuatro roles de negocio sin `operacion`.
   - `default.acr.values: mfa` en los tres clientes de usuario (derivado de BR-U2-03).
   - `use.refresh.tokens: 'true'` en los clientes de usuario (BR-U2-06 implica refresh).
   - `loa-condition-level` 1 y 2 y la estructura de subflujos con prioridades 10, 20, 30 (mecánica de Keycloak para el LoA).
   - Contraseñas con `temporary: false`, también `break-glass` (NFR-U2-24 pide rotarla tras cada uso; eso no es del realm).
   - Scopes de cliente con `include.in.token.scope: 'true'` y `display.on.consent.screen: 'false'`.
   - Nombres de las acciones requeridas (`Configure OTP`, `Webauthn Register`) y prioridades 10 y 20.
3. Contrato con el Paso 5 (INF-U2-01): `PUBLIC_HOSTNAME`, `CLIENT_<ID>_JWKS`, `SYNTH_<USUARIO>_PASSWORD` y `_TOTP_SEED`, `BREAK_GLASS_PASSWORD`, `LDAP_*`.
Bloqueos nuevos: ninguno que impida cerrar la tarea; los puntos del grupo 2 son decisiones para el usuario si quiere fijarlos en el diseño.
