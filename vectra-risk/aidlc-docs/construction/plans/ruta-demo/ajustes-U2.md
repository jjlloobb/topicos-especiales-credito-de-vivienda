# Ruta demo: ajustes de U2 `identity-edge`

Análisis de solo lectura, 2026-11-07. Fuentes:
- repo `wt-demo-ruta/vectra-risk`, rama `demo/ruta` (`fb414b2`);
- ramas `origin/tarea/U02-T15`, `origin/tarea/U02-T17` y `origin/tarea/U02-T18`;
- el worktree local `wt-U02-T18` (`49db24b`). Va 3 commits por delante de `origin`: las rondas 4 y 5 y M5 **no están empujadas**;
- el clúster `kind-vectra`, consultado solo con `kubectl get`, `kubectl describe` y `docker stats --no-stream`;
- el catálogo de `kind-registry`, leído con `GET /v2/_catalog`, que es de solo lectura.

Marcas:
- **[VERIFICAR]**: no se pudo comprobar sin ejecutar algo contra Keycloak o el clúster.
- **EXT**: el cambio toca una extensión activa y necesita la decisión del usuario.

---

## 0. Estado del clúster hoy (afecta a cualquier instalación)

| Hecho | Evidencia |
|---|---|
| U1 está degradado desde hace ≈ 4 h 40 min (reinicio del host) | `linkerd-cni` en `CrashLoopBackOff`/`Error` en 2 de 3 nodos. `linkerd-destination`, `linkerd-identity`, `linkerd-proxy-injector`, las 5 bases, MinIO y toda la observabilidad están en `Unknown`. El init container `linkerd-network-validator` de `keycloak-db-1` está en `BackOff` |
| Vault dev se reinició (10 reinicios; el último a las 15:05 UTC) y perdió todo | Todos los `ExternalSecret` están en `SecretSyncedError` |
| `cloud-provider-kind` no está corriendo | `docker ps` solo muestra `kind-registry` y los 3 nodos. Sin él, el Service `LoadBalancer` del gateway queda en `<pending>` |
| El controlador de Envoy Gateway en vivo es anterior a U02-T10/T11 | Hay 1 réplica, el ConfigMap no tiene `rateLimit.backend` y las imágenes son de `docker.io`. La Application `envoy-gateway` está `OutOfSync`, y la de `root` también |
| U2 no tiene imágenes en `kind-registry` | `_catalog` = `grafana-folder-permissions`, `mc`, `minio`, `restore-drill` |
| Memoria | Los 3 nodos de `docker stats` suman 5,27 GiB (con muchos pods de U1 caídos, así que con U1 sano será más). Según `free`, el host usa 10 GiB de 14 y tiene 4 GiB disponibles, con el swap lleno (3/3). Fuera de kind se van ≈ 4,7 GiB |

Antes de instalar U2 hay que recuperar U1 (Linkerd, volver a sembrar Vault y `cloud-provider-kind`). Eso no es un ajuste de U2, pero bloquea cualquier escenario.

---

## 1. Réplicas de U2 en kind-demo

### 1.1 Qué baja a 1 y qué no

Hecho clave: las reglas de Kyverno de U1 (`require-min-replicas`, `require-zone-spread`, `require-pdb`, `require-hpa-bounds`) y `platform/policies/rego/hpa.rego` **solo miran `Deployment`**. Comprobado en `platform/policies/kyverno/require-spread-and-pdb.yaml:17` y `require-hpa-bounds.yaml:14`, y está también en CANDIDATAS L61. Por eso, para U2:
- Keycloak, Valkey y Sentinel son `StatefulSet`, y Kyverno no los ve.
- El data plane de Envoy (`Deployment` en `vectra-edge`) está excluido de `require-min-replicas` y de `require-pdb` por `gateway.envoyproxy.io/owning-gateway-name`. `deployment-needs-hpa-or-exemption` es solo `Audit`.
- El controlador y `envoy-ratelimit` viven en `envoy-gateway-system`, fuera del alcance de Kyverno.

**El recorte de U2 no necesita la excepción RD1.** Lo que lo bloquea son las políticas conftest/rego **propias de U2** y las pruebas que leen los números del diseño.

| Pieza | Hoy | kind-demo propuesto | Se ahorra (requests) |
|---|---|---|---|
| Keycloak (`StatefulSet`) | HPA 2–4, PDB `minAvailable: 1`, spread | **1 réplica, sin HPA, sin PDB**. El spread se puede quedar | 0,52 GiB (con M4) |
| Data plane de Envoy (`EnvoyProxy`) | `replicas: 2`, `envoyHpa` 2–6, `envoyPDB` 1 | **1 réplica, sin `envoyHpa` ni `envoyPDB`** | 0,30 GiB |
| Controlador de Envoy Gateway | `deployment.replicas: 2` | **1** | 0,125 GiB |
| `envoy-ratelimit` | `replicas: 2`, `rateLimitHpa` 2–4, `rateLimitPDB` 1 | **1, sin HPA ni PDB** (`rateLimitHpa: null` y `rateLimitPDB: null` en el overlay de kind) | 0,0625 GiB |
| Valkey a/b + Sentinel 1 + 2 | Cada `StatefulSet` ya tiene 1 réplica (sentinel-b, 2), quórum 2 | **Sin cambios** | 0 (se podrían ganar ≈ 0,28 GiB, pero no compensa: ver 1.2) |

### 1.2 Qué rompe cada cambio

**Keycloak a 1**
- **Sesiones e Infinispan.** Keycloak 26.8.1 tiene `persistent-user-sessions` activo por defecto (`keycloak/values/common.yaml:62`). Las sesiones viven en `keycloak-db`, así que sobreviven a un reinicio del único pod. Con `jdbc-ping`, un clúster de un solo miembro funciona.
- **Lo que se pierde:**
  - la disponibilidad mientras el pod reinicia (1–2 min: `start --optimized`, más la base y la malla);
  - los contadores de fuerza bruta (`loginFailures` en caché, no persistidos). **[VERIFICAR]** en 26.8.1.
