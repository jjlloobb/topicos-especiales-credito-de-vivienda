# U02-T11 — Servicio de rate limit y Valkey

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-611 (exceso de solicitudes → 429)
**Depende de:** U02-T10 (controlador, `Gateway`, `EnvoyProxy`, `auth-rate-limits` y `egctl`), en `main`

Paso 9 del plan de U2. El plan pedía rediseñar este paso al prepararlo (decisión W1 de U02-T10). El 2026-11-04 el orquestador comprobó el diseño contra el código de dos versiones:
- Envoy Gateway v1.9.3, la versión pinneada en `vectra-risk-gitops/components.yaml`;
- `envoyproxy/ratelimit` `5ae0682e`, la imagen que ese chart trae en `global.images.ratelimit`.

El usuario decidió R1–R4: R1, la conexión por Sentinel; R2, el endurecimiento y las imágenes; R3, la topología; R4, las ACL. Las decisiones están en INF-U2-03, INF-U2-04, NFR-U2-27 y component-dependency §0 y §2.8.

> **Enmienda del 2026-11-04 (orquestador, decisión R5 del usuario tras la detención de la ronda 1):** las listas de comandos de R4 no funcionaban en Valkey 8.1.11 ni con radix v4.1.4. Rigen las de R5, en INF-U2-04 («ACL definitivas»). Donde esta tarea dice «R4» para listas de ACL, léase R5. Cambia lo siguiente:
> - `+role` sale del usuario `sentinel` de Valkey, que gana `&__sentinel__:hello`;
> - el usuario `ratelimit` de Sentinel usa `+sentinel|master +sentinel|slaves +sentinel|sentinels` y `&switch-master`;
> - se agrega el usuario de pares `sentinel-peer`, con `sentinel sentinel-user` y `sentinel sentinel-pass`;
> - el exportador usa los comandos de sus defaults;
> - el master se llama `ratelimit`;
> - las propiedades de `edge/valkey` son `ratelimit`, `replication`, `sentinel`, `sentinel-peer`, `exporter` y `sentinel-ratelimit`.

> **Enmienda del 2026-11-04 (orquestador, decisiones R6–R8 del usuario tras la ronda 1; `revisiones/U02-T11/ronda-1.md`):**
> - **R6 (F-01):** las zonas son `zone-a` y `zone-b` en kind, staging y prod (INF-U2-04 e INF-U1-01). `test_valkey_chart.py` comprueba la zona de cada StatefulSet en los tres entornos, leída del diseño, y conftest la exige. Debe fallar con otra zona en `values/prod.yaml` o `values/staging.yaml`.
> - **R7 (F-01):** los tiempos de Sentinel son `down-after-milliseconds 5000`, `failover-timeout 60000` y `parallel-syncs 1` (INF-U2-04). El oráculo los lee del diseño y conftest los exige, cada uno con su caso que falla. Un tiempo distinto en los values debe hacer fallar CA-3.
> - **R8 (candidata del revisor):** `rateLimitDeployment.container.env` agrega `TRACING_EXPORTER_PROTOCOL=grpc` (INF-U2-03). `test_envoy_gateway_values.py` lo lee del diseño, `test_ratelimit_deployment.py` lo comprueba en la env final del modelo y `policy-ratelimit` lo exige con su caso que falla.
> - **F-04, ratificado:** los pods de Valkey y Sentinel consultan a Sentinel con el usuario `ratelimit` de Sentinel (INF-U2-04, «Consulta al arrancar»). No hay que cambiarlo.
> - **F-03, ratificado:** el cambio en `platform/tests/test_integration.py` entra en el alcance. La quita queda como candidata para el Paso 12.
> - **F-05:** la candidata de `readOnlyRootFilesystem` y `RUNTIME_ROOT` se retira de la bitácora, porque no aplica con `GRPC_XDS_SOTW`.
> - Ninguna prueba debe fijar estos valores con un literal propio. Si cambia el diseño y el oráculo no, falla.

