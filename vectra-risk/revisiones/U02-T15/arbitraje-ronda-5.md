# U02-T15 — Arbitraje después de la ronda 5 (orquestador, 2026-11-07)

La ronda 5 salió VERDE y se abrió el PR 76. La revisión de código del PR 76 (`revision-codigo-pr76.md`) encontró 9 hallazgos. **El usuario decidió una ronda 6 solo con D-01 y D-02.** Después se fusiona el PR 76 sin otra revisión de código.

| Hallazgo | Decisión |
|---|---|
| D-01: la espera de 30 s convierte un fallo en cientos de checks fallidos | **Ronda 6** |
| D-02: `create` borra antes de crear | **Ronda 6** |
| D-03 a D-09 | `CANDIDATAS.md` |

## Lo que se espera de la ronda 6

- **D-01**: mientras dura la espera, el VU sale de la iteración sin registrar un check fallido. Las iteraciones saltadas se cuentan en una métrica propia, con un umbral en `options.thresholds` que sale del diseño o de J7. Si ninguno lo fija, se elige uno, se justifica en la bitácora y se marca como pendiente para el Paso 16. Hay una prueba con el gateway falso que devuelve un 5xx: los checks fallidos quedan acotados (uno por fallo real) y la métrica cuenta las iteraciones saltadas. Su rojo va contra `818cf7b`.
- **D-02**: un fallo en `create` no puede dejar a un usuario de carga borrado sin avisar. Primero busca, en la Admin API de Keycloak 26.8.1, un camino que no borre y que cumpla C-01 y C-03, y cita la ruta y la línea. Si no existe, `create` sigue borrando y creando, pero el error nombra los usuarios que quedaron sin crear, y una segunda corrida los repara. `FakeAdmin` simula el POST que falla. La bitácora registra el rojo.
- Nada más se reabre. Se corren CA-1 a CA-6, con CA-6 en serie después de CA-5.
