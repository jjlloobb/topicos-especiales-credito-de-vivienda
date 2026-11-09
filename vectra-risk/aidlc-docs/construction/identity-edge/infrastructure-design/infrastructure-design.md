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
- **Enmienda del 2026-11-04 (decisiones W2, W4, W5 y W6 del usuario al preparar U02-T10)**, comprobada contra Envoy Gateway v1.9.3:
  - **Service** (W2): `LoadBalancer` con `externalTrafficPolicy: Local` y la etiqueta `app.kubernetes.io/name: api-gateway`, la que exige `restrict-loadbalancer` de U1. Envoy toma la IP de la dirección remota y no confía en ningún salto de `X-Forwarded-For`: el balanceador del banco es L4 y no agrega esa cabecera, así que su último valor lo escribiría el cliente.
  - **Imagen del data plane** (W4): `registro.banco.internal/vectra/envoy` (`kind-registry:5000/vectra/envoy` en kind), espejo de `docker.io/envoyproxy/envoy:distroless-v1.39.5`, la imagen por defecto de v1.9.3. El espejo conserva el digest `sha256:9d84a586119a27b50437dbb01eccd4722832741539b1ed53c8e9d6da6067a6e0`, que va en los values de cada entorno; sin digest, el render falla. El controlador, en `envoy-gateway-system`, no está sujeto a `restrict-registries` y queda con su imagen de upstream. El sidecar `shutdown-manager` de cada pod de Envoy sí corre en `vectra-edge`, y su imagen sale de la config del controlador (`provider.kubernetes.shutdownManager.image`). Es `registro.banco.internal/vectra/envoy-gateway` (`kind-registry:5000/vectra/envoy-gateway` en kind), espejo de `docker.io/envoyproxy/gateway:v1.9.3`, con el digest de upstream `sha256:192fc9bdadb6d2462e8cf7bd702ce3dd9648f3310c6038787448a1f509b7cd9f` (enmienda del 2026-11-04, decisión X3 del usuario en la ronda 1 de U02-T10).
  - **Etiquetas del Deployment del data plane**: `vectra.io/criticality: high` va en `Gateway.spec.infrastructure.labels`, que es de donde v1.9.3 toma las `metadata.labels` del Deployment que valida `require-criticality-label`; `pod.labels` del `EnvoyProxy` solo llega al pod.
  - **Enmienda del 2026-11-04 (decisiones Y2–Y4 del usuario en la ronda 1 de U02-T10):**
    - Y2: con `envoyHpa`, v1.9.3 deja sin fijar `replicas` del Deployment. La regla de réplicas de `require-spread-and-pdb` de U1 exime los Deployments con la etiqueta `gateway.envoyproxy.io/owning-gateway-name`, como ya lo hace su regla de PDB. El mínimo de 2 lo da `minReplicas: 2` del `envoyHpa`, que vigila la regla `envoy-scaling` de U2 (`require-hpa-bounds` no mira `minReplicas` de un HPA; corrección del 2026-11-04 tras la ronda 2 de U02-T10). Por la decisión Z2 del usuario, `require-spread-and-pdb` se parte en dos reglas: una de réplicas, que exime `owning-gateway-name` solo en `vectra-edge`, y otra de reparto por zona para todos, sin exención. `require-spread-gateway` no existe.
    - Y3: `platform/operators/envoy-gateway-kind.yaml` lleva la imagen de kind del `shutdown-manager`, con su `kind_values` en `components.yaml`.
    - Y4: la `ClientTrafficPolicy` fija TLS 1.2 como mínimo y 1.3 como máximo (NFR-U2-22). K14 incluye el RBAC del ServiceAccount `certgen` del chart.
  - **Identidad del data plane** (enmienda del 2026-11-04, decisión Z1 del usuario en la ronda 2 de U02-T10): el pod conserva `app.kubernetes.io/name: envoy`, que fija Envoy Gateway. En v1.9.3 el selector del Deployment usa esa etiqueta (`stableSelector`, `EnvoyAppLabel`), y sobrescribirla con `pod.labels` deja un selector que no selecciona su template, que el apiserver rechaza. La identidad `api-gateway` de `flows.yaml` selecciona el data plane por `gateway.envoyproxy.io/owning-gateway-name: api-gateway` (Paso 10). Linkerd lo identifica por la ServiceAccount `api-gateway`, que no cambia.
  - **Escalado** (W5): `envoyHpa` de 2 a 6 réplicas con un objetivo de CPU del 70 %, y `envoyPDB` con `minAvailable: 1`, repartido por zona (los mismos valores que Keycloak).
  - **Telemetría** (W6): el access log de P-U2-07, en JSON a stdout con exactamente sus campos, y tracing OpenTelemetry hacia `otel-collector.vectra-observability.svc:4317` (F61) con muestreo del 100 %, el valor por defecto de `VECTRA_TRACE_RATIO` (P-U0-11). Sin un span, `%TRACE_ID%` sale vacío en los `Problem`.