## Alcance

**Dentro:** todo el Paso 9 del plan. Texto del plan, sin recortes:

- [ ] **Paso 9 — Servicio de rate limit y Valkey**
  - `envoyproxy/ratelimit` (HPA de 2 a 4, quinta revisión de coherencia entre unidades, 2026-10-31; gRPC en 8083, métricas en 8081) con la configuración de descriptores generada por `route-gen`.
  - Chart propio de Valkey 8: 2 nodos en zonas distintas, primaria preferida en la zona A, 3 Sentinel, sin persistencia, PDB, exportador como sidecar, ACL `ratelimit`, de replicación y de Sentinel desde ESO (seguimiento de la quinta revisión de coherencia, 2026-10-31), usuario `default` deshabilitado, `maxmemory 128mb`, `volatile-ttl`, prioridad `vectra-high`.
  - **Nota del 2026-11-04 (decisión W1 del usuario al preparar U02-T10):** el servicio de rate limit es el `envoy-ratelimit` que despliega Envoy Gateway, no un `envoyproxy/ratelimit` propio en el 8083 con configuración de `route-gen` (INF-U2-03). Este paso se rediseña al prepararlo.
  - **Rediseño del 2026-11-04 (decisiones R1–R4 del usuario al preparar U02-T11; INF-U2-03, INF-U2-04, NFR-U2-27, component-dependency §0 y §2.8):**
    - `envoy-ratelimit` de Envoy Gateway v1.9.3, en `envoy-gateway-system`, configurado en `platform/operators/envoy-gateway.yaml` (`rateLimit`, `rateLimitDeployment`, `rateLimitHpa` de 2 a 4 al 70 %, `rateLimitPDB` `minAvailable: 1`). Los puertos los fija v1.9.3: gRPC 8081, health 8080 y métricas 19001;
    - conexión por Sentinel con `REDIS_TYPE=SENTINEL`, y `REDIS_AUTH` y `REDIS_SENTINEL_AUTH` desde un `ExternalSecret` en `envoy-gateway-system`; K11 se amplía a ese namespace (R1);
    - el endurecimiento de `rateLimitDeployment` lo exige conftest sobre el render, porque Kyverno no alcanza `envoy-gateway-system`. Imagen `ratelimit:5ae0682e` espejada con digest (R2);
    - chart `identity-edge/charts/valkey`: `valkey-a` y `valkey-b` por zona con `replica-priority`, `sentinel-a` (1) y `sentinel-b` (2) (R3);
    - ACL armadas por la plantilla de ESO, con el usuario `exporter` y la ACL propia de Sentinel (R4);
    - Valkey 8.1.11-alpine y redis_exporter v1.95.0-alpine con digest (R2).
  - Diseño: NFR-U2-20, 27, 30; P-U2-04, 06; INF-U2-03, 04. Historia: US-611 (exceso de solicitudes → 429).
  - **Aceptación** (enmendada el 2026-11-04 con R1–R4; la original pedía los puertos 8083/8081 y descriptores generados por `route-gen`):
    - `helm template` de `identity-edge/charts/valkey` y del chart `gateway-helm` v1.9.3 con los values, más `conftest test` con las políticas de `identity-edge/ratelimit/policy/` e `identity-edge/charts/valkey/policy/`: puertos 8081, 8080 y 19001 de `envoy-ratelimit`, Sentinel por env, sin RDB ni AOF, ACL presente, `default` deshabilitado y reparto por zona;
    - `uv run pytest identity-edge/tests/unit/test_ratelimit_config.py`: los descriptores del IR de `egctl x translate --to ir` coinciden con `routes.yaml`.

Precisiones del diseño enmendado que la tarea aplica. La fuente de cada una va entre paréntesis.

