# Modelo de lógica — U5 `reference-model`

## 1. Módulos lógicos

| Módulo | Responsabilidad | Reglas |
|---|---|---|
| `generate` | Datasets sintéticos deterministas desde `generator.yaml` | BR-U5-01..06 |
| `train` | XGBoost con semilla e hiperparámetros fijos; AUC de validación | BR-U5-07, 08 |
| `envelope` | Envolvente de dominio y función `confidence(x)` (implementación de referencia, idéntica a la de U6) | BR-U5-11..13 |
| `package` | Predictor, explicador, fondo, envolvente, diccionario, especificación y manifiesto | BR-U5-09, 10 |
| `proxy` | Variante RT-2 y su medición de disparidad (librería de U9) | BR-U5-14, 15 |
| `adversarial` | Casos RT-1, RT-4 y artefactos RT-3 con su manifiesto | BR-U5-16..18 |
| `release` | Orquesta todo; falla si cualquier regla de calidad no se cumple | BR-U5-06, 08, 13, 14 |

`envelope.confidence` es una función pura que se publica como librería del workspace, para
que U6 la use tal cual (una sola implementación).

## 2. Flujo de entrega

```text
generator.yaml (versión + semilla)
  -> generate: train / validation / test (Parquet, validados con U0)
  -> train: XGBoost -> AUC(validation) >= 0,85 ? si no, falla
  -> envelope: cuantiles, categorías, MCD, F(d_M) -> RT-4 bajo umbral y >= 95 % de test sobre umbral ? si no, falla
  -> disparidad base (U9) < 5 pp ? si no, falla
  -> package: manifest.json con SHA-256 de cada archivo -> model_version_id
  -> proxy (opcional): disparidad >= 10 pp ? -> paquete purpose=rt2-demo
  -> adversarial: RT-1 (pares), RT-4 (fuera de envolvente), RT-3 (paquetes alterados)
  -> subir al model-store y a validation-datasets -> el ingeniero registra en U4 (US-201)
```

## 3. Propiedades testeables (PBT-01)

| ID | Componente | Propiedad | Categoría | Generadores (PBT-07) |
|---|---|---|---|---|
| PBT-U5-01 | `generate` | Para toda semilla, generar dos veces da los mismos bytes | Idempotencia / determinismo | Semillas aleatorias; tamaños pequeños |
| PBT-U5-02 | `generate` | Toda fila generada pasa el validador de `ApplicationIn` de U0 | Invariante | Semillas y configuraciones con parámetros en sus bordes |
| PBT-U5-03 | `envelope` | `confidence(x)` ∈ [0, 1] para toda entrada; es 0 con cualquier categoría no vista; es no creciente si una feature numérica se aleja de [p1, p99] manteniendo las demás fijas | Invariante | Entradas dentro y fuera de la envolvente; desplazamientos de una feature |
| PBT-U5-04 | `envelope` | La implementación de U5 y la de U6 coinciden para toda entrada (misma librería; la prueba lo fija contra regresiones) | Oráculo | Entradas aleatorias válidas |
| PBT-U5-05 | `package` | Para todo paquete generado: cada archivo del manifiesto existe, su SHA-256 coincide, todos tienen el mismo `model_version_id` y ninguno tiene bytes mágicos de pickle o zip de joblib | Invariante | Paquetes con alteraciones aleatorias (debe fallar) y sin ellas (debe pasar) |
| PBT-U5-06 | `package` | El diccionario cubre todas las features del `feature_spec` y el `feature_spec` base no contiene features excluidas | Invariante | Especificaciones con features agregadas o quitadas al azar |
| PBT-U5-07 | `adversarial` | Todo caso RT-1 difiere de su par solo en `free_text`; todo caso RT-4 es válido según U0 y está fuera de la envolvente | Invariante | Los casos generados y mutaciones de ellos |

**Pruebas de ejemplo obligatorias (PBT-10):**
- entrega completa con la semilla de referencia: AUC ≥ 0,85 y disparidad base < 5 pp;
- la variante proxy da ≥ 10 pp;
- los 18 casos RT-4 quedan bajo el umbral y ≥ 95 % de `test` queda sobre él;
- U4 rechaza `RT3-d` al registrar (cuando U4 exista; mientras tanto, contra su validador de manifiesto);
- ningún archivo de la entrega contiene un identificador sin el prefijo `SYN-`.

## 4. Cumplimiento de extensiones (Functional Design U5)

Revisada contra el cuerpo de los tres artefactos antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| SECURITY-11 | Cumple | BR-U5-16..18: el módulo `adversarial` construye los casos de abuso deliberados, cada uno con su resultado esperado en `adversarial/manifest.json`: inyección en `free_text` (RT-1, 20 pares), paquetes desincronizados (RT-3, 4 artefactos) y entradas fuera de dominio (RT-4, 18 casos). Es la categoría de evidencia que Application Design asignó a SECURITY-11 («RT-1..5»). U5 **construye** los casos; las pruebas que los ejecutan contra el sistema son de U12 |
| SECURITY-13 | Cumple | BR-U5-09 (sin pickle/joblib; manifiesto con SHA-256 de cada archivo) |
| SECURITY-05 | Cumple | BR-U5-03 (toda fila válida según U0), BR-U5-17 (casos RT-4 válidos) |
| AUTONOMIA-05 | Cumple | BR-U5-01 (ningún dato real); U5 corre offline y no tiene runtime |
| AUTONOMIA-06 | Cumple | BR-U5-18 (artefactos RT-3 para probar el fail-closed) |
| PBT-01 | Cumple | §3 |
| PBT-07 | Cumple | Columna «Generadores» de §3 |
| PBT-10 | Cumple | Pruebas de ejemplo de §3 |
| PBT-06 | N/A | U5 no tiene componentes con estado |
| RESILIENCY-* | N/A | Herramienta offline, sin runtime |