### INF-U2-10 — Manifiestos de `route-gen` (enmienda del 2026-11-03, decisiones V4, V8 y V9 del usuario al preparar U02-T09)
- **`Gateway`** (V9): `api-gateway` en `vectra-edge`, con el listener `https` (443). Es el mismo nombre que la identidad de `flows.yaml`. Lo crea el Paso 8; las HTTPRoute de `route-gen` lo referencian en `parentRefs` con `sectionName: https`.
- Las HTTPRoute y las políticas van en `vectra-edge`. En cada namespace de destino (`vectra-app`, `vectra-identity`, `vectra-observability`) hay un `ReferenceGrant` que admite solo las HTTPRoute de `vectra-edge` hacia los Services de ese namespace que usan, por nombre. El de `vectra-identity` admite además la `SecurityPolicy` (`gateway.envoyproxy.io`) de `vectra-edge`, solo hacia el Service `keycloak`, porque Envoy Gateway v1.9.3 exige el grant para el `backendRefs` de la JWKS (`internal/gatewayapi/validate.go`). Enmienda del 2026-11-04, decisión D-1 del usuario tras la ronda 1 de U02-T09.
- **Límites de tasa** (enmienda del 2026-11-04, decisión D-3 del usuario tras la ronda 1 de U02-T09): todos van en una `BackendTrafficPolicy` del `Gateway` (`edge-rate-limits`) con selectores de camino, cabecera e IP, que cada ruta hereda con `mergeType: StrategicMerge`. En v1.9.3, un contador `shared` solo se comparte dentro de su política, y las reglas de cada ruta se separan por método por los reintentos. Así el límite global de 200/s queda en un solo contador. Los dos contadores por IP de `/auth/**` van en la única política de ruta de `/auth/**`, con reglas `shared` y su propio filtro de rate limit (decisiones W3 y X1 del usuario, U02-T10, P-U2-01). Las rutas `directResponse` del cierre quedan fuera de todo límite, y su política no declara 429 (BR-U2-10; decisión D-6 del usuario tras la ronda 2 de U02-T09).
- **Destinos** (Service y puerto):
  - `console-spa` 8080 (`vectra-edge`), `console-bff` 8080, `case-service` 8080 y `governance-service` 8080 (`vectra-app`): el nombre y el puerto de `flows.yaml` (F02, F03, F04, F08);
  - `keycloak` 8443 (`vectra-identity`), con la `BackendTLSPolicy` de U02-T07 (F05);
  - `kube-prometheus-stack-grafana` 80 y `kube-prometheus-stack-prometheus` 9090 (`vectra-observability`), los Services del chart de U1, que llegan a los puertos 3000 y 9090 de F06 y F09.
