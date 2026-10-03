# Infrastructure Design — U2 `identity-edge`

Decisiones del plan (`identity-edge-infrastructure-design-plan.md`, Q1–Q6 = A). Se apoya en
la infraestructura compartida de U1 (`construction/shared-infrastructure.md`). Los IDs
`INF-U2-xx` se referencian en el plan de tareas.

---

## 1. Hostnames (Q1)

### INF-U2-01

| Entorno | Hostname público | Certificado |
|---|---|---|
| kind | `vectra.localtest.me` | CA interna de U1 |
| staging | `vectra.staging.banco.internal` | `ClusterIssuer` de la CA del banco |
| prod | `vectra.banco.internal` | `ClusterIssuer` de la CA del banco |

- Un solo origen para la SPA, `/api/**`, `/auth/**`, `/grafana/**` y `/federate`. Esto sostiene la CSP con `'self'` y el embebido de Grafana (BR-U2-13).
- Keycloak: `hostname` = el público con el path `/auth`; `hostname-admin` = `keycloak-admin.vectra-identity.svc.cluster.local`, que no está en el gateway (X10).
- Los nombres de staging y prod son de ejemplo y se fijan con el banco en los values de cada entorno.

## 2. Gateway (Q2)

### INF-U2-02 — Envoy Gateway

| Pieza | Namespace | Réplicas | Notas |
|---|---|---|---|
| Controlador | `envoy-gateway-system` | 2 (elección de líder) | Binding nuevo **K14** |
| Data plane (Envoy) | `vectra-edge` | HPA de 2 a 6, spread por zona, PDB | Despliegue en el namespace del `Gateway`, si la versión pinneada lo soporta |
| `GatewayClass` / `Gateway` | `vectra-edge` | — | Un `Gateway` con un listener HTTPS (443) y el certificado de INF-U2-01 |

- **Si la versión pinneada no permite desplegar el data plane en `vectra-edge`**, queda en `envoy-gateway-system`; `flows.yaml` se ajusta y la decisión se registra en `audit.md`. Se verifica en el plan de tareas.
- El Service del data plane es el **único** `LoadBalancer` del clúster (INF-U1-05), con `externalTrafficPolicy: Local` o PROXY protocol v2 (NFR-U2-23).
- La comunicación controlador → Envoy (xDS) es el flujo nuevo F95.

### INF-U2-03 — Servicio de rate limit
- `envoyproxy/ratelimit` en `vectra-edge`: 2 réplicas repartidas por zona, PDB.
- **gRPC en el puerto 8083.** Se cambia el 8081 por defecto, que en Vectra está reservado para health y métricas (convención de U0). Métricas y health en 8081.
- Configuración de descriptores generada por `route-gen` desde `routes.yaml` (P-U2-06).

## 3. Almacenamiento (Q3)

### INF-U2-04 — Valkey 8
- Imagen oficial de Valkey 8, pinneada por digest y firmada; chart propio mínimo en `identity-edge/charts/valkey`.
- StatefulSet de **2 nodos** (primaria + réplica) en zonas distintas y **3 Sentinel** repartidos por zona.
- **Sin persistencia** (sin RDB ni AOF; `emptyDir`): los contadores son efímeros.
- ACL: usuario `ratelimit` con permisos mínimos (`+@read +@write +@connection -@dangerous`) y contraseña desde ESO. Usuario `default` deshabilitado.
- `maxmemory 128mb`, política `volatile-ttl` (todas las claves de rate limit tienen TTL).
- Prioridad `vectra-high`; NetworkPolicy que solo admite al servicio de rate limit, a la réplica y a los Sentinel (F91–F93).

### INF-U2-05 — `keycloak-db`
Sin cambios: el cluster de CloudNativePG de U1 (INF-U1-02: 10 Gi + 5 Gi, `max_connections` 100). Keycloak usa un pool máximo de 20 conexiones por pod.

## 4. Cómputo (Q4)

### INF-U2-06 — Recursos iniciales

| Componente | Requests | Limits | Notas |
|---|---|---|---|
| Keycloak | 500m / 1 GiB | 2 CPU / 2 GiB | `-XX:MaxRAMPercentage=70` |
| Envoy (data plane) | 250m / 256 MiB | 1 CPU / 512 MiB | — |
| Controlador de Envoy Gateway | 100m / 128 MiB | 500m / 256 MiB | — |
| Servicio de rate limit | 100m / 64 MiB | 500m / 128 MiB | — |
| Valkey (cada nodo) | 100m / 128 MiB | 500m / 256 MiB | `maxmemory 128mb` |
| Sentinel (cada uno) | 50m / 32 MiB | 100m / 64 MiB | — |
| `keycloak-config-cli`, `realm-drift` | 100m / 256 MiB | 500m / 512 MiB | Jobs |

