# Plan de generación de historias de usuario — Vectra Risk

Rol asumido: product owner. Entradas: `inception/requirements/requirements.md` (aprobado),
`entradas/prd.md` §3.4, §5, §7 y §11.

---

## Parte A — Preguntas (responder antes de generar)

Escribe la letra de tu elección después de cada `[Answer]:`. Si ninguna opción encaja,
usa la última (Other) y descríbela.

## Question 1
**Enfoque de desglose de las historias.**

A) **Journey-based**: las historias siguen los journeys del PRD (7.1 analista, 7.2 despliegue de modelo, 7.3 desincronía, 7.4 sesgo). Muy cercano a la demo de la Sesión 16, pero reparte las capacidades transversales (registro, RBAC) entre varios journeys

B) **Persona-based**: agrupadas por rol (analista, ingeniero de riesgo, CRO, cumplimiento). Fácil de validar con cada stakeholder, pero oculta las historias de sistema (fail-closed, freeze)

C) **Epic-based híbrido**: épicas por capacidad de negocio (Originación explicada, Gobierno de modelos y política, Vigilancia de sesgo, Registro y auditoría, Seguridad y plataforma). Dentro de cada épica, historias por persona y trazadas a los journeys y a los RT-1..5. Es el que mejor se mapea a unidades de trabajo (recomendado)

D) **Feature-based**: una épica por servicio o módulo del PRD §9. Está alineado a la arquitectura, pero se aleja del valor para el usuario

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 2
**Historias de sistema / plataforma.** Varios requisitos no tienen un actor humano
directo: fail-closed, congelamiento automático, NetworkPolicies, cadena de hashes. ¿Cómo
se expresan?

A) Como historias cuyo beneficiario es la persona humana que protegen (p. ej. "Como oficial de cumplimiento, quiero que el modelo se congele automáticamente…"). Todo queda centrado en el usuario (recomendado)

B) Como "historias técnicas / enablers" con actor "el sistema" en una épica aparte

C) Como requisitos no funcionales referenciados desde las historias, sin historia propia

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
**Granularidad.**

A) Historias pequeñas: cada una se implementa y verifica dentro de una sola unidad de trabajo, y apunta a unas 30–50 historias en total (recomendado para mapear después a planes de tareas)

B) Historias medianas, del tamaño de una capacidad: unas 15–25 en total, con subtareas definidas más tarde

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
**Formato de los criterios de aceptación.**

A) Gherkin (Given/When/Then), con al menos un escenario negativo o de abuso por historia cuando aplique, y una línea "Verificación" que nombra el tipo de prueba o comando (AUTONOMIA-02) (recomendado)

B) Lista de condiciones verificables en viñetas, cada una con su verificación

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
**Personas.** ¿Cuántas y cuáles?

A) Las 4 personas humanas del sistema (analista, ingeniero de riesgo, CRO, oficial de cumplimiento), más una persona "comité de crédito" que consume la evidencia pero no opera la UI

B) Solo las 4 personas que operan el sistema

C) Las 4 operativas + comité + una persona "auditor/supervisor externo" (Superintendencia), que no usa el sistema pero a la que hay que poder responder (caso de uso 2)

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 6
**Priorización dentro de las historias.**

A) MoSCoW heredado de los requisitos (M/S/C→), sin ordenamiento adicional

B) MoSCoW + marca de "demo Sesión 16" para las historias que sostienen las 5 demostraciones del PRD §13

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 7
**Irrelevancia silenciosa (North Star y métrica de ruido).** ¿Se escriben historias
para el comportamiento del analista que alimenta esas métricas? Por ejemplo: registrar si
abrió el detalle de la explicación, o pedir una justificación estructurada cuando se
aparta del score.

A) Sí: historias explícitas de instrumentación del uso, con justificación **estructurada** (lista de factores de la explicación que usó + texto libre) al registrar la decisión (recomendado: sin eso la North Star no se puede calcular)

B) Sí, pero con justificación en texto libre únicamente