- **Tamaño por ruta** (V4): `BackendTrafficPolicy.requestBuffer.limit` de cada ruta, que responde 413. La `ClientTrafficPolicy` aplica al `Gateway` o al listener, no a una ruta, y queda para `X-Forwarded-For` o PROXY protocol y para las cabeceras de entrada y salida.
- **JWT**: el `issuer` es `https://<hostname público>/auth/realms/vectra`, con el hostname de INF-U2-01 de cada entorno. La JWKS se pide por la URL interna `https://keycloak.vectra-identity.svc:8443/auth/realms/vectra/protocol/openid-connect/certs` (P-U2-03), con `cacheDuration` de 5 min.
- **Validación** (V8): `kubeconform` v0.8.0, con checksum, en `platform/tools.env` y `platform/install-tools.sh`. `platform/charts.sh` también descarga los charts OCI de `components.yaml`, entre ellos `gateway-helm` v1.9.3, que trae los CRDs de Envoy Gateway y de Gateway API v1.6.1. Un script de `identity-edge/tools/` los convierte a esquemas JSON en `.tools`, sin versionarlos.

### INF-U2-03 — Servicio de rate limit
- **Enmienda del 2026-11-04 (decisión W1 del usuario al preparar U02-T10).** En Envoy Gateway v1.9.3, el rate limit global de las `BackendTrafficPolicy` lo atiende el servicio que despliega el propio controlador: `envoy-ratelimit`, en `envoy-gateway-system`, gRPC en el 8081. Su configuración la arma el controlador por xDS a partir de las políticas de `route-gen` (`internal/infrastructure/kubernetes/ratelimit`), y Envoy no se puede apuntar a otro servicio. Las viñetas siguientes quedan **superadas**, salvo que Valkey es el backend. La conexión a Valkey (Sentinel y ACL), el HPA de 2 a 4, los recursos y los flujos F90–F93 se rediseñan al preparar el Paso 9.
- **Enmienda del 2026-11-04 (decisiones R1 y R2 del usuario al preparar U02-T11).** El orquestador comprobó contra v1.9.3 (`internal/infrastructure/kubernetes/ratelimit/resource.go` y `resource_provider.go`; `api/v1alpha1/envoygateway_types.go`) y contra `envoyproxy/ratelimit` `5ae0682e`, la imagen del chart (`src/settings/settings.go`, `src/redis/driver_impl.go`):
  - **Dónde y cómo se configura.** `envoy-ratelimit` corre en el namespace del controlador (`ControllerNamespace`, `envoy-gateway-system`). Se configura en `platform/operators/envoy-gateway.yaml`, con `config.envoyGateway.rateLimit` y `config.envoyGateway.provider.kubernetes.rateLimitDeployment`, `rateLimitHpa` y `rateLimitPDB`. `rateLimit.failClosed: false`, porque el cierre de `/auth/**` lo hace la `EnvoyPatchPolicy` de P-U2-01. El timeout es el de v1.9.3, 20 ms.
  - **Puertos (los fija v1.9.3, no son configurables).**
    - gRPC en el 8081 (`InfraGRPCPort`);
    - health y readiness en el 8080 (`ReadinessPort`);
    - métricas Prometheus en el 19001 (`PrometheusPort`);
    - xDS del controlador hacia `envoy-ratelimit` en el 18001.

    La convención de U0 que reserva el 8081 para health y métricas no se puede cumplir en este componente. El 8083 queda superado.
  - **Conexión a Valkey (R1).**
    - `rateLimit.backend.redis.url` = `<nombre del master>,<sentinel-a-0>:26379,<sentinel-b-0>:26379,<sentinel-b-1>:26379`, con los FQDN de `vectra-edge`. `ValidateRedisURL` acepta la lista separada por comas.
    - `rateLimitDeployment.container.env` agrega `REDIS_TYPE=SENTINEL`, y `REDIS_AUTH` y `REDIS_SENTINEL_AUTH` por `secretKeyRef`. `ExpectedContainerEnv` reemplaza o agrega por nombre.
    - El formato es `usuario:contraseña` (`splitAuth`) y el Secret lo materializa ESO en `envoy-gateway-system`.
    - `REDIS_SOCKET_TYPE=tcp` lo pone el controlador.
  - **Endurecimiento (R2).** Las políticas Kyverno de U1 no alcanzan `envoy-gateway-system`, así que `rateLimitDeployment` fija lo mismo que exigirían, y una regla de conftest sobre el render del chart exige cada campo:
    - réplicas 2;
    - imagen espejada con digest;
    - `securityContext`: no root, sin privilegios, raíz de solo lectura y `seccompProfile: RuntimeDefault`;
    - recursos de INF-U2-06;
    - `priorityClassName: vectra-high` y `vectra.io/criticality: high`;
    - reparto por zona;
    - `rateLimitHpa` de 2 a 4 con CPU al 70 % y `rateLimitPDB` `minAvailable: 1`.

    La imagen es `envoyproxy/ratelimit:5ae0682e`, la de `global.images.ratelimit` de v1.9.3, con `@sha256:b95206e32b1a5f824fb06062fbb85bbdfb7f5de54135e92afe8462f22c979681`. Se espeja en `registro.banco.internal/vectra/ratelimit`, y en kind en `kind-registry:5000/vectra/ratelimit` por `envoy-gateway-kind.yaml`.
  - **Telemetría.** Métricas Prometheus activas (el default) y tracing OpenTelemetry hacia `otel-collector.vectra-observability.svc:4317` con muestreo del 100 %, como el data plane (W6).
    - **Enmienda del 2026-11-04 (decisión R8 del usuario tras la ronda 1 de U02-T11).** `envoyproxy/ratelimit` `5ae0682e` exporta por OTLP HTTP salvo que se diga otra cosa: `TRACING_EXPORTER_PROTOCOL` vale `"http"` por defecto (`src/settings/settings.go:316`). El 4317 es OTLP gRPC. Por eso `rateLimitDeployment.container.env` agrega `TRACING_EXPORTER_PROTOCOL=grpc`, y el endpoint sigue en el 4317, como el resto de componentes.
  - **Descriptores.** No los genera `route-gen`: el controlador los arma por xDS desde las `BackendTrafficPolicy` (`edge-rate-limits` y `auth-rate-limits`). Se comprueban offline con el IR de `egctl x translate --to ir`.