- **Políticas y pruebas que fallan:**
  - `keycloak.rego:86-91` (`replicas` presente y ≠ 2);
  - `keycloak.rego:94-140` (`hpa`, si se quita el HPA con su `expected_hpa_spec`);
  - la regla `pdb` (`keycloak.rego:162`);
  - `tests/unit/test_keycloak_deploy.py:652` (`test_design_replicas_hpa_and_pdb[env]`, para los 3 entornos) y `:715`. `design_replicas()` lee «HPA de 2 a 4» de P-U2-04.
- Kyverno de U1: nada.

**Data plane de Envoy a 1**
- `routes.yaml:14-16` fija `replicas`, `hpa` y `pdb_min_available` **globalmente**, no por entorno. `route_gen.py` necesita aceptar un override desde `gateway/values/kind.yaml`.
- Fallan:
  - `gateway/policy/edge.rego:345-381` (`envoy-scaling`: `< 2`, HPA ≠ {2, 6}, PDB ≠ 1);
  - `tests/unit/test_data_plane_policies.py`;
  - las pruebas de route-gen que comparan con `generated/`.
- Con 1 réplica y `externalTrafficPolicy: Local`, el Service LB funciona.

**Controlador a 1**
- **Elección de líder.** Sigue activa: un único candidato toma el lease. Si el pod muere, el data plane conserva el último xDS (NFR-U2-04). No hay rotura funcional.
- Fallan:
  - `tests/unit/test_envoy_gateway_values.py:83,110,165`. `controller_replicas()` lee «Controlador de Envoy Gateway: 2 r» de NFR-U2-03, en `tests/strategies/envoy_gateway_design.py:17`;
  - `make policy-ratelimit` renderiza también kind, con `-f envoy-gateway-kind.yaml`.

**`envoy-ratelimit` a 1**
- Fallan:
  - `ratelimit/policy/ratelimit.rego:125-155` (`replicas == 2`, HPA min 2 / max 4 / CPU 70 %, PDB 1), aplicada también al render de kind;
  - el spread de `:238-271` (con 1 réplica la restricción sigue siendo válida; se puede conservar);
  - `tests/unit/test_ratelimit_deployment.py:304-386,560`. `ratelimit_replicas()` y `ratelimit_hpa()` leen INF-U2-03.

**Valkey: por qué no se toca**
- Quitar `valkey-b` y `sentinel-b` rompe:
  - el quórum 2 de 3 Sentinel (`valkey.rego:359-363`);
  - las reglas `replicas` (`:338-356`) y `pdb` de Sentinel (`minAvailable: 2`, `:375-378`);
  - la URL de Sentinel de `envoy-ratelimit`, con 3 FQDN escritos en `platform/operators/envoy-gateway.yaml:20`, que es común a todos los entornos, y en `ratelimit.rego:17`;
  - el escenario P-U2-01 (Valkey a 0).
- El ahorro real es mínimo: Valkey con `maxmemory 128mb` vacío usa decenas de MiB.

### 1.3 Escenarios del Paso 16 con el recorte

| Escenario del Paso 16 | Con kind-demo |
|---|---|
| 5. Borrado del pod de Keycloak con sesión activa → el refresh sigue (NFR-U2-02) | **Cambia de sentido.** Con 1 réplica no hay otro pod que atienda: el refresh falla mientras reinicia y vuelve a funcionar cuando el pod está `Ready`, gracias a las sesiones persistentes. Ya no prueba la alta disponibilidad, solo la persistencia. Es inyección de fallos, así que entra en RD3 como diferido |
| 6. Controlador escalado a 0 → las rutas siguen (NFR-U2-04) | **Sigue pudiendo correr**: escalar de 1 a 0 equivale a escalar de 2 a 0. Es inyección de fallos (RD3) |
| 4. Valkey a 0 → consola 200 y token 503 (P-U2-01) | Sin cambios (Valkey no se recorta). RD3 |
| 8. `POST` contra un backend con 503 → 1 llamada (P-U2-02) | Sin cambios. Con 1 pod de Envoy, la detección de outliers no tiene a qué otro pod desviar, pero el escenario mide reintentos, no la expulsión |
| 2. Carga k6 (NFR-U2-10..12) | No representativa con 1 Keycloak y 1 Envoy. Ya está diferida (RD3) |

### 1.4 Memoria (tabla de las rondas 4 y 5 de `bitacoras/U02-T18.md`, en el worktree local `49db24b`)

Las cifras son requests de memoria en GiB, con el proxy de Linkerd donde hay malla. Las columnas «kind-demo» son mi cálculo con las mismas requests por pod.

| Componente | Hoy, con M4 | Hoy, sin M4 | kind-demo, con M4 | kind-demo, sin M4 |
|---|---|---|---|---|
| Keycloak | 2 × 0,5195 = 1,0391 | 2 × 1,0195 = 2,0391 | 1 × 0,5195 = 0,5195 | 1,0195 |
| Data plane de Envoy (256 + 32 + 20 MiB) | 2 × 0,3008 = 0,6016 | igual | 0,3008 | 0,3008 |
| Controlador de Envoy Gateway | 2 × 0,125 = 0,25 | igual | 0,125 | 0,125 |
| `envoy-ratelimit` | 2 × 0,0625 = 0,125 | igual | 0,0625 | 0,0625 |
| valkey-a + valkey-b | 0,3516 | igual | 0,3516 | 0,3516 |
| sentinel-a + sentinel-b (1 + 2) | 0,1523 | igual | 0,1523 | 0,1523 |
| **Subtotal U2** | **2,5195** | **3,5195** | **1,5117** | **2,0117** |
| KServe (M5) | 0,5859 | | 0,5859 | |
| Resto del perfil (U1) | 3,9492 | | 3,9492 | |
| **Total del perfil (`BUDGET_GIB` = 8,0 con M5)** | **7,0547** (margen 0,95) | 8,05 (rojo) | **6,0469** (margen 1,95) | 6,55 (margen 1,45) |

