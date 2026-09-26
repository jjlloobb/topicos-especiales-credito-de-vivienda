# Plan de Application Design — Vectra Risk

Entradas: `requirements.md`, `stories.md` y `personas.md` (aprobados), y PRD §9 (módulos y
diagrama). Alcance: componentes, responsabilidades, interfaces y dependencias. Las
reglas de negocio detalladas quedan para Functional Design, por unidad.

El PRD §9 da 8 módulos. Al cruzarlos con las historias aparecen responsabilidades que el
PRD no ubica en ningún componente:
- el ciclo de vida del caso (estados de la bandeja, reintentos con backoff);
- el registro de versiones de modelo y de política con sus aprobaciones;
- el cálculo de las métricas de negocio (North Star y métrica de ruido);
- el mecanismo concreto de congelamiento.

Estas preguntas deciden dónde vive cada una.

---

## Parte A — Preguntas

Escribe la letra de tu elección después de cada `[Answer]:`. Si ninguna opción encaja,
usa la última (Other) y descríbela.

## Question 1
**Gobierno de modelos, políticas y fuentes de datos** (US-201..208, US-306). ¿Dónde vive?

A) Un `governance-service` dedicado que administra versiones de modelo, versiones de política, fuentes de datos y sus aprobaciones y máquinas de estado. Scoring solo **lee** la versión activa y la política vigente, y así cumple FR-POL-04: los servicios no modifican su propia política (recomendado)

B) Dos servicios separados: `model-registry-service` (modelos y fuentes) y `policy-service` (políticas)

C) Dentro de `scoring-service`, con endpoints de administración protegidos por rol

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 2
**Propiedad del Decision Registry.**

A) Un `decision-registry-service` dedicado es el **único escritor** de la BD del registro. Expone una API de agregado (append) y consulta, y serializa la cadena de hashes. Los demás servicios le escriben por API y nunca tocan la BD (recomendado: un solo punto controla el append-only)

B) BD compartida: cada servicio escribe con su rol de BD en tablas del registro, y la cadena de hashes se calcula con un trigger en PostgreSQL

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 3
**Ciclo de vida del caso y orquestación** (bandeja, estados, reintentos con backoff, escalamiento; US-107, US-112).

A) Un `case-service` administra la solicitud y el caso: estados listo / en_sincronizacion / no_disponible / modelo_congelado, reintentos y escalamiento. Invoca a `scoring-service`, que conserva la llamada síncrona a `explainability-service` y el fail-closed (flujo SC→EX del PRD) (recomendado)

B) `scoring-service` orquesta todo: ingesta, estados del caso, reintentos, explicación y persistencia

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 4
**Comunicación síncrona o asíncrona.** Los reintentos, el cálculo periódico de sesgo y los eventos de gobierno necesitan algún mecanismo diferido.

A) HTTP síncrono entre servicios. Los reintentos y los trabajos diferidos van en una cola transaccional en PostgreSQL (tabla de trabajos con `SKIP LOCKED`) y en CronJobs de Kubernetes para el sesgo. No se agrega un broker (recomendado: menos componentes que asegurar, operar y respaldar en el clúster del banco)

B) Agregar un broker de mensajes in-cluster (NATS JetStream o Redpanda) para ingesta y eventos de dominio

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 5
**API Gateway y acceso de la SPA.**

A) Un gateway estándar (p. ej. Envoy Gateway) que valida JWT, aplica rate limiting y access log, más un **BFF** en FastAPI para la SPA. Cada servicio vuelve a validar el JWT y el rol, como defensa en profundidad (SECURITY-08, SECURITY-11) (recomendado)

B) Un gateway propio en FastAPI que hace enrutamiento, autenticación y autorización

C) Un gateway estándar sin BFF: la SPA llama directamente a las APIs de cada servicio

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 6
**Dónde se calcula SHAP** (clave para el fail-closed).

A) El explicador corre como **componente `explainer` del mismo `InferenceService` de KServe** que el predictor, así que la misma revisión despliega ambos. `explainability-service` pide el vector SHAP a ese explicador, compara el `model_version_id`, genera la narrativa y valida la factualidad. La sincronía queda reforzada por la plataforma, no solo por código (recomendado)

B) `explainability-service` es autónomo: carga el artefacto del modelo por `model_version_id` y calcula SHAP por su cuenta

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 7
**Mecanismo de congelamiento** (US-303, AUTONOMIA-04).

A) `bias-monitoring-service` llama a `governance-service` con una identidad de servicio que **solo** puede ejecutar la transición `activo → congelado`. `case-service`/`scoring-service` consultan el estado antes de servir. Ningún servicio tiene permisos sobre recursos de Kubernetes para esto (recomendado: mínimo privilegio, sin escritura en el clúster)

B) `bias-monitoring-service` modifica el `InferenceService`: lo escala a 0 o le pone una anotación de congelado. Requiere permisos de escritura sobre recursos de KServe

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 8
**Métricas de negocio** (North Star, métrica de ruido, tasa sostenida; US-503..505).

A) Un componente `product-metrics` (job o servicio ligero) calcula las métricas de negocio a partir del Decision Registry y las expone a Prometheus. Las métricas operativas (latencia, errores, fail-closed) las emite cada servicio. Todo va a Grafana (recomendado)

B) Cada servicio emite contadores y todas las métricas de negocio se derivan con recording rules de Prometheus

X) Other (please describe after [Answer]: tag below)

[Answer]: 

---

## Parte B — Checklist de ejecución

- [ ] 1. Analizar el contexto (requirements, stories, personas, PRD §9) y fijar el inventario de componentes según Q1–Q8
- [ ] 2. Generar `aidlc-docs/inception/application-design/components.md`
  - [ ] 2.1 Propósito, responsabilidades e interfaces de cada componente
  - [ ] 2.2 Clasificación de criticidad y efecto de su indisponibilidad (RESILIENCY-01)
  - [ ] 2.3 Restricciones AUTONOMIA/SECURITY que aplican a cada componente
- [ ] 3. Generar `component-methods.md`
  - [ ] 3.1 Firmas de métodos/endpoints con tipos de entrada y salida (sin reglas de negocio detalladas)
  - [ ] 3.2 Contrato de sincronía scoring ↔ explicación ↔ registro (`model_version_id`, `policy_version_id`)
  - [ ] 3.3 Interfaz reemplazable de narrativa (FR-EXP-06)
- [ ] 4. Generar `services.md`
  - [ ] 4.1 Orquestación de los flujos: originación (7.1), promoción de modelo (7.2), desincronía (7.3), congelamiento (7.4), expediente (caso de uso 2)
- [ ] 5. Generar `component-dependency.md`
  - [ ] 5.1 Matriz de dependencias y patrones de comunicación
  - [ ] 5.2 Diagrama de flujo de datos (Mermaid validado + alternativa en texto)
  - [ ] 5.3 Fronteras de confianza y egress permitido (AUTONOMIA-05)
- [ ] 6. Generar `application-design.md` consolidado
- [ ] 7. Validar que el diseño es completo y consistente: cada historia tiene al menos un componente responsable; compliance de extensiones
