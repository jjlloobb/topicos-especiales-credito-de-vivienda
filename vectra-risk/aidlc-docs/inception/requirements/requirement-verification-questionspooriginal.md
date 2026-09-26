# Preguntas de verificación de requisitos — Vectra Risk

`entradas/prd.md` es muy completo en el *qué* y el *por qué*. Estas preguntas cubren solo
lo que el PRD deja abierto (TBD), lo que se contradice entre PRD, PVB y la extensión
de límite de autonomía, y las decisiones técnicas que la especificación necesita para
poder descomponer el producto en unidades con planes de tareas verificables.

Responde cada pregunta escribiendo la letra después de `[Answer]:`. Si ninguna opción
encaja, elige la última (Other) y describe tu preferencia. Avísame cuando termines.

---

## Parte A — Conflictos detectados entre las fuentes

## Question 1
**Fail-closed en el primer incremento.** El PRD §13 (Módulos 4-5) entrega
`explainability-service` "sin fail-closed activo todavía". La regla bloqueante
AUTONOMIA-06 prohíbe cualquier tarea que entregue un score como decisión usable sin
explicación sincronizada. ¿Cómo se resuelve?

A) Fail-closed activo desde el primer incremento en que `scoring-service` y `explainability-service` coexisten; el PRD §13 se ajusta (recomendado — cumple AUTONOMIA-06 sin excepciones)

B) Se respeta la secuencia del PRD, pero en ese incremento ningún consumidor (consola, API externa) recibe el score: solo se usa para pruebas internas de serving, y fail-closed se activa antes de exponer cualquier score

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 2
**Congelamiento automático del modelo.** El PRD §8 lo clasifica como *Should have*,
pero la respuesta a la objeción de sesgo (§3.7), el journey 7.4, el red-teaming #2 y la
Sesión 16 lo presentan como activo "desde el día uno". ¿Qué prioridad tiene?

A) Se promueve a *Must have* del MVP (recomendado — varias promesas del PRD dependen de él)

B) Se mantiene como *Should have*; la respuesta a la objeción de §3.7 se reformula para no prometerlo

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 3
**Modelo de despliegue y tiers.** El PVB §7 describe el tier *Enterprise* como
"despliegue self-hosted", lo que implica que Starter/Growth no lo son. El PRD
(Principio 2 y *Won't have*: multi-tenant/SaaS) exige self-hosted siempre. ¿Qué rige
la especificación?

A) Rige el PRD: todo tier es self-hosted en el clúster del banco; los tiers solo difieren en límites comerciales y la especificación no implementa licenciamiento (recomendado)

B) Rige el PRD, y además el MVP incluye un contador de solicitudes evaluadas por mes para soportar los límites de los tiers (sin bloquear el scoring)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 4
**Alcance de los *Should have* en esta especificación.** ¿Qué entra en el alcance que
se descompone en unidades?

A) Todos los *Must* + todos los *Should* (disparidad pre/post por fuente, métrica de adopción de la explicación, GitOps, freeze automático) — coherente con el plan de Módulo 8 y la Sesión 16 (recomendado)

B) Solo los *Must*; los *Should* quedan documentados como backlog sin unidades

C) Los *Must* + solo los *Should* que se demuestran en la Sesión 16 (freeze, pre/post, métrica de adopción/ruido), dejando GitOps como backlog

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Parte B — Vacíos funcionales del PRD

## Question 5
**Narrativa de la explicación (TBD de arquitectura, PRD §11).** ¿Cómo traduce
`explainability-service` los valores SHAP a lenguaje no técnico? Nota: cualquier LLM
debe correr dentro del clúster del banco (AUTONOMIA-05).

A) Plantilla determinística sobre el vector SHAP (menor riesgo, menor naturalidad)

B) LLM self-hosted en el clúster con **solo SHAP estructurado** como input, con validación automática de factualidad contra el vector SHAP antes de mostrar (recomendación del PRD)

C) Plantilla determinística en el MVP, con el contrato preparado para enchufar la opción B después

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 6
**Sobre qué se mide la disparidad.** El sistema nunca aprueba ni rechaza (Principio 1).
¿La "disparidad de tasa de aprobación" (<5 pp) se calcula sobre…?

A) La recomendación del modelo (score contra el punto de corte de la política), porque es lo que el sistema controla y lo que se congela

B) La decisión final humana registrada en el Decision Registry

C) Ambas, reportadas por separado; el freeze se dispara solo con la disparidad de la recomendación del modelo

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 7
**Grupos protegidos a monitorear** (datos sintéticos en el MVP).

A) Sexo y rango de edad

B) Sexo, rango de edad y región/departamento

C) Sexo, rango de edad, región y estrato socioeconómico (estrato tratado como posible proxy a vigilar, no como variable de decisión)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 8
**"Controlando por capacidad de pago"** (PVB §8). ¿Cómo se implementa la métrica?

A) Diferencia de tasas de recomendación favorable entre grupos, calculada dentro de bandas de capacidad de pago (relación cuota/ingreso) y agregada; el umbral de 5 pp aplica a la agregada

B) Diferencia bruta de tasas entre grupos (paridad estadística), con la vista por bandas solo como información de contexto

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 9
**Separación modelo / política de negocio** (cumplimiento veta si no existe, PRD §3.4).
¿Debe el MVP tener una política de negocio versionada separada del modelo (punto de
corte, umbral de baja confianza, reglas por canal)?

A) Sí: política versionada e independiente del modelo, cambiable solo con aprobación explícita del CRO, y cada decisión registra `policy_version_id` además de `model_version_id` (recomendado)

