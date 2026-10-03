# Plan de unidades de trabajo — Vectra Risk

Entradas: `application-design.md` (aprobado: 18 componentes, flujos F01–F73, K01–K06,
X01–X10), `stories.md` (49 historias) y `execution-plan.md`.

**Recordatorio del entregable:** cada unidad definida aquí pasará en CONSTRUCTION por
Functional Design, NFR Requirements, NFR Design, Infrastructure Design y **plan de
tareas**. Ahí termina el trabajo. La descomposición determina cuántos planes de tareas
habrá y qué contiene cada uno.

---

## Parte A — Descomposición propuesta (base para las preguntas)

| # | Unidad propuesta | Componentes | Épicas / historias principales |
|---|---|---|---|
| U1 | `platform-foundation` | namespaces, NetworkPolicy deny-all base, operador de PostgreSQL + bases, model-store, observability-stack, Argo CD, plantillas de CI | US-604 (base), US-605, US-606, US-607, US-608, US-610 (stack) |
| U2 | `identity-edge` | Keycloak (realm, roles, MFA, clientes/scopes), api-gateway (Envoy), rutas F01–F07 | US-601, US-611 |
| U3 | `decision-registry` | decision-registry-service, `registry-db` | E4 (US-401..404), US-113 |
| U4 | `governance` | governance-service, model-validation-job, promotion-tool | E2 (US-201..208), US-305, US-306 (lado governance) |
| U5 | `model-serving` | InferenceService predictor + explainer del modelo de referencia | US-201 (artefacto), US-204 (manifiestos), US-609 (KServe) |
| U6 | `scoring-explainability` | scoring-service (+ motor de política), explainability-service | US-103..106, US-109, US-110, US-111, US-207 (motor) |
| U7 | `case-management` | case-service, core-banking-mock | US-101, US-102, US-107, US-108, US-112, US-501, US-502, US-603 |
| U8 | `bias-monitoring` | bias-monitoring-service, librería de disparidad | E3 (US-301..304, US-306..308) |
| U9 | `console` | console-bff, console-spa | vistas de E1–E5, US-602 |
| U10 | `product-metrics` | product-metrics, dashboards y alertas de negocio | E5 (US-503..505) |

Transversales que dependen de las respuestas: contratos compartidos (Q3), modelo de
referencia (Q7) y verificación de sistema / red-teaming (Q8).

---

## Parte B — Preguntas

Escribe la letra de tu elección después de cada `[Answer]:`. Si ninguna opción encaja,
usa la última (Other) y descríbela.

## Question 1 — Granularidad (Story Grouping / Business Domain)
¿Qué nivel de descomposición quieres?

A) La propuesta de la Parte A: unas 10 unidades, más las transversales que resulten de Q3, Q7 y Q8. Cada unidad es una capacidad coherente con su propio dueño de datos (recomendado)

B) Una unidad por componente desplegable: unas 16 unidades y planes de tareas más pequeños, pero con más coordinación entre ellos

C) Unidades gruesas por épica: unas 5 (plataforma, originación, gobierno, sesgo, consola) y planes de tareas grandes

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Scoring y explainability (Dependencies / Technical)
Son dos servicios desplegables, pero el fail-closed (AUTONOMIA-06, RT-3) es un contrato
entre ambos.

A) Una sola unidad (`scoring-explainability`) con dos servicios: el contrato de sincronía, sus PBT y RT-3 se diseñan y planifican juntos (recomendado)

B) Dos unidades separadas; el contrato se fija en la unidad de contratos (Q3) y RT-3 se verifica en la unidad de verificación de sistema

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Contratos compartidos (Dependencies)
Varios servicios comparten tipos (`Recommendation`, `FailClosed`, `MonitoringLabels`,
entradas del registro), scopes y utilidades (logger sin PII, validación de JWT).

A) Una unidad `contracts` que se construye **primero**: especificaciones OpenAPI de todas las APIs internas, modelos Pydantic y cliente TypeScript generados a partir de ellas, y librerías comunes (logger con redacción de PII, middleware de autenticación y correlación). Las demás unidades dependen de versiones publicadas (recomendado)

B) Contract-first sin unidad propia: cada unidad publica su OpenAPI y los consumidores generan sus clientes; las utilidades comunes se duplican

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Organización del código y del repositorio GitOps (Code Organization)
Patrón greenfield multi-servicio de AI-DLC: `{unit-name}/src/`, `{unit-name}/tests/`.

A) **Monorepo** de aplicación (`vectra-risk/`: una carpeta por unidad, más `contracts/` y `platform/`) y un **repositorio GitOps separado** (`vectra-risk-gitops`) que solo contiene values y manifiestos desplegables. Los autores de código y los aprobadores del despliegue quedan separados (SECURITY-13) y Argo CD solo lee manifiestos (F71) (recomendado)

B) Monorepo único que también contiene el directorio `gitops/`; Argo CD lee solo esa ruta

C) Un repositorio por unidad (polyrepo) más un repositorio GitOps

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Equipo (Team Alignment)
¿Quién construirá las unidades? Esto afecta el orden y cuánto hay que fijar por
adelantado.

