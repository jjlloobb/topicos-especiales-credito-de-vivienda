# U02-T14 — Arbitraje de la ronda 2 (orquestador, 2026-11-05)

Informe: `ronda-2.md`, NO-VERDE.

| Hallazgo | Decisión |
|---|---|
| F-10 ROJO: prioridades de los flujos de autenticación cambiadas sin declararlo | **Entra en la ronda 3.** Es una regresión del propio diff, así que es del diff |
| F-11 AMARILLO: la guarda `wait <= 0` sin cubrir | Entra en la ronda 3 |
| F-12 AMARILLO: el instante del fallo se toma antes del intento | Entra en la ronda 3 |
| F-13 AMARILLO: referencia de línea | Entra en la ronda 3 |

## Lo que se espera de la ronda 3

- **F-10**:
  - las 21 prioridades vuelven a 30: 7 por realm en kind, staging y prod;
  - se regenera `jobs/rendered/`;
  - `git diff 8c18021 -- identity-edge/keycloak/realm/` solo puede tocar `bruteForceStrategy`, `maxTemporaryLockouts` y la entrada de `UPDATE_PASSWORD` en `requiredActions`;
  - una prueba lo fija y falla si cambia cualquier otro campo de los realms frente a una línea base versionada de `authenticationFlows`, o frente al modelo de los flujos que ya exista en las pruebas de realm;
  - el codificador cuenta en la bitácora cómo se produjo el reemplazo, para no repetirlo.
- **F-11, F-12 y F-13**: como fija el informe.
- **CA-1 a CA-7** se vuelven a correr; CA-5 y CA-6 en serie.