- *(Superado por la enmienda anterior.)* `envoyproxy/ratelimit` en `vectra-edge`: HPA de 2 a 4 por CPU, repartido por zona, PDB. Sin HPA ni exención, `require-hpa-bounds` lo rechazaría (quinta revisión de coherencia entre unidades, 2026-10-31).
- *(Superado: el puerto lo fija v1.9.3, ver la enmienda de R1 y R2.)* **gRPC en el puerto 8083.** Se cambia el 8081 por defecto, que en Vectra está reservado para health y métricas (convención de U0). Métricas y health en 8081.
- *(Superado: los descriptores los arma el controlador.)* Configuración de descriptores generada por `route-gen` desde `routes.yaml` (P-U2-06).

## 3. Almacenamiento (Q3)

### INF-U2-04 — Valkey 8
- Imagen oficial de Valkey 8, espejada en un registro que admita `restrict-registries` (`registro.banco.internal/vectra`, y `kind-registry:5000` en kind), pinneada por digest y firmada (revisión de consistencia entre unidades, 2026-11-01); chart propio mínimo en `identity-edge/charts/valkey`.
- StatefulSet de **2 nodos** (primaria + réplica) en zonas distintas y **3 Sentinel** repartidos por zona.
- **Sin persistencia** (sin RDB ni AOF; `emptyDir`): los contadores son efímeros.
- ACL: usuario `ratelimit` con permisos mínimos (`+@read +@write +@connection -@dangerous`) y contraseña desde ESO. Usuario `default` deshabilitado. También usuarios de replicación y de Sentinel con los comandos mínimos de cada uno, desde ESO, y sin ellos F92 y F93 no funcionan. PDB: Valkey `minAvailable: 1` y Sentinel `minAvailable: 2` (seguimiento de la quinta revisión de coherencia, 2026-10-31).
- **Sentinel con dos zonas** (seguimiento de la quinta revisión de coherencia, 2026-10-31): 1 Sentinel en la zona A y 2 en la B. La primaria se prefiere en la zona A: si cae A, los 2 de B promueven la réplica; si cae B, la primaria sigue. Tras una conmutación, el runbook la devuelve a A. Mientras esté en B, una caída de B deja 1 de 3 Sentinel, sin promoción, y `/auth/**` responde 503 hasta que vuelva la zona. Es un riesgo aceptado para el MVP.
- `maxmemory 128mb`, política `volatile-ttl` (todas las claves de rate limit tienen TTL).
- Prioridad `vectra-high`; NetworkPolicy que solo admite al servicio de rate limit, a la réplica y a los Sentinel (F91–F93).
- **Enmienda del 2026-11-04 (decisiones R2 a R4 del usuario al preparar U02-T11).**
  - **Imágenes (R2).** `valkey/valkey:8.1.11-alpine` `@sha256:2602ace2be6569bc2bbb06f873776516ab9089821525be34f4305c67eb9db02a`, para Valkey y para Sentinel. El exportador es `oliver006/redis_exporter:v1.95.0-alpine` `@sha256:19bb5c732f5812d5b60b2e0af3c6d82c5b3e418cd020068d65f588a56df4a118`. Se espejan en `registro.banco.internal/vectra/valkey` y `.../redis-exporter`, y en kind en `kind-registry:5000/vectra/...`.
  - **Topología (R3).**
    - Valkey va en dos StatefulSets de 1 réplica, `valkey-a` y `valkey-b`, cada uno con `nodeAffinity` obligatoria a `topology.kubernetes.io/zone` (`zone-a` y `zone-b`; *superado* «solo en kind; las zonas de cada entorno van en los values» por la decisión R6, más abajo: son `zone-a` y `zone-b` en los tres entornos). `valkey-a` arranca como primaria y `valkey-b` como réplica de ella.
    - `replica-priority` favorece a A: 10 en `valkey-a` y 100 en `valkey-b`. Así, Sentinel promueve a A cuando vuelve y el runbook de INF-U2-04 solo tiene que forzar el failover.
    - Sentinel va en `sentinel-a` (1 réplica, zona A) y `sentinel-b` (2 réplicas, zona B), con quórum 2. Usa `resolve-hostnames yes` y `announce-hostnames yes` sobre Services headless.
    - Al reiniciar, un nodo pregunta a Sentinel por la primaria actual antes de declararse réplica. Sentinel reescribe su configuración, así que la copia a un `emptyDir` al arrancar.
    - PDB: `minAvailable: 1` sobre la etiqueta común de Valkey y `minAvailable: 2` sobre la de Sentinel. Las políticas de réplicas de U1 solo miran Deployments.
  - **ACL (R4).**
    - ESO arma los archivos de ACL con `target.template`, desde la clave de Vault `edge/valkey`. El `users.acl` de Valkey lleva:
      - `user default off`;
      - `ratelimit` con `~* +@read +@write +@connection -@dangerous`;
      - `replication` con `+psync +replconf +ping`;
      - `sentinel` con los comandos que pide Sentinel: `+multi +exec +slaveof +ping +subscribe +publish +info +role +config|rewrite +client|setname +client|kill +script|kill`;
      - `exporter`, de solo lectura de métricas: `+info +ping +client|list +config|get +slowlog|get +latency|latest +memory|stats`.
    - El `sentinel.conf` lleva `user default off` y un usuario `ratelimit` limitado a `+sentinel|get-master-addr-by-name +sentinel|sentinels +sentinel|replicas +subscribe +ping +auth +hello &*`, más `sentinel auth-user`/`auth-pass` con el usuario `sentinel`.
    - Los Secrets van en `vectra-edge`. El de `envoy-ratelimit` (`REDIS_AUTH` y `REDIS_SENTINEL_AUTH`, `ratelimit:<contraseña>`) es un segundo `ExternalSecret` en `envoy-gateway-system`, y K11 se amplía a ese namespace.
    - Valkey y Sentinel arrancan con `aclfile` montado de solo lectura; nunca se escribe una contraseña en un ConfigMap.
  - **ACL definitivas (decisión R5 del usuario, 2026-11-04, tras la detención de la ronda 1 de U02-T11; reemplazan las listas de R4).** El orquestador comprobó el informe del codificador contra Valkey 8.1.11 y contra radix v4.1.4, el cliente de `envoyproxy/ratelimit` `5ae0682e`:
    - en `sentinel.c:1938`, Sentinel tiene `sentinel-user` y `sentinel-pass` para hablar con sus pares, aparte de `auth-user`;
    - Sentinel usa el canal `__sentinel__:hello`, y `acl-pubsub-default` es `resetchannels`;
    - radix envía `SENTINEL MASTER`, `SLAVES` y `SENTINELS` (`sentinel.go:285-391`) y se suscribe a `switch-master`. En Valkey, `sentinel|master` y `sentinel|slaves` son subcomandos distintos de `primary` y `replicas`.

    Las listas quedan así:
    - **`users.acl` de Valkey:**
      - `user default off`;
      - `ratelimit`: `~* +@read +@write +@connection -@dangerous`, sin cambios;
      - `replication`: `+psync +replconf +ping`, sin cambios;
      - `sentinel`: `+auth +client|setname +client|kill +config|rewrite +exec +info +multi +ping +publish +script|kill +slaveof +subscribe &__sentinel__:hello`, sin `+role`;
      - `exporter`: `+info +ping +client|setname +config|get +slowlog|get +slowlog|len +latency|latest +latency|histogram +command|info +commandlog|len`, que es lo que usa redis_exporter v1.95.0 por defecto.
    - **ACL de cada `sentinel.conf`:**
      - `user default off`;
      - `ratelimit`: `+auth +hello +ping +subscribe +sentinel|master +sentinel|slaves +sentinel|sentinels &switch-master`;
      - `sentinel-peer`: `+auth +ping +publish +client|setname +sentinel|is-master-down-by-addr &__sentinel__:hello`, más `sentinel sentinel-user sentinel-peer` y `sentinel sentinel-pass`.
      - `sentinel auth-user sentinel` y `auth-pass` siguen igual, hacia el master y las réplicas.
    - **Nombres:** el master se llama `ratelimit` (deployment-architecture). Las propiedades de la clave de Vault `edge/valkey` son `ratelimit`, `replication`, `sentinel`, `sentinel-peer`, `exporter` y `sentinel-ratelimit`.
  - **Zonas, tiempos de Sentinel y consulta al arrancar (decisiones R6 y R7 del usuario tras la ronda 1 de U02-T11, 2026-11-04; hallazgos F-01 y F-04).**
    - **Zonas (R6).** Las zonas se llaman `zone-a` y `zone-b` en los tres entornos, no solo en kind. Es un requisito para la plataforma del banco: sus nodos llevan esos valores en `topology.kubernetes.io/zone` (INF-U1-01, enmendado igual). `valkey-a` y `sentinel-a` van a `zone-a`, y `valkey-b` y `sentinel-b` a `zone-b`, en kind, staging y prod.
    - **Tiempos de Sentinel (R7).** Para el master `ratelimit`:
      - `sentinel down-after-milliseconds ratelimit 5000`;
      - `sentinel failover-timeout ratelimit 60000`;
      - `sentinel parallel-syncs ratelimit 1`.

      Con quórum 2, la primaria se da por caída a los 5 s. Ese tiempo, más la promoción, es lo que dura el 503 de `/auth/**` en una conmutación.
    - **Consulta al arrancar.** Para preguntar por la primaria actual, los pods de Valkey y de Sentinel usan el usuario `ratelimit` de Sentinel, con la contraseña `sentinel-ratelimit` de `edge/valkey`. Es el único usuario de R5 que tiene `+sentinel|master`. Lo ratificó el orquestador tras la ronda 1 de U02-T11 (F-04).
  - **Flujos (para el Paso 10):**
    - F90 pasa a ser Envoy (`vectra-edge`) → `envoy-ratelimit` (`envoy-gateway-system`) en el 8081;
    - F91 sale de `envoy-ratelimit` en `envoy-gateway-system` hacia Valkey y Sentinel en `vectra-edge`;
    - el scrape de `envoy-ratelimit` va al 19001 y el del exportador al 9121.

    La NetworkPolicy de Valkey solo admite a F91–F93.
  - **Flujos y sondas (decisiones T1 a T4 del usuario al preparar U02-T12, 2026-11-05):**
    - **T1.** `envoy-ratelimit` no está en la malla. En los `Server` de Linkerd de Valkey (6379), Sentinel (26379) y `otel-collector` (4317) se autoriza con una `NetworkAuthentication` por `pod_cidr`, como F80; `unmeshed_source` de `platform/network/generate.py` deja de estar limitado al 5432. La NetworkPolicy limita el origen a los pods de `envoy-ratelimit` (`app.kubernetes.io/name: envoy-ratelimit`, `app.kubernetes.io/component: ratelimit`, `app.kubernetes.io/managed-by: envoy-gateway`; ServiceAccount `envoy-ratelimit`; `rateLimitLabels()` e `InfraName` de v1.9.3). En staging y prod, `pod_cidr` vale `0.0.0.0/32` hasta que el banco entregue el rango, así que F91 y su tracing no se autorizan antes.
    - **T2.** F92 suma Valkey → Sentinel en el 26379, para la consulta al arrancar.
    - **T3.** F60 suma Envoy (data plane) en el 19001, `envoy-ratelimit` en el 19001 y el exportador de Valkey en el 9121.
    - **T4.** Detrás del proxy de Linkerd, una sonda `tcpSocket` la contesta el proxy y no Valkey. Las sondas de Valkey y Sentinel pasan a `exec` con `valkey-cli ping` (contra el 6379 y el 26379, con `REDISCLI_AUTH`), si se confirma ese comportamiento contra el código de Linkerd de la versión pinneada. Si no se confirma, se detiene y se reporta.
      - **Credenciales de las sondas (decisión T5 del usuario, 2026-11-05, tras la detención de la ronda 1 de U02-T12).** Se confirmó T4: en edge-26.10.2 (proxy v2.372.0), `linkerd2-proxy-init` redirige al proxy todo el TCP entrante, y el proxy acepta la conexión antes de abrir la de la aplicación (`linkerd/app/core/src/serve.rs` y `linkerd/app/inbound/src/server.rs`). `REDISCLI_AUTH` es la contraseña del usuario `ratelimit` de Sentinel, y sin `--user` `valkey-cli` se autentica como `default`, que está deshabilitado. Por eso:
        - **Valkey (6379):** la sonda usa el usuario `exporter`, el de menos privilegio con `+ping`. El contenedor `valkey` recibe `VALKEY_PROBE_PASSWORD` por `secretKeyRef` a la clave `exporter-password` del Secret `valkey-acl`, que ya existe. La sonda es `sh -c '[ "$(REDISCLI_AUTH="$VALKEY_PROBE_PASSWORD" valkey-cli --user exporter -p 6379 ping)" = PONG ]'`. `REDISCLI_AUTH` del contenedor no cambia, porque lo usa la consulta al arrancar;
        - **Sentinel (26379):** la sonda usa el usuario `ratelimit` de Sentinel, con el `REDISCLI_AUTH` que ya está en el pod: `sh -c '[ "$(valkey-cli --user ratelimit -p 26379 ping)" = PONG ]'`. Ese usuario tiene `+ping` (R5);
        - en las dos se compara la salida con `PONG`, no solo el código de salida. Ninguna contraseña va en la línea de comandos.
    - La identidad `api-gateway` selecciona el data plane por `gateway.envoyproxy.io/owning-gateway-name: api-gateway` (Z1, INF-U2-02).

