# Unidades de trabajo — Vectra Risk

Descomposición aprobada (`inception/plans/unit-of-work-plan.md`, respuestas Q1–Q8 = A):
**13 unidades**. Tres de ellas son transversales: U0 `contracts`, U5 `reference-model`
y U12 `system-verification`.

Cada unidad recorre en CONSTRUCTION las etapas de diseño que le apliquen (§2) y termina
con su **plan de tareas** (`aidlc-docs/construction/plans/{unit}-code-generation-plan.md`).
Ahí termina este trabajo.

Terminología: **Servicio** = componente desplegable independiente. **Módulo** =
agrupación lógica dentro de un servicio. **Unidad** = agrupación para planificar.

---

## 1. Definición de las unidades

### U0 — `contracts`
- **Propósito**: fijar primero los contratos compartidos para que el resto de las unidades se construya contra versiones publicadas.
- **Contenido**:
  - especificaciones **OpenAPI** de todas las APIs internas y del BFF (case, scoring, explainability, governance, bias, registry, core-banking-mock, console-bff);
  - paquete Python `vectra_contracts`: modelos Pydantic generados y tipos de dominio (`Recommendation`, `Explanation`, `FailClosed`, `MonitoringLabels`, `RegistryEntryIn`), con el **constructor de `Recommendation` que hace cumplir el invariante de sincronía**;
  - paquete Python `vectra_common`: logger JSON con **redacción de PII**, middleware de validación de JWT y scopes, propagación del correlation ID, handler global de errores genéricos y configuración de OpenTelemetry;
  - cliente TypeScript generado para la SPA;
  - **catálogo de scopes** de identidades de servicio (fuente para U2).
- **Datos propios**: ninguno.
- **Flujos**: ninguno propio; define los contratos de F10–F32.
- **Criticidad**: indirecta. Un error se propaga a todos los servicios.
- **Historias**: no es dueña de ninguna. Contribuye a US-111, US-602, US-604 y US-611.

### U1 — `platform-foundation`
- **Propósito**: la base de Kubernetes sobre la que corre todo, sin lógica de negocio.
- **Contenido**:
  - namespaces (§1 de `component-dependency.md`) y NetworkPolicy **deny-all** de ingress y egress por namespace;
  - operador de PostgreSQL y clusters para `case-db`, `governance-db`, `registry-db` y `keycloak-db`, con réplica síncrona multi-zona (F45), backups cifrados y WAL fuera del sitio (F70);
  - model-store;
  - instalación del controlador de KServe (K05);
  - observability stack: Prometheus, Alertmanager (con receptor F72), Grafana, Loki, Tempo, OTel Collector y agente de logs (F60–F65, K02, K03);
  - Argo CD con **sync manual** (K04, F71) y la estructura inicial del repositorio `vectra-risk-gitops`;
  - workflows reutilizables de GitHub Actions: pruebas con semilla de PBT, escaneo de dependencias e imágenes, SBOM, evidencia `helm template` y `kubectl diff`, y **verificación de pasos prohibidos** (`apply`/`install`/`sync`);
  - runbooks de restore y failover de zona.
- **Datos propios**: la infraestructura de las bases de datos (los esquemas pertenecen a cada unidad).
- **Flujos**: F45, F60–F67, F70–F72, F74–F76, F80–F88 (F09 opcional); K02–K13 (ver U1 Infrastructure Design).
- **Criticidad**: High. Todo depende de ella.
- **Historias (dueña)**: US-604 (base de red y egress), US-605, US-606, US-607, US-608, US-610.

### U2 — `identity-edge`
- **Propósito**: identidad y borde.
- **Contenido**:
  - **realm de Keycloak como código**: roles, MFA obligatorio para `ingeniero_riesgo`, `cro` y `cumplimiento`, protección contra fuerza bruta, clientes (SPA, Grafana e identidades de servicio con los scopes de U0) y consola de administración no expuesta;
  - **Envoy Gateway**: rutas F01–F07, validación de JWT, rate limiting, límite de payload, access log y cabeceras de seguridad de la SPA.
