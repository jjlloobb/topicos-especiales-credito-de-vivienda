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
- Los nombres de staging y prod son de ejemplo y se fijan con el banco en los values de cada entorno. El realm no los repite: usa `$(env:PUBLIC_HOSTNAME)`, que sale de esos values (enmienda del 2026-11-02, decisión del usuario tras la ronda 1 de U02-T04).
- Contrato de variables del realm con el despliegue (Paso 5): `PUBLIC_HOSTNAME`, `CLIENT_<ID>_JWKS`, `SYNTH_<USUARIO>_*`, `BREAK_GLASS_PASSWORD` y `LDAP_*` (enmienda del 2026-11-02, decisión del usuario tras la ronda 1 de U02-T04).
- Claves de la bóveda para los secretos de U2, con prefijo `identity/` (enmienda del 2026-11-03, decisión Q4 del usuario al preparar U02-T07):
  - `identity/ca`, propiedad `ca.crt`: certificado público de la CA de INF-U2-01 (INF-U2-05b);
  - `identity/clients/<clientId>`, propiedades `private-key` (PEM de la llave ES256 del cliente, solo para los clientes cuyo pod firma aserciones) y `jwks` (su llave pública, que alimenta `CLIENT_<ID>_JWKS`);
  - `identity/break-glass`, propiedad `BREAK_GLASS_PASSWORD`;
  - `identity/synthetic-users`, una propiedad por variable `SYNTH_<USUARIO>_*` (solo kind y staging);
  - `identity/ldap`, una propiedad por variable `LDAP_*` (solo prod).
  - Regla: cuando la clave lleva variables del contrato, el nombre de la propiedad es el de la variable.
- Nombres de los Secret en `vectra-identity` que crean esos `ExternalSecret` (enmienda del 2026-11-03, decisión D-5 del usuario tras la ronda 1 de U02-T07): `identity-ca` (de `identity/ca`), `keycloak-config-cli-client` y `keycloak-reader-client` (de `identity/clients/<clientId>`).
- `ClusterIssuer` del certificado interno: `vectra-internal-ca` en kind; en staging y prod, el de la CA del banco, cuyo nombre se fija en la integración. Hasta entonces el ejemplo es `banco-ca`, y staging y prod nunca usan el de kind (enmienda del 2026-11-03, decisión D-3 del usuario tras la ronda 1 de U02-T07).

## 2. Gateway (Q2)

### INF-U2-02 — Envoy Gateway

| Pieza | Namespace | Réplicas | Notas |
|---|---|---|---|
| Controlador | `envoy-gateway-system` | 2 (elección de líder) | Binding nuevo **K14** |
| Data plane (Envoy) | `vectra-edge` | HPA de 2 a 6, spread por zona, PDB | Despliegue en el namespace del `Gateway`, si la versión pinneada lo soporta |
| `GatewayClass` / `Gateway` | `vectra-edge` | — | Un `Gateway` con un listener HTTPS (443) y el certificado de INF-U2-01 |

- **Si la versión pinneada no permite desplegar el data plane en `vectra-edge`**, queda en `envoy-gateway-system`; `flows.yaml` se ajusta y la decisión se registra en `audit.md`. Se verifica en el plan de tareas.
- El Service del data plane es el **único** `LoadBalancer` del clúster (INF-U1-05), con `externalTrafficPolicy: Local` o PROXY protocol v2 (NFR-U2-23).
- La comunicación xDS es el flujo nuevo F95: Envoy se conecta al controlador (cuarta revisión de coherencia entre unidades, 2026-10-31).

### INF-U2-03 — Servicio de rate limit
- `envoyproxy/ratelimit` en `vectra-edge`: HPA de 2 a 4 por CPU, repartido por zona, PDB. Sin HPA ni exención, `require-hpa-bounds` lo rechazaría (quinta revisión de coherencia entre unidades, 2026-10-31).
- **gRPC en el puerto 8083.** Se cambia el 8081 por defecto, que en Vectra está reservado para health y métricas (convención de U0). Métricas y health en 8081.
- Configuración de descriptores generada por `route-gen` desde `routes.yaml` (P-U2-06).

## 3. Almacenamiento (Q3)