B) No: el punto de corte vive como configuración del despliegue del modelo

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 10
**Origen de las solicitudes de crédito** (no hay integración real con core ni canales).

A) Un generador/simulador de canal que envía solicitudes sintéticas al API Gateway (y permite inyectar casos adversariales del red-teaming)

B) El analista registra solicitudes manualmente en la consola

C) Ambas: simulador de canal + alta manual en consola

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 11
**Lógica normativa colombiana (VIS, subsidios, tasas SFC)** — *Could have* en el PRD,
pero es la mitad del diferenciador declarado.

A) Fuera del MVP; la política de negocio (Q9) deja el punto de extensión documentado

B) Incluir una versión mínima: clasificación VIS/No VIS por valor de vivienda y validación de tasa contra el tope de usura vigente como reglas de la política de negocio

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 12
**Escalamiento del fail-closed persistente** (journey 7.3: "si persiste, escala como
incidente técnico").

A) Reintentos automáticos con backoff y límite configurable; al agotarlos, el caso queda en estado "no disponible" y se dispara una alerta en Alertmanager dentro del clúster

B) Igual que A, y además un aviso visible en la consola de riesgo/CRO con la lista de casos afectados

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Parte C — Decisiones técnicas

## Question 13
**Lenguaje de los servicios backend.**

A) Python (FastAPI) para todos los servicios — alineado con SHAP, Fairlearn/AIF360 y KServe

B) Python para scoring/explicación/sesgo; Go o Java para API Gateway y Decision Registry

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 14
**Consolas (analista, riesgo/CRO, cumplimiento).**

A) Una sola aplicación web (SPA, p. ej. React + TypeScript) con vistas por rol

B) Tres aplicaciones web separadas, una por rol

C) Aplicación renderizada en servidor mínima (sin SPA)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 15
**Almacenamiento append-only del Decision Registry.**

A) PostgreSQL con `UPDATE`/`DELETE` revocados al rol de la aplicación + cadena de hashes por registro para detectar manipulación (recomendado)

B) PostgreSQL con permisos revocados, sin cadena de hashes

C) Log de eventos (p. ej. Kafka/Redpanda) con retención infinita + proyección en PostgreSQL

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 16
**Identity provider del banco** (externo en producción; hay que simularlo).

A) Keycloak desplegado aparte, simulando el SSO del banco vía OIDC, con roles analista / ingeniero de riesgo / CRO / cumplimiento

B) Dex con un LDAP de prueba (OpenLDAP)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 17
**Modelo de referencia que se sirve** (no hay datos reales de cartera).

A) El equipo entrena un modelo de gradient boosting (XGBoost/LightGBM) sobre un dataset sintético con forma de crédito de vivienda colombiano, como "modelo atascado del banco"; el contrato de `scoring-service` acepta cualquier modelo tabular en formato soportado por KServe

B) Regresión logística sobre dataset sintético (más simple de explicar), mismo contrato genérico

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 18
**Clúster usado durante CONSTRUCTION** (afecta AUTONOMIA-01: nada se aplica sin aprobación humana).

A) Clúster local (kind/k3d) por desarrollador; los cambios se entregan como PR con `kubectl diff`/`helm template` como evidencia

B) Clúster compartido del curso; mismo flujo de PR con aprobación humana antes de cualquier `apply`

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 19
**Pipeline GitOps y observabilidad.**

A) Argo CD (sync manual, sin auto-sync, para respetar AUTONOMIA-01) + Prometheus/Grafana/Alertmanager dentro del clúster

B) Flux (con aprobación manual) + Prometheus/Grafana/Alertmanager dentro del clúster

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 20
**Idioma de la interfaz y de la explicación al analista.**

A) Español únicamente

B) Español con textos externalizados (i18n preparado, sin segunda lengua en el MVP)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

---

## Parte D — Extensiones de AI-DLC

## Question: Security Extensions
Should security extension rules be enforced for this project?

A) Yes — enforce all SECURITY rules as blocking constraints (recommended for production-grade applications)

B) No — skip all SECURITY rules (suitable for PoCs, prototypes, and experimental projects)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question: Resiliency Extensions
Should the resiliency baseline be applied to this project?

**Qué es.** Un conjunto de buenas prácticas **direccionales, de diseño**, derivadas del
**AWS Well-Architected Framework (pilar de Confiabilidad)**: tolerancia a fallos, alta
disponibilidad, observabilidad y recuperabilidad, en 15 áreas de práctica.

**Qué NO es.** No hace que la carga esté lista para producción ni certifica ningún
objetivo de disponibilidad, RTO o RPO. Es un **punto de partida**, no un sustituto de una
revisión formal Well-Architected.

A) Yes — apply the resiliency baseline as directional best practices and design-time guidance (recommended for business-critical workloads, as an informed starting point that you can validate and harden before go-live)

B) No — skip the resiliency baseline (suitable for PoCs, prototypes, and experimental projects where rapid iteration matters more than reliability)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question: Property-Based Testing Extension
Should property-based testing (PBT) rules be enforced for this project?

A) Yes — enforce all PBT rules as blocking constraints (recommended for projects with business logic, data transformations, serialization, or stateful components)

B) Partial — enforce PBT rules only for pure functions and serialization round-trips (suitable for projects with limited algorithmic complexity)

C) No — skip all PBT rules (suitable for simple CRUD applications, UI-only projects, or thin integration layers with no significant business logic)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

---

**Nota:** la extensión *Límite de autonomía del agente* (AUTONOMIA-01 a 06) no tiene
opt-in: se aplica siempre como restricción bloqueante.
