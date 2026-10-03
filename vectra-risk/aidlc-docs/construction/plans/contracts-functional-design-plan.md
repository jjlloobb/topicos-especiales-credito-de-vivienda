# Plan de Functional Design — U0 `contracts`

**Alcance de la unidad:** contratos y tipos de dominio compartidos. Incluye:
- OpenAPI de las APIs internas y del BFF;
- el esquema de la solicitud y de las features;
- `MonitoringLabels`;
- el invariante de `Recommendation`;
- las entradas del registro;
- el modelo de errores;
- la redacción de PII en logs;
- el catálogo de scopes.

**Historias:** contribuye a US-111 (invariante de sincronía), US-602 (middleware de
autorización), US-604 (logs sin PII) y US-611 (errores genéricos).

U0 define la forma de los datos que usan todas las demás unidades. Por eso varias de
estas preguntas son de negocio aunque la unidad sea técnica.

---

## Parte A — Preguntas

Escribe la letra de tu elección después de cada `[Answer]:`. Si ninguna opción encaja,
usa la última (Other) y descríbela.

## Question 1 — Campos de la solicitud de crédito (Domain Model)
¿Qué campos tiene la solicitud (`ApplicationIn`)? Son los que U5 sintetiza y el modelo
de referencia usa.

A) Conjunto propuesto:
   - **identificación**: nombre, tipo y número de documento, fecha de nacimiento, teléfono, email, dirección, departamento, municipio;
   - **ingresos y obligaciones**: ingreso mensual, otros ingresos, tipo de empleo (asalariado, independiente, pensionado), antigüedad laboral en meses, obligaciones mensuales vigentes, días de mora máxima en 12 meses;
   - **crédito**: valor de la vivienda, monto solicitado, plazo en meses, tasa propuesta EA, vivienda nueva o usada, canal, broker;
   - **monitoreo**: sexo, estrato;
   - **texto libre**: observaciones del solicitante o del canal.

   (Recomendado: cubre VIS, usura, cuota/ingreso y las etiquetas de monitoreo)

B) Conjunto mínimo: ingreso, obligaciones, valor de la vivienda, monto, plazo, tasa, canal, atributos de monitoreo y texto libre (sin datos de contacto ni de empleo)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Qué se considera PII y cómo se redacta en logs (Business Rules, US-604)

A) **Allowlist**: el logger solo emite los campos declarados como "loggable" en el contrato (IDs técnicos, `case_id`, `model_version_id`, códigos de estado y de error, duraciones). Cualquier otro campo se descarta, sin intentar detectar PII. Las `MonitoringLabels` tampoco se registran en logs: solo viven en el registro (recomendado)

B) **Denylist**: el logger emite todo salvo los campos marcados como PII (identificación, ingresos, texto libre)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Categorías de `MonitoringLabels` (Domain Model, Q7/Q8 de requisitos)

A) Propuesta:
   - **sexo**: `F`, `M`, `no_informado`;
   - **rango_edad**: `18-25`, `26-35`, `36-45`, `46-55`, `56-65`, `66+`;
   - **región**: las **6 regiones naturales** (Andina, Caribe, Pacífica, Orinoquía, Amazonía, Insular), derivadas del departamento;
   - **estrato**: `1`–`6` y `no_informado`;
   - **banda de capacidad de pago**, por relación cuota/ingreso: `<20%`, `20–30%`, `>30%`.

   El límite del 30 % se toma como referencia de política para vivienda en Colombia **[VERIFICAR contra la norma vigente]**. (Recomendado: las regiones evitan grupos con muestras muy pequeñas)

B) Igual que A, pero con **departamento** (33 valores) como región: más detalle, pero muchas bandas con muestra insuficiente

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Datos de entrada guardados en el registro (Data Flow, US-403)
El expediente para el supervisor necesita los "datos de entrada" de la decisión, y el
registro es inmutable.

A) El registro guarda el **vector de features que usó el modelo** (valores ya transformados), las `MonitoringLabels` y una referencia al caso (`case_id`). **No** guarda identificadores directos (nombre, documento, contacto), que se quedan en `case-db`. El expediente los une solo cuando lo pide un rol autorizado (recomendado: minimiza la PII en un almacén que no se puede borrar)

B) El registro guarda una copia completa de la solicitud, identificadores incluidos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Etiquetas legibles de las features para la narrativa (Integration Points)
La plantilla en español necesita un nombre legible por feature ("relación cuota/ingreso",
"días de mora en 12 meses") y la frase de dirección del efecto. Las features pueden
cambiar entre versiones de modelo.

A) Cada paquete de modelo trae un **diccionario de features** versionado: id, etiqueta en español, unidad y frases de dirección. U0 define su esquema, U5 lo produce, governance lo registra con la versión y explainability lo usa. Si el diccionario no cubre una feature del vector SHAP, la explicación **falla** y se aplica fail-closed (recomendado)

B) Un diccionario global en U0, igual para todos los modelos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Modelo de errores de las APIs (Error Handling, US-611)

A) `application/problem+json` (RFC 9457) con `type`, `title` genérico, `status` y `code` de un catálogo cerrado (p. ej. `validation_error`, `forbidden`, `mfa_required`, `conflict_state`, `fail_closed`), más `correlation_id`. Nunca incluye detalle interno ni stack traces (recomendado)

B) Un JSON propio `{error, message, correlation_id}` con mensajes genéricos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Versionado de contratos (Business Logic Modeling / coordinación)

A) **Una sola versión semántica para todo el paquete** de contratos (specs + librerías). Un cambio incompatible sube la versión mayor y exige actualizar a todos los consumidores en el mismo PR del monorepo (recomendado para un solo equipo)

B) Versión semántica independiente por especificación de servicio

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Representación de montos y tasas (Domain Model)
El tope de usura en Colombia se expresa como tasa efectiva anual.

A) Montos en **pesos colombianos enteros** (sin decimales). Tasas como **decimal efectivo anual** con 4 decimales (p. ej. `0.1350`). Nunca se usa punto flotante binario para montos ni tasas en las reglas de política (recomendado)

B) Montos y tasas como decimal con 2 decimales

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el contexto de la unidad (unit-of-work, story map, component-methods)
- [x] 2. Generar `construction/contracts/functional-design/domain-entities.md`
  - [x] 2.1 Solicitud, features, `MonitoringLabels`, `Recommendation`, `Explanation`, `FailClosed`, entradas del registro por tipo, diccionario de features, modelo de errores, scopes
- [x] 3. Generar `business-rules.md`
  - [x] 3.1 Invariante de construcción de `Recommendation` (AUTONOMIA-06)
  - [x] 3.2 Reglas de validación de campos (rangos, formatos, longitudes)
  - [x] 3.3 Reglas de redacción de logs (Q2) y de derivación de etiquetas (Q3)
  - [x] 3.4 Reglas de versionado (Q7) y de representación numérica (Q8)
- [x] 4. Generar `business-logic-model.md`
  - [x] 4.1 Flujos de las librerías comunes (autorización, correlación, errores, redacción)
  - [x] 4.2 **Propiedades testeables (PBT-01)** por componente, con su categoría
- [x] 5. Verificar el cumplimiento de las extensiones