- **Datos propios**: el realm (en `keycloak-db`).
- **Flujos**: F01–F09 (F09 opcional), F43, F50 (destino), F73 (solo prod), F90–F95; K14; X09, X10 (ver U2 Infrastructure Design).
- **Criticidad**: High.
- **Historias (dueña)**: US-601, US-611.

### U3 — `decision-registry`
- **Propósito**: el registro append-only encadenado, que es el único componente Critical.
- **Contenido**: `decision-registry-service` (append serializado con hash encadenado, confirmación tras réplica síncrona, consultas filtradas por rol y scope, expediente, `verify_chain` como API, CLI y CronJob); esquema y migraciones de `registry-db`; roles `registry_app` (solo `INSERT`/`SELECT`) y `registry_migrator`.
- **Datos propios**: `registry-db`.
- **Flujos**: F42, F44 (migración), F96, F97, F98 (solo kind); egress F77, F78, F79, F99; destino de F13, F16, F21, F23, F24, F26 y F28; X06 (ver U3 Infrastructure Design).
- **Criticidad**: **Critical**.
- **Historias (dueña)**: US-401, US-402, US-403, US-404.

### U4 — `governance`
- **Propósito**: gobierno de modelos, políticas y fuentes de datos.
- **Contenido**:
  - `governance-service`: máquina de estados del modelo, aprobaciones del CRO y de cumplimiento con MFA, transiciones acotadas por identidad (`freeze` solo para bias; salida de `congelado` solo para cumplimiento), políticas versionadas (con parámetros normativos VIS/usura con vigencia), fuentes de datos y `serving-config`;
  - esquema de `governance-db`;
  - `model-validation-job`;
  - CLI `promotion-tool`, que genera un PR de un solo commit con evidencia en `vectra-risk-gitops`.
- **Datos propios**: `governance-db`.
- **Flujos**: F11, F18, F24, F25, F27, F32 (destino), F41, F47, F101, F102, F103 y F104 (destino; U7 FD Q4 y U8 FD Q1); egress F100; **K01**; X03, X04 (ver U4 Infrastructure Design).
- **Criticidad**: High.
- **Historias (dueña)**: US-201, US-202, US-203, US-204, US-205, US-206, US-208, US-305.

### U5 — `reference-model`
- **Propósito**: hacer de "banco que entrega su modelo". Queda **fuera de la frontera del producto** (el PRD dice que el banco entrena fuera de Vectra Risk).
- **Contenido**:
  - generador de **dataset sintético** con forma de crédito de vivienda colombiano: ingreso, cuota/ingreso, valor de vivienda para VIS, tasa, canal, atributos de monitoreo y texto libre;
  - **variante con variables proxy** para RT-2;
  - entrenamiento gradient boosting y empaquetado del **predictor + explainer SHAP** en formato KServe, con `model_version_id` y checksum;
  - dataset de validación;
  - **conjunto adversarial curado de 30–50 casos**: RT-1 (inyección en texto), RT-4 (fuera de dominio) y artefactos de versión desincronizada para RT-3.
- **Datos propios**: datasets sintéticos y artefactos versionados.
- **Flujos**: ninguno en runtime. Entrega sus artefactos por el flujo de registro de U4.
- **Historias**: no es dueña de ninguna. Contribuye a US-106, US-109, US-111, US-201, US-202 y US-303.

