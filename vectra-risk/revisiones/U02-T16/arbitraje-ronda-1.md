# U02-T16 — Arbitraje de la ronda 1 (orquestador, 2026-11-06)

Informe: `ronda-1.md`, NO-VERDE.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 ROJO: CA-2 sobre texto sintético | Entra en la ronda 2 | CA-2 pide la localización sobre el texto del plan y el mismo bloque en todos los estados |
| F-02 AMARILLO: el ancla `^` sin prueba | Entra en la ronda 2 | El comentario promete el ancla; un caso de una línea la cubre |
| F-03 AMARILLO: `[X]` en mayúscula | Entra en la ronda 2 | Arreglo de un carácter en el mismo patrón |

## Lo que se espera de la ronda 2

- **F-01**: el caso parametrizado lee `PLAN`, reescribe los encabezados de los Pasos 13 y 14 en cada estado (`[ ]`/`[x]`, con y sin sufijo) y comprueba que `plan_bullets(variante) == plan_bullets()`. Rojo contra la versión de 08e29d2 en la bitácora.
- **F-02**: un caso con una mención `- [ ] **Paso 14` sangrada dentro del Paso 13 falla si se quita el `^`.
- **F-03**: el patrón acepta `[X]`, cubierto por el mismo caso parametrizado.
- CA-1 a CA-5 se vuelven a correr; CA-5 en serie después de CA-4.