Todos en el pool `general`. Se ajustan con la prueba de carga de NFR-U2-10 y se reflejan en
las cuotas de U1 (NFR-U1-13).

## 5. Federación LDAP en producción (Q5)

### INF-U2-07
- **LDAPS (636)** hacia el LDAP del banco (F73), verificando su certificado con la CA del banco (truststore desde ESO).
- Cuenta de *bind* de solo lectura, desde ESO.
- Modo de edición `READ_ONLY`; importación de usuarios habilitada; sincronización de cambios cada 15 min; mapper de grupos → roles según `group-role-map` (BR-U2-15).
- Sin caché de contraseñas: si el LDAP no responde, los usuarios no pueden autenticarse. Alerta **`LdapUnavailable` (SEV2)**, que se agrega a las alertas de P-U2-09.
- F73 ya existe en el inventario de egress («solo en producción real»).

## 6. Imagen de Keycloak (Q6)

### INF-U2-08
- `identity-edge/keycloak/Dockerfile`: imagen oficial de Keycloak 26.x pinneada por digest + tema `vectra` + `kc.sh build` con las opciones de producción (base de datos `postgres`, health y métricas habilitados, `cache=ispn`).
- Construida en CI, escaneada con Trivy y firmada con Cosign (`supply-chain.yml` de U1); el banco la replica a su registro interno.
- Arranque: `start --optimized`.

## 7. Cambios aplicados a otros artefactos

Registrados en `audit.md` (2026-10-03):

| Artefacto | Cambio |
|---|---|
| `component-dependency.md` §0 | Puertos `6379`/`26379` (Valkey y Sentinel), `8083` (gRPC del servicio de rate limit), `18000` (xDS); `9000` también como puerto de gestión de Keycloak |
| `component-dependency.md` §1 | `vectra-edge`: + servicio de rate limit, Valkey y Sentinel; `vectra-identity`: + `keycloak-config-cli`, `realm-drift` y el exportador de llaves; `envoy-gateway-system` en la lista de controladores |
| `component-dependency.md` §2.8 (nueva) | F90–F95 |
| `component-dependency.md` §3 | K14 (controlador de Envoy Gateway) |
| `component-dependency.md` §7 y §9; `unit-of-work.md` U2; `application-design.md` | Rangos F01–F95, K01–K14 |
| `identity-edge/nfr-design/logical-components.md` §3 | Puerto de rate limit 8083 (antes 8081) |
| `identity-edge/nfr-design/nfr-design-patterns.md` P-U2-09 | Alerta `LdapUnavailable` |
| `construction/shared-infrastructure.md` | Nueva §4: lo que U2 provee a las demás unidades |

## 8. Cumplimiento de extensiones (Infrastructure Design U2)

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-08 / 09 | Cumple | INF-U2-02, 03, 04 (spread por zona, HPA, PDB) |
| RESILIENCY-10 | Cumple | INF-U2-04 (sin persistencia: los contadores se pierden sin afectar la corrección) |
| SECURITY-01 | Cumple | INF-U2-01 (certificado de la CA del banco), INF-U2-07 (LDAPS) |
| SECURITY-06 | Cumple | K14 acotado; ACL mínima de Valkey (INF-U2-04) |
| SECURITY-07 | Cumple | INF-U2-04 y flujos F90–F95 en `flows.yaml` |
| SECURITY-09 | Cumple | INF-U2-01 (`hostname-admin` interno) |
| SECURITY-10 | Cumple | INF-U2-04, 08 (imágenes oficiales pinneadas y firmadas) |
| SECURITY-12 | Cumple | INF-U2-07 (bind de solo lectura desde ESO) |
| SECURITY-13 | Cumple | INF-U2-08 (integridad de artefactos): la imagen de Keycloak parte de la imagen oficial pinneada por digest, se construye en CI, se escanea con Trivy y se firma con Cosign; la política `verify-images` de U1 verifica esa firma al admitirla |
| AUTONOMIA-01 | Cumple | Imagen y realm por CI + PR + sync manual |
| AUTONOMIA-05 | Cumple | El único egress de U2 es F73 (LDAP, solo prod), sin datos de solicitantes |
