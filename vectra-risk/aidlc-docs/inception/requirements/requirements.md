# Requisitos — Vectra Risk

> Fuente autoritativa: `entradas/prd.md`. Visión: `entradas/pvb.md`. Decisiones del
> usuario: `requirement-verification-questions.md` (Q1–Q20 + extensiones) y
> `requirement-followup-questions.md` (R1–R9). Las etiquetas **[INTERNO]** y
> **[VERIFICAR]** del PRD se conservan: ningún supuesto se convierte en hecho aquí.

---

## 0. Análisis de intención

| Aspecto | Valor |
|---|---|
| **Solicitud del usuario** | "Using AI-DLC, lee entradas/prd.md y entradas/pvb.md y especifica el producto que describen. No escribas código: este trabajo se detiene al terminar el plan de tareas de cada unidad." |
| **Tipo de solicitud** | New Project (greenfield) |
| **Alcance** | System-wide: varios microservicios, tres consolas, almacenamiento, IdP simulado, plataforma Kubernetes, GitOps y observabilidad |
| **Complejidad** | Complex: dominio regulado, ML explicable, restricciones de autonomía bloqueantes y cuatro extensiones activas |
| **Profundidad de requisitos** | Comprehensive, con trazabilidad al PRD |
| **Límite del trabajo** | INCEPTION completa + CONSTRUCTION hasta Code Generation **Parte 1 (plan de tareas)** por unidad. Sin código y sin Build & Test |

---

## 1. Visión y propósito

Vectra Risk lleva a producción, **dentro del clúster Kubernetes del propio banco**, el
modelo de scoring de crédito de vivienda que el área de riesgo ya construyó y que el
comité no puede aprobar. Cada score se entrega con una explicación calculada en el mismo
request, sincronizada por versión de modelo. El sesgo se monitorea de forma continua y
cada decisión humana queda en un registro append-only.
**El modelo puntúa, el analista decide, el registro queda.**

**North Star:** tasa de decisiones en que la explicación cambia o sustenta materialmente
la decisión final del comité, y no solo la acompaña. El target se define con el piloto
**[INTERNO]**.

