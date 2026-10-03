# Reglas de negocio — U5 `reference-model`

Los IDs `BR-U5-xx` se referencian en los planes de tareas.

---

## 1. Datos sintéticos (Q1, Q8)

**BR-U5-01 — Sin datos reales.** El generador solo usa la configuración de
`generator.yaml`. Ningún archivo de U5 contiene datos de personas reales. Los
identificadores llevan el prefijo `SYN-` y los nombres salen de un catálogo ficticio.

**BR-U5-02 — Determinismo.** El mismo `generator_version` y la misma `seed` producen los
mismos Parquet byte a byte (orden de filas y de columnas fijo, sin timestamps de
generación dentro de los archivos).

**BR-U5-03 — Validez.** Toda fila generada pasa el validador de `ApplicationIn` de U0
(BR-U0-20..30). Una fila inválida es un error del generador, no se descarta en silencio.

**BR-U5-04 — Partición.** 70/15/15 estratificada por `default`, con semilla fija; ningún
solapamiento entre particiones (verificado por el id sintético).

## 2. Etiqueta (Q2)

**BR-U5-05 — Función de riesgo latente.**
`logit(p) = β0 + β1·installment_to_income + β2·loan_to_value + β3·max_days_past_due_12m
+ β4·employment_months + β5·[employment_type] + β6·(monthly_obligations / ingreso) + ε`.
Los coeficientes están en `generator.yaml`, calibrados para una tasa de incumplimiento de
~4 % **[VERIFICAR]** y un AUC de validación de ~0,88.

**BR-U5-06 — Base sin dependencia protegida.** En el dataset base, ni la función de la
etiqueta ni ninguna variable generada a propósito dependen de sexo, estrato, región o edad,
más allá de las correlaciones de contexto declaradas en `correlations` (p. ej. ingreso ↔
estrato). La disparidad agregada del modelo base, medida con la librería de U9, debe quedar
**por debajo de 5 pp**. Si no queda por debajo, la entrega falla.

## 3. Modelo (Q3, Q4)

**BR-U5-07 — Features permitidas.** El `feature_spec.json` del modelo base solo contiene
las features de domain-entities §3.1. Una validación del paquete falla si aparece una
feature excluida.

**BR-U5-08 — Entrenamiento.** XGBoost con hiperparámetros fijos en la configuración y
semilla. Calidad mínima para entregar: AUC de validación ≥ 0,85 **[INTERNO]**. Si no se
alcanza, la entrega falla. U4 no lo bloquea (BR-U4-07): el umbral lo hace cumplir U5 como
proveedor.

**BR-U5-09 — Empaquetado sin código ejecutable.** Predictor en XGBoost JSON y explicador,
fondo, envolvente, diccionario y especificación en JSON o CSV. Ningún `pickle`/`joblib`.
`manifest.json` lista cada archivo con su SHA-256, y todos llevan el mismo
`model_version_id`.

**BR-U5-10 — Diccionario completo.** `feature_dictionary.json` cubre **todas** las features
de `feature_spec.json` (BR-U0-80), con `label_es`, unidad, frases de dirección y
`applicant_safe`. En la variante proxy, `zona_vivienda` y `canal_originacion_detalle` se
marcan con `applicant_safe = false`.

## 4. Confianza (Q5; US-106, RT-4)

**BR-U5-11 — Envolvente de dominio.** Calculada sobre `train`:
- p1 y p99 de cada feature numérica;
- categorías vistas de cada categórica;
- media y covarianza robusta (MCD) de las numéricas;
- distribución empírica `F` de las distancias de Mahalanobis del entrenamiento.

**BR-U5-12 — Fórmula.** Para una entrada `x`:
- `c_rango = 1 − (features numéricas fuera de [p1, p99]) / (features numéricas)`;
- `c_dist = 1 − F(d_M(x))`;
- `confidence = 0` si hay alguna categoría no vista; si no, `confidence = min(c_rango, c_dist)`, cuantizada a `Decimal4` (BR-U0-07).

La calcula el predictor de U6, en el mismo proceso que la predicción, con `domain_envelope.json`.

**BR-U5-13 — Calibración contra RT-4.** Los 18 casos RT-4 deben dar `confidence` por debajo
del umbral de baja confianza de la política de referencia, y al menos el 95 % de `test`
debe quedar por encima. Si no, la entrega falla.

## 5. Variante proxy (Q6; US-303, RT-2)

**BR-U5-14 — Disparidad esperada.** La variante proxy debe producir una disparidad agregada
**≥ 10 pp** (el doble del umbral de U9) sobre `validation`, medida con la librería de U9.
Si no la produce, la entrega de la variante falla.

**BR-U5-15 — Uso restringido.** La variante proxy se registra como una versión distinta,
con la etiqueta `purpose = rt2-demo` en el manifiesto, y solo se usa en kind y staging para
la demostración. El municipio nunca llega al `FeatureVector`: la búsqueda ocurre en `derive`
y solo sale `zona_vivienda`, con al menos 5 municipios por zona (BR-U0-34).

## 6. Conjunto adversarial (Q7)

**BR-U5-16 — Pares RT-1.** Cada caso RT-1 y su par difieren **solo** en `free_text`
(comparación campo a campo). Los textos cubren instrucciones en español e inglés, HTML y
`<script>`, SQL, Markdown, Unicode engañoso (bidi, homoglifos) y un texto de 2 000
caracteres (máximo de U0).

**BR-U5-17 — Casos RT-4.** Cada caso es una `ApplicationIn` **válida** según U0 y fuera de la
envolvente de dominio (al menos una feature fuera de [p1, p99] o una categoría no vista).

**BR-U5-18 — Artefactos RT-3.** Los cuatro paquetes alterados de domain-entities §5 se
generan a partir de un paquete válido, con cada alteración documentada en el manifiesto
adversarial.

## 7. Cambios a otras unidades (registrados en `audit.md`)

| Unidad | Cambio | Motivo |
|---|---|---|
| U4 (FD) | `ModelVersion` registra `manifest_uri` y `manifest_sha256`; BR-U4-06 verifica **cada** archivo listado en el manifiesto (formato permitido, sin bytes mágicos de pickle, SHA-256) y que todos lleven el mismo `model_version_id` | El paquete tiene más archivos que predictor y explicador (Q4, Q5) |
| U0 (FD) | `derive(application, evaluated_at, feature_spec)`: además de las features estándar, aplica las búsquedas del `feature_spec` del paquete activo, solo sobre campos permitidos de `ApplicationIn` (nunca identificadores directos ni `free_text`) | Variante proxy (Q6) |
| U6 (pendiente) | El predictor de U6 calcula `confidence` con `domain_envelope.json` (BR-U5-12) | Q5 |
| U7/U8 | El `FeatureVector` se arma con el `feature_spec` de la versión activa. **Resuelto** por U8 FD Q1 (BR-U8-05): case-service lee el `feature_spec` de governance (F104) en cada intento y scoring rechaza un vector de otra versión | Q6 |
