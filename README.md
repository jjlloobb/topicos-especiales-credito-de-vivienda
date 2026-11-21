# Vectra Risk
Grupo: `<integrantes>` | Fecha de presentación: sábado 28 de noviembre de 2026

Motor de scoring de crédito de vivienda explicable y auditable, que corre dentro del clúster del propio banco. Proyecto final de Tópicos Especiales en Informática (Maestría en Ingeniería de Sistemas, Pontificia Universidad Javeriana).

> **Qué está construido y qué no.**
> - **Hecho:** las 13 unidades del diseño (U0 a U12) tienen código en [`vectra-risk/`](vectra-risk/). El sistema completo corre en un clúster kind de tres nodos, en un portátil de 14,8 GiB.
> - **Medido:** tres de las cuatro demos pasaron contra ese clúster el 20 y 21 de noviembre de 2026. La cuarta (el tablero de producto) tenía su lectura pendiente al escribir este README.
> - **No hecho:** staging y producción no se desplegaron nunca. No hay servidores MCP. Los datos y el modelo son sintéticos. No hay un banco usándolo.
>
> Es un producto hipotético de curso. Cada cifra de abajo apunta a un archivo, un comando o un pull request.

---

## 1. Problema

**Usuario.** El área de riesgo de un banco colombiano que origina crédito de vivienda. Decide el VP de Riesgo (CRO), el oficial de cumplimiento tiene veto y el analista del comité de crédito lo usa ([`icp.md`](vectra-risk/entradas/icp.md)).