**Diferenciador declarado:** soberanía del dato (self-hosted) y conocimiento normativo
colombiano. **No** se vende "explicamos las decisiones". La exclusividad self-hosted
frente a los vendors globales sigue marcada como **[VERIFICAR]** (PRD §0 #2).

---

## 2. Actores y roles

| Rol | Tipo | Responsabilidad en el sistema |
|---|---|---|
| Analista de crédito | Usuario humano | Revisa casos con score+explicación, registra recomendación firmada, puede registrar solicitudes manualmente |
| Ingeniero de riesgo | Usuario humano | Empaqueta y registra versiones de modelo, lanza validación en staging |
| VP de Riesgo / CRO | Usuario humano (aprobador) | Aprueba despliegue de versiones de modelo y de versiones de política de negocio |
| Oficial de cumplimiento | Usuario humano (aprobador) | Aprueba/rechaza fuentes de datos, gestiona alertas de congelamiento, **único rol que reactiva un modelo congelado** |
| Simulador de canal | Sistema (sintético) | Envía solicitudes sintéticas y casos adversariales al API Gateway |
| Core bancario (mock/adapter) | Sistema externo | Expone estado de crédito **solo lectura** para Vectra Risk |
| Identity provider (Keycloak) | Sistema externo simulado | Autenticación OIDC y roles |

---

## 3. Principios no negociables (restricciones bloqueantes)

| ID | Principio (PRD §6) | Regla de autonomía | Consecuencia verificable |
|---|---|---|---|
| P1 | El modelo puntúa, el humano decide | AUTONOMIA-03 | Ningún servicio escribe estado de crédito; RBAC de solo lectura sobre recursos de crédito; red-teaming #5 debe fallar como se espera |
| P2 | Soberanía del dato | AUTONOMIA-05 | Egress denegado por defecto desde scoring/explainability/bias; sin PII en logs; ningún LLM ni API externa |
| P3 | Fail-closed scoring ↔ explicación | AUTONOMIA-06 | Sin explicación con `model_version_id` idéntico no hay score usable; red-teaming #3 |
| P4 | El monitoreo mide y alerta, no certifica | AUTONOMIA-04 | Congelamiento automático; reactivación solo manual por cumplimiento; la UI nunca dice "sin sesgo" |
| P5 | La explicación es aproximación post-hoc | — | Toda explicación muestra metadata de aproximación post-hoc |
| — | Cambios a infraestructura solo vía PR aprobado | AUTONOMIA-01 | Ningún plan contiene `kubectl apply`/`helm install`/sync automático sin aprobación humana previa |
| — | Criterios de aceptación ejecutables | AUTONOMIA-02 | Cada tarea de cada unidad nombra el comando o prueba que la verifica |

---

## 4. Decisiones del usuario que moldean la especificación

| # | Decisión | Efecto |
|---|---|---|
| Q1=A | Fail-closed activo desde el primer incremento en que coexisten scoring y explicación | Se **corrige PRD §13 (Módulos 4-5)**: no existe incremento sin fail-closed |
| Q2=A | Congelamiento automático promovido a **Must** | Coherente con §3.7, journey 7.4, red-teaming #2 y Sesión 16 |
| Q3=A | Todo tier es self-hosted; sin licenciamiento en la especificación | Se descarta la lectura del PVB §7 ("Enterprise = self-hosted") |
| Q4=A | Alcance = todos los Must + todos los Should | Entran disparidad pre/post, métrica de adopción, GitOps, freeze |
| Q5=C | Plantilla determinística en el MVP; contrato preparado para LLM in-cluster (opción 2 del PRD) después | Se resuelve el TBD de arquitectura de PRD §11 |
| Q6=C | Disparidad sobre la recomendación del modelo **y** sobre la decisión humana, reportadas por separado; el freeze solo se dispara por la del modelo | — |
| Q7=C | Grupos: sexo, rango de edad, región/departamento, estrato (estrato como proxy vigilado, nunca variable de decisión) | — |
| Q8=A | Disparidad calculada dentro de bandas de capacidad de pago (cuota/ingreso) y agregada; umbral 5 pp sobre la agregada | — |
| Q9=A | Política de negocio versionada, separada del modelo, cambiable solo con aprobación del CRO; cada decisión registra `policy_version_id` | — |
| Q10=C | Solicitudes desde simulador de canal **y** alta manual en consola | — |
| Q11=B | Lógica normativa mínima: clasificación VIS/No VIS y validación de tasa contra tope de usura, como reglas de la política | Se promueve un *Could* a alcance |
| Q12=B | Reintentos con backoff → estado "no disponible" + alerta Alertmanager + aviso en consola de riesgo/CRO | — |
| Q13=A | Python (FastAPI) en todos los servicios backend | — |
| Q14=A | Una SPA (React + TypeScript) con vistas por rol | — |
| Q15=A | PostgreSQL con `UPDATE`/`DELETE` revocados + cadena de hashes | — |
| Q16=A | Keycloak como IdP simulado (OIDC) | — |
| Q17=A | Modelo de referencia gradient boosting sobre dataset sintético; contrato genérico para cualquier modelo tabular soportado por KServe | — |
| Q18=A | Clúster local kind/k3d; entrega vía PR con evidencia (`kubectl diff`, `helm template`) | — |
| Q19=A | Argo CD sync manual + Prometheus/Grafana/Alertmanager in-cluster | — |
| Q20=B | Español, con textos externalizados (i18n preparado) | — |
| R1=A | DR: Backup & Restore (RTO/RPO en horas) a nivel de sitio | — |
| R2=A | RPO = 0 para el Decision Registry (escritura síncrona replicada antes de confirmar; si no persiste, fail-closed) | Ver §8.4 (interpretación por capas) |
| R3=B | Gestión de cambios propuesta por AI-DLC: PR + evidencia + aprobación humana + nota de rollback | — |
| R4=A | CI en GitHub Actions | — |
| R5=A | Rollback = revert en Git + sync manual de Argo CD / rollback de Helm, con aprobación | — |
| R6=B | Rolling update para servicios (los modelos siguen el flujo del journey 7.2) | — |
| R7=A | Un sitio, multi-zona (≥2 zonas de fallo) | — |
| R8=A | HPA con mín./máx. + escalado de KServe, validado con carga simulada; carga a escala real sigue en *Won't* | Se resuelve la tensión con PRD §8 |
| R9=B | Proceso de incidentes ligero propuesto por AI-DLC (severidades, runbooks, rutas de Alertmanager, COE) | — |
| Ext. | Security = Sí, Resiliency = Sí, PBT = Sí (completo) | Reglas bloqueantes en todas las etapas |

---

## 5. Requisitos funcionales

Prioridad: **M** = Must, **S** = Should (en alcance por Q4=A), **C→** = Could promovido.
Trazabilidad: sección del PRD de origen.

### 5.1 Ingesta de solicitudes (FR-ING)

| ID | Requisito | Prio | Origen |
|---|---|---|---|
| FR-ING-01 | El sistema recibe solicitudes de crédito de vivienda a través del API Gateway con un esquema validado (datos del solicitante, ingreso, valor de vivienda, monto, plazo, canal, atributos demográficos para monitoreo) | M | §5 caso 1, Q10 |
| FR-ING-02 | Un **simulador de canal** genera solicitudes sintéticas con volumen configurable y permite inyectar los casos adversariales curados (30–50) del plan de red-teaming | M | Q10, §11 |
| FR-ING-03 | El analista puede registrar una solicitud manualmente desde la consola | M | Q10 |
| FR-ING-04 | Los campos de texto libre se tratan como **datos, nunca como instrucciones**; se almacenan escapados y no se pasan a ningún componente generador de texto | M | §11 red-teaming #1 |
| FR-ING-05 | Los atributos protegidos (sexo, rango de edad, región, estrato) se capturan **solo para monitoreo de sesgo** y no se envían como features al modelo, salvo decisión explícita documentada en la política | M | Q7 |

### 5.2 Scoring (FR-SCO) — `scoring-service`

| ID | Requisito | Prio | Origen |
|---|---|---|---|
| FR-SCO-01 | Invoca el modelo activo a través de un `InferenceService` de KServe y devuelve `score`, `confidence` y `model_version_id` | M | §9 |
| FR-SCO-02 | Aplica la **política de negocio vigente** (punto de corte, umbral de baja confianza, reglas VIS/usura) para producir una **recomendación** (favorable / desfavorable / revisión requerida), nunca una decisión | M | P1, Q9 |
| FR-SCO-03 | Una recomendación con confianza bajo el umbral de la política se marca explícitamente como **baja confianza** y nunca se presenta como segura | M | §6 P1 |
| FR-SCO-04 | Solicita la explicación a `explainability-service` **en el mismo request** y solo entrega un objeto de recomendación usable si recibe una explicación con el `model_version_id` idéntico (fail-closed) | M | P3, AUTONOMIA-06 |
| FR-SCO-05 | Si la explicación falla, excede el timeout o la versión no coincide, responde con estado **"no disponible, reintentando"**, sin score visible como decisión; el caso queda pendiente con reintento automático (backoff, límite configurable) | M | §7.3, Q12 |
| FR-SCO-06 | Al agotar los reintentos: el caso queda en **"no disponible"**, se dispara una alerta en Alertmanager y aparece un aviso en la consola de riesgo/CRO con los casos afectados | M | Q12 |
| FR-SCO-07 | No sirve solicitudes con un modelo en estado **congelado**; esas solicitudes quedan en "no disponible – modelo congelado" | M | P4, §7.4 |
| FR-SCO-08 | Persiste la recomendación en el Decision Registry **antes** de devolverla; si la persistencia falla, la recomendación no se entrega | M | R2 |
| FR-SCO-09 | No tiene ningún cliente, ruta ni permiso que modifique estado de crédito en el core bancario | M | AUTONOMIA-03 |
| FR-SCO-10 | Acepta cualquier modelo tabular en formato soportado por KServe (contrato genérico); el MVP incluye un modelo de referencia gradient boosting sobre dataset sintético | M | Q17, §5 caso 4 |

### 5.3 Explicabilidad (FR-EXP) — `explainability-service`

| ID | Requisito | Prio | Origen |
|---|---|---|---|
| FR-EXP-01 | Calcula valores SHAP para la solicitud contra **la misma versión de modelo** que produjo el score y devuelve el vector SHAP con `model_version_id` | M | §9 |
| FR-EXP-02 | Rechaza (error explícito) cualquier solicitud cuyo `model_version_id` no tenga explicador disponible; **nunca** usa un explicador de otra versión, un valor por defecto ni una plantilla genérica como respaldo | M | AUTONOMIA-06 |
| FR-EXP-03 | Traduce el vector SHAP a lenguaje no técnico en español mediante **plantilla determinística**: factores ordenados por importancia absoluta, dirección del efecto, sin jerga | M | Q5=C, §11 |
| FR-EXP-04 | Toda explicación incluye metadata visible: "aproximación post-hoc, no lectura del razonamiento del modelo", método, versión de modelo y versión de plantilla | M | P5 |
| FR-EXP-05 | **Validación automática de factualidad** por request: la narrativa se contrasta contra el vector SHAP (mismos factores, mismo orden, mismo signo) antes de entregarse; si falla, la explicación se trata como fallida (→ fail-closed) | M | §11 criterios |
| FR-EXP-06 | Contrato de narrativa definido como interfaz reemplazable, preparada para un generador LLM **in-cluster** con solo SHAP estructurado como input (opción 2 del PRD) — no implementado en el MVP | S | Q5=C |
| FR-EXP-07 | LIME como método alternativo | C (fuera) | §8 |

### 5.4 Monitoreo de sesgo (FR-BIA) — `bias-monitoring-service`

| ID | Requisito | Prio | Origen |
|---|---|---|---|
| FR-BIA-01 | Calcula disparidad de tasa de **recomendación favorable del modelo** entre grupos protegidos (sexo, rango de edad, región, estrato), dentro de bandas de capacidad de pago y agregada | M | Q6, Q7, Q8 |
| FR-BIA-02 | Calcula por separado la disparidad sobre **decisiones finales humanas** registradas; se reporta, no dispara congelamiento | M | Q6 |
| FR-BIA-03 | Cuando la disparidad agregada del modelo supera **5 pp** (configurable, [INTERNO]), congela el modelo **automáticamente** para nuevas solicitudes | M | Q2, §7.4 |
| FR-BIA-04 | Al congelar genera un **paquete de contexto**: métrica antes/después, fuente de datos, volumen afectado, versión congelada, grupos y bandas implicados | M | §7.4 |
| FR-BIA-05 | **Ninguna** ruta automática reactiva un modelo congelado; solo una acción autenticada del rol cumplimiento, registrada con `user_id` y timestamp | M | AUTONOMIA-04 |
| FR-BIA-06 | Mide disparidad **antes y después** de incorporar cada nueva fuente de datos; la incorporación requiere aprobación del oficial de cumplimiento | S | §8, P4 |
| FR-BIA-07 | Monitoreo inicial de sesgo obligatorio en staging para toda nueva versión de modelo antes de solicitar aprobación del CRO | M | §7.2 |
| FR-BIA-08 | Ningún texto del producto presenta el monitoreo como "prueba de ausencia de discriminación" | M | P4 |
| FR-BIA-09 | El monitoreo corre dentro del clúster y sus datasets agregados no contienen PII en claro | M | AUTONOMIA-05 |

### 5.5 Decision Registry (FR-REG)

| ID | Requisito | Prio | Origen |
|---|---|---|---|
| FR-REG-01 | Almacena por caso: solicitud (referencia), score, confianza, recomendación, explicación (vector + narrativa), `model_version_id`, `policy_version_id`, decisión humana final, `user_id`, timestamps | M | §9, Q9 |
| FR-REG-02 | **Append-only**: el rol de aplicación no tiene `UPDATE`/`DELETE`; cada registro encadena el hash del anterior; existe un verificador de integridad de la cadena | M | Q15 |
| FR-REG-03 | Registra si la decisión final **siguió o se apartó** del score, y si el analista consultó el detalle de la explicación antes de decidir | M/S | §5 caso 5, §10 |
| FR-REG-04 | Lectura filtrada por rol; escritura solo desde los servicios | M | §9 |
| FR-REG-05 | Registra eventos de gobierno: aprobaciones de modelo y política (CRO), congelamientos, reactivaciones y decisiones sobre fuentes (cumplimiento) | M | §7.2, §7.4 |
| FR-REG-06 | Permite reconstruir, para un caso dado, la explicación completa y sincronizada tal como se mostró (caso de uso 2: defender un rechazo) | M | §5 caso 2 |

### 5.6 Política de negocio (FR-POL)

| ID | Requisito | Prio | Origen |
|---|---|---|---|
| FR-POL-01 | La política es un artefacto versionado, **independiente del modelo**: punto de corte, umbral de baja confianza y reglas por canal | M | Q9 |
| FR-POL-02 | Reglas normativas mínimas: clasificación **VIS / No VIS** por valor de vivienda y validación de la tasa contra el **tope de usura vigente** (parámetros configurables con fecha de vigencia; los valores concretos son **[VERIFICAR]** contra la fuente oficial) | C→ | Q11 |
| FR-POL-03 | Toda nueva versión de política requiere aprobación explícita del CRO antes de activarse | M | Q9 |
| FR-POL-04 | Los servicios **no** pueden modificar su propia política | M | §6 P1 |

### 5.7 Gobierno de versiones de modelo (FR-MOD)

| ID | Requisito | Prio | Origen |
|---|---|---|---|
| FR-MOD-01 | El ingeniero de riesgo registra una versión de modelo (artefacto + explicador asociado + metadata) para staging | M | §7.2 |
| FR-MOD-02 | Validación en staging: AUC-ROC contra dataset de validación (target > 0.85 **[INTERNO]**, recalibrar con cartera real), sesgo inicial (FR-BIA-07) y **sincronía verificada** con `explainability-service` | M | §7.2 |
| FR-MOD-03 | Promoción a producción solo con aprobación explícita del CRO, registrada; el cambio se materializa vía PR GitOps con sync manual | M | §7.2, AUTONOMIA-01 |
| FR-MOD-04 | Scoring y explicador de una versión se despliegan como unidad atómica versionada; un despliegue parcial deja la versión sin servir (fail-closed), nunca mezcla versiones | M | P3 |
| FR-MOD-05 | Estados de modelo: `registrado → en_validación → aprobado → activo → congelado → retirado`; transición `congelado → activo` solo por cumplimiento | M | AUTONOMIA-04 |

### 5.8 Consolas (FR-UI) — una SPA con vistas por rol

| ID | Requisito | Prio | Origen |
|---|---|---|---|
| FR-UI-01 | **Analista**: bandeja de casos; detalle con score, confianza, recomendación, explicación en lenguaje no técnico y metadata post-hoc; registro de decisión firmada (sigue / se aparta + justificación) | M | §7.1 |
| FR-UI-02 | Los casos "no disponible" se muestran como tales, sin score visible | M | P3 |
| FR-UI-03 | **Riesgo/CRO**: aprobación de versiones de modelo y de política; aviso de casos en fail-closed persistente | M | §9, Q12 |
| FR-UI-04 | **Cumplimiento**: aprobación de fuentes de datos, alertas de congelamiento con paquete de contexto, reactivación o descarte de modelos congelados | M | §9, §7.4 |
| FR-UI-05 | Dashboard de sesgo (modelo y decisión humana), con leyenda permanente: "mide y alerta, no certifica" | M | P4 |
| FR-UI-06 | Textos en español externalizados (i18n preparado) | M | Q20 |
| FR-UI-07 | Autorización por rol aplicada en el servidor; la UI solo oculta, no protege | M | SECURITY-08 |

### 5.9 Métricas de producto (FR-MET)

| ID | Requisito | Prio | Origen |
|---|---|---|---|
| FR-MET-01 | North Star: tasa de decisiones donde la explicación cambió o sustentó la decisión (derivada de FR-REG-03) | S | §10 |
| FR-MET-02 | Métrica de fallo por ruido: tasa de consulta al detalle de la explicación antes de decidir, con alerta si cae bajo un piso configurable | S | §10 |
| FR-MET-03 | % de solicitudes con score+explicación en el mismo request (target 100 %) y frecuencia de fail-closed por desincronía | M | §10 |
| FR-MET-04 | Tiempo de originación hasta recomendación explicada (target < 1 h en 80 % de casos estándar **[INTERNO]**) | S | §10 |
| FR-MET-05 | Tasa de decisiones sostenidas sin modificación por el comité (> 70 % al mes 6 **[INTERNO]**) | S | §10 |

### 5.10 Integraciones (FR-INT)

| ID | Requisito | Prio | Origen |
|---|---|---|---|
| FR-INT-01 | **Core bancario mock/adapter** que expone estado de crédito solo lectura; ninguna ruta de escritura accesible desde Vectra Risk | M | §8 Won't, P1 |
| FR-INT-02 | Autenticación OIDC contra **Keycloak** con roles: analista, ingeniero_riesgo, cro, cumplimiento | M | Q16 |
| FR-INT-03 | Único egress permitido desde el namespace de Vectra Risk hacia fuera: el IdP del banco | M | AUTONOMIA-05 |

### 5.11 Plataforma y entrega (FR-PLT)

| ID | Requisito | Prio | Origen |
|---|---|---|---|
| FR-PLT-01 | Despliegue self-hosted vía Helm charts | M | §8 |
| FR-PLT-02 | RBAC y NetworkPolicies que impiden escritura de estado de crédito y egress no aprobado | M | §8, P1, P2 |
| FR-PLT-03 | Pipeline GitOps con **Argo CD en sync manual** (sin auto-sync) | S | Q19, AUTONOMIA-01 |
| FR-PLT-04 | CI en GitHub Actions: build, pruebas (incluidas PBT), escaneo de dependencias e imágenes, SBOM, `helm template`/`kubectl diff` como evidencia del PR | M | R4, SECURITY-10 |
| FR-PLT-05 | Políticas de admisión y escaneo de imágenes | M | §13 Módulo 7 |

---

## 6. Escenarios de red-teaming como criterios de aceptación del sistema

| # | Escenario | Resultado esperado (verificable por prueba automatizada) |
|---|---|---|
| RT-1 | Inyección indirecta vía texto libre | Texto almacenado como dato; ninguna narrativa ni acción cambia; no hay componente que lo interprete |
| RT-2 | Variables proxy discriminatorias sin variable protegida declarada | `bias-monitoring-service` detecta disparidad > umbral y **congela**; permanece congelado tras reintentos |
| RT-3 | Desincronía forzada de versión scoring ↔ explicación | Respuesta "no disponible, reintentando"; **cero** scores entregados como decisión |
| RT-4 | Adversarial examples sobre modelo tabular | La confianza reportada no se infla; entradas fuera de dominio se marcan baja confianza |
| RT-5 | Intento de escritura a estado de crédito desde scoring/explainability | Denegado por RBAC **y** por NetworkPolicy (`kubectl auth can-i` = no; conexión rechazada) |

---

## 7. Requisitos no funcionales

### 7.1 Seguridad (Security Baseline activa)

| ID | Requisito | Regla |
|---|---|---|
| NFR-SEC-01 | Cifrado en reposo del volumen de PostgreSQL y de backups; TLS 1.2+ en toda conexión a BD y entre servicios | SECURITY-01 |
| NFR-SEC-02 | Access logging en el ingress/API Gateway hacia el stack de logs in-cluster | SECURITY-02 |
| NFR-SEC-03 | Logging estructurado JSON (timestamp, correlation ID, nivel, mensaje) centralizado **dentro del clúster**; **sin PII, tokens ni secretos** | SECURITY-03, AUTONOMIA-05 |
| NFR-SEC-04 | Cabeceras HTTP de seguridad en la SPA (CSP restrictiva sin `unsafe-inline`, HSTS, nosniff, DENY, Referrer-Policy) | SECURITY-04 |
| NFR-SEC-05 | Validación de esquema en todo endpoint (tipos, longitudes, formatos, límites de payload); consultas parametrizadas | SECURITY-05 |
| NFR-SEC-06 | RBAC de Kubernetes y roles de BD de mínimo privilegio, sin comodines; lectura/escritura separadas | SECURITY-06, AUTONOMIA-03 |
| NFR-SEC-07 | NetworkPolicies deny-by-default (ingress y egress) | SECURITY-07, AUTONOMIA-05 |
| NFR-SEC-08 | Autenticación obligatoria por defecto, validación de JWT en cada request, autorización por función y por objeto, CORS con orígenes explícitos | SECURITY-08 |
| NFR-SEC-09 | Sin credenciales por defecto (Keycloak, PostgreSQL, Grafana, Argo CD); errores genéricos sin stack traces; sin endpoints de documentación en producción | SECURITY-09 |
| NFR-SEC-10 | Dependencias con lockfile, escaneo de vulnerabilidades, SBOM, imágenes base pinneadas por digest (sin `latest`) | SECURITY-10 |
| NFR-SEC-11 | Rate limiting en el gateway; lógica de authN/authZ aislada; casos de abuso documentados (RT-1..5) | SECURITY-11 |
| NFR-SEC-12 | Credenciales gestionadas por Keycloak (hash adaptativo, bloqueo por fuerza bruta, MFA para cro/cumplimiento/admin); sesiones con expiración; secretos vía Kubernetes Secrets cifrados | SECURITY-12 |
| NFR-SEC-13 | Deserialización segura de artefactos de modelo (formatos con verificación de checksum/firma); pipeline CI con separación autor/aprobador; auditoría de cambios críticos (Decision Registry) | SECURITY-13 |
| NFR-SEC-14 | Alertas por fallos de autenticación/autorización repetidos; logs en almacenamiento tamper-evident con retención ≥ 90 días; dashboards de seguridad | SECURITY-14 |
| NFR-SEC-15 | Manejo explícito de errores en llamadas externas, handler global, **fail-closed** en toda ruta de error | SECURITY-15, P3 |

### 7.2 Resiliencia (Resiliency Baseline activa)

| ID | Requisito | Regla |
|---|---|---|
| NFR-RES-01 | Clasificación de criticidad por componente y mapa de dependencias (se completa en Application Design). Propuesta inicial: Decision Registry = **Critical** (evidencia regulatoria); scoring/explainability = **High** (el banco puede seguir con su proceso manual); bias-monitoring = **High** (un monitoreo caído no puede dejar un modelo sin vigilar: si el monitoreo no corre, ver NFR-RES-11); consolas = Medium; simulador = Low | RESILIENCY-01 |
| NFR-RES-02 | SLA propuesto **[INTERNO]**: 99,5 % mensual en horario operativo del banco para la ruta de recomendación. Justificación: el fail-closed hace que la indisponibilidad degrade velocidad, no corrección, y el banco conserva su proceso manual. Se valida en NFR Requirements | RESILIENCY-02 |
| NFR-RES-03 | RTO del sitio: horas (Backup & Restore, R1=A). RPO: ver §8.4 | RESILIENCY-02, -11 |
| NFR-RES-04 | Gestión de cambios propuesta: PR + evidencia + aprobación humana + nota de rollback; historial = Git + Decision Registry para eventos de modelo/política | RESILIENCY-03, R3 |
| NFR-RES-05 | CI GitHub Actions; CD Argo CD sync manual; rollback = revert + sync / `helm rollback` aprobado; servicios con rolling update | RESILIENCY-04, R4–R6 |
| NFR-RES-06 | Métricas (latencia, errores, throughput, saturación), logs centralizados, **tracing distribuido in-cluster** (p. ej. OpenTelemetry → backend self-hosted) y dashboards Grafana | RESILIENCY-05, AUTONOMIA-05 |
| NFR-RES-07 | Health checks liveness/readiness; readiness profunda (BD, KServe, explainability) en servicios críticos | RESILIENCY-06 |
| NFR-RES-08 | Alarmas de resiliencia: réplica de BD caída o rezagada, fallos de backup, operación en una sola zona, saturación de HPA | RESILIENCY-07 |
| NFR-RES-09 | Un sitio, ≥ 2 zonas de fallo: réplicas de servicios repartidas con topology spread, PostgreSQL con réplica síncrona en otra zona | RESILIENCY-08, R7 |
| NFR-RES-10 | HPA con mínimo/máximo por servicio y escalado KServe, validado con carga simulada; cuotas de recursos del namespace documentadas | RESILIENCY-09, R8 |
| NFR-RES-11 | Timeouts explícitos en toda llamada; circuit breaker hacia explainability y KServe; la degradación de dependencias críticas es **fail-closed**, nunca "modo degradado con score"; si `bias-monitoring-service` no ha evaluado en la ventana configurada, se alerta (el modelo sigue sirviendo o se congela según la política definida en Functional Design) | RESILIENCY-10, P3 |
| NFR-RES-12 | Backups automáticos cifrados de PostgreSQL con archivado continuo de WAL a almacenamiento del banco **fuera del sitio**; retención definida; prueba de restauración documentada | RESILIENCY-12 |
| NFR-RES-13 | Runbooks de failover (zona) y de restore (sitio), plan de comunicación, validación post-recuperación (incluye verificación de la cadena de hashes) | RESILIENCY-13 |
| NFR-RES-14 | Enfoque de pruebas de resiliencia: **se preguntará en NFR Design** | RESILIENCY-14 |
| NFR-RES-15 | Proceso de incidentes propuesto: severidades, runbook por alerta, rutas Alertmanager, post-mortem (COE) y seguimiento de acciones correctivas | RESILIENCY-15, R9 |

### 7.3 Calidad y pruebas (PBT activa)

| ID | Requisito | Regla |
|---|---|---|
| NFR-TST-01 | Framework PBT: **Hypothesis** (Python) y **fast-check** (TypeScript) | PBT-09 |
| NFR-TST-02 | Cada unidad con lógica identifica propiedades en Functional Design. Candidatas ya visibles: round-trip de serialización de recomendación/explicación; invariante "narrativa ⇔ vector SHAP" (mismos factores/orden/signo); invariante fail-closed "nunca score usable con versión distinta"; invariante de cadena de hashes; máquina de estados de modelo (congelado nunca pasa a activo sin cumplimiento) como PBT stateful; oráculo de disparidad contra cálculo de referencia de Fairlearn | PBT-01..06 |
| NFR-TST-03 | Generadores de dominio centralizados (solicitud de vivienda colombiana realista, versiones de modelo, políticas) | PBT-07 |
| NFR-TST-04 | Semilla registrada en CI; shrinking habilitado | PBT-08 |
| NFR-TST-05 | Pruebas de ejemplo para cada ruta crítica además de PBT; escenarios RT-1..5 como pruebas de integración | PBT-10, AUTONOMIA-02 |

### 7.4 Rendimiento, usabilidad y mantenibilidad

| ID | Requisito |
|---|---|
| NFR-PER-01 | Recomendación explicada disponible para el analista al abrir el caso (cálculo síncrono o precalculado en ingesta); latencia objetivo por request **[INTERNO]** a fijar en NFR Requirements; el scoring nunca es cuello de botella frente al target < 1 h |
| NFR-USA-01 | Explicación en español sin jerga técnica; accesibilidad WCAG 2.1 AA como objetivo de la SPA |
| NFR-MNT-01 | Contratos de API versionados (OpenAPI); servicios desacoplados por contrato; narrativa y método de explicación como interfaces reemplazables |
| NFR-AUD-01 | Toda aprobación humana (modelo, política, fuente, reactivación) queda en el Decision Registry con `user_id`, rol y timestamp |

---

## 8. Restricciones, supuestos y fuera de alcance

### 8.1 Restricciones
- Self-hosted siempre; sin multi-tenant ni SaaS.
- Sin integración real con core bancario (mock) y sin datos reales de cartera (sintéticos).
- Ninguna tarea de CONSTRUCTION aplica cambios al clúster sin aprobación humana (AUTONOMIA-01). La entrega es un PR con evidencia.

### 8.2 Fuera de alcance (Won't)
Aprobación/rechazo automático de crédito (prohibición **permanente**); integración real con core; datos reales; multi-tenant; pruebas de carga a escala real; LIME; LLM de narrativa (solo contrato preparado); licenciamiento por tier.

### 8.3 Supuestos marcados
- Exclusividad self-hosted frente a vendors globales: **[VERIFICAR]**.
- Señales 1 y 2 del ICP: **[VERIFICAR con entrevistas]**.
- Targets de AUC, disparidad, tiempos y North Star: **[INTERNO]**.
- Valores de tope de usura y umbral VIS: **[VERIFICAR]** contra fuente oficial vigente; se parametrizan con fecha.

### 8.4 Interpretación por capas de R1 + R2 (a confirmar en revisión)
- **Fallo de zona:** RPO = 0 para el Decision Registry (réplica síncrona en otra zona; si no se confirma la escritura, la recomendación no se entrega).
- **Pérdida del sitio:** estrategia Backup & Restore (RTO en horas) con archivado **continuo** de WAL fuera del sitio, de modo que el RPO del registro quede acotado al intervalo de archivado, que se fija en NFR Requirements.
- Los demás datos (métricas, dashboards, caché) aceptan RPO en horas.

### 8.5 Corrección aplicada al PRD §13
- Módulos 4-5: `explainability-service` se entrega **con** fail-closed activo desde que coexiste con scoring (Q1=A). No existe ningún incremento que entregue un score sin explicación sincronizada.

---

## 9. Resumen de cumplimiento de extensiones (etapa Requirements Analysis)

| Extensión / regla | Estado | Nota |
|---|---|---|
| AUTONOMIA-01 | Cumple | Recogido en FR-PLT-03/04, FR-MOD-03, §8.1 |
| AUTONOMIA-02 | Cumple | Criterios de sistema RT-1..5 ejecutables; exigencia trasladada a los planes por unidad |
| AUTONOMIA-03 | Cumple | FR-SCO-09, FR-INT-01, RT-5, NFR-SEC-06 |
| AUTONOMIA-04 | Cumple | FR-BIA-05, FR-MOD-05 |
| AUTONOMIA-05 | Cumple | FR-INT-03, FR-BIA-09, NFR-SEC-03/07, narrativa sin LLM externo |
| AUTONOMIA-06 | Cumple | FR-SCO-04/05, FR-EXP-02/05, §8.5 (conflicto del PRD resuelto) |
| SECURITY-01..15 | Cumple (como requisito) | NFR-SEC-01..15; la verificación de diseño y código ocurre en etapas posteriores |
| RESILIENCY-01, -02 | Cumple (propuesta) | NFR-RES-01/02/03; SLA propuesto como [INTERNO] |
| RESILIENCY-03, -04, -08, -09, -15 | Cumple | Decisiones del usuario R3–R9 registradas |
| RESILIENCY-05..07, -10..13 | Cumple (como requisito) | Detalle en NFR/Infra Design |
| RESILIENCY-14 | N/A en esta etapa | Pregunta obligatoria en NFR Design |
| PBT-09 | Cumple | NFR-TST-01 |
| PBT-01..08, -10 | N/A en esta etapa | Se aplican en Functional Design y Code Generation (Planning); candidatas listadas en NFR-TST-02 |