Uso real estimado de U2. No está medido: son órdenes de magnitud típicos de estos procesos.

| | Keycloak (JVM) | Envoy (cada pod, con `shutdown-manager` y proxy) | Controlador | `envoy-ratelimit` | Valkey y Sentinel (5 pods, con exportadores y proxies) | **Total** |
|---|---|---|---|---|---|---|
| Hoy | 0,7–1,0 GiB × 2 | ≈ 0,1 GiB × 2 | ≈ 0,08 GiB × 2 | ≈ 0,03 GiB × 2 | ≈ 0,2 GiB | **≈ 1,9–2,5 GiB** |
| kind-demo | 0,7–1,0 GiB | ≈ 0,1 GiB | ≈ 0,08 GiB | ≈ 0,03 GiB | ≈ 0,2 GiB | **≈ 1,1–1,4 GiB** |

**Riesgo de Keycloak:** con el limit de 2 GiB y `-XX:MaxRAMPercentage=70`, el heap puede crecer hasta ≈ 1,4 GiB aunque la request sea de 512 MiB. Es el primer candidato a desalojo, como ya dice el runbook de M5.

**Contexto:** U3–U11 suman ≈ 3,0–3,5 GiB de requests, según las tablas de la ruta (U3–U6, 1,1–1,6; U7–U9, 1,3; U10, 0,33; U11, 0,28). Sin el recorte de U2, el perfil pasa de 8,0 GiB en cuanto entra U3. Con el recorte también lo pasa, pero más tarde. En uso real:
- el host deja ≈ 10 GiB para kind;
- U1 ocupa 5,3, U2 recortado ≈ 1,2, y U3–U11 en uso real ≈ 2–3,5;
- **el total va justo, sin holgura para picos (validación de U4, promoción de U6, Chromium de U12).**

---

## 2. Realm de kind frente a lo que necesitan las unidades de la demo

`realm.kind.yaml` tiene:
- 5 roles: `analista`, `ingeniero_riesgo`, `cro`, `cumplimiento`, `operacion`;
- 17 client scopes, con su audiencia;
- 17 clientes;
- 10 usuarios sintéticos con contraseña y TOTP.

Lo contrasté con el catálogo de U0 (`contracts/functional-design/domain-entities.md` §7.2), que es la fuente del realm, con las rutas de `contracts/.../routes/__init__.py` y con los Infrastructure Design de U8, U10 y U12.

| Unidad, necesidad de la demo | En el realm | Estado |
|---|---|---|
| U3: rutas del registro. `POST /v1/entries` con `registry:append:{case,scoring,governance}`; `GET /v1/entries` con `read:{explanation,metrics,monitoring}`; dossier e integridad por rol | Están los 6 scopes con `aud decision-registry-service`. `vectra-console` lleva `aud decision-registry-service` | Completo |
| U4: `governance-service` (`bias:compare`, `registry:append:governance`), `model-validation-job` (`governance:validation-report`), `promotion-tool` (público PKCE, `governance:promotion` solo para `ingeniero_riesgo`, `acr = mfa`, redirect `http://127.0.0.1`) | Sí | Completo |
| U7: `scoring-service` (`governance:read-serving`, `registry:append:scoring`, `scoring:explain`), `explainability-service` (`governance:read-dictionary`, `registry:read:explanation`) | Sí | Completo |
| U8: `case-service` (`core:read-credit`, `governance:read-serving`, `registry:append:case`), `case-worker` (`case:recommend`, `governance:read-feature-spec`, `governance:read-serving`); `core:write-credit` sin titular (RT-5) | Sí; ningún cliente tiene `core:write-credit` | Completo. `core-banking-mock` no es un cliente, solo una audiencia (no pide tokens); `U7-U9.md` dice «cliente», y eso es inexacto pero no falta nada |
| U9: `bias-monitoring-service` (`registry:read:monitoring`), `bias-monitoring-job` (`governance:freeze`, `registry:read:monitoring`) | Sí | Completo |
| U10: un solo cliente público `vectra-console` (no hay `console-spa` ni `console-bff` como clientes: el BFF reenvía el token del usuario, como fija U10 domain-entities L49). Lleva PKCE S256, `/callback`, `/stepup-callback`, audiencias del BFF y de los 5 backends, y los claims `roles`, `acr`, `amr` y `auth_time` | Sí | Completo |
| Roles del CRO y de cumplimiento, cuatro ojos (U4 BR-U4-10) | `cro-1`/`cro-2`, `cumplimiento-1`/`-2`, `ingeniero-1`/`-2` y flujos `vectra-mfa-<rol>` | Completo. **No existe un rol de «comité»** en ningún diseño: la única mención es un [VERIFICAR] de negocio en U10 BR-U10-09b. No hace falta crearlo |
| Aprobador con TOTP (journey-7-4: `cro-1` con step-up) | Las 10 cuentas tienen credencial `otp`, con semilla `$(env:SYNTH_*_TOTP_SEED)` | Completo en Git. Queda pendiente que las semillas lleguen (secciones 4 y 5) y comprobar que la semilla Base32 se lee bien (CANDIDATAS L44) |
| U11: `product-metrics` (`registry:read:metrics`) | Sí | Completo |
| U12: `channel-simulator` (`intake:submit`, 30/s), `verification-reader` (`registry:read:metrics` + `registry:read:monitoring`, que cubren `GET /v1/entries?entry_type=freeze` y `/v1/monitoring/freezes`), `analista-1`/`-2` por el BFF | Sí | Completo |
| U11 sub-ítem 4 y paso 13 del guion: `cro-1` en Grafana | Cliente `grafana` confidencial con `private_key_jwt` ES256 y mapper `roles` | Está en el realm, pero **no sirve sin U1** (ver 3.3) |

**Conclusión 2:** en Git no falta ningún cliente, scope, rol ni usuario. Lo que falta es todo lo que lleva el realm al clúster: la importación (4), los valores de las 35 variables `$(env:…)` (5) y la comprobación de `aud` (6, A6).

