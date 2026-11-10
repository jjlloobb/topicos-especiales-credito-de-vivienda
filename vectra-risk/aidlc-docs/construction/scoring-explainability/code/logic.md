# Lógica pura de `scoring-explainability` (U07-T02, Pasos 3 a 7 del plan)

Resumen de lo que hace cada módulo, sus pruebas de propiedades y su cobertura. Se cierra con lo diferido. Diseño: BR-U7-04 a 07, 10, 11 y 14; NFR-U7-32, 40 y 42.

## Módulos

| Módulo | Qué hace | Diseño · historias |
|---|---|---|
| `scoring/src/scoring/policy.py` | `evaluate(PolicyEvaluationInput) -> PolicyResult`. Evalúa las cinco reglas, acumula los motivos en el orden de la tabla y gana el resultado más conservador. `cutoff_efectivo` por canal (`effective_cutoff`). `normative` nulo da `revision_requerida` con `parametro_normativo_no_vigente`, sin fail-closed. | BR-U7-04, 05, 06, 07 · US-103, US-106, US-207 |
| `explainability/src/explainability/narrative.py` | `NarrativeGenerator` (interfaz) y su única implementación `TemplateNarrativeGenerator` (`template:v1`). Top 5 por \|SHAP\| sin ceros, desempate por `feature_id`, intensidad `fuerte`/`moderada`/`leve`, encabezado, leyenda post-hoc y sin números de SHAP. | BR-U7-10; NFR-U7-32 · US-104 |
| `explainability/src/explainability/factuality.py` | `FactualityValidator` / `validate(...) -> bool`, independiente del generador: no importa `narrative` ni lee la plantilla. Parte la narrativa en encabezado, líneas y leyenda; reconoce `label_es` y la dirección contra el diccionario; reimplementa la selección y el desempate (con `Fraction`). | BR-U7-11 · US-105 |
| `explainability/src/explainability/applicant.py` | `generate(case_id, shap_vector, dictionary, generated_at) -> ApplicantSummary`. Hasta 3 factores `applicant_safe` con SHAP > 0, por \|SHAP\|; leyenda de `applicant:v1`. No guarda; el reloj lo inyecta quien llama. | BR-U7-14 · US-110 |
| `explainability/src/explainability/template_files.py` | Carga las plantillas versionadas (`templates/*.txt`, líneas `@clave texto`) desde la rueda o desde el árbol de fuentes. | Apoyo de `narrative` y `applicant` |
| `explainability/templates/template_v1.txt`, `applicant_v1.txt` | Plantillas versionadas. `forbidden_phrases.py` pasa sobre las dos (BR-U0-94). | BR-U7-10, 14 |

Las plantillas viven junto a `src/` (como dibuja el §1 del plan) y la rueda de `vectra-explainability` las incluye dentro del paquete (`force-include` en su `pyproject.toml`). Las imágenes del Paso 16 deben copiar `explainability/templates/`.

## Pruebas de propiedades (perfil `ci`, 500 ejemplos)

| PBT | Archivo | Qué comprueba |
|---|---|---|
| PBT-U7-01 | `tests/property/test_policy.py` | `outcome` en los tres valores; fuerzan revisión `normative` nulo, tasa sobre el tope y baja confianza; `reasons` en el orden de BR-U7-04 y sin duplicados. Oráculo en enteros de 0,0001. |
| PBT-U7-02 | `tests/property/test_policy.py` | Bordes (valor, ±1 paso): igual a la usura no es «sobre»; `property_value == vis_max` da `vis`; `score == cutoff` da `desfavorable` (general y por canal); `confidence == umbral` no es baja. |
| PBT-U7-03 | `tests/property/test_narrative.py` | Determinismo (también ante otro orden de entrada), orden por \|SHAP\| con el desempate, hasta 5 líneas, sin números de SHAP. |
| PBT-U7-04 | `tests/property/test_factuality.py` | Ida y vuelta: `validate(generate(v), v)` es verdadero. |
| PBT-U7-05 | `tests/property/test_factuality.py` | Un operador de mutación por estrategia: omitir, reordenar, invertir el signo, factor ajeno, intensidad, texto en la línea, texto adicional, encabezado y leyenda cambiados o ausentes; además otro modelo y otro vector. Todos dan `False`. |
| PBT-U7-06 | `tests/property/test_applicant.py` | Solo factores `applicant_safe` con SHAP > 0, a lo sumo 3, sin campos prohibidos ni números. |

Pruebas de ejemplo: `tests/unit/test_policy_examples.py` (US-103, US-106 con los 18 casos RT-4 de `vectra_reference`, US-207), `test_narrative_examples.py` (US-104: caso fijo, una sola implementación, plantilla sin frases prohibidas), `test_factuality_examples.py` (US-105: factor invertido) y, en `test_applicant.py`, el rechazo sin campos prohibidos.

## Cobertura (NFR-U7-40)

`make -C scoring-explainability coverage` mide los paquetes `scoring` y `explainability` con ramas y exige el 100 % por módulo en `policy.py`, `narrative.py` y `factuality.py` (el `--cov=policy` del plan no mide nada: los módulos viven en esos paquetes). Cifras de la última corrida en `bitacoras/U07-T02.md`. `make check` de la unidad la incluye.

## Diferido

- `mutmut` sobre `policy` y `factuality` y su allowlist (NFR-U7-41): se difiere a T3 (enmienda §2.3). Mientras tanto, PBT-U7-02 y PBT-U7-05 fijan los bordes y los operadores de mutación, y la bitácora de U07-T02 registra los pares falla-pasa de mutaciones hechas a mano.
- Fuera de esta tarea (U07-T03): clientes, `explain`, `dictionary_cache`, `orchestrator`, endpoints, cliente F23 y el log `applicant_summary.generated`.

## Observaciones de diseño

- US-207 pide una recomendación con «tasa sobre usura y normativa no vigente». Con `normative` nulo no hay tope de usura que comparar, así que BR-U7-04 no permite ambos motivos a la vez; la prueba de ejemplo cubre los dos casos por separado.
