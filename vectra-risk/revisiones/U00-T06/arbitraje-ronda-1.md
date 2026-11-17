# U00-T06 — Arbitraje de la ronda 1 (orquestador, 2026-11-17)

Informe: `ronda-1.md`. NO-VERDE **sin ningún ROJO**: un NARANJA (F-01) y cuatro AMARILLO. Los seis criterios pasan en las corridas del revisor, la elección del caso (c) es correcta (no existe versión corregida de `picomatch`) y el workflow sigue fallando cuando el guion falla.

**Decisión: ronda 2, la última (RL-2), acotada.** Por RL-3 un NARANJA no bloquea, y el revisor mide que el guion no es más débil que `npm audit --audit-level=high` (npm ignora igual las severidades desconocidas). Pero el encargo de la revisión decía «ningún verde indebido» ante severidades en otra capitalización, el guion es una puerta de seguridad que sustituye a la de npm en toda la CI, y el arreglo es de pocas líneas. Mismo criterio que en U01-T17 y U01-T18. No subo F-01 a ROJO: lo trato como el NARANJA que es y lo arreglo ahora.

| Hallazgo | Decisión | Qué se pide |
|---|---|---|
| F-01 NARANJA: severidades no canónicas dan verde | Ronda 2 | Lista de **permitidos**, no de bloqueantes: solo `info`, `low` y `moderate`, en minúsculas exactas, dejan pasar; cualquier otra severidad (ausente, `High`, `CRITICAL`, `severe`, no cadena) bloquea, tanto en el paquete como en cada aviso de `via`. Una prueba roja primero por cada caso de la lista del revisor |
| F-03 AMARILLO: la excepción no se ata a `picomatch` | Ronda 2 | La excepción vale solo para el aviso `GHSA-fc5q-39xc-vjpf` **del paquete `picomatch` y con severidad `high`**: si sube a `critical`, o aparece con ese id en otro paquete, rojo. Una `via` colgante (nombre que no está en `vulnerabilities`) da rojo aunque vaya junto a `picomatch`. Con sus pruebas |
| F-04 AMARILLO: cuatro mutantes sobreviven | Ronda 2 | Pruebas que maten: `error` junto a `vulnerabilities`; salida vacía de npm; fecha en UTC (no local); y una que fije `EXEMPT_UNTIL == 2026-12-17` |
| F-05 AMARILLO: errores sin mensaje | Ronda 2 | Raíz JSON que no es objeto y `npm` ausente: mensaje de una línea y rc 1, sin traza |
| F-02 AMARILLO: frase inexacta en la bitácora | Ronda 2 | Corrige la frase de `size-limit` en una sección «Ronda 2» de la bitácora (lo ya escrito no se reescribe: se corrige debajo). La conclusión (c) se mantiene |

A `CANDIDATAS.md`, al final:
- U10, `console/spa/tests/unit/views/governance/shell.test.tsx` («cumplimiento: `/` lleva a su inicio…»): inestable con la máquina cargada (falló con carga 146 a 217, pasó con 9.45, sin cambios de código).
- U0/U10: subir `size-limit` y `@size-limit/file` a 14.3.0 quita unas 3 de las 11 entradas de la auditoría; no cierra el aviso (`vite` y `vitest` siguen arrastrando `picomatch`).
- U0: la excepción de `contracts/tools/npm_audit.py` caduca el 2026-12-17; ese día el check `checks` vuelve a rojo y hay que mirar si ya existe `picomatch` corregido.

**Fuera de la ronda 2:** `package.json`, el lockfile, el workflow (ya correcto) y todo lo que el revisor dio por pasado. No se reabre.