Observación sin impacto en la demo: `vectra-console` tiene `default.acr.values: mfa`, así que el login de un analista pide TOTP aunque BR-U10-09b diga «MFA disponible, no obligatorio». U12 ya hace el login con TOTP.

---

## 3. Rutas

### 3.1 Backends de la demo

| Ruta (`routes.yaml`) | Backend | Lo que fijan la unidad y `flows.yaml` | Estado |
|---|---|---|---|
| `/` SPA (F02), afinidad `vectra-spa-route` | `console-spa.vectra-edge:8080` | U10 INF-U10-04 y F02 (`console-spa` en `vectra-edge`, 8080) | Coincide |
| `/api/console/**` (F03), `azp = vectra-console`, roles de negocio, 64 KiB, 15 s | `console-bff.vectra-app:8080` | U10 INF-U10-04 y F03 | Coincide. `client-errors` exige roles en el contrato, así que el JWT en el gateway es coherente |
| `POST /api/intake/v1/intake/applications` (F04/F07) → `/v1/intake/applications`, `azp ∈ {channel, channel-simulator}`, `intake:submit` | `case-service.vectra-app:8080` | U8 y F04 | Coincide. `X-Test-Scenario` e `Idempotency-Key` pasan (P-U2-06); el límite es 30/s para `channel-simulator` |
| `/api/promotion/v1/models?state=aprobado` y `.../activation` (F08) | `governance-service.vectra-app:8080` | U4 y F08 | Coincide con `list_promotable` y `mark_active` (U4 business-logic-model L15) |
| `/auth/realms/vectra/...` (F05), lista cerrada | `keycloak.vectra-identity:8443` | Coincide | Coincide |
| `/grafana/**` (F06) | `kube-prometheus-stack-grafana.vectra-observability:80` | El Service existe con el puerto 80 (`kubectl get svc`) y F06 apunta al 3000 de destino | Ruta correcta; **el backend no está listo** (3.3) |
| U3, U7, U9 y U11 | Sin ruta pública, por diseño (llegan por el BFF o por la malla; U12 usa `port-forward` a un pod) | — | Correcto |

### 3.2 Rutas que necesita el guion de `U10-U12.md`

Los pasos 2 a 6 y 9 a 11 (consola), el 3 (ingesta), el 12 (promoción y rollback por `promotion-tool`) y el 13 (Grafana) tienen ruta. **No falta ninguna ruta.**

Observación para U10 y U12, no para U2: el paso 6 del guion dice que **cumplimiento** abre «la verificación de integridad». Pero en `routes/__init__.py`, `POST /v1/integrity-checks` es `roles=CRO, mfa=True` y `GET /v1/integrity-checks/{id}` es `roles=CRO`. Cumplimiento solo puede ver el expediente (`CRO_CUMPLIMIENTO`). Hay que corregir el guion.

### 3.3 Lo que hace falta para que las rutas funcionen de verdad en kind

1. **Acceso desde el host.** `vectra.localtest.me` resuelve a `127.0.0.1`. U12 (deployment-architecture L74) supone que entra por el `extraPortMappings` 443 del control-plane (`platform/kind/cluster.yaml`). Pero dentro del nodo nada escucha en el 443:
   - el Service del gateway es `LoadBalancer`, servido por `cloud-provider-kind`, que hoy no corre;
   - en Linux, ese LB da una IP de la red `kind`, no `127.0.0.1`;
   - el data plane no corre en el control-plane.

   Hace falta una de dos cosas: una entrada `vectra.localtest.me → <IP del LB>` en el host (o `--host-resolver-rules` en Chromium), o el mapeo de puertos de `cloud-provider-kind`. Además, el navegador del presentador y el contenedor de U12 tienen que confiar en la CA `vectra-internal-ca`. **[VERIFICAR]**: no existe ningún procedimiento escrito, ni en U1 ni en U2.
2. **Grafana por el gateway.** En `platform/observability/values/kube-prometheus-stack*.yaml` no hay `grafana.ini` con:
   - `server.root_url`/`serve_from_sub_path` para `/grafana`;
   - ni `auth.generic_oauth` contra Keycloak.

   Sin eso, `/grafana/**` no sirve, y tampoco el login de `cro-1` y `analista-1` (U11 16.4, paso 13 del guion). Además, sigue abierto si Grafana `generic_oauth` admite `private_key_jwt` ES256 (CANDIDATAS L47). **[VERIFICAR]**, dueño principal U1.
3. **Eco del Paso 13 (H1).** `tests/e2e/echo/manifests.yaml` crea objetos con los **nombres reales** de `console-spa`, `console-bff`, `case-service` y `governance-service`. Hay que borrarlo después del Paso 16 y antes de instalar U8 y U10; si no, chocan con sus Applications.

---

## 4. `keycloak-config-cli` bloqueado: cómo se importa el realm en kind

### 4.1 Evidencia de que hoy no hay ninguna vía

- **El diseño fija la herramienta:**
  - BR-U2-12: «Toda configuración del realm sale de `realm.{env}.yaml` en Git y **la aplica `keycloak-config-cli`** como hook de un sync manual»;
  - tech-stack-decisions L13 (FD Q10);
  - NFR RESILIENCY-03/04 lo citan como evidencia de cumplimiento;
  - INF-U2-05a L182 registra el bloqueo: no hay ningún release con `private_key_jwt`, y la rama principal solo lee un JWT ya firmado, sin firmante diseñado.
- **El render no lleva otra vía:**
  - `keycloak/rendered/kind/keycloak.yaml` no tiene `--import-realm`, volumen de import, `KC_BOOTSTRAP_ADMIN_*` ni un `ExternalSecret` con las variables del realm. Los únicos son `identity-ca`, `keycloak-config-cli-client` y `keycloak-reader-client`;
  - `keycloak.rego:177` exige `args == ["start", "--optimized"]`, y la regla F-06 (`:414-472`) fija el pod template exacto.