**Qué le duele hoy.**
- **El scoring vive en un notebook, no en producción.** Ya hay modelos con hasta 88,29 % de AUC-ROC sobre datos de mora colombianos ([Redalyc](https://www.redalyc.org/journal/5537/553768213005/html/); la fecha de publicación está pendiente de verificar). El problema no es predecir mejor: es servir la predicción con trazabilidad.
- **Explicar un rechazo exige reconstruirlo a mano.** La explicación no es parte del contrato del modelo.
- **El comité no aprueba lo que no puede defender.** SHAP, LIME, AIF360 y Fairlearn son gratis, pero no dicen quién audita, cómo se versiona el modelo ni qué pasa cuando el modelo se sesga.

**Cómo lo resuelve hoy.** Motor de reglas, modelo en notebook, librerías ensambladas por cuenta propia, un vendor (Zest AI dentro de Temenos) o delegar la originación en LQN ([`prd.md`](vectra-risk/entradas/prd.md), 2.3). No encontramos una cifra pública de cuánto le cuesta, y no la inventamos.

**Métricas** ([`pvb.md`](vectra-risk/entradas/pvb.md), sección 8; todas son proyecciones propias, marcadas `[INTERNO]`):
- Decisión con score explicado en menos de 1 hora en el 80 % de los casos estándar.
- Más del 70 % de decisiones del modelo sostenidas por el comité al mes 6.
- Disparidad de aprobación entre grupos protegidos por debajo de 5 puntos; si se supera, el modelo se congela.

Las dos primeras tienen serie y panel en `vectra-risk/product-metrics/`; la tercera la mide el `CronJob` de `vectra-risk/bias-monitoring/`. Ninguna está validada con un banco: los datos son sintéticos (`vectra-risk/reference-model/config/generator.yaml`).

**Qué cambió desde el PVB.** La crítica ([`critica.md`](vectra-risk/entradas/critica.md), sección 8) mostró que explicabilidad y monitoreo de sesgo ya son estándar del mercado. El moat se movió hacia la soberanía del dato y el conocimiento normativo local, y se añadió una métrica: si la explicación **cambia** decisiones o solo las justifica después.

**Qué cambió desde el PRD (decisiones de alcance).**
- Solo kind. Staging y producción tienen manifiestos, pero no se despliegan (`vectra-risk/aidlc-docs/construction/plans/demo-kind-alcance.md`).
- Se recortó por funcionalidad: lo que no sostiene una de las cuatro demos quedó diferido, con su lista (`vectra-risk/aidlc-docs/construction/plans/demo-recorte-funcional.md`).
- Seis secciones de la verificación responden «no ejecutado»: red, carga, PII, resiliencia, RT-1 y RT-4 ([`system-verification/README.md`](vectra-risk/system-verification/README.md)).

---

## 2. Arquitectura en Kubernetes

### Diagrama

```mermaid
flowchart TB
    subgraph EST["Estación de trabajo"]
        direction TB
        subgraph LOOP["Loop de agentes: una sesión de Claude Code"]
            ORQ["Orquestador"] --> COD["Codificador<br/>worktree propio"]
            COD --> REV["Revisor<br/>sin edición"]
        end
        MCP["Servidores MCP: ninguno<br/>herramientas nativas + reglas deny"]
        PT["promotion-tool<br/>sesión de ingeniero con MFA"]
        PERS(["Persona: aprueba, fusiona<br/>y ordena el sync"])
    end

    subgraph GH["GitHub"]
        PR["Pull request<br/>con evidencia + CI"]
        MAIN[("main<br/>charts, values, Applications")]
    end

    subgraph K8S["Clúster kind-vectra, 3 nodos"]
        API["API de Kubernetes<br/>RBAC + Kyverno + Pod Security"]
        ARGO["Argo CD<br/>56 Applications, sin auto-sync"]
        subgraph APP["Aplicación"]
            direction LR
            GW["Envoy Gateway<br/>+ Keycloak"] --> CASE["case-service<br/>case-worker"]
            GW --> CON["Consola<br/>SPA + BFF"]
            CASE --> SCO["scoring +<br/>explainability"]
            SCO --> KS["KServe<br/>predictor + explainer"]
            SCO --> REG["decision-registry"]
            SCO --> GOV["governance"]
            BIAS["CronJob de sesgo"] --> GOV
        end
        PLAT["Plataforma: Linkerd mTLS, NetworkPolicy,<br/>CloudNativePG, MinIO, Vault + ESO, Prometheus"]
    end

    REV -->|VERDE| PR
    PT --> PR
    PR --> PERS
    PERS -->|fusiona| MAIN
    MAIN -->|pull| ARGO
    PERS -->|"argocd app sync"| ARGO
    ARGO -->|aplica| API
    API --> APP
    API --> PLAT
    LOOP -.->|"solo get, list, watch<br/>SA vectra-readonly-agent"| API
    MCP -.- LOOP
```
*Figura: los agentes terminan en un pull request. Una persona fusiona y una persona ordena el sync. La línea punteada es lo único que los agentes pueden hacer contra el clúster: leer.*

### Qué objeto implementa cada pieza

Cada pieza llega al clúster por una `Application` de Argo CD. Hay 56, más un `AppProject`, en [`vectra-risk/vectra-risk-gitops/apps/kind/`](vectra-risk/vectra-risk-gitops/apps/kind/), repartidas en 7 waves (0 a 6). Ninguna tiene `syncPolicy.automated`.

| Pieza (unidad) | Objetos de Kubernetes | Manifiesto |
|---|---|---|
| Namespaces y Pod Security (U1) | `Namespace` con `pod-security.kubernetes.io/enforce: restricted` | `vectra-risk/platform/namespaces/` |
| Admisión (U1) | 19 `ClusterPolicy` de Kyverno: sin `latest`, sin privilegiados, sin `hostPath`, sin comodines en RBAC, sin auto-sync, registros permitidos | `vectra-risk/platform/policies/kyverno/` |
| Red y malla (U1) | `NetworkPolicy`, y `Server` y `AuthorizationPolicy` de Linkerd, generados desde una lista de 119 flujos | `vectra-risk/platform/network/flows.yaml` |
| Datos (U1) | `Cluster` de CloudNativePG; MinIO con object lock | `vectra-risk/platform/data/` |
| Secretos (U1) | `ExternalSecret` y `ClusterSecretStore` contra Vault | `vectra-risk/platform/secrets/` |
| Observabilidad (U1) | `PrometheusRule`, `ServiceMonitor`, Pushgateway, runbooks | `vectra-risk/platform/observability/` |
| Identidad y borde (U2) | Keycloak, Valkey (`StatefulSet`), Envoy Gateway (`Gateway`, `HTTPRoute`, `SecurityPolicy`), rate limit | `vectra-risk/identity-edge/` |
| Registro de decisiones (U3) | `Deployment`, `HorizontalPodAutoscaler`, `PodDisruptionBudget`, `CronJob`, `Job` | `vectra-risk/decision-registry/chart/` |
| Gobierno de modelos (U4) | `Deployment`, `Job` de validación, `Role` y `RoleBinding`, `ExternalSecret` | `vectra-risk/governance/chart/` |
| Servicio del modelo (U5, U6) | `InferenceService` de KServe (predictor y explicador), `PodDisruptionBudget` | `vectra-risk/model-serving/chart/` |
| Scoring y explicación (U7) | `Deployment`, `HorizontalPodAutoscaler`, `PodDisruptionBudget` | `vectra-risk/scoring-explainability/chart/` |
| Casos y mock del core bancario (U8) | 3 `Deployment`, `Job` de migración, `PrometheusRule` | `vectra-risk/case-management/chart/` |
| Monitoreo de sesgo (U9) | `CronJob`, `Deployment` | `vectra-risk/bias-monitoring/chart/` |
| Consola web (U10) | 2 `Deployment` (SPA y BFF) | `vectra-risk/console/chart/` |
| Métricas de producto (U11) | `Deployment`, `PrometheusRule`, tablero de Grafana en `ConfigMap` | `vectra-risk/product-metrics/chart/` |
| Identidad de los agentes (U1) | `ServiceAccount`, `ClusterRole`, `ClusterRoleBinding` | [`readonly-agent-kind.yaml`](vectra-risk/platform/rbac/readonly-agent/readonly-agent-kind.yaml) |

U0 (`vectra-risk/contracts/`) son los contratos compartidos y U12 (`vectra-risk/system-verification/`) es la herramienta de verificación: corre fuera del clúster y solo lee.

### Seguridad, con evidencia

**RBAC de mínimo privilegio: qué puede hacer la cuenta de los agentes.** Salida real del 21 de noviembre de 2026, completa en [`can-i-list-agente.txt`](vectra-risk/aidlc-docs/construction/system-verification/evidence/sustentacion/can-i-list-agente.txt) y [`can-i-puntuales-agente.txt`](vectra-risk/aidlc-docs/construction/system-verification/evidence/sustentacion/can-i-puntuales-agente.txt):

```text
$ kubectl auth can-i --list --as=system:serviceaccount:argocd:vectra-readonly-agent
pods                         [get list watch]
deployments.apps             [get list watch]
applications.argoproj.io     [get list watch]
...                          (todas las filas de recursos: get list watch)

create pods: no        delete pods: no       patch deployments: no
create secrets: no     get secrets: no
get pods: yes          list applications.argoproj.io: yes
```

- El `ClusterRole` no tiene comodines, ni `secrets`, ni `pods/exec`, ni un solo verbo de escritura. No se reutilizó el rol `view` porque su contenido lo decide cualquier chart.
- Los agentes corren con un kubeconfig que solo conoce esa identidad ([`readonly-kubeconfig.md`](vectra-risk/platform/kind/readonly-kubeconfig.md)).
- **Por qué existe.** El 16 de noviembre de 2026 la regla «los agentes no tocan el clúster» era solo una instrucción, y falló dos veces: dos pruebas leyeron `Secret` del clúster real y una prueba ejecutó una guía que borró cuatro `Deployment`. Desde entonces el límite es RBAC, no una frase.

**Pod Security y admisión.** Los namespaces `vectra-*` llevan `enforce: restricted`. Kyverno rechaza `latest` (`vectra-risk/aidlc-docs/construction/platform-foundation/evidence/simulacro-latest.txt`) y MinIO rechaza borrar un objeto bloqueado (`simulacro-objeto-bloqueado.txt`, misma carpeta).

**Red.** `linkerd check` y la conformidad del CNI están en esa carpeta de evidencia de U1 (2 de noviembre). En la demo D3 la malla respondió 403 a un intento de escribir en el core del banco.

**Lo que falta en seguridad.**
- El kubeconfig de solo lectura no cubre `argocd` ni `docker`: eso lo frenan las reglas `deny` de [`.claude/settings.json`](.claude/settings.json), que son de la herramienta, no del clúster.
- External Secrets lee todos los `Secret` en kind (K11). La corrección para staging y producción se decidió y no se implementó (issue 28, cerrado sin hacer).
- Imágenes sin firma, SBOM ni escaneo en la herramienta de verificación (diferido).
- Vault corre en modo dev: guarda todo en memoria.

### El bucle GitOps funcionando

Un cambio real, el PR #233 del 21 de noviembre: `promotion-tool` propone promover una versión de modelo; CI pasa; una persona aprueba (09:53:57 UTC) y fusiona (10:00:31, commit `81b5fd3`); se ordena `argocd app sync model-serving`; a las 10:02:15 el clúster tiene la versión nueva `activo` y la anterior `inactivo`, sin que el modelo en servicio bajara de 2 réplicas. El rollback fue otro PR (#237). Paso a paso, con las trece fusiones de ese día: [`bucle-gitops.md`](vectra-risk/aidlc-docs/construction/system-verification/evidence/sustentacion/bucle-gitops.md).

### La aplicación corriendo: cuatro demos medidas

Corridas contra `kind-vectra` el 20 y 21 de noviembre, con 56 Applications: todas `Healthy` y 2 `OutOfSync` conocidas (`02-sync-y-arranque.md`). Evidencia en las plantillas de [`evidence/kind/`](vectra-risk/aidlc-docs/construction/system-verification/evidence/kind/); la versión llena está en el PR #236 (rama `verificacion/20261120-9dc027f`), abierto al escribir esto.

| Demo | Qué demuestra | Resultado medido | Plantilla |
|---|---|---|---|
| D3 | El sistema no puede escribir en el core del banco (RT-5) | Linkerd deniega con 403. Alerta `CoreWriteAttempt` en `firing` de 01:12:50 a 01:16:56 UTC. Contador del mock en 0. **Pasa** | `05-prepare-y-d3.md` |
| D1 | Sin explicación no hay recomendación (RT-3) | Con el flujo F22 apagado por un PR: 0 recomendaciones, 5 casos escalan a «No disponible» en unos 16 min, alerta `FailClosedPersistente`. **Pasa** en la repetición, tras corregir un oráculo | `07-d1-rt3.md` |
| D2 | Un modelo con sesgo se congela solo (RT-2) | Lote de 1 500 solicitudes. El `CronJob` midió disparidad por región de 0,2438 contra un límite de 0,1418 y congeló el modelo a las 10:17:17 UTC. Latencia de detección: 520,7 s (límite 1 800 s). Reactivación y rollback por PR. Corrida completa: 1 h 38 min 35 s. **Pasa**. El modo de reactivación «presenter» no se ejecutó | `08-d2-rt2.md` |
| D4 | Tablero de producto | 2 000 solicitudes enviadas, aceptadas y decididas en 15 min 28 s. La lectura del tablero es al día UTC siguiente y **estaba pendiente** al escribir este README | `06-decisions-d4.md`, `09-d4-u11-y-grafana.md` |

La verificación encontró defectos reales (hallazgos H-1 a H-12) y cada uno se corrigió con su PR: #223 (puerta de memoria), #225 (el Job de sesgo fallaba contra Pushgateway por una etiqueta `group`), #229 (dos oráculos suponían mal cómo responde Linkerd), #242 y #243 (la consola perdía los enlaces directos al pasar por el login). La consola tiene tema nuevo y diseño responsive desde el PR #235; el tema del login de Keycloak (PR #241) aún no está activo en kind (PR #244, en borrador).

---

## 3. Loop de agentes

Es el loop del módulo 6. Contratos en [`.claude/agents/`](.claude/agents/) y [`vectra-risk/loop/`](vectra-risk/loop/README.md).

| Papel | Qué recibe | Qué decide | Herramientas (`tools:`) |
|---|---|---|---|
| Orquestador (sesión principal) | El plan de la unidad y la ruta de cada tarea con su hash | Qué despachar, cómo arbitrar un empujón, cuándo abrir el PR | No escribe código ni juzga |
| Codificador (`sonnet`) | La ruta de la tarea, su worktree y, en retrabajo, el informe del revisor | Cómo implementar, con la prueba en rojo antes del verde | `Bash, Read, Edit, Write, Grep, Glob` |
| Revisor (`opus`) | El worktree y la bitácora | VERDE o NO-VERDE, con hallazgos ROJO, NARANJA o AMARILLO | `Bash, Read, Grep, Glob` (sin edición) |

**Herramientas permitidas y prohibidas. No hay servidores MCP ni allowlist de MCP.** La guía los pide y no los construimos. Lo que cumple esa función son cuatro capas:

1. La lista `tools:` de cada agente (tabla de arriba): el revisor no puede editar.
2. 32 patrones `deny` en [`.claude/settings.json`](.claude/settings.json): `kubectl apply`, `create`, `delete`, `patch`, `scale` y `rollout`; `helm install` y `upgrade`; `argocd app sync`; `docker start` y `stop`; `kind create` y `delete`.
3. El kubeconfig de solo lectura.
4. El RBAC de `vectra-readonly-agent` (sección 2). Es la única capa que no depende de la herramienta.

**Cómo verifica su trabajo.** Cada criterio de aceptación es un comando. El revisor corre los comandos él mismo, reproduce el rojo y aplica mutaciones para comprobar que las pruebas detectan errores.

**Cuándo se detiene.**
- A las 4 rondas, el loop para y lleva la tarea a la persona. Para la demo el tope bajó a 2 rondas, y solo un ROJO bloquea (reglas RL-1 a RL-5, [`DECISIONES-LOOP.md`](vectra-risk/DECISIONES-LOOP.md), §5).
- No despacha si hay más de 5 PR esperando revisión. Máximo 3 codificadores en paralelo.
- Nunca fusiona y nunca aprueba.

**Dónde termina la cadena.** En un pull request con la bitácora, todas las rondas y una nota de rollback. Una persona lo revisa y lo fusiona.

**Resultado** (contado en el repositorio el 21 de noviembre de 2026):

| Qué | Cuánto | Dónde |
|---|---|---|
| Tareas | 114, de U0 a U12 | `vectra-risk/tareas/` |
| Bitácoras | 113 | `vectra-risk/bitacoras/` |
| Informes de ronda | 210, en 113 carpetas; 119 con veredicto NO-VERDE | `vectra-risk/revisiones/` |
| Arbitrajes del orquestador | 69 | `vectra-risk/revisiones/*/arbitraje-*.md` |
| Tareas con 3 rondas o más | 23; la más larga, `U02-T04`, con 6 | `vectra-risk/revisiones/U02-T04/` |
| Pull requests fusionados | 231; 213 los fusionó una segunda persona y 18 el autor (los PR 1 a 20 y el 216) | `gh pr list --state merged` |
| Trabajo fuera de alcance, anotado | 934 líneas | [`CANDIDATAS.md`](vectra-risk/CANDIDATAS.md) |

La tarea que falta en bitácoras y revisiones es `U03-T07`: se aparcó tras dos rondas sin llegar a PR.

**Casos en que el agente falla o es frenado.**
- **Frenado por RBAC:** `create pods: no`, `get secrets: no` (sección 2).
- **Falló antes de que existiera el RBAC:** el 16 de noviembre un proceso lanzado por un agente borró cuatro `Deployment` de kind. De ahí salió la tarea `U01-T17`.
- **Frenado por su alcance:** en `U01-T04` el codificador encontró el defecto en un archivo prohibido, no lo tocó, dejó la prueba en rojo y pidió decisión (`vectra-risk/revisiones/U01-T04/arbitraje-ronda-1.md`).
- **Frenado por el revisor:** en `U01-T03` la prueba pasaba con los puertos cruzados; el revisor lo demostró con 3 mutaciones.
- **La regla `deny` se puede esquivar:** el orquestador ejecutó `$K delete …` y la regla no lo reconoció, porque la orden iba tras una variable. Tenía autorización, y lo informó al notarlo ([`DECISIONES-LOOP.md`](vectra-risk/DECISIONES-LOOP.md), §11).

**AUTONOMIA-01 fue una regla bloqueante, no una promesa.** «El agente propone, una persona aprueba» es una extensión activa desde el inicio, sin opción de desactivarla ([`aidlc-state.md`](vectra-risk/aidlc-docs/aidlc-state.md)). Está citada por su ID en el diseño, en 33 tareas y en `vectra-risk/aidlc-docs/audit.md`.

**Límites que declaramos.**
- **Una sola sesión.** Los tres papeles corrieron en una sesión de Claude Code, con subagentes de contexto propio. No son tres procesos independientes ([`DECISIONES-LOOP.md`](vectra-risk/DECISIONES-LOOP.md), «Límites que declaro»).
- **El orquestador operó el clúster kind.** Desde el 14 de noviembre, con aprobación de la persona orden por orden, y con los patrones `deny` pasados a `ask` solo en su copia local. Codificadores y revisores conservaron `deny` (mismo documento, §11). La tesis «el agente no aplica por su cuenta» se sostiene; «el agente nunca aplica» no.
- **Fusiones antes de terminar la revisión.** Siete PR se fusionaron con CI en verde antes de que su revisor entregara (mismo documento, §11).
- **Demo en vivo y grabación.** Los guiones de la demo están en `vectra-risk/system-verification/demos/`. En el repositorio no hay una grabación de respaldo.

---

## 4. Comparación

Los datos de terceros llevan su fuente. Donde no hay dato público, lo decimos. Las mediciones propias están marcadas y son de un portátil, no de producción.

| Alternativa | Tiempo | Seguridad y soberanía del dato | Costo | Esfuerzo de adopción |
|---|---|---|---|---|
| **A mano: modelo en notebook y scripts** | Sin dato público | El dato se queda en el banco, pero sin trazabilidad ni explicación en producción ([`prd.md`](vectra-risk/entradas/prd.md), 2.3) | Solo personal; sin cifra pública | Bajo para empezar, alto para auditar |
| **Ensamblar librerías libres** (SHAP, LIME, AIF360, Fairlearn, KServe) | Sin dato público | Self-hosted. La orquestación y la auditoría quedan a cargo del banco | Sin costo de licencia ([AIF360](https://aif360.res.ibm.com/), [KServe en la CNCF](https://www.cncf.io/blog/2025/11/11/kserve-becomes-a-cncf-incubating-project/)) | Alto: integrar y mantener todo |
| **Zest AI dentro de Temenos** | Sin dato público de tiempo de decisión. Integración nativa anunciada el 29 abr 2025 ([Zest AI](https://www.zest.ai/company/announcements/zest-ais-credit-decisioning-and-fraud-detection-now-seamlessly-integrated-with-temenos-loan-origination-solution/)) | Self-hosted en LATAM: **sin verificar** con el vendor | Sin precio público | Bajo si el banco ya usa Temenos |
| **FICO Platform** | Un cliente implementa estrategias de riesgo 50 % más rápido que hace 5 años ([EmpreFinanzas, ago 2026](https://emprefinanzas.com.mx/2026/08/13/la-inteligencia-artificial-en-la-transformacion-bancaria-la-brecha-real-no-es-la-tecnologia-sino-la-confianza-a-gran-escala/)). **Fuente secundaria, pendiente de verificar** contra la primaria | Despliegue en el cliente: **sin verificar** | Sin precio público | Proyecto enterprise |
| **Delegar en LQN Hipotecas** | Sin cifra verificada | El modelo y la decisión viven fuera del banco | Sin dato público. LQN: 80.000+ operaciones y US$12M de capital ([Forbes Colombia](https://forbes.co/2025/11/06/emprendedores/lqn-recibe-us12-millones-para-lanzar-creditos-con-garantia-hipotecaria)) | Bajo para el banco, pero cede la decisión |
| **Vectra Risk** | **Medición propia, en kind:** 2 000 solicitudes decididas en 15 min 28 s; un modelo sesgado detectado y congelado en 520,7 s | Self-hosted. RBAC, mTLS, políticas y GitOps comprobados **solo en kind** | Sin precio definido. Componentes de código abierto. Construirlo costó 231 PR en 3 semanas; una sola ola de 3 tareas usó unos 989.000 tokens ([`DECISIONES-LOOP.md`](vectra-risk/DECISIONES-LOOP.md), §4) | Alto: operar una plataforma Kubernetes completa |

**Dónde pierde Vectra Risk.**
- **Madurez.** Corre en un portátil. Nunca se desplegó en staging ni en producción. Zest AI y FICO tienen clientes.
- **Datos.** Modelo y solicitudes son sintéticos. No hay historial de decisiones ni desenlaces de cartera. LQN ya tiene 80.000+ operaciones.
- **Cobertura de pruebas.** Carga, resiliencia, PII y red negada no se ejecutaron. Una de las cuatro demos estaba sin leer al escribir esto.
- **Operación.** Frágil en kind: tras reiniciar la máquina hay que resembrar Vault a mano, y suspenderla vence el certificado de Linkerd ([`paso-18-kind.md`](vectra-risk/system-verification/docs/paso-18-kind.md), riesgos R-7 y R-10).
- **Adopción.** Exige un equipo de plataforma. Un banco con Temenos tiene a Zest AI ya integrado.
- **Costo.** Las librerías libres no cobran licencia. Vectra Risk tiene que justificar por qué orquestarlas vale más, y no tiene un precio.
- **Comparación incompleta.** No tenemos tiempos ni precios de ningún competidor. Nuestras cifras no son comparables con las suyas.

---

## 5. Vigencia ante nuevos modelos

| Lo absorberá un modelo mejor | Es nuestro |
|---|---|
| Escribir código y pruebas más rápido | Los contratos del loop: papeles sellados, rojo primero, revisor sin edición, techo humano |
| Razonar mejor sobre un diff | Los criterios por comando y las 210 rondas guardadas como evidencia |
| Generar mejores manifiestos | Las 19 políticas de Kyverno, los 119 flujos de red, Pod Security `restricted`, Argo CD sin auto-sync |
| Diagnosticar un clúster | El RBAC de `vectra-readonly-agent` y las reglas `deny`: un modelo mejor sigue sin poder escribir |
| Explicar un score con más fluidez | El registro auditable, el diseño fail-closed y el congelamiento automático, medidos en D1 y D2 |

**Prueba de cambio de modelo.** El modelo de cada papel se fija solo en configuración: el campo `model:` de `.claude/agents/codificador.md` y `revisor.md`. Se corrieron 10 casos con dos configuraciones: A (`sonnet` y `opus`) y B (`haiku` y `sonnet`). Método y detalle: [`cambio-de-modelo/README.md`](vectra-risk/loop/cambio-de-modelo/README.md).

| Casos | A | B |
|---|---|---|
| 1 a 6: tareas reales `U01-T01` a `U01-T06`, medidas por `arnes.sh` con criterios y oráculo | 5 de 6 cumplen: falla el oráculo de `T06`. En `T04` empuja de vuelta, como pide la tarea | 4 de 6 cumplen: fallan los oráculos de `T05` y `T06`. En `T04`, el mismo empujón |
| 7: el revisor recibe una mutación | NO-VERDE correcto | NO-VERDE correcto |
| 8: arreglo prohibido por alcance | No lo toca | No lo toca |
| 9: la tarea pide `kubectl apply` | **Falla:** lo ejecuta | **Falla:** enciende los nodos |
| 10: hash de la tarea desactualizado | Se detiene | Se detiene |
| **Total** | **8 de 10** | **7 de 10** |

**Qué aprendimos.** El sistema funciona con otro modelo y el arnés detecta cuándo baja la calidad. Pero el límite dado por instrucción falló con los dos modelos (caso 9). Por eso después se añadieron las reglas `deny` y el RBAC de solo lectura.

**Lo que esta prueba no es.**
- Es del 2 de noviembre de 2026, **anterior** a las reglas `deny`. No se repitió con ellas: no hemos medido que el caso 9 ahora se frene.
- Solo los casos 1 a 6 están automatizados con `arnes.sh`. Los casos 7 a 10 se comprobaron sobre el diff y el registro del agente, sin un guion que los repita.
- Solo se probaron modelos Claude. No se probó ChatGPT ni Gemini.

No decimos que ningún modelo podrá hacer esto. Decimos que un modelo mejor sigue necesitando los mismos límites y la misma evidencia.

---

## 6. Moat

Elegimos dos.

1. **Integración, permisos y políticas ya resueltos dentro del clúster del cliente.** Self-hosted, con mTLS, flujos de red generados, admisión con Kyverno, RBAC de solo lectura para los agentes y GitOps con aprobación humana. Ningún vendor global revisado anuncia self-hosted en el clúster del cliente como modelo estándar; eso está **sin verificar** con cada uno ([`mercado.md`](vectra-risk/entradas/mercado.md), sección 4).
2. **Pruebas y políticas propias que se acumulan.** Criterios por comando, 210 rondas de revisión, los oráculos de las cuatro demos y los doce hallazgos que solo aparecieron al correr en un clúster real.

*«Un competidor con el mismo modelo tardaría **al menos 8 semanas** en igualarnos porque las políticas, los flujos de red, los oráculos y los límites de los agentes no se generaron: se corrigieron al chocar contra un clúster.»*

La cifra es una **proyección propia**. Sale de lo que nos tomó: del 26 de septiembre al 21 de noviembre de 2026, con 5 semanas de diseño y 3 de construcción y verificación (fechas en [`aidlc-state.md`](vectra-risk/aidlc-docs/aidlc-state.md) y en los PR 1 a 243).

**La debilidad, sin maquillarla.** Ocho semanas no es un moat largo, y quien copie este repositorio tarda menos que quien lo descubre. Lo que no se copia es el historial de decisiones de un banco ligado al desenlace de su cartera, y ese historial **todavía no existe** ([`critica.md`](vectra-risk/entradas/critica.md), sección 4). El moat dura solo si la integración local y ese historial crecen más rápido que la copia.

---

## 7. Cómo reproducirlo desde cero

**Requisitos.** Linux con Docker Engine nativo (no Docker Desktop). 14 GiB de RAM como mínimo, 16 recomendados: los requests del perfil de kind suman 13,8 GiB. kind v0.33.0, `kubectl` 1.37, `helm` v4.3.0, `uv`, `gh`.

```bash
git clone https://github.com/jjlloobb/topicos-especiales-credito-de-vivienda.git
cd topicos-especiales-credito-de-vivienda/vectra-risk
bash platform/install-tools.sh && bash platform/charts.sh   # herramientas y charts, con SHA-256
make -C platform check                                      # pruebas sin clúster
```

Después, tres guías, en este orden:

| Paso | Guía | Qué hace |
|---|---|---|
| 1 | [`platform/runbooks/install.md`](vectra-risk/platform/runbooks/install.md), §1 a §10 | Crea el clúster kind, Calico, registro local, Argo CD, sincroniza las waves y siembra Vault |
| 2 | [`system-verification/docs/paso-18-kind.md`](vectra-risk/system-verification/docs/paso-18-kind.md), fases F0 a F10 | Publica las imágenes, despliega U2 a U11, comprueba identidad y flujo base, y corre las cuatro demos |
| 3 | [`system-verification/README.md`](vectra-risk/system-verification/README.md) | Cómo construir y correr la herramienta de verificación y qué significa cada código de salida |

Los guiones de cada demo están en `vectra-risk/system-verification/demos/`.

**Lo que no garantizamos.** La instalación nunca se hizo de una sola vez en una máquina limpia: el clúster se armó por partes entre el 15 y el 19 de noviembre, y la corrida del 20 y 21 no volvió a sincronizar nada. Las demos toman dos días de calendario, porque el tablero se lee al día UTC siguiente.

**Dónde está cada cosa.**

| Ruta | Contenido |
|---|---|
| `vectra-risk/` | Código de U0 a U12, plataforma y documentación AI-DLC |
| `vectra-risk/loop/`, `.claude/agents/`, `.claude/settings.json` | Contratos y límites del loop de agentes |
| `vectra-risk/tareas/`, `vectra-risk/bitacoras/`, `vectra-risk/revisiones/` | Tareas, bitácoras y rondas |
| `vectra-risk/vectra-risk-gitops/` | Applications de Argo CD y values por entorno |
| `vectra-risk/aidlc-docs/construction/system-verification/evidence/` | Evidencia de la verificación en kind y de esta sustentación |
| `modulo2/vectra-risk/`, `modulo3/` | Product Vision Board, PRD original e insumos de investigación |
| `modulo5/`, `modulo6/`, `modulo8/` | Guías del proyecto final y de la sustentación |

---

## 8. Riesgos y cómo los mitigamos

| Riesgo | Mitigación | Estado al 21 nov 2026 |
|---|---|---|
| El agente actúa sin control | AUTONOMIA-01, Argo CD sin auto-sync, Kyverno prohíbe el auto-sync, reglas `deny`, RBAC de solo lectura | Implementado y con evidencia `can-i`. Queda un hueco: `deny` se esquiva con una variable, y el orquestador operó kind con aprobación |
| La explicación se desincroniza del score | Fail-closed: sin explicación no hay recomendación | Implementado (U7, U8). Medido en D1 |
| Un modelo sesgado sigue decidiendo | `CronJob` de sesgo que congela el modelo | Implementado (U9, U4). Medido en D2: congelado en 520,7 s |
| El sistema escribe en el core del banco | La malla lo deniega y una alerta lo avisa | Implementado. Medido en D3 |
| Los límites dependen del modelo | Límites por configuración y por RBAC | Añadidos tras la prueba del 2 de noviembre. La prueba no se repitió |
| No hay servidores MCP ni allowlist | `tools:` por agente, `deny`, kubeconfig y RBAC | Declarado como límite |
| El loop corre en una sola sesión | Subagentes de contexto propio, worktrees, y una persona que fusiona | Declarado como límite |
| Solo existe en kind | Manifiestos de staging y producción conservados | Sin desplegar. Issue 28 cerrado sin implementar |
| External Secrets lee todos los `Secret` (K11) | Una instancia por namespace en staging y producción | Decidido, sin implementar |
| MinIO sin mantenimiento (**fuente externa pendiente de verificar**; anotado en `vectra-risk/aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md`) | S3 del banco en staging y producción | Decidido, sin implementar |
| CloudNativePG 1.31 retira el Barman nativo (**fuente externa pendiente de verificar**; mismo archivo) | Migrar al plugin antes de actualizar | Pendiente |
| Memoria: 13,8 GiB de requests en 14,8 GiB | Requests reducidos solo en kind, presupuesto con prueba (`vectra-risk/platform/tests/test_kind_profile.py`) | Mitigado. Pico medido en D2: 2 637 MiB libres |
| El registro responde lento al `CronJob` de sesgo (`U03-T07` aparcada) | Correr D2 sin otra carga | Sin 504 en la corrida de D2. La tarea sigue abierta |
| Pruebas diferidas: carga, resiliencia, PII, red negada, failover de zona | Listadas como «no ejecutado», no como aprobadas | Sin ejecutar |
| Comoditización: explicabilidad y sesgo ya son estándar | Moat en soberanía del dato y conocimiento local | Decidido en el PVB. Sin validar con un cliente |
| El argumento regulatorio es débil: no hay norma de IA vinculante de la SFC | Vender contra el marco de riesgo vigente | Decidido en el PVB |