### INF-U2-04 — Valkey 8
- Imagen oficial de Valkey 8, espejada en un registro que admita `restrict-registries` (`registro.banco.internal/vectra`, y `kind-registry:5000` en kind), pinneada por digest y firmada (revisión de consistencia entre unidades, 2026-11-01); chart propio mínimo en `identity-edge/charts/valkey`.
- StatefulSet de **2 nodos** (primaria + réplica) en zonas distintas y **3 Sentinel** repartidos por zona.
- **Sin persistencia** (sin RDB ni AOF; `emptyDir`): los contadores son efímeros.
- ACL: usuario `ratelimit` con permisos mínimos (`+@read +@write +@connection -@dangerous`) y contraseña desde ESO. Usuario `default` deshabilitado. También usuarios de replicación y de Sentinel con los comandos mínimos de cada uno, desde ESO, y sin ellos F92 y F93 no funcionan. PDB: Valkey `minAvailable: 1` y Sentinel `minAvailable: 2` (seguimiento de la quinta revisión de coherencia, 2026-10-31).
- **Sentinel con dos zonas** (seguimiento de la quinta revisión de coherencia, 2026-10-31): 1 Sentinel en la zona A y 2 en la B. La primaria se prefiere en la zona A: si cae A, los 2 de B promueven la réplica; si cae B, la primaria sigue. Tras una conmutación, el runbook la devuelve a A. Mientras esté en B, una caída de B deja 1 de 3 Sentinel, sin promoción, y `/auth/**` responde 503 hasta que vuelva la zona. Es un riesgo aceptado para el MVP.
- `maxmemory 128mb`, política `volatile-ttl` (todas las claves de rate limit tienen TTL).
- Prioridad `vectra-high`; NetworkPolicy que solo admite al servicio de rate limit, a la réplica y a los Sentinel (F91–F93).

### INF-U2-05a — Credencial de administración (seguimiento de la quinta revisión de coherencia, 2026-10-31)
- Dos clientes de administración del realm `vectra`, por F94, con `private_key_jwt` desde ESO (enmienda del 2026-11-02, decisión del usuario tras la ronda 3 de U02-T03):
  - `keycloak-config-cli`: su cuenta de servicio tiene el rol `realm-admin` de `realm-management`; es el único que escribe;
  - `keycloak-reader`: su cuenta de servicio tiene solo `view-realm`, `view-clients` y `view-users` de `realm-management`, y el `clientScopeMappings` de `realm-management` para `keycloak-reader` es ese mismo conjunto; lo usan `realm-drift` y `signing-key-age`, que solo leen. En Keycloak 26.8.1, `view-realm` no basta para leer clientes, client scopes ni usuarios (`ClientPermissions.canView` exige `view-clients`; `UserPermissions.canView`, `view-users`), y `partial-export` exige `manage-realm` (`RealmAdminResource.java`) (enmienda del 2026-11-03, decisión R1 del usuario al preparar U02-T08).
- `realm-lint` rechaza cualquier rol de `realm-management` en otra cuenta de servicio, y en la de `keycloak-reader` cualquier rol fuera de `view-realm`, `view-clients` y `view-users` (enmienda del 2026-11-03, decisión R1 del usuario al preparar U02-T08).

- `keycloak-config-cli` corre como hook **`PostSync`** de Argo CD, con `hook-delete-policy: BeforeHookCreation`, cuando la wave 3 ya está sana (enmienda del 2026-11-03, decisión Q3 del usuario al preparar U02-T07).
- **Bloqueo** (enmienda del 2026-11-03, decisión Q1 del usuario al preparar U02-T07): ninguna versión publicada de `keycloak-config-cli` admite `private_key_jwt` (la última, v6.5.1 de 2026-05-22, solo admite contraseña o `client_secret`). El soporte entró en su rama principal el 2026-09-13 y lee un JWT **ya firmado** desde un archivo (`clientAssertionFile`), así que además hace falta un firmante que este diseño no tiene. El Job se separa del Paso 5 en una tarea propia, que espera un release con aserciones de cliente y el diseño del firmante.