- **La Application `keycloak` de U02-T18 solo sincroniza el render** (M2: sin `keycloak-config-cli`).
- **Las variables `$(env:…)` son sintaxis de `keycloak-config-cli`.** Keycloak no las entiende.

### 4.2 Bloqueo nuevo: el arranque inicial («huevo y gallina»)

El bloqueo es más profundo que el de INF-U2-05a:
- `keycloak-config-cli` y `keycloak-reader` son **clientes del propio realm `vectra`** (`realm.kind.yaml:1331-1370`, `clientScopeMappings` de `realm-management`). Con `vectra` inexistente al primer arranque, ningún cliente puede autenticarse para crearlo.
- El diseño no prevé un admin de `master` ni un `KC_BOOTSTRAP_ADMIN_*`. Busqué «bootstrap», «primera vez», «login-realm» y «master» en `aidlc-docs/construction/identity-edge/`, el plan y CANDIDATAS, sin resultados.
- Por lo tanto, **aunque `keycloak-config-cli` publicara mañana `private_key_jwt`, el primer sync tampoco podría crear el realm.**
- Esto bloquea:
  - toda la demo: login, tokens de servicio de U3–U11, ingesta de U12;
  - y además el Paso 16 entero de U2.

### 4.3 Alternativas

| Opción | Cómo | Qué cambia del diseño | Costo y riesgo |
|---|---|---|---|
| **A. Import al arrancar (`--import-realm`), solo en kind** | `realm-gen` (o el render de `jobs/`) convierte `realm.kind.yaml` a JSON de `RealmRepresentation`, con `$(env:X)` → `${X}`. Va en un ConfigMap montado en `/opt/keycloak/data/import`. Un `ExternalSecret` `keycloak-realm-env` (solo kind) lleva `CLIENT_*_JWKS` (15) y `SYNTH_*` (20). En `values/kind.yaml`: `args: [start, --optimized, --import-realm]` | BR-U2-12 y la fila «Realm como código»: en kind, el primer apply lo hace Keycloak, no `keycloak-config-cli`. `keycloak.rego` (args y pod template) admite esa variante solo en kind | Keycloak sustituye `${ENV}` en los archivos de import (**[VERIFICAR]** en 26.8.1). El import **ignora un realm que ya existe**: los cambios posteriores, o un Vault reiniciado con llaves nuevas, piden volver a importar (ver la fila C). Los secretos sintéticos quedan en el entorno del pod de Keycloak (aceptable en kind: son sintéticos, pero es SECURITY-12, **EXT**). `realm-drift` funciona igual (lee con `keycloak-reader`) |
| **B. Job propio `realm-apply` en `identity-jobs`** | Python con `vectra_common.service_token`, que **ya firma `private_key_jwt` ES256** y lo usa `realm-drift` (`jobs/keycloak_admin.py`). Se autentica como `keycloak-config-cli` y aplica por la Admin API (`partialImport` para clientes, roles y usuarios, y llamadas propias para flujos, `authenticatorConfig`, `requiredActions` y `clientScopes`) | Reemplaza `keycloak-config-cli` como aplicador (BR-U2-12, tech-stack, INF-U2-05a, P-U2-04): **es una decisión del usuario** | Es reimplementar `keycloak-config-cli`: semanas de trabajo y PBT. **No resuelve el arranque**: sigue necesitando A, o un admin temporal de `master`, para crear `vectra` |
| **C. `kc.sh import --dir … --override true` como Job one-shot** (misma imagen y misma base, con Keycloak escalado a 0) | El operador lo lanza tras un PR aprobado. No usa la API ni credenciales de admin: escribe directo en `keycloak-db` | Igual que A, y además un Job de U2 en kind | Recrea el realm: se pierden sesiones y **se regeneran las llaves del realm**, y todos los tokens vigentes se invalidan. Sirve como **procedimiento de reimportación** de A después de un reinicio de Vault, no como camino normal |
| D. Esperar a `keycloak-config-cli` y diseñar el firmante (lo previsto) | — | Ninguno | Sin fecha. Además, choca con 4.2: hace falta resolver el arranque igual |

**¿El diseño lo prohíbe?** No hay ninguna prohibición explícita del import al arrancar. Pero BR-U2-12 y tech-stack nombran a `keycloak-config-cli` como el aplicador, y la política `keycloak.rego:177` lo hace imposible hoy. Usar A o B **cambia una decisión aprobada (FD Q10, BR-U2-12)** y necesita la del usuario. AUTONOMIA-01 se mantiene: el realm sale de Git y llega por un PR y un sync manual.

**Recomendación:**
- A, solo en kind, para el arranque y la demo, con C documentado como reimportación;
- staging y prod siguen esperando D, y el problema de arranque de 4.2 se registra en CANDIDATAS y en INF-U2-05a para esos entornos.

---

## 5. Secretos de U2 en el Vault de kind

**Lo que espera U2** (INF-U2-01 L22-29 y los renders):

| Ruta | Propiedades | Quién la lee | Forma del valor |
|---|---|---|---|
| `identity/ca` | `ca.crt` | `identity-ca` (Keycloak); clientes de F50 y F94 | El certificado **real** de `vectra-internal-ca` (cert-manager), no un aleatorio |
| `identity/clients/<clientId>` | `private-key` (PEM ES256) y `jwks` (pública, va a `CLIENT_<ID>_JWKS`) | 15 clientes `client-jwt`: `grafana`, `case-service`, `case-worker`, `scoring-service`, `explainability-service`, `governance-service`, `bias-monitoring-service`, `bias-monitoring-job`, `model-validation-job`, `product-metrics`, `verification-reader`, `channel`, `channel-simulator`, `keycloak-config-cli` y `keycloak-reader`. Las privadas las leen los charts de cada unidad, U1 (Grafana) y U12 (directo de Vault) | Un par EC P-256 coherente; JWKS con `kid` y `alg ES256` |
| `identity/synthetic-users` | `SYNTH_<USUARIO>_PASSWORD` y `SYNTH_<USUARIO>_TOTP_SEED` × 10 usuarios | El `ExternalSecret` del realm (no existe todavía), U12, e2e y Playwright de U10 | Contraseña de ≥ 14 caracteres que no contenga el usuario (`passwordPolicy`); semilla **Base32** |
| `identity/break-glass` | `BREAK_GLASS_PASSWORD` | Solo staging y prod: `realm.kind.yaml` no tiene ese usuario (las 7 coincidencias de «break-glass» son nombres de flujo) | No hace falta en kind |
| `identity/federate` | `.htpasswd` | Solo con F09, que está deshabilitada | No hace falta en kind |
| `edge/valkey` | `ratelimit`, `replication`, `sentinel`, `sentinel-peer`, `exporter`, `sentinel-ratelimit` | Valkey y `envoy-ratelimit-valkey` | Aleatorio |