### U6 — `model-serving`
- **Propósito**: servir predictor y explainer **en la misma revisión** (Q6 de Application Design).
- **Contenido**: chart y plantilla del `InferenceService` (RawDeployment, predictor + explainer, `storageUri`, anotación de `model_version_id`) para prod (`vectra-serving`) y staging (`vectra-staging`); escalado de KServe con mínimo y máximo; probes; NetworkPolicies de destino F19, F22 y F30; plantilla que consume `promotion-tool`.
- **Datos propios**: ninguno.
- **Flujos**: F46; destino de F19, F22 y F30; X08.
- **Criticidad**: High.
- **Historias**: no es dueña de ninguna. Contribuye a US-111 (sincronía por plataforma), US-204 (plantilla atómica) y US-609 (escalado de KServe).

### U7 — `scoring-explainability`
- **Propósito**: producir la recomendación usable o un fail-closed. Son **dos servicios en una unidad** (Q2).
- **Contenido**:
  - `scoring-service`: lectura de `serving-config` con TTL, predictor, **motor de política** (corte, baja confianza, reglas VIS/usura), llamada a la explicación, verificación de versión, append al registro antes de responder, circuit breakers y `FailClosed` tipificado;
  - `explainability-service`: vector SHAP del explainer, `TemplateNarrativeGenerator`, `FactualityValidator`, interfaz `NarrativeGenerator` y resumen para el solicitante.
- **Datos propios**: ninguno (stateless).
- **Flujos**: F12 (destino), F15 (destino), F18–F23; sin egress (X02); sin acceso al core (X01).
- **Criticidad**: High.
- **Historias (dueña)**: US-103, US-104, US-105, US-106, US-109, US-110, US-111, US-113, US-207.

### U8 — `case-management`
- **Propósito**: ciclo de vida del caso y la frontera con el core bancario.
- **Contenido**:
  - `case-service`: ingesta, alta manual, estados, cola transaccional de reintentos con backoff, escalamiento (métrica `FailClosedPersistente` y lista para el CRO), decisión humana con justificación estructurada, eventos de consulta de la explicación y lectura del estado del crédito;
  - esquema de `case-db`;
  - `core-banking-mock`: `GET` de estado de crédito, y una ruta de escritura que **existe solo para demostrar el bloqueo RT-5**.
- **Datos propios**: `case-db` (PII), estado de crédito simulado.
- **Flujos**: F04, F10 (destino), F15, F16, F17, F40, F44, F104 (U8 FD Q1); X01.
- **Criticidad**: High.
- **Historias (dueña)**: US-101, US-102, US-107, US-108, US-112, US-501, US-502, US-603.

### U9 — `bias-monitoring`
- **Propósito**: medir, alertar y congelar, sin certificar.
- **Contenido**: `bias-monitoring-service` y su CronJob; librería de disparidad por banda de capacidad de pago y agregada (validada contra el oráculo de Fairlearn; también la usa el validation-job de U4); disparidad de decisiones humanas (sin congelar); evaluación de umbral y `freeze` vía governance; paquete de contexto; `compare_source`; API del dashboard; métrica del último cálculo y alerta `MonitoreoSesgoDetenido`.
- **Datos propios**: ninguno (lee el registro).
- **Flujos**: F14 (destino), F25 (destino), F26, F27; sin egress (X02); X04.
- **Criticidad**: High.
- **Historias (dueña)**: US-301, US-302, US-303, US-304, US-306, US-307, US-308.

### U10 — `console`
- **Propósito**: la experiencia de las cuatro personas que operan el sistema.
- **Contenido**:
  - `console-bff`: 29 endpoints con rol, MFA y regla de objeto (tabla de `component-methods.md`), propagación del token y errores genéricos;
  - `console-spa`: bandeja, detalle, decisión con factores, aprobaciones, congelados, dashboards embebidos de Grafana, i18n en español y **lint de frases prohibidas** ("sin sesgo" y similares).
- **Datos propios**: ninguno.
- **Flujos**: F02 y F03 (destino), F10–F14.
- **Criticidad**: High (BFF) y Medium (SPA).
- **Historias (dueña)**: US-602. Contribuye a otras 22 historias (lista en `unit-of-work-story-map.md` §1).

