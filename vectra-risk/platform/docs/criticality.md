# Clasificación de criticidad (NFR-U1-01)

| Componente | Criticidad |
|---|---|
| `registry-db` | critical |
| `case-db`, `governance-db`, `keycloak-db`, KServe, Argo CD | high |
| MinIO | high |
| Observabilidad | medium |

Cada chart declara la etiqueta `vectra.io/criticality`.