- **Ubicación:**
  - Lo de `envoy-ratelimit` va en `platform/operators/envoy-gateway.yaml`, y el registro de kind en `platform/operators/envoy-gateway-kind.yaml`.
  - El `ExternalSecret` de `envoy-gateway-system` y las reglas de conftest de `envoy-ratelimit` van en `identity-edge/ratelimit/`.
  - El chart de Valkey va en `identity-edge/charts/valkey/`, con sus values por entorno y su `policy/`.
  - Lo renderizado de Valkey se versiona en `identity-edge/charts/valkey/rendered/<env>/` y lo vigila un `check-valkey-rendered`, como `check-keycloak-rendered`.
- **`envoy-ratelimit`** (INF-U2-03, R1, R2, INF-U2-06):
  - `config.envoyGateway.rateLimit`:
    - `backend.type: Redis`;
    - `backend.redis.url` = `<master>,<sentinel-a-0>:26379,<sentinel-b-0>:26379,<sentinel-b-1>:26379`, con los FQDN de los Services headless de `vectra-edge`;
    - `failClosed: false`;
    - tracing OpenTelemetry hacia `otel-collector.vectra-observability.svc:4317`, al 100 %;
    - métricas Prometheus sin deshabilitar.

    Comprueba los campos en `api/v1alpha1/envoygateway_types.go` de v1.9.3.
  - `provider.kubernetes.rateLimitDeployment`:
    - `replicas: 2`;
    - imagen `registro.banco.internal/vectra/ratelimit@sha256:b95206e32b1a5f824fb06062fbb85bbdfb7f5de54135e92afe8462f22c979681`, y `kind-registry:5000/vectra/ratelimit@…` (el mismo digest) en `envoy-gateway-kind.yaml`;
    - recursos 100m / 64 MiB y 500m / 128 MiB;
    - `priorityClassName: vectra-high` y etiqueta `vectra.io/criticality: high` en el pod;
    - `securityContext`: no root, sin privilegios, raíz de solo lectura y `seccompProfile: RuntimeDefault`;
    - `topologySpreadConstraints` por `topology.kubernetes.io/zone`, con un selector que seleccione de verdad los pods. Lección de F-12 de U02-T10: el modelo lo comprueba contra `rateLimitLabels()` y `LabelSelector()` de v1.9.3;
    - `container.env`: `REDIS_TYPE=SENTINEL`, y `REDIS_AUTH` y `REDIS_SENTINEL_AUTH` por `secretKeyRef` al Secret del `ExternalSecret`.
  - `rateLimitHpa`: de 2 a 4, CPU al 70 %. `rateLimitPDB`: `minAvailable: 1`.
  - Los puertos no se configuran: 8081, 8080, 19001 y 18001 son constantes de `resource.go`. La prueba los lee del modelo, no de un literal propio.
  - Valores que ya son el default del chart no se repiten salvo que el diseño los fije.
- **Modelo del Deployment** (R2; lección de U02-T10): el controlador crea el Deployment de `envoy-ratelimit` en tiempo de ejecución, así que no aparece en el render. `identity-edge/tests/unit/test_ratelimit_deployment.py` arma el Deployment, el HPA y el PDB como lo harían `resource_provider.go` y `resource.go` de v1.9.3, con su env de base, `ExpectedContainerEnv` y los volúmenes. Sobre eso:
  - comprueba que la env final tiene `REDIS_TYPE=SENTINEL`, `REDIS_SOCKET_TYPE=tcp`, la URL y las dos credenciales por `secretKeyRef`;
  - comprueba que los selectores del Deployment, del PDB y del reparto seleccionan el template;
  - lo pasa por `kyverno apply` con las `STATIC_POLICIES` de U1, en una copia cuyo `match` incluye `envoy-gateway-system`. Debe pasar.