**¿Existe la siembra? No.**
- `platform/kind/seed-vault.sh` → `vault_paths.py`. Sus `SOURCES` (`vault_paths.py:24-29`) son solo manifiestos de `platform/`, y `test_vault_paths.py:36-38` solo comprueba `PLATFORM.rglob`. Ningún `ExternalSecret` de `identity-edge/` entra.
- Aunque se agregaran a `SOURCES`, `plan()` genera `secrets.token_hex(24)`. Eso sirve para `edge/valkey` y las contraseñas, pero **no** para:
  - `ca.crt`;
  - el par `private-key`/`jwks`;
  - las semillas TOTP (el hex no es Base32 válido).
- El `ExternalSecret` con las variables del realm tampoco existe: estaba previsto con el Job de `keycloak-config-cli`.

**Riesgo operativo comprobado hoy:** Vault dev guarda todo en memoria y se reinició 10 veces. Tras un reinicio, la siembra genera llaves nuevas, pero el realm ya importado en `keycloak-db` conserva los JWKS viejos. Resultado: todos los tokens de servicio dan `invalid_client`. La siembra de U2 y la reimportación (4.3 C) tienen que ir juntas en el runbook.

---

## 6. Pendientes de U2 (CANDIDATAS y ramas) que bloquean la demo

| Pendiente | Fuente | ¿Bloquea la demo? |
|---|---|---|
| Importación del realm, `keycloak-config-cli` y su firmante | L57-59; INF-U2-05a | **Sí, todo** (sección 4) |
| Imagen de Keycloak propia: digest `sha256:…01` en `keycloak/values/kind.yaml`; ningún workflow la construye | L55, L63 | **Sí.** Hay que construirla (`identity-edge/keycloak/Dockerfile`), subirla a `kind-registry:5000/vectra/keycloak` y fijar el digest por PR. Lo mismo para `identity-jobs` (L72; digest `…01` en `jobs/values/kind.yaml`), aunque los CronJobs no son de la demo |
| Imágenes de terceros sin espejar en `kind-registry`: `vectra/envoy`, `vectra/envoy-gateway` (`shutdown-manager`), `vectra/ratelimit`, `vectra/valkey`, `vectra/redis-exporter` | `_catalog` actual | **Sí.** Un `crane copy` conserva el digest que ya está en los values |
| Digest marcador del eco (`e2e-echo@sha256:000…`) | L120 | Solo para el Paso 16 (e2e) |
| Métricas de contrato que nada emite: `vectra_role_conflict_total`, `vectra_ldap_connection_failures_total` | L144-145 | **No**: no hay LDAP en kind y las alertas están diferidas (RD3) |
| `aud` de la aserción frente a `hostname` fijo: `service_token` pone `aud` = URL del POST interno, y Keycloak puede esperar la pública | L65 | **Posible bloqueo transversal** de todos los servicios que piden token por F50 (U3–U11). Hay que comprobarlo apenas Keycloak esté arriba; si falla, decidir entre `hostname-backchannel-dynamic` o separar `aud` (**EXT**, SECURITY) |
| Grafana `generic_oauth` con `private_key_jwt` | L47 | Bloquea el paso 13 del guion y U11 16.4 (sección 3.3) |
| Lectura de la semilla Base32 y las `credentials` en usuarios ya existentes | L44 | Hay que comprobarlo en el primer login; con el import al arrancar solo cuenta la primera carga |
| CSP de `/auth/**` frente a los scripts en línea de `keycloak.v2` | L53 | No bloquea: el perfil `auth` solo **agrega** `frame-ancestors 'self'` (`routes.yaml:76-78`). Comprobarlo en el primer login |
| Chart `keycloakx` y herramientas fuera de `charts.sh`/`uv sync` | L88 y T18 | Solo afecta a `make check` en un worktree nuevo |
| U02-T18: rondas 4–5 y M5 sin empujar (`wt-U02-T18` va 3 por delante de `origin`) | `git status -sb` | Bloquea el cierre de T18 y, con él, la Application `keycloak` en `main` |
| U02-T15 (ronda 6, D-01/D-02) y U02-T17 | ramas | No afectan al runtime de la demo (carga y alertas: RD3). Son requisito de orden (README de la ruta, «Orden» 1) |
| Controlador de Envoy Gateway en vivo, anterior a U02-T10/T11 | sección 0 | **Sí**: sin `rateLimit.backend`, `envoy-ratelimit` no existe. Necesita un sync de la Application `envoy-gateway` de U1 |
| `RateLimitBackendDown` con un solo Valkey caído (T17) | T17 CANDIDATAS | No: alertas diferidas |

---

## 7. El Paso 16 y la demo