### INF-U2-05a — Credencial de administración (seguimiento de la quinta revisión de coherencia, 2026-10-31)
- Dos clientes de administración del realm `vectra`, por F94, con `private_key_jwt` desde ESO (enmienda del 2026-11-02, decisión del usuario tras la ronda 3 de U02-T03):
  - `keycloak-config-cli`: su cuenta de servicio tiene el rol `realm-admin` de `realm-management`; es el único que escribe;
  - `keycloak-reader`: su cuenta de servicio tiene solo `view-realm`, `view-clients` y `view-users` de `realm-management`, y el `clientScopeMappings` de `realm-management` para `keycloak-reader` es ese mismo conjunto; lo usan `realm-drift` y `signing-key-age`, que solo leen. En Keycloak 26.8.1, `view-realm` no basta para leer clientes, client scopes ni usuarios (`ClientPermissions.canView` exige `view-clients`; `UserPermissions.canView`, `view-users`), y `partial-export` exige `manage-realm` (`RealmAdminResource.java`) (enmienda del 2026-11-03, decisión R1 del usuario al preparar U02-T08).
- `realm-lint` rechaza cualquier rol de `realm-management` en otra cuenta de servicio, y en la de `keycloak-reader` cualquier rol fuera de `view-realm`, `view-clients` y `view-users` (enmienda del 2026-11-03, decisión R1 del usuario al preparar U02-T08).