- **`ExternalSecret` de `envoy-gateway-system`** (R1, R4):
  - toma `ratelimit` y `sentinel-ratelimit` de la clave de Vault `edge/valkey`, con el `ClusterSecretStore` `vectra-store`;
  - con `target.template` arma `REDIS_AUTH=ratelimit:<contraseña>` y `REDIS_SENTINEL_AUTH=ratelimit:<contraseña de Sentinel>`.
- **K11** (R1): `platform/secrets/eso-rbac-k11*.yaml` agrega el Role y el RoleBinding de `envoy-gateway-system`, igual que los demás namespaces. Si alguna prueba de U1 fija la lista de namespaces, se amplía con el mismo cambio.
- **Chart de Valkey** (INF-U2-04, R2, R3, R4, INF-U2-06):
  - **Valkey:**
    - StatefulSets `valkey-a` y `valkey-b` de 1 réplica, cada uno con `nodeAffinity` obligatoria a su zona. Las zonas van en los values: `zone-a` y `zone-b` en kind;
    - imagen `…/vectra/valkey@sha256:2602ace2be6569bc2bbb06f873776516ab9089821525be34f4305c67eb9db02a` (8.1.11-alpine), con el registro de cada entorno;
    - `valkey-a` arranca como primaria y `valkey-b` como réplica de ella. Al reiniciar, cada nodo pregunta a Sentinel por la primaria actual;
    - `replica-priority` 10 en A y 100 en B;
    - sin RDB (`save ""`) ni AOF (`appendonly no`), con `emptyDir`;
    - `maxmemory 128mb` y `maxmemory-policy volatile-ttl`;
    - `aclfile` montado de solo lectura desde el Secret;
    - `masteruser replication` y `masterauth` desde el Secret;
    - recursos 100m / 128 MiB y 500m / 256 MiB.
  - **Exportador:** sidecar `…/vectra/redis-exporter@sha256:19bb5c732f5812d5b60b2e0af3c6d82c5b3e418cd020068d65f588a56df4a118` (v1.95.0-alpine), con el usuario `exporter`, puerto 9121 y recursos 50m / 32 MiB y 100m / 64 MiB.
  - **Sentinel:**
    - `sentinel-a` (1 réplica, zona A) y `sentinel-b` (2 réplicas, zona B), con la imagen de Valkey;
    - quórum 2, `resolve-hostnames yes` y `announce-hostnames yes`;
    - `sentinel.conf` copiado a un `emptyDir` al arrancar, con `user default off`, el usuario `ratelimit` de R4 y `sentinel auth-user sentinel` / `auth-pass`;
    - recursos 50m / 32 MiB y 100m / 64 MiB.
  - **Services headless** para cada grupo.
  - **PDB:** Valkey `minAvailable: 1` y Sentinel `minAvailable: 2`, sobre etiquetas comunes que seleccionan de verdad los pods.
  - **Todos los pods:**
    - `priorityClassName: vectra-high` y `vectra.io/criticality: high`;
    - `securityContext` que cumpla las `STATIC_POLICIES` de U1: no root, sin privilegios, raíz de solo lectura y `RuntimeDefault`;
    - en `vectra-edge`.
  - **`ExternalSecret` de `vectra-edge`:** con `target.template` desde `edge/valkey` arma `users.acl` con las líneas exactas de R4 (`default off`, `ratelimit`, `replication`, `sentinel` y `exporter`), el ACL de Sentinel y las contraseñas de `masterauth`, del exportador y de `auth-pass`. Ninguna contraseña va en un ConfigMap.
- **Descriptores** (INF-U2-03, P-U2-06): `test_ratelimit_config.py` corre `egctl x translate --from gateway-api --to ir` sobre `generated/<env>/`, con los mismos documentos de apoyo que `xds_gateway.py`. Comprueba que las reglas `global` de `edge-rate-limits` y `auth-rate-limits` en el IR coinciden con los límites de `routes.yaml`:
  - selectores de cabecera `x-vectra-sub` y `x-vectra-azp`;
  - IP de origen en `/auth/**`;
  - `requests`, `unit` y `shared`.

  Las comprueba en los tres entornos. Si una regla de `routes.yaml` cambia y el IR no, falla.