**Hace falta como «instalación de U2 en kind» (DEMO):**
1. Requisito: PR de los Pasos 1–15 aprobado (T15, T17, T18 y T19 fusionadas), U1 sano y la Application `envoy-gateway` de U1 sincronizada.
2. Imágenes en `kind-registry` (6 sección) y un PR con los digests reales de Keycloak (e `identity-jobs` si se sincroniza esa Application).
3. Siembra de los secretos de U2 (sección 5) e importación del realm (sección 4), con aprobación del operador.
4. Sync manual de las waves: `valkey` (2) → `keycloak`, `api-gateway`, `rate-limit` (3) → `identity-monitors` (4, barato). `identity-rules` y `identity-jobs` pueden esperar (RD3).
5. Humo con evidencia:
   - `/.well-known/openid-configuration` por el gateway;
   - login de `analista-1` con TOTP;
   - step-up de `cro-1` (`acr = mfa`);
   - token `client_credentials` de `channel-simulator` por el gateway y de un cliente interno por el Service interno (L65);
   - 404 de un prefijo cerrado;
   - cabeceras CSP, HSTS y Trusted Types en `/` y `/api/**`.
6. Un subconjunto de la suite Playwright del Paso 13 (sub-ítem 1). Entran los casos de los que dependen U10 y U12:
   - aprobador sin TOTP sin token;
   - step-up OIDC;
   - cabeceras y CSP;
   - 429 con `Retry-After` en `/api/console`;
   - 413;
   - `/auth/admin` → 404;
   - token de otro servicio → 403;
   - `x-vectra-sub` inyectada → sin efecto;
   - `Idempotency-Key` y `X-Test-Scenario` intactas (eco).
   
   **El eco se borra al terminar.**
7. `testssl.sh` (sub-ítem 3): barato (≈ 1 min) y SECURITY. Propongo que entre.

**Se puede diferir con RD3** (cada uno queda como «diferido (ruta demo)»):
- PBT-U2-08 stateful de fuerza bruta (sub-ítem 1, parte PBT stateful).
- k6 (sub-ítem 2, carga).
- Valkey a 0, borrado de Keycloak, controlador a 0 y `POST` 503 (sub-ítems 4, 5, 6 y 8, inyección de fallos). El 5 además cambia de sentido con 1 réplica (1.3).
- Rotación de la llave (sub-ítem 7, operación).
- Los CronJobs `realm-drift` y `signing-key-age` y las alertas.

Son partes de un paso **EXT** (RESILIENCY-14, SECURITY), cubiertas por la aprobación en bloque de RD3.

---

## Ajustes propuestos para U2

Ordenados por urgencia. «DEC» significa que necesita una decisión del usuario.

