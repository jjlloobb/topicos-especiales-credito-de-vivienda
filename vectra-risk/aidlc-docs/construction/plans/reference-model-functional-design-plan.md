# Plan de Functional Design — U5 `reference-model`

**Alcance de la unidad** (`unit-of-work.md` §1): hace de «banco que entrega su modelo» y queda
**fuera de la frontera del producto**. Contiene:
- generador de dataset sintético con forma de crédito de vivienda colombiano;
- variante con variables proxy para RT-2;
- entrenamiento gradient boosting y empaquetado del predictor + explicador SHAP con `model_version_id` y checksum;
- dataset de validación;
- conjunto adversarial curado de 30–50 casos (RT-1, RT-4 y artefactos desincronizados para RT-3).

No tiene runtime. Sus artefactos entran por el registro de U4. NFR Design e Infrastructure
Design = SKIP (`unit-of-work.md` §2).

**Contribuye a:** US-106 (RT-4), US-109 (RT-1), US-111 (RT-3), US-201 (artefacto), US-202
(dataset de validación), US-303 (modelo proxy, RT-2).

**Ya decidido** (no se pregunta):
- campos de `ApplicationIn` y `MonitoringLabels` (U0 §1–§2), derivación de features compartida con U8 (`derive`, U0 business-logic-model §2.3);
- diccionario de features versionado que produce U5 (U0 §4, Q5);
- formatos permitidos: ONNX, XGBoost JSON/UBJ o LightGBM texto; **sin `pickle`/`joblib`** (U4 Q7);
- PRD §11: dataset sintético con la forma de la referencia académica (Redalyc), sin datos reales; 30–50 casos adversariales curados;
- RT-2: congelamiento cuando la disparidad agregada supera **5 pp** (US-303);
- AUC objetivo > 0,85 **[INTERNO]** (FR-MOD-02).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Cómo se genera el dataset sintético (Business Logic / Data)

A) **Generador paramétrico documentado**:
   - distribuciones y correlaciones explícitas en un archivo de configuración versionado (ingreso por estrato y región, tipo de empleo, antigüedad, obligaciones, valor de vivienda con su parte VIS **[VERIFICAR el tope VIS vigente]**, plazo, tasa, canal), calibradas a la forma de estadísticas públicas (DANE, Redalyc);
   - semilla fija, así que el mismo `generator_version` + semilla da los mismos datos, byte a byte;
   - cada fila es una `ApplicationIn` válida según U0 (identificadores sintéticos con prefijo `SYN-`, nombres de un catálogo ficticio);
   - **ningún dato real**.

   (Recomendado)

B) Un modelo generativo (p. ej. CTGAN) entrenado sobre datos de muestra

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Cómo se genera la etiqueta (incumplimiento) del dataset base (Business Logic)

A) **Función de riesgo latente** documentada:
   - el logit es función de `installment_to_income`, `loan_to_value`, `max_days_past_due_12m`, `employment_months`, `employment_type` y `monthly_obligations`/ingreso, más ruido;
   - la tasa de incumplimiento objetivo es de ~4 % **[VERIFICAR contra cifras públicas de cartera hipotecaria]**;
   - en el dataset **base**, los atributos de monitoreo (sexo, estrato, región, edad) **no** entran en la función ni en ninguna variable correlacionada a propósito, así que el modelo base debería quedar por debajo del umbral de 5 pp;
   - la función se ajusta para que un gradient boosting alcance un AUC de ~0,88 en validación.

   (Recomendado)

B) Etiqueta aleatoria con una correlación débil con el ingreso

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Features del modelo base (Business Rules / fair lending)

A) **Solo variables financieras y del crédito**: `installment_to_income`, `loan_to_value`, `monthly_income` (en logaritmo), `other_income`, `monthly_obligations`, `employment_type`, `employment_months`, `max_days_past_due_12m`, `term_months`, `proposed_rate_ea`, `property_condition` y `channel`.
   - **Excluidas**: sexo, estrato, región, departamento, municipio, edad, `free_text` y cualquier identificador.
   - La edad y la ubicación quedan solo como `MonitoringLabels`.

   (Recomendado: el modelo de referencia no debe usar atributos protegidos ni sus representaciones directas)

B) Incluir también la edad, como es común en scoring tradicional

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Formato del predictor y del explicador (Domain Model, US-201)