### U11 — `product-metrics`
- **Propósito**: saber si la explicación se usa de verdad.
- **Contenido**: servicio `product-metrics` (North Star, tasa de consulta de la explicación, tasa sostenida por el comité, tiempo de originación); recording y alerting rules (`RuidoExplicacion`); dashboards de producto en Grafana como código.
- **Datos propios**: ninguno (lee el registro).
- **Flujos**: F28, F60 (origen del scrape).
- **Criticidad**: Medium.
- **Historias (dueña)**: US-503, US-504, US-505.

### U12 — `system-verification`
- **Propósito**: verificar lo que cruza unidades (Q8).
- **Contenido**:
  - `channel-simulator` en modo normal y adversarial (F07);
  - **suite e2e de RT-1..5**;
  - **pruebas negativas de X01–X10**;
  - prueba de **carga simulada** (US-609);
  - scripts de las **demos de la Sesión 16**: journey 7.3, journey 7.4, RT-5 y dashboard;
  - informe de verificación que junta evidencias.
- **Datos propios**: ninguno (usa los datasets de U5).
- **Criticidad**: Low en runtime; alta como puerta de calidad.
- **Historias (dueña)**: US-609. Verifica de extremo a extremo US-101, 106, 109, 111, 303, 305, 603 y 604.

---

## 2. Etapas de CONSTRUCTION por unidad

✔ = se ejecuta · ✖ = se omite (con justificación). El **plan de tareas** (Code Generation
Part 1) se ejecuta **siempre** en las 13 unidades.

| Unidad | Functional Design | NFR Requirements | NFR Design | Infrastructure Design | Justificación de omisiones |
|---|---|---|---|---|---|
| U0 contracts | ✔ | ✔ | ✔ | ✖ | Librerías y especificaciones, nada desplegable |
| U1 platform-foundation | ✖ | ✔ | ✔ | ✔ | Sin lógica de negocio: backups, redes y GitOps son decisiones de NFR e infraestructura |
| U2 identity-edge | ✔ | ✔ | ✔ | ✔ | — (FD: modelo de roles, scopes y MFA) |
| U3 decision-registry | ✔ | ✔ | ✔ | ✔ | — |
| U4 governance | ✔ | ✔ | ✔ | ✔ | — |
| U5 reference-model | ✔ | ✔ | ✖ | ✖ | Herramienta offline fuera del producto: no tiene runtime ni despliegue propio; sus artefactos entran por U4 |
| U6 model-serving | ✖ | ✔ | ✔ | ✔ | Sin lógica de negocio: configura cómo KServe sirve lo que U5 produce |
| U7 scoring-explainability | ✔ | ✔ | ✔ | ✔ | — |
| U8 case-management | ✔ | ✔ | ✔ | ✔ | — |
| U9 bias-monitoring | ✔ | ✔ | ✔ | ✔ | — (FD resuelve NFR-RES-11 / US-308) |
| U10 console | ✔ | ✔ | ✔ | ✔ | — |
| U11 product-metrics | ✔ | ✔ | ✔ | ✔ | — |
| U12 system-verification | ✔ | ✔ | ✖ | ✔ | El arnés de verificación no es carga de producción; la ejecución en kind se define en Infrastructure Design |

La pregunta obligatoria de RESILIENCY-14 (enfoque de pruebas de resiliencia) se hace en
el NFR Design de **U1**, que es la primera unidad que ejecuta NFR Design sobre la
plataforma. Su respuesta aplica a todas las unidades.

---

## 3. Organización del código y de los repositorios (Q4 = A)

Patrón greenfield multi-servicio (`{unit-name}/src/`, `{unit-name}/tests/`). Raíz del
workspace:
`/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk`.

### 3.1 Monorepo de aplicación (workspace root)