C) No: se deja como requisito de métrica sin historia de usuario

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8
**Solicitante final.** El solicitante no usa el sistema, pero el PRD §5 caso 2 menciona
defender un rechazo "ante el solicitante".

A) Incluir una historia para que el analista o el CRO obtenga un resumen de los factores del rechazo en lenguaje apto para el solicitante (sin datos de terceros ni detalles del modelo)

B) Fuera de alcance: solo la defensa ante el comité y el supervisor

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución (Part 2 — Generation)

- [x] 1. Crear `aidlc-docs/inception/user-stories/personas.md`
  - [x] 1.1 Definir cada persona según Q5: objetivos, frustraciones, contexto, qué la hace vetar o abandonar el sistema (PRD §3.4)
  - [x] 1.2 Indicar para cada persona permisos de rol (Keycloak) y MFA requerido
- [x] 2. Definir la estructura de épicas según Q1
  - [x] 2.1 Enumerar las épicas con su objetivo de negocio y los requisitos FR/NFR que cubren
- [x] 3. Redactar las historias según Q2, Q3 y Q4
  - [x] 3.1 Épica(s) de originación explicada (journey 7.1, FR-ING, FR-SCO, FR-EXP, FR-UI-01/02)
  - [x] 3.2 Fail-closed y desincronía (journey 7.3, FR-SCO-04..08, RT-3)
  - [x] 3.3 Gobierno de versiones de modelo y política (journey 7.2, FR-MOD, FR-POL, VIS/usura)
  - [x] 3.4 Vigilancia de sesgo y congelamiento (journey 7.4, FR-BIA, RT-2)
  - [x] 3.5 Registro y auditoría (FR-REG, caso de uso 2)
  - [x] 3.6 Métricas de adopción y ruido (FR-MET, según Q7)
  - [x] 3.7 Seguridad, soberanía y límites de autonomía (FR-INT, FR-PLT, RT-1, RT-4, RT-5)
  - [x] 3.8 Historia del solicitante, según Q8
- [x] 4. Asignar a cada historia: ID, persona, prioridad (Q6), requisitos trazados y restricciones AUTONOMIA/SECURITY aplicables
- [x] 5. Verificar INVEST (Independent, Negotiable, Valuable, Estimable, Small, Testable) en cada historia y documentar las excepciones
- [x] 6. Construir la matriz de trazabilidad requisito → historia y verificar que todo FR Must/Should y todo RT-1..5 tiene al menos una historia
- [x] 7. Construir el mapa persona → historias
- [x] 8. Guardar `aidlc-docs/inception/user-stories/stories.md` y hacer una revisión final de cumplimiento de extensiones

---

## Parte C — Enfoque resultante (según respuestas)

- **Desglose (Q1=C)**: épicas por capacidad de negocio (E1 Originación explicada, E2 Gobierno de modelos y política, E3 Vigilancia de sesgo, E4 Registro y auditoría, E5 Adopción y métricas, E6 Seguridad, soberanía y plataforma). Dentro de cada épica, historias por persona trazadas a los journeys 7.1–7.4 y a RT-1..5.
- **Historias de sistema (Q2=A)**: se redactan con la persona humana protegida como beneficiaria.
- **Granularidad (Q3=A)**: historias pequeñas, cada una dentro de una sola unidad; entre 30 y 50 en total.
- **Criterios (Q4=A)**: Gherkin con escenario negativo o de abuso cuando aplique, más una línea "Verificación" (AUTONOMIA-02).
- **Personas (Q5=C)**: analista, ingeniero de riesgo, CRO, oficial de cumplimiento, comité de crédito (consumidor) y auditor/supervisor externo (no usuario).
- **Prioridad (Q6=B)**: MoSCoW + marca 🎯 "demo Sesión 16".
- **Irrelevancia silenciosa (Q7=A)**: historias explícitas de instrumentación y justificación estructurada (factores usados + texto libre).
- **Solicitante (Q8=A)**: se incluye una historia de resumen de factores del rechazo, apto para el solicitante.
- **Análisis de respuestas**: sin ambigüedades ni contradicciones.