**Fuera:**
- Flujos, NetworkPolicies y RBAC de `flows.yaml` (F90–F93 con los puertos y namespaces enmendados, y el scrape del 19001 y del 9121): Paso 10.
- Alertas y el runbook de la vuelta de la primaria a la zona A: Paso 11.
- Entradas de `vectra-risk-gitops/components.yaml` para Valkey y lo generado: Paso 12.
- Sembrar `edge/valkey` en el Vault de kind, y probar el failover, el 429 y el 503 en vivo: Paso 16.
- `routes.yaml`, `route_gen.py` y `generated/`: no cambian. Si la prueba de descriptores encuentra que no coinciden, detente y repórtalo.
- Cualquier cosa contra un clúster o contra Docker.
- En `platform/` solo se tocan `operators/envoy-gateway.yaml`, `operators/envoy-gateway-kind.yaml` y `secrets/eso-rbac-k11*.yaml`, más las pruebas de U1 que fijan esas listas.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Pasos 8, 9 y 10)
- `aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md` (INF-U2-03, 04 y 06, con las enmiendas de R1–R4)
- `aidlc-docs/construction/identity-edge/nfr-requirements/nfr-requirements.md` (NFR-U2-20, 21, 25, 27 y 30)
- `aidlc-docs/construction/identity-edge/nfr-design/nfr-design-patterns.md` (P-U2-01, 04 y 06)
- `aidlc-docs/inception/application-design/component-dependency.md` (§0, §2.8, K11)
- `identity-edge/docs/adr-envoy-gateway.md`, `identity-edge/tools/xds_gateway.py`, `identity-edge/tests/unit/test_data_plane_policies.py` y `test_envoy_gateway_values.py` (Paso 8: el modelo de Deployment y el render del chart)
- `identity-edge/gateway/routes.yaml`, `identity-edge/gateway/generated/`
- `identity-edge/keycloak/values/common.yaml` (patrón de `ExternalSecret`), `identity-edge/Makefile`
- `platform/operators/envoy-gateway.yaml`, `platform/operators/envoy-gateway-kind.yaml`, `platform/secrets/`, `platform/policies/kyverno/`

## Criterios de aceptación

- [ ] **CA-1** — Descriptores. Es la segunda aceptación del Paso 9.
  ```bash
  uv run pytest identity-edge/tests/unit/test_ratelimit_config.py -q
  ```
  Esperado: pasa en los tres entornos con `egctl` de verdad, en segundos y no en milisegundos. Falla con un límite de `routes.yaml` alterado en una copia, y con una regla quitada de `edge-rate-limits` o `auth-rate-limits` en una copia de `generated/`.
- [ ] **CA-2** — `envoy-ratelimit`. Es la primera aceptación del Paso 9, para el controlador.
  ```bash
  make -C identity-edge render-envoy-gateway policy-ratelimit && uv run pytest identity-edge/tests/unit/test_envoy_gateway_values.py identity-edge/tests/unit/test_ratelimit_deployment.py -q
  ```
  Esperado: pasa. `policy-ratelimit` corre conftest con `identity-edge/ratelimit/policy/` sobre el `EnvoyGateway` del render, en kind y en el banco. Exige:
  - Sentinel por env y las dos credenciales por `secretKeyRef`;
  - imagen con digest de un registro permitido;
  - réplicas, HPA de 2 a 4 al 70 % y PDB;
  - recursos, prioridad, criticidad, `securityContext` y reparto.

  Cada regla tiene un caso que falla. `test_envoy_gateway_values.py` ya no exige «sin `rateLimit`», y exige los valores de R1 y R2 leídos del diseño. `test_ratelimit_deployment.py` comprueba el modelo de v1.9.3: puertos 8081, 8080 y 19001, env final, selectores y `kyverno apply` con resultado `pass` y `fail: 0`.