- `keycloak-config-cli` corre como hook **`PostSync`** de Argo CD, con `hook-delete-policy: BeforeHookCreation`, cuando la wave 3 ya está sana (enmienda del 2026-11-03, decisión Q3 del usuario al preparar U02-T07).
- **Bloqueo** (enmienda del 2026-11-03, decisión Q1 del usuario al preparar U02-T07): ninguna versión publicada de `keycloak-config-cli` admite `private_key_jwt` (la última, v6.5.1 de 2026-05-22, solo admite contraseña o `client_secret`). El soporte entró en su rama principal el 2026-09-13 y lee un JWT **ya firmado** desde un archivo (`clientAssertionFile`), así que además hace falta un firmante que este diseño no tiene. El Job se separa del Paso 5 en una tarea propia, que espera un release con aserciones de cliente y el diseño del firmante.
- **Excepción solo en kind** (decisión del usuario, 2026-11-08, opción a de B-1 en `identity-edge/docs/paso-16-kind.md`): mientras dure el bloqueo, en kind corre `keycloak-config-cli` v6.5.1 como hook `PostSync` de `keycloak`, autenticado con un **administrador de arranque** del realm `master` (`KC_BOOTSTRAP_ADMIN_USERNAME` y `KC_BOOTSTRAP_ADMIN_PASSWORD`, desde la bóveda en `identity/keycloak-admin` por `ExternalSecret`) y no con `private_key_jwt`. Importa `realm.kind.yaml` con la sustitución de `$(env:…)` activa. El Job y el administrador de arranque solo se renderizan con los values de kind; staging y prod siguen bloqueados como dice el punto anterior. Es una desviación de seguridad acotada a kind: el administrador de arranque tiene todos los permisos del servidor.

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
| `shutdown-manager` (sidecar de cada pod de Envoy) | 10m / 32 MiB | 50m / 64 MiB | Por `envoyDeployment.patch`; v1.9.3 no le pone limits (enmienda del 2026-11-04, decisión Y1 del usuario en la ronda 1 de U02-T10) |

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
  - Un campo escalar cuyo valor en Git contiene un marcador `$(env:…)` se excluye de la comparación. En una lista de valores, solo se excluyen los elementos de Git con marcador: los demás se comparan, y cada elemento de Keycloak que no está en Git cuenta como diferencia, salvo uno por cada elemento de Git con marcador (enmienda del 2026-11-03, decisión S2 del usuario tras la ronda 1 de U02-T08).
  - Un valor con marcador debe conservar el texto literal que lo rodea en Git: el valor de Keycloak empieza con el texto anterior al primer marcador y termina con el posterior al último (por ejemplo, `ldaps://` y `:636` en `ldaps://$(env:LDAP_HOST):636`). Se compara por prefijo y sufijo exactos, sin expresiones regulares (enmienda del 2026-11-03, decisión S3 del usuario tras la ronda 2 de U02-T08).
  - En los usuarios no se comparan `requiredActions` ni `credentials`: los cambia el propio login (por ejemplo, el primer login de `break-glass` quita `CONFIGURE_TOTP` y agrega la credencial `otp`). Se siguen comparando la existencia del usuario, `enabled`, sus atributos y sus roles (enmienda del 2026-11-03, decisión S1 del usuario tras la ronda 1 de U02-T08).
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
