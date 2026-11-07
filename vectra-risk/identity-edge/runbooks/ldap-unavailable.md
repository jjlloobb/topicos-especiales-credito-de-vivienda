# LdapUnavailable

- **Severidad**: SEV2
- **Alerta**: `LdapUnavailable` (U2, solo prod)

## Síntoma
Un fallo de conexión en los últimos 5 minutos (`increase(vectra_ldap_connection_failures_total[5m]) > 0`) o una serie nueva del contador (`vectra_ldap_connection_failures_total > 0 unless vectra_ldap_connection_failures_total offset 5m`, el primer fallo de un contador que nace con él): la federación LDAP de Keycloak no se conecta al LDAP del banco (F73, 636 o 443). Dispara sin espera (`for` 0m, B12): un solo fallo corto basta, y el aviso dura hasta que la ventana de 5 minutos deja de verlo. Es una métrica de contrato que todavía no emite nada (ver `CANDIDATAS.md`); en kind y staging no hay series y la alerta no dispara.

## Impacto
Los usuarios del banco que entran por LDAP no pueden iniciar sesión.

## Diagnóstico
1. Conexión desde Keycloak, en el log: `kubectl -n vectra-identity logs -l app.kubernetes.io/name=keycloak --tail=300`.
2. Política de red F73: `kubectl -n vectra-identity get networkpolicy`.
3. Certificado y CA del LDAP del banco: el secreto de la federación en `kubectl -n vectra-identity get externalsecret`.
4. Pregunta al banco si el LDAP está en mantenimiento o cambió su certificado.

## Mitigación
1. Si el LDAP del banco está caído, espera su recuperación y avisa a los usuarios afectados.
2. Si cambió el certificado o la credencial de enlace, actualiza la CA o el secreto en la bóveda y deja que ESO lo sincronice.
3. Mientras tanto, los operadores que necesiten entrar usan el procedimiento de `break-glass-login.md` con aprobación.

## Escalamiento
SEV1 y SEV2 exigen COE en 5 días hábiles (`platform/runbooks/coe-template.md`).

## Verificación
- `kubectl -n vectra-identity logs -l app.kubernetes.io/name=keycloak --tail=100` no muestra nuevos fallos de conexión LDAP.
- Un login de un usuario LDAP de prueba termina bien (con aprobación del banco): `kubectl -n vectra-identity logs -l app.kubernetes.io/name=keycloak --tail=50` muestra el evento `LOGIN` sin error.
- La alerta deja de estar `firing` en Alertmanager (la ventana de `increase` es de 5 minutos).
- `promtool test rules identity-edge/observability/rules/tests/*.yaml` en el repositorio (la alerta dispara y no dispara con series sintéticas).
