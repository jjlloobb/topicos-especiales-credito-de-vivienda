# KeycloakDown

- **Severidad**: SEV1
- **Alerta**: `KeycloakDown` (U2)

## Síntoma
Ninguna réplica de Keycloak está lista (`kube_statefulset_status_replicas_ready == 0` durante 1 minuto). La expresión está en `identity-edge/observability/rules/identity-edge-rules.yaml`.

## Impacto
Nadie inicia sesión ni obtiene tokens nuevos. Los servicios no pueden renovar su JWKS ni pedir tokens de servicio (F50).

## Diagnóstico
1. Estado del StatefulSet: `kubectl -n vectra-identity get statefulset keycloak`.
2. Pods y eventos: `kubectl -n vectra-identity get pods -l app.kubernetes.io/name=keycloak` y `kubectl -n vectra-identity describe pods -l app.kubernetes.io/name=keycloak`.
3. Causa en el log: `kubectl -n vectra-identity logs -l app.kubernetes.io/name=keycloak --tail=200`.
4. Base de datos `keycloak-db` (CloudNativePG): `kubectl get clusters.postgresql.cnpg.io -A`.
5. Certificado y Secrets: `kubectl -n vectra-identity get certificate keycloak-tls` y `kubectl -n vectra-identity get externalsecret`.
6. Solo en kind (límite aceptado, C-03 / M5 de U02-T18): Keycloak pide 512 Mi y tiene un limit de 2 Gi, y arranca usando más que su request. Con presión de memoria en el nodo entra en el grupo que el kubelet puede desalojar. Por su prioridad `vectra-high` (100000), antes que él caen los pods de U1 que no tienen request de memoria ni prioridad. Busca `Evicted` u `OOMKilled` en `describe pods`; no es un defecto de staging ni de prod, donde pide 1 Gi.

## Mitigación
1. Si `keycloak-db` no está sana, sigue el runbook de la base de datos (`platform/runbooks/postgres-replica-lag.md`, `platform/runbooks/zone-failover.md`).
2. Si el pod no arranca por un Secret o el certificado, corrige el `ExternalSecret` o la emisión de `keycloak-tls` y deja que el StatefulSet reintente.
3. Si empezó tras un despliegue, revierte el cambio en Git (`vectra-risk-gitops`) y deja que Argo CD sincronice; no edites el clúster a mano.

## Escalamiento
SEV1 y SEV2 exigen COE en 5 días hábiles (`platform/runbooks/coe-template.md`). Avisa a seguridad: sin Keycloak no hay autenticación en ningún servicio.

## Verificación
- `kubectl -n vectra-identity get statefulset keycloak -o jsonpath='{.status.readyReplicas}'` devuelve 1 o más.
- La alerta `KeycloakDown` deja de estar `firing` en Alertmanager.
- `promtool test rules identity-edge/observability/rules/tests/*.yaml` en el repositorio (la alerta dispara y no dispara con series sintéticas).
