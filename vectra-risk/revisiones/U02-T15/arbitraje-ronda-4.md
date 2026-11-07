# U02-T15 — Arbitraje después de la ronda 4 (orquestador, 2026-11-07)

La ronda 4 salió VERDE. Después, la revisión de código del PR 72 (`revision-codigo-pr72-ronda-4.md`) trajo 8 hallazgos. **El usuario decidió una ronda 5 acotada.**

| Hallazgo | Decisión |
|---|---|
| C-01: `create` no es idempotente con `passwordHistory(5)` | **Ronda 5** |
| C-02: el login se reintenta sin espera | **Ronda 5** |
| C-03: no rehabilita a un usuario existente (`enabled`, `requiredActions`, OTP) | **Ronda 5** |
| C-05: `aud` de `private_key_jwt` sin normalizar | **Ronda 5** |
| C-04: la pata directa de NFR-U2-11 por `port-forward` | `CANDIDATAS.md` (decisión de diseño) |
| C-06, C-07, C-08 | `CANDIDATAS.md` |

## Lo que se espera de la ronda 5

- **C-01:** cada hallazgo se demuestra primero con un rojo. `FakeAdmin` modela `passwordHistory` como Keycloak 26.8.1 y rechaza reusar la contraseña vigente. Fija ese comportamiento contra el código pinneado y cita la ruta y la línea en la bitácora. `create` no reusa la contraseña: o elige otro camino para el usuario existente, o falla con un mensaje claro si no lo hay. Cuál de los dos, lo decides tú con evidencia.
- **C-03:** un usuario existente queda `enabled: true`, sin `requiredActions` y sin credenciales OTP, y `FakeAdmin` lo comprueba.
- **C-02:** después de un fallo de refresh o de login, el VU espera antes de volver a intentar el login. Una prueba con el gateway falso devolviendo un 5xx muestra que el número de logins queda acotado.
- **C-05:** el `aud` se normaliza igual que `REDIRECT_URI`, y hay una prueba con un `BASE_URL` que lleva puerto.
- Nada más se reabre. Se corren CA-1 a CA-6, con CA-6 en serie después de CA-5.