| # | Qué cambia | Archivos | DEC / EXT | Unidad que lo necesita | Cómo se comprueba |
|---|---|---|---|---|---|
| **A1** | **Arranque e importación del realm en kind** (sección 4, opción A, y C como reimportación). Realm a JSON con `${VAR}`, ConfigMap de import, `ExternalSecret` `keycloak-realm-env` (solo kind), `--import-realm` en kind, y regla de `keycloak.rego` que lo admite solo en kind. Además, registrar el problema de arranque de staging y prod en INF-U2-05a | `identity-edge/tools/` (conversor nuevo o `realm_gen`), `keycloak/values/kind.yaml`, `keycloak/values/common.yaml` (volumen opcional), `keycloak/policy/keycloak.rego`, `tests/unit/test_keycloak_deploy.py`, `keycloak/rendered/kind/`, INF-U2-05a, BR-U2-12, tech-stack, plan (Paso 5 y Paso 16), `runbooks/` (reimportación) | **DEC**: cambia BR-U2-12 y FD Q10. **EXT** SECURITY-12 (secretos sintéticos en el entorno del pod) | Todas (U3–U12): sin realm no hay tokens | `make -C identity-edge check`; en kind: `kubectl -n vectra-identity logs keycloak-0 \| grep -i "import"` y `curl --cacert ca.crt https://vectra.localtest.me/auth/realms/vectra/.well-known/openid-configuration` → 200 con `issuer` `https://vectra.localtest.me/auth/realms/vectra` |
| **A2** | **Siembra de Vault de U2 para kind**: pares ES256 + JWKS con `kid` por cliente `client-jwt` (15), contraseñas que cumplan la política, semillas Base32, `ca.crt` copiado del Secret de `vectra-internal-ca`, aleatorios de `edge/valkey`. Conserva lo existente. Avisa de que, tras un reinicio de Vault, hay que reimportar el realm (A1-C) | `platform/kind/vault_paths.py` (`SOURCES` + generadores por tipo) o un `identity-edge/tools/seed_vault_kind.py`; `platform/kind/tests/test_vault_paths.py`; runbook de instalación | No hay decisión de diseño (las rutas ya las fija INF-U2-01). Hay que decidir el dueño: U1 o U2 | U2, U3–U11 (llaves de cliente), U12 (`channel-simulator`, `verification-reader`, TOTP) | `uv run python platform/kind/vault_paths.py list \| grep -E '^(identity\|edge)/'` lista las 18 rutas; prueba nueva: el JWKS verifica una firma de su llave y la semilla decodifica en Base32 |
| **A3** | **Imágenes de U2 en `kind-registry` y digests reales**: espejar envoy, envoy-gateway, ratelimit, valkey y redis-exporter (`crane copy`, mismo digest); construir keycloak, identity-jobs y e2e-echo; PR con los digests en `keycloak/values/kind.yaml`, `jobs/values/kind.yaml` y `tests/e2e/echo/manifests.yaml`, más los renders | Esos tres archivos, `keycloak/rendered/kind/`, `jobs/rendered/kind/`, procedimiento en el runbook | No | Toda la demo | `curl -s http://127.0.0.1:5001/v2/_catalog` incluye las 8; `make -C identity-edge check-keycloak-rendered check-jobs-rendered` |
| **A4** | **Perfil kind-demo de U2** (sección 1): Keycloak 1 sin HPA ni PDB; data plane 1 sin `envoyHpa`/`envoyPDB` (override por entorno en `route_gen`); controlador 1; `envoy-ratelimit` 1 sin HPA ni PDB; Valkey sin cambios; etiqueta `vectra.io/profile: kind-demo`. Enmiendas de diseño con una fila kind-demo para que las pruebas lean el número por entorno | `keycloak/values/kind.yaml`, `gateway/routes.yaml` + `gateway/values/kind.yaml` + `tools/route_gen.py`, `platform/operators/envoy-gateway-kind.yaml`, `keycloak/policy/keycloak.rego`, `gateway/policy/edge.rego`, `ratelimit/policy/ratelimit.rego`, `tests/unit/test_keycloak_deploy.py`, `test_data_plane_policies.py`, `test_envoy_gateway_values.py`, `test_ratelimit_deployment.py`, `tests/strategies/*_design.py`, renders y `generated/kind/`; diseño: NFR-U2-01/03, P-U2-04, INF-U2-02/03/06 | Lo cubre RD0, que ya está decidido. **EXT** RESILIENCY-08/09: hay que registrarlo en el cumplimiento de U2 y en las enmiendas de diseño | Todas, por memoria (≈ 1,0 GiB de requests y ≈ 0,8–1,1 GiB reales menos) | `make -C identity-edge check`; `uv run pytest platform/tests/test_kind_profile.py -q` → U2 ≈ 1,51 GiB, total ≈ 6,05; `git diff` de `rendered/{staging,prod}` y `generated/{staging,prod}` vacío; en kind: `kubectl -n vectra-identity get sts keycloak` → 1/1 |
| **A5** | **Comprobar la `aud` de las aserciones contra Keycloak 26.8.1** (CANDIDATAS L65) para el token por el Service interno; si falla, `hostname-backchannel-dynamic=true` o separar la `aud` | `keycloak/values/common.yaml` o `kind.yaml`, `keycloak.rego` (env exacta), `vectra_common/service_token` | **DEC/EXT** (SECURITY) si hay que cambiarlo | U3–U11 (F50) y los jobs de U2 | Token `client_credentials` de `case-service` pedido a `https://keycloak.vectra-identity.svc:8443/auth/realms/vectra/protocol/openid-connect/token` → 200. Si falla: `kubectl -n vectra-identity logs keycloak-0 \| grep -iE 'invalid_client\|audience'` |
| **A6** | **Acceso desde el host y confianza en la CA**: `cloud-provider-kind` corriendo, `vectra.localtest.me` → IP del LB (hosts o `--host-resolver-rules`), CA en el navegador y en el contenedor de U12. Corregir la suposición del `extraPortMappings` | Runbook de U2 (instalación en kind), `platform/runbooks/install.md` (U1); nota en U12 deployment-architecture L74 | No (procedimiento). **[VERIFICAR]** el camino del 443 | U10 (navegador), U12 (contenedor), U4 (`promotion-tool`) | `kubectl -n vectra-edge get svc -l app.kubernetes.io/name=api-gateway` con `EXTERNAL-IP` asignada; `curl --cacert ca.crt https://vectra.localtest.me/auth/realms/vectra/.well-known/openid-configuration` |
| **A7** | **Grafana detrás del gateway con OIDC** (U1 `grafana.ini`: `root_url`, `serve_from_sub_path`, `generic_oauth` con `role_attribute_path` por `roles`). Comprobar `private_key_jwt`; si Grafana no lo admite, decidir el método del cliente `grafana` en kind | U1: `platform/observability/values/kube-prometheus-stack*.yaml`. U2: `realm.kind.yaml` (cliente `grafana`), `realm-lint` si cambia el método | **DEC/EXT** (BR-U2-09, SECURITY-12) si cambia el método de autenticación | U11 (16.4), paso 13 del guion | `curl -sI --cacert ca.crt https://vectra.localtest.me/grafana/login` → 200 y redirección a `/auth/realms/vectra/protocol/openid-connect/auth?client_id=grafana` |
| **A8** | **Cerrar las ramas de U2**: empujar las rondas 4–5 y M5 de U02-T18 (local 3 por delante), cerrar U02-T15 (ronda 6) y U02-T17, y luego U02-T19 | Ramas `tarea/U02-T15`, `T17`, `T18`, `T19` | No (ya están decididas) | Requisito del Paso 16 | `git -C wt-U02-T18 status -sb` sin `ahead`; PRs fusionados; `make -C identity-edge check` en `main` |
| **A9** | **Marcar el Paso 16 en el plan de U2** con la clasificación de la sección 7 (DEMO: instalación, humo, Playwright reducido, `testssl`; DIFERIDO por RD3: PBT-U2-08, k6, sub-ítems 4, 5, 6, 7 y 8) y agregar `make -C identity-edge check-demo` (RD3) | `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md`, `identity-edge/Makefile`, cumplimiento de extensiones de U2 | Cubierto por RD3 (aprobación en bloque); registrarlo | U2 | `make -C identity-edge check-demo`; `grep -n "diferido (ruta demo)" aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` |
| **A10** | **Sincronizar `envoy-gateway` de U1** antes de U2 (controlador con `rateLimit` y overlay de kind) | — (ya está en `main`; es una acción del operador) | No | U2 (`envoy-ratelimit`) | `kubectl -n envoy-gateway-system get cm envoy-gateway-config -o yaml \| grep -A3 rateLimit` muestra `backend` |
| **A11** | **Eco del Paso 13**: borrarlo al terminar el Paso 16, o cambiar los nombres que comparte con U8 y U10 | `tests/e2e/echo/manifests.yaml`, `tests/e2e/README` o runbook | No | U8, U10 (choque de nombres) | `kubectl -n vectra-app get deploy case-service -o jsonpath='{.spec.template.spec.containers[0].image}'` no es `e2e-echo` antes del sync de U8 |
| A12 | (Opcional) Limit de memoria de Keycloak en kind (por ejemplo 1 GiB) o `MaxRAMPercentage` menor, para que su uso real se acerque a los 512 Mi de request | `keycloak/values/kind.yaml`, `keycloak.rego` | **DEC**: cambia M4 («los limits no cambian») | Memoria de toda la demo | `docker stats --no-stream` después del sync: Keycloak por debajo de 1 GiB |

Fuera de U2, para los dueños: el guion de `U10-U12.md`, paso 6, asigna la verificación de integridad a cumplimiento, pero el contrato la da solo a `cro` con MFA (sección 3.2).