### INF-U2-05b — Certificado interno de Keycloak (quinta revisión de coherencia entre unidades, 2026-10-31)
- `Certificate` `keycloak-tls` en `vectra-identity`, con SAN `keycloak.vectra-identity.svc` y `keycloak-admin.vectra-identity.svc.cluster.local` (el de `hostname-admin`; (enmienda del 2026-11-03, decisión D-2 del usuario tras la ronda 1 de U02-T07)), emitido por la CA de INF-U2-01 de cada entorno; 90 días, se renueva a los 60 (P-U1-03).
- El certificado público de esa CA está en la bóveda. Los clientes lo reciben por `ExternalSecret`: el gateway (`BackendTLSPolicy` de F05), los servicios de F50, `keycloak-config-cli` y `realm-drift` (F94).

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
| `keycloak-config-cli`, `realm-drift`, `signing-key-age` | 100m / 256 MiB | 500m / 512 MiB | Jobs y CronJobs (seguimiento de la quinta revisión de coherencia, 2026-10-31) |
| Exportador de Valkey (sidecar de cada nodo) | 50m / 32 MiB | 100m / 64 MiB | seguimiento de la quinta revisión de coherencia, 2026-10-31 |

Con `maxSurge: 1`, y el rate limit con HPA de 2 a 4, los aportes con el proxy y el 30 % son: `vectra-edge` ≈ 5,72 CPU / 3,64 GiB de requests y ≈ 25,35 CPU / 9,18 GiB de limits; `vectra-identity` ≈ 4,68 CPU / 7,68 GiB y ≈ 20,15 CPU / 16,25 GiB (seguimiento de la quinta revisión de coherencia, 2026-10-31).

Todos en el pool `general`. Se ajustan con la prueba de carga de NFR-U2-10 y se reflejan en
las cuotas de U1 (NFR-U1-13).

## 5. Federación LDAP en producción (Q5)

### INF-U2-07
- **LDAPS (636)** hacia el LDAP del banco (F73), verificando su certificado con la CA del banco (truststore desde ESO).
- Cuenta de *bind* de solo lectura, desde ESO.
- Modo de edición `READ_ONLY`; importación de usuarios habilitada; sincronización de cambios cada 15 min; mapper de grupos → roles según `group-role-map` (BR-U2-15).
- Host, base DN, atributos y vendor del LDAP salen de ESO o de los values como `$(env:LDAP_*)`; los demás parámetros de la federación quedan con el valor por defecto de Keycloak (enmienda del 2026-11-02, decisión del usuario tras la ronda 1 de U02-T04).
- Sin caché de contraseñas: si el LDAP no responde, los usuarios no pueden autenticarse. Esto no es `cachePolicy: NO_CACHE` (caché de usuarios), que no se exige (enmienda del 2026-11-02, decisión del usuario tras la ronda 1 de U02-T04). Alerta **`LdapUnavailable` (SEV2)**, que se agrega a las alertas de P-U2-09.
- F73 ya existe en el inventario de egress («solo en producción real»).

## 6. Imagen de Keycloak (Q6)

### INF-U2-08
- `identity-edge/keycloak/Dockerfile`: imagen oficial de Keycloak 26.x pinneada por digest + tema `vectra` + `kc.sh build` con las opciones de producción (base de datos `postgres`, health y métricas habilitados, `cache=ispn`).
- `kc.sh build` lleva además `--http-relative-path=/auth`: en Keycloak 26.8.1 es una opción de build (`buildTime(true)` en `HttpOptions.java`), y con `start --optimized` un valor de ejecución distinto se ignora. Sin ella, Keycloak sirve en `/` y no se cumplen el `hostname` con `/auth` (INF-U2-01) ni la JWKS interna `/auth/realms/…` (enmienda del 2026-11-03, decisión D-1 del usuario tras la ronda 1 de U02-T07).
- Imagen base: `quay.io/keycloak/keycloak:26.8.1@sha256:3f3c5f8e03c614774b4bd9173b88391fefa4153bfc010d8012d59ad825377332`, la última 26.x estable al 2026-11-02. Se comprobó que en ese tag siguen las claves `default.reference.value` y `default.reference.maxAge` de domain-entities §1.2 (`Constants.java`) (enmienda del 2026-11-02, decisión P2 del usuario al preparar U02-T06).
- Referencia en los values de `keycloakx` (enmienda del 2026-11-03, decisión Q2 del usuario al preparar U02-T07): repositorio `registro.banco.internal/vectra/keycloak` (`kind-registry:5000/vectra/keycloak` en kind) con el **digest en los values de cada entorno**. La plantilla lo exige: sin digest, el render falla. Mientras ningún workflow construya la imagen, las pruebas usan un digest de ejemplo.
- Chart `keycloakx` de codecentric, versión **7.4.0** (appVersion 26.8.1, la de esta imagen), comprobada el 2026-11-03 (enmienda del 2026-11-03, decisión Q2 del usuario al preparar U02-T07).
- Construida en CI, escaneada con Trivy y firmada con Cosign (`supply-chain.yml` de U1); el banco la replica a su registro interno.
- Arranque: `start --optimized`.