A) Un solo equipo pequeño (curso) que avanza unidad por unidad en orden de dependencias

B) Varios equipos en paralelo; los contratos (Q3) se congelan antes y las unidades independientes avanzan a la vez

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Secuencia frente al plan del curso (PRD §13)
El PRD organiza la entrega por módulos del curso (4-5 K8s/CKA, 6 CKAD, 7 CKS, 8
producción).

A) Ordenar las unidades por dependencias técnicas y **anotar** en cada una el módulo del curso donde se demuestra, de modo que se sigan cubriendo los hitos del PRD §13 (corregido: fail-closed desde el inicio) (recomendado)

B) Ordenar estrictamente por módulo del curso, aunque eso obligue a construir partes de una unidad en momentos distintos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Modelo de referencia y dataset sintético
El PRD dice que el banco entrena **fuera** de Vectra Risk. El MVP igual necesita un
dataset sintético con forma de crédito de vivienda colombiano, un modelo gradient
boosting y su explicador SHAP empaquetados, y los datasets de validación y
adversariales (30–50 casos).

A) Una unidad propia, `reference-model`, **fuera de la frontera del producto**: genera el dataset sintético (incluidas variables proxy para RT-2), entrena, empaqueta predictor y explainer en el formato de KServe y produce los datasets de validación y adversariales. Hace de "banco" que entrega un modelo (recomendado)

B) Dentro de la unidad `model-serving`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Verificación de sistema y red-teaming (Technical)
RT-1..5, la carga simulada (US-609), las pruebas negativas X01–X10 y las demos de la
Sesión 16 cruzan varias unidades.

A) Una unidad final, `system-verification`, que contiene el channel-simulator (con modo adversarial), la suite e2e de RT-1..5 y X01–X10, la prueba de carga simulada y los scripts de demo de la Sesión 16. Cada unidad sigue teniendo sus propias pruebas; esta unidad cubre lo que cruza unidades (recomendado)

B) Sin unidad propia: cada escenario va en la unidad que "más" lo toca (p. ej. RT-5 en `case-management`) y el simulador va en `case-management`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte C — Checklist de ejecución (Part 2 — Generation)

- [x] 1. Fijar la lista final de unidades según Q1, Q2, Q3, Q7 y Q8
- [x] 2. Generar `aidlc-docs/inception/application-design/unit-of-work.md`
  - [x] 2.1 Por unidad: propósito, componentes, responsabilidades, datos propios, flujos F/K/X que le corresponden y criticidad
  - [x] 2.2 Por unidad: qué etapas de diseño de CONSTRUCTION aplican (con justificación si alguna se omite) y el módulo del curso (Q6)
  - [x] 2.3 Estrategia de organización del código y de repositorios (Q4), con rutas concretas por unidad
- [x] 3. Generar `unit-of-work-dependency.md`
  - [x] 3.1 Matriz de dependencias entre unidades (de contrato, de datos, de plataforma)
  - [x] 3.2 Orden de construcción y ruta crítica (Q5, Q6), con Mermaid validado y alternativa en texto
- [x] 4. Generar `unit-of-work-story-map.md`
  - [x] 4.1 Asignar las 49 historias: una unidad **dueña** por historia y unidades **contribuyentes** cuando aplique
  - [x] 4.2 Asignar los flujos X01–X10 y los escenarios RT-1..5 a la unidad que los verifica
- [x] 5. Validar: todas las historias asignadas, ningún componente sin unidad, sin dependencias circulares; compliance de extensiones

---

## Parte D — Descomposición resultante (según respuestas: todas A)

Análisis de respuestas: sin ambigüedades ni contradicciones. Q1=A se combina con Q3=A,
Q7=A y Q8=A, lo que agrega 3 unidades transversales a las 10 de la Parte A. Q2=A mantiene
scoring y explainability juntas.

| Orden | Unidad | Nota |
|---|---|---|
| U0 | `contracts` | Nueva (Q3): OpenAPI, modelos generados, librerías comunes. Se construye primero |
| U1 | `platform-foundation` | — |
| U2 | `identity-edge` | — |
| U3 | `decision-registry` | — |
| U4 | `governance` | — |
| U5 | `reference-model` | Nueva (Q7): fuera de la frontera del producto; actúa como "banco" |
| U6 | `model-serving` | — |
| U7 | `scoring-explainability` | Una unidad, dos servicios (Q2) |
| U8 | `case-management` | case-service + core-banking-mock; el channel-simulator pasa a U12 (Q8) |
| U9 | `bias-monitoring` | — |
| U10 | `console` | — |
| U11 | `product-metrics` | — |
| U12 | `system-verification` | Nueva (Q8): simulador, RT-1..5, X01–X10, carga, demos de la Sesión 16 |

- Repositorios (Q4=A): monorepo `vectra-risk/` + repositorio `vectra-risk-gitops` separado.
- Equipo (Q5=A): un solo equipo, avance secuencial por dependencias.
- Secuencia (Q6=A): orden por dependencias, con el módulo del curso anotado en cada unidad.
- El orden exacto y la ruta crítica se validan en `unit-of-work-dependency.md`.
