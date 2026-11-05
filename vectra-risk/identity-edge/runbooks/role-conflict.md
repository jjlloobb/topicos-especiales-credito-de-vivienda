# RoleConflict

- **Severidad**: SEV2
- **Alerta**: `RoleConflict` (U2)

## Síntoma
`increase(vectra_role_conflict_total[15m]) > 0` durante 5 minutos: Keycloak emitió `ROLE_CONFLICT` para un usuario LDAP con dos grupos que mapean a roles distintos. Es una métrica de contrato: todavía no la emite nada (ver `CANDIDATAS.md`, BR-U2-17), así que la alerta solo dispara cuando exista ese mecanismo.

## Impacto
Por BR-U2-01, ese usuario no recibe ningún rol y no puede operar. No es una falla del sistema: la membresía de grupos del banco es ambigua.

## Diagnóstico
1. Identifica al usuario y sus grupos en el evento `ROLE_CONFLICT` (Loki, Grafana Explore, o `kubectl -n vectra-identity logs -l app.kubernetes.io/name=keycloak --tail=500`).
2. Revisa el mapa de grupo a rol (`identity-edge/keycloak/realm/`, BR-U2-01).
3. Confirma con el banco cuál es el grupo correcto.

## Mitigación
1. El banco corrige la membresía en LDAP: el usuario debe quedar en un solo grupo mapeado.
2. No asignes un rol a mano: eso oculta el conflicto y rompe BR-U2-01.
3. Si el conflicto es del mapa y no del usuario, corrige `group-role-map.yaml` por PR.

## Escalamiento
SEV1 y SEV2 exigen COE en 5 días hábiles (`platform/runbooks/coe-template.md`).

## Verificación
- `kubectl -n vectra-identity logs -l app.kubernetes.io/name=keycloak --tail=200` no muestra nuevos `ROLE_CONFLICT` para el usuario tras su próximo login.
- La alerta deja de estar `firing` en Alertmanager (la ventana de `increase` es de 15 minutos).
- `promtool test rules identity-edge/observability/rules/tests/*.yaml` en el repositorio (la alerta dispara y no dispara con series sintéticas).