## 6a. CronJobs de identidad (enmienda del 2026-11-03, decisiones R1–R4 del usuario al preparar U02-T08)

### INF-U2-09 — `realm-drift` y `signing-key-age`
- **Lectura por F94** con la credencial de `keycloak-reader` (INF-U2-05a): token por `private_key_jwt` ES256 con `vectra_common.service_token` de U0 (BR-U2-09), llave del Secret `keycloak-reader-client` (propiedad `private-key`) y CA del Secret `identity-ca`. La API de administración se llama por `hostname-admin` (INF-U2-01), puerto 8443: `https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/admin/realms/vectra`. El token se pide al mismo host: `VECTRA_TOKEN_URL` = `https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/realms/vectra/protocol/openid-connect/token`.
- **Comparación de `realm-drift`** (decisión R2): proyección sobre Git.
  - Se comparan solo los campos que fija `realm.<env>.yaml`. Lo que Keycloak agrega por defecto no cuenta.
  - Las listas de entidades se emparejan por su clave: `clientId` (clientes), `name` (client scopes, roles, componentes), `alias` (flujos, acciones requeridas, configuración de autenticadores) y `username` (usuarios). Una entidad de Git que falta en Keycloak y una de Keycloak que no está en Git cuentan cada una como una diferencia. Los usuarios se leen uno a uno por su `username` de Git; no se listan, así que los importados de LDAP no se leen ni cuentan.
  - Un campo cuyo valor en Git contiene un marcador `$(env:…)` se excluye de la comparación.
  - La normalización quita secretos, IDs internos y timestamps, y es idempotente.
  - `vectra_realm_drift` es el número de diferencias.
- **`signing-key-age`** (decisión R4): empuja `vectra_signing_key_created_timestamp_seconds`, con etiquetas `kid` y `algorithm`. Su valor es el `notBefore` del certificado de la llave `ACTIVE` de uso `SIG` con mayor prioridad del algoritmo de firma por defecto del realm, leída en `GET /admin/realms/vectra/keys`. Esa respuesta no trae la fecha de creación (`KeyResource.java` de 26.8.1). Si la llave no tiene certificado, el job falla. `SigningKeyAgeHigh` calcula `time() - vectra_signing_key_created_timestamp_seconds > 80 d`.
- **Push** a `http://pushgateway.vectra-observability.svc:9091` (F112), con `PUT /metrics/job/realm-drift` y `PUT /metrics/job/signing-key-age`.
- **Horarios** (UTC): `realm-drift` `0 3 * * *`; `signing-key-age` `0 * * * *`. `concurrencyPolicy: Forbid`.
- **Imagen** (decisión R3): `registro.banco.internal/vectra/identity-jobs` (`kind-registry:5000/vectra/identity-jobs` en kind), sobre `docker.io/library/python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159` (la misma base que los jobs de U1), con los scripts de los dos jobs y `vectra_common`. El digest va en los values de cada entorno y la plantilla lo exige. Construida, escaneada y firmada por `supply-chain.yml` de U1.
- **Realm de Git** (decisión R3): el render de `identity-edge/jobs/` genera un ConfigMap con `realm.<env>.yaml` del entorno, versionado en `rendered/` como el de Keycloak. Así el realm de comparación llega en el mismo sync que lo aplica.
- Cuentas de servicio `realm-drift` y `signing-key-age` en `vectra-identity` (`platform/network/flows.yaml`), prioridad `vectra-low`, recursos de INF-U2-06.

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