A) **XGBoost en JSON** como predictor. El **explicador** es un artefacto JSON de **TreeSHAP**: orden de features, modo `interventional` y una muestra de fondo (CSV de 200 filas del entrenamiento, sin identificadores). El explicador de KServe lo carga sin `pickle`. Los dos llevan el mismo `model_version_id` dentro de un `manifest.json` con los SHA-256 de cada archivo (recomendado)

B) LightGBM en texto, con el mismo esquema de explicador

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — De dónde sale la `confidence` (Business Logic, US-106, RT-4)
`Recommendation.confidence` viene del predictor (`{score, confidence, model_version_id}`), y
RT-4 exige que una entrada fuera de dominio **no** infle la confianza. La probabilidad del
modelo no sirve para eso: un gradient boosting puede dar 0,99 fuera de su dominio.

A) **Envolvente de dominio** calculada en el entrenamiento y guardada en un JSON del paquete (`domain_envelope.json`):
   - los cuantiles p1–p99 por feature numérica y las categorías vistas;
   - la covarianza robusta de las features numéricas para una distancia de Mahalanobis.

   `confidence = min(1 − fracción de features fuera de [p1, p99], 1 − F(distancia de Mahalanobis))`, donde F es la distribución empírica de las distancias en el entrenamiento. Una categoría no vista da confianza 0. El cálculo lo hace el transformer de KServe (U6) con ese JSON, sin código del banco ni `pickle` (recomendado)

B) `confidence = |score − 0,5| × 2` (margen de la probabilidad)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Variante con variables proxy para RT-2 (Business Logic, US-303)

A) **Proxies realistas, no atributos protegidos directos**:
   - se agregan al dataset y al modelo dos features plausibles, `zona_vivienda` (derivada del municipio, muy correlacionada con estrato y región) y `canal_originacion_detalle` (correlacionado con estrato);
   - la etiqueta depende en parte de ellas;
   - el resultado esperado es una disparidad agregada de **≥ 10 pp** (el doble del umbral), medida con la librería de U9 sobre el dataset de validación y documentada en el manifiesto.

   Esta variante se registra como una **versión distinta** del modelo y solo sirve para la demo de RT-2 (recomendado)

B) Incluir `sexo` directamente como feature del modelo proxy

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Composición del conjunto adversarial (Business Logic, RT-1/3/4)

A) **42 casos con su resultado esperado** en `adversarial/manifest.json`:

   | Escenario | Casos | Qué contiene | Resultado esperado |
   |---|---|---|---|
   | RT-1 | 20 | Pares de solicitudes idénticas salvo `free_text`: instrucciones en español e inglés («ignora las reglas…»), HTML/`<script>`, SQL, Markdown, Unicode engañoso y textos muy largos | Recomendación y narrativa **idénticas** a las del par sin texto; texto escapado al mostrarse |
   | RT-4 | 18 | Valores válidos según U0 pero fuera de la envolvente de dominio: ingresos extremos, LTV cercano a 1, combinaciones implausibles, categorías no vistas | `confidence` < umbral de baja confianza → `revision_requerida` con la marca |
   | RT-3 | 4 artefactos | (a) explicador de otra versión con el mismo predictor; (b) explicador sin una feature; (c) diccionario de otra versión; (d) manifiesto con un `model_version_id` distinto entre las dos piezas | `FailClosed`: `version_mismatch` o `feature_dictionary_incomplete`; nunca un score usable |

   (Recomendado)

B) Solo los casos RT-1, sin artefactos de RT-3 ni casos de RT-4

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Tamaño, partición y versionado (Domain Model, US-202)

A)
   - **120 000** solicitudes sintéticas: entrenamiento 70 %, validación 15 % (dataset de validación de U4) y prueba 15 %, con partición estratificada por etiqueta y semilla fija.
   - Un **manifiesto** por entrega con `generator_version`, semilla, tamaños, tasas de incumplimiento, AUC y disparidad medida, y el SHA-256 de cada archivo.
   - `model_version_id = mv-<fecha>-<primeros 8 hex del SHA-256 del manifiesto>`.
   - Datasets en Parquet; artefactos en el bucket `model-store` y el dataset de validación en `validation-datasets`.

   (Recomendado)

B) 20 000 solicitudes sin partición de prueba

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el contexto (unit-of-work, historias a las que contribuye, PRD §11, decisiones de U0 y U4)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/reference-model/functional-design/domain-entities.md`
- [x] 4. Generar `construction/reference-model/functional-design/business-rules.md`
- [x] 5. Generar `construction/reference-model/functional-design/business-logic-model.md` (generación, entrenamiento, empaquetado, conjunto adversarial; PBT)
- [x] 6. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