```text
vectra-risk/
|-- contracts/                    # U0
|   |-- openapi/                  #   specs por servicio
|   |-- python/vectra_contracts/  #   modelos generados + tipos de dominio
|   |-- python/vectra_common/     #   logger sin PII, authz, correlación, errores, OTel
|   |-- ts/                       #   cliente TypeScript generado
|   `-- tests/
|-- platform/                     # U1
|   |-- charts/                   #   namespaces, netpol base, postgres, model-store, observabilidad, argocd
|   |-- ci/                       #   workflows reutilizables
|   |-- runbooks/
|   `-- tests/
|-- identity-edge/                # U2
|   |-- keycloak/                 #   realm como código
|   |-- gateway/                  #   Envoy Gateway
|   `-- tests/
|-- decision-registry/            # U3
|   |-- src/  tests/  migrations/  chart/
|-- governance/                   # U4
|   |-- src/  tests/  migrations/  chart/
|   |-- validation-job/
|   `-- promotion-tool/
|-- reference-model/              # U5
|   |-- src/  tests/  datasets/
|-- model-serving/                # U6
|   |-- chart/  tests/
|-- scoring-explainability/       # U7
|   |-- scoring-service/{src,tests}/
|   |-- explainability-service/{src,tests}/
|   `-- chart/
|-- case-management/              # U8
|   |-- case-service/{src,tests,migrations}/
|   |-- core-banking-mock/{src,tests}/
|   `-- chart/
|-- bias-monitoring/              # U9
|   |-- src/  tests/  chart/
|-- console/                      # U10
|   |-- bff/{src,tests}/
|   |-- spa/{src,tests}/
|   `-- chart/
|-- product-metrics/              # U11
|   |-- src/  tests/  rules/  dashboards/  chart/
|-- system-verification/          # U12
|   |-- simulator/  e2e/  negative/  load/  demos/
|-- .github/workflows/            #   usa platform/ci
`-- aidlc-docs/                   #   SOLO documentación
```

### 3.2 Repositorio GitOps separado: `vectra-risk-gitops`

```text
vectra-risk-gitops/
|-- apps/            # Applications de Argo CD (sin syncPolicy.automated)
|-- environments/
|   |-- staging/     # values por unidad + InferenceServices de staging
|   `-- prod/        # values por unidad + InferenceService activo
`-- README.md        # proceso de cambio: PR + evidencia + aprobación + sync manual
```

- Solo contiene values y manifiestos desplegables que referencian imágenes por digest y charts versionados del monorepo.
- Tienen permiso de merge solo los aprobadores de despliegue (separación de funciones, SECURITY-13). `promotion-tool` abre PRs aquí; **nunca** hace merge ni sync.
- Argo CD solo lee este repositorio (F71).

---

## 4. Mapa a los módulos del curso (Q6 = A)

El orden de construcción es por dependencias (ver `unit-of-work-dependency.md`). Cada
unidad se **demuestra** en el módulo indicado.

| Módulo (PRD §13) | Unidades que lo sostienen | Qué se demuestra |
|---|---|---|
| 4-5 (K8s / CKA) | U1, U3, U5, U6, U7 | Clúster reproducible, persistencia, KServe sirviendo el modelo de referencia, explainability **con fail-closed activo** (corrección Q1 de requisitos) |
| 6 (CKAD) | U2, U4, U8, U10 | Consolas, gateway con RBAC por rol, ConfigMaps y Secrets, primeras NetworkPolicies por servicio |
| 7 (CKS) | U1 (endurecimiento), U2, U12 (X01–X10, RT-5) | RBAC de solo lectura sobre crédito, NetworkPolicies completas, cifrado, admisión y escaneo de imágenes |
| 8 (producción) | U1 (GitOps), U4 (flujo del CRO), U9, U11, U12 (carga) | GitOps con sync manual, aprobación del CRO en el pipeline, freeze continuo, métricas y autoscaling bajo carga simulada |
| Sesión 16 | U12 | Demos 7.3, 7.4, RT-5 y dashboard (North Star y ruido) |
