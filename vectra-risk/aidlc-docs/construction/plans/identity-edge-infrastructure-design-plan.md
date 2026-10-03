# Plan de Infrastructure Design — U2 `identity-edge`

**Alcance:** asignar los componentes lógicos de U2 (`nfr-design/logical-components.md`) a la
infraestructura que provee U1 (`construction/shared-infrastructure.md`), y formalizar en
`component-dependency.md` los componentes y flujos nuevos (Redis, servicio de rate limit,
controlador de Envoy Gateway, jobs del realm).

**Heredado de U1** (no se pregunta): entornos kind, staging y prod; pool `general`;
balanceador L4 del banco o MetalLB (`cloud-provider-kind` en kind) con un único Service
`LoadBalancer`; cert-manager; ESO; registro interno de imágenes con firma; Linkerd;
PriorityClasses; observabilidad.

**Categorías obligatorias:**

| Categoría | Aplica | Preguntas |
|---|---|---|
| Deployment Environment | Heredado de U1 | Q1 (hostnames) |
| Compute Infrastructure | Sí | Q4 |
| Storage Infrastructure | Sí | Q3 (Redis); `keycloak-db` ya está dimensionado en U1 (INF-U1-02) |
| Messaging Infrastructure | **N/A**: U2 no usa colas ni eventos asíncronos; Redis guarda contadores, no mensajes | — |
| Networking Infrastructure | Sí | Q1, Q2, Q5 |
| Monitoring Infrastructure | Heredado de U1 (P-U2-09 define las alertas) | — |
| Shared Infrastructure | Sí | Q2, Q6 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Hostnames (Networking / Deployment)
La CSP de la SPA (`connect-src 'self'`, `frame-src 'self'`) y el embebido de Grafana asumen
que todo se sirve desde el **mismo origen**.

A) **Un solo hostname público** por entorno (p. ej. `vectra.banco.internal` en prod, `vectra.staging.banco.internal` en staging y `vectra.localtest.me` en kind) para la SPA, `/api/**`, `/auth/**`, `/grafana/**` y `/federate`. La consola de administración de Keycloak usa un hostname **interno** (`hostname-admin`) que solo resuelve dentro del clúster y no está en el gateway (recomendado)

B) Subdominios separados (`auth.`, `grafana.`, `api.`), ajustando la CSP y el embebido

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Dónde corren el controlador y el data plane de Envoy Gateway (Networking / Shared)

A) **Controlador** en su namespace estándar `envoy-gateway-system`, con un binding nuevo (K14) para leer recursos de Gateway API y gestionar el data plane. **Data plane** (Envoy) en `vectra-edge`, si la versión pinneada permite desplegar los proxies en el namespace del `Gateway`. Si no lo permite, el data plane queda en `envoy-gateway-system` y las NetworkPolicies y flujos se generan para ese namespace (se verifica en el plan de tareas, como P-U2-01) (recomendado)

B) Controlador y data plane en `vectra-edge`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Implementación de Redis (Storage / Licencia)
Redis cambió de licencia (RSAL/SSPL en 7.4; AGPL como opción desde 8.0). Valkey es el fork
con licencia BSD y es compatible con el protocolo que usa el servicio de rate limit.

A) **Valkey 8** con la imagen oficial, desplegado con un chart propio y mínimo: StatefulSet de 2 nodos (primaria + réplica) y 3 Sentinel, sin persistencia, ACL desde ESO, repartido por zona, prioridad `vectra-high`. Sin operador (recomendado: licencia sin restricciones para el banco y sin depender de imágenes de terceros que cambiaron de distribución)

B) Redis 7.2 (última versión BSD) con un chart de terceros

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Recursos iniciales (Compute)
Valores iniciales, que se ajustan con la prueba de carga de NFR-U2-10.

A)

| Componente | Requests | Limits | Notas |
|---|---|---|---|
| Keycloak | 500m CPU / 1 GiB | 2 CPU / 2 GiB | Heap de la JVM al 70 % del límite |
| Envoy (data plane) | 250m / 256 MiB | 1 CPU / 512 MiB | — |
| Controlador de Envoy Gateway | 100m / 128 MiB | 500m / 256 MiB | — |
| Servicio de rate limit | 100m / 64 MiB | 500m / 128 MiB | — |
| Valkey (cada nodo) | 100m / 128 MiB | 500m / 256 MiB | `maxmemory 128mb`, política `volatile-ttl` |
| Sentinel (cada uno) | 50m / 32 MiB | 100m / 64 MiB | — |

(Recomendado)

B) Sin límites de CPU, solo requests

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Federación LDAP en producción (Networking, F73)

A) **LDAPS (636)** contra el LDAP del banco, verificando su certificado con la CA del banco (truststore desde ESO). Cuenta de *bind* de solo lectura desde ESO. Modo de edición `READ_ONLY`, importación de usuarios habilitada (necesaria para las sesiones), sincronización de cambios cada 15 min y mapper de grupos → roles según `group-role-map` (BR-U2-15). Si el LDAP no responde, los usuarios ya importados no pueden autenticarse (no hay caché de contraseñas) y se alerta SEV2 `LdapUnavailable` (recomendado)

B) LDAP sin TLS (389) dentro de la red del banco

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Empaquetado de Keycloak con el tema (Shared / Supply chain)

A) **Imagen propia** construida en CI: imagen oficial de Keycloak + tema `vectra` + `kc.sh build` (necesario para `start --optimized`). Se escanea con Trivy, se firma con Cosign y se publica en el registro de CI; el banco la replica a su registro interno (U1). El tema queda versionado con la imagen (recomendado)

B) Imagen oficial sin cambios y el tema montado desde un ConfigMap en un initContainer

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar NFR Requirements y NFR Design de U2 y la infraestructura compartida de U1
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/identity-edge/infrastructure-design/infrastructure-design.md`
- [x] 4. Generar `construction/identity-edge/infrastructure-design/deployment-architecture.md` (diagrama validado)
- [x] 5. Actualizar `inception/application-design/component-dependency.md` (namespaces, flujos, bindings) y `construction/shared-infrastructure.md` si cambia lo que consumen otras unidades; registrar en `audit.md`
- [x] 6. Verificar el cumplimiento de las extensiones
