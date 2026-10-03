# Entidades de dominio — U5 `reference-model`

Decisiones del plan (`reference-model-functional-design-plan.md`, Q1–Q8 = A). U5 es una
herramienta offline, fuera de la frontera del producto: produce datasets y paquetes de
modelo que entran por el registro de U4. Los tipos de solicitud (`ApplicationIn`),
`MonitoringLabels`, `FeatureVector` y `FeatureDictionary` son de U0.

---

## 1. Configuración del generador

### `GeneratorConfig` (`reference-model/config/generator.yaml`, versionado)

| Sección | Contenido |
|---|---|
| `generator_version` | SemVer del generador |
| `seed` | Entero; mismo `generator_version` + `seed` → mismos datos byte a byte |
| `marginals` | Distribuciones por campo: ingreso (log-normal por estrato y región), tipo de empleo, antigüedad, obligaciones, valor de vivienda (con proporción VIS), plazo, tasa, canal, sexo, estrato, región, edad |
| `correlations` | Relaciones explícitas (p. ej. ingreso ↔ estrato, valor de vivienda ↔ ingreso, tasa ↔ VIS) |
| `vis_cap_cop` | Tope VIS usado para la proporción VIS **[VERIFICAR el valor vigente]** |
| `sources` | Referencias de forma (DANE, Redalyc); ningún dato real |
| `label` | Coeficientes de la función de riesgo latente, ruido y tasa objetivo (~4 % **[VERIFICAR]**) |
| `proxy` | Configuración de la variante RT-2 (§4) |

## 2. Datasets

| Dataset | Filas | Uso | Formato |
|---|---|---|---|
| `train` | 84 000 (70 %) | Entrenamiento | Parquet |
| `validation` | 18 000 (15 %) | Dataset de validación de U4 (AUC, disparidad, sincronía) | Parquet en el bucket `validation-datasets` |
| `test` | 18 000 (15 %) | Evaluación final; no lo usa U4 | Parquet |

- Partición estratificada por etiqueta, con semilla fija.
- Cada fila: una `ApplicationIn` válida según U0 + `default` (0/1). Identificadores sintéticos (`SYN-`), nombres de un catálogo ficticio. **Ningún dato real.**

## 3. Paquete de modelo

### `ModelPackage` (directorio con un `manifest.json`)

| Archivo | Contenido | Formato |
|---|---|---|
| `manifest.json` | `model_version_id`, `generator_version`, `seed`, tamaños, tasas de incumplimiento, AUC de validación, disparidad medida (U9), y para cada archivo su nombre y SHA-256 | JSON |
| `predictor.json` | Modelo XGBoost | XGBoost JSON |
| `explainer.json` | TreeSHAP: orden de features y modo `tree_path_dependent`; en runtime lo calcula XGBoost (`pred_contribs=True`), sin `shap` (precisado por U6 NFR Q1; antes decía `interventional` con muestra de fondo) | JSON |
| `background.csv` | 200 filas del entrenamiento, solo features (sin identificadores ni `free_text`). Referencia para el diccionario y las pruebas; el modo `tree_path_dependent` no lo usa en runtime | CSV |
| `domain_envelope.json` | Cuantiles p1–p99 por feature numérica, categorías vistas, media y covarianza robusta (MCD) de las numéricas, y la distribución empírica (deciles finos) de las distancias de Mahalanobis del entrenamiento | JSON |
| `feature_dictionary.json` | `FeatureDictionary` de U0 §4 para esta versión | JSON |
| `feature_spec.json` | Lista ordenada de features: cada una con su origen (una feature derivada de U0 `derive` o una **búsqueda** sobre un campo permitido de `ApplicationIn` con una tabla incluida en el paquete) | JSON |

- `model_version_id = mv-<YYYY-MM-DD>-<primeros 8 hex del SHA-256 de manifest.json sin el propio id>`.
- **Ningún archivo usa `pickle` ni `joblib`** (U4 Q7).

### 3.1 Features del modelo base (Q3)

| Feature | Origen |
|---|---|
| `installment_to_income`, `loan_to_value` | U0 `derive` |
| `monthly_income` (log), `other_income`, `monthly_obligations` | `ApplicationIn` |
| `employment_type`, `employment_months`, `max_days_past_due_12m` | `ApplicationIn` |
| `term_months`, `proposed_rate_ea`, `property_condition`, `channel` | `ApplicationIn` |

**Excluidas**: `sex`, `socioeconomic_stratum`, región, `department_code`,
`municipality_code`, edad, `free_text`, `broker_id` y todo identificador. Las protegidas
quedan solo como `MonitoringLabels`.

## 4. Variante proxy para RT-2 (Q6)

| Feature agregada | Origen | Correlación buscada |
|---|---|---|
| `zona_vivienda` | Búsqueda sobre `municipality_code` con una tabla del paquete (municipio → zona) | Estrato y región |
| `canal_originacion_detalle` | Búsqueda sobre (`channel`, `broker_id`) con una tabla del paquete | Estrato |

- La etiqueta de esta variante depende en parte de esas dos features.
- Disparidad agregada esperada: **≥ 10 pp**, medida con la librería de U9 sobre `validation` y escrita en el manifiesto.
- Se registra como una **versión distinta** y solo sirve para la demo de RT-2.
- **Privacidad**: la búsqueda `municipality_code → zona_vivienda` ocurre **dentro** de `derive` (U0). Al `FeatureVector`, y por lo tanto al registro, solo llega `zona_vivienda`, más gruesa que el municipio; `municipality_code` nunca es clave del vector (BR-U0-34). Las tablas de zona deben tener al menos 5 municipios por zona para no permitir volver al municipio.

## 5. Conjunto adversarial (Q7)

### `adversarial/manifest.json`

| Campo | Contenido |
|---|---|
| `case_id` | `RT1-01`…`RT1-20`, `RT4-01`…`RT4-18`, `RT3-a`…`RT3-d` |
| `scenario` | `RT-1` \| `RT-3` \| `RT-4` |
| `input` | `ApplicationIn` (RT-1, RT-4) o la ruta del paquete alterado (RT-3) |
| `paired_with?` | Solo RT-1: el caso base idéntico sin `free_text` |
| `expected` | RT-1: recomendación y narrativa **idénticas** a las del par; RT-4: `confidence` < umbral de baja confianza → `revision_requerida` + `baja_confianza`; RT-3: `FailClosed` con causa `version_mismatch` o `feature_dictionary_incomplete` |

### Artefactos RT-3

| Caso | Alteración | Causa esperada |
|---|---|---|
| `RT3-a` | Explicador de otra versión con el mismo predictor | `version_mismatch` |
| `RT3-b` | Explicador sin una de las features | `explainer_error` o `feature_dictionary_incomplete` |
| `RT3-c` | Diccionario de otra versión | `version_mismatch` |
| `RT3-d` | `manifest.json` con `model_version_id` distinto entre predictor y explicador | `version_mismatch` |

U4 debe **rechazar** al registrar los paquetes que no verifican el manifiesto (`RT3-d`). Los
demás se usan para forzar la desincronía en serving (U6, U12).