- [ ] **CA-3** — Chart de Valkey. Es la primera aceptación del Paso 9, para Valkey.
  ```bash
  make -C identity-edge check-valkey-rendered policy-valkey policy-valkey-u1 && uv run pytest identity-edge/tests/unit/test_valkey_chart.py -q
  ```
  Esperado: pasa en los tres entornos.
  - `policy-valkey` corre conftest con `identity-edge/charts/valkey/policy/`. Exige:
    - sin RDB ni AOF;
    - ACL presente y `default off` en Valkey y Sentinel;
    - usuarios y permisos exactos de R4;
    - `maxmemory` y política;
    - zonas de R3, `replica-priority` y quórum;
    - PDB;
    - sidecar del exportador;
    - ninguna contraseña fuera de un Secret.
  - `policy-valkey-u1` corre `kyverno apply` con las `STATIC_POLICIES` de U1 sobre lo renderizado, con resultado `pass` y `fail: 0`.
  - `test_valkey_chart.py` compara el conjunto exacto de documentos de cada entorno con un oráculo que lee del diseño cada valor que el diseño fija (lección de U02-T09). Comprueba que cada selector de StatefulSet, Service y PDB selecciona su template, y que un cambio en el diseño que no llega al oráculo hace fallar una prueba.

  Cada regla de conftest tiene un caso que falla.
- [ ] **CA-4** — K11.
  ```bash
  make -C platform check-local
  ```
  Esperado: pasa, con el Role y el RoleBinding de ESO en `envoy-gateway-system` en las tres variantes de K11.
- [ ] **CA-5** — Lo anterior sigue cumpliendo.
  ```bash
  uv sync --frozen && make -C identity-edge check
  ```
  Esperado: todo pasa y termina en 0, sin pruebas omitidas. `check` incluye `policy-ratelimit`, `check-valkey-rendered`, `policy-valkey` y `policy-valkey-u1`. Corre CA-4 y CA-5 en serie, no en paralelo.

## Plan de pruebas

**Rojo primero:** escribe `test_ratelimit_config.py`, `test_ratelimit_deployment.py`, `test_valkey_chart.py`, los casos nuevos de `test_envoy_gateway_values.py` y los casos que fallan de cada regla de conftest. Registra en la bitácora que fallan antes de cambiar los values, el chart y K11.

## Notas

- Implementa lo que define el diseño enmendado. Detente y repórtalo, sin sustituirlo por otro mecanismo, si pasa algo de esto:
  - falta un dato;
  - un campo de v1.9.3 no permite expresar una precisión;
  - una lista de comandos de R4 no basta en Valkey 8.1 o en el cliente radix de `envoyproxy/ratelimit` `5ae0682e`. Compruébalo en `src/redis/driver_impl.go` y en la documentación de ACL de Sentinel de Valkey 8.1.
- Los campos se comprueban contra el código de los tags, no de memoria:
  - `gh api repos/envoyproxy/gateway/contents/<ruta>?ref=v1.9.3 -H "Accept: application/vnd.github.raw"`;
  - `gh api repos/envoyproxy/ratelimit/contents/<ruta>?ref=5ae0682e`;
  - `gh api repos/valkey-io/valkey/contents/<ruta>?ref=8.1.11`.
- Las clases de valores se definen por listas exactas. No uses expresiones regulares sobre el texto de los manifiestos.
- Lo renderizado de Valkey es salida generada y versionada.
- Trabaja solo en tu worktree. **Nada contra un clúster ni contra Docker**: el proyecto los deniega por configuración. El destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. La red solo se usa para `install-tools.sh`, `charts.sh` y `gh api` de lectura.
- CA-5 necesita el chart `keycloakx` en `platform/.charts/` (candidata abierta). Si falta, cópialo del worktree de `main` sin versionarlo y anótalo en la bitácora.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
