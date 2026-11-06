# U02-T14 — Arbitraje de la ronda 1 (orquestador, 2026-11-05)

Informe: `ronda-1.md`, NO-VERDE.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01a ROJO: bloqueo rápido | **Lo decide el orquestador: entra en la ronda 2, sin cambiar el realm** | BR-U2-05 no dice nada del bloqueo rápido y el realm usa los valores por defecto de Keycloak. Se arregla en la prueba y en el modelo, sin cambio de diseño |
| F-01b ROJO: el evento del bloqueo queda en DEBUG | **Decisión H11 del usuario: entra en la ronda 2** | Keycloak escribe los eventos de éxito en info |
| F-01c ROJO: `UPDATE_PASSWORD` sin registrar | **Decisión H12 del usuario: entra en la ronda 2** | Se registra en los tres realms, con su regla en `realm-lint` |
| F-02 NARANJA: candidata falsa de contraseña vacía | Entra en la ronda 2 | Se retira de `CANDIDATAS.md` y se corrige la bitácora |
| F-03 NARANJA: `x-vectra-sub` sin contador | Entra en la ronda 2 | Es la verificación que fija P-U2-06 |
| F-04 NARANJA: ventana fija del contador de `/auth` | Entra en la ronda 2 | La prueba es inestable |
| F-05 NARANJA: sondas del eco con 403 en Linkerd | Entra en la ronda 2, **solo en los manifiestos del eco** | `flows.yaml` sigue fuera |
| F-06 NARANJA: literales como valores esperados | Entra en la ronda 2 | La tarea lo prohíbe |
| F-07, F-08, F-09 AMARILLO | Entran en la ronda 2 | Son arreglos acotados dentro de la tarea |

## Lo que se espera de la ronda 2

- **F-01a**:
  - las pruebas que cuentan fallos (`test_five_failures_lock_the_user` y la máquina de PBT-U2-08) separan sus intentos más que `quickLoginCheckMilliSeconds`;
  - ese valor se lee del realm y, si el realm no lo fija, del valor por defecto de 26.8.1, citado con ruta y línea;
  - el modelo puro incluye la regla del bloqueo rápido (`DefaultBruteForceProtector.java`, líneas 121-127) y su prueba unitaria la cubre.
- **F-01b (H11)**:
  - el listener `jboss-logging` de Keycloak escribe los eventos de éxito en `info` en los tres entornos;
  - comprueba en 26.8.1 el nombre exacto de la opción (SPI `events-listener`, proveedor `jboss-logging`, propiedad `success-level`) y cómo se pasa: variable `KC_SPI_…` en `extraEnv` o argumento;
  - se regenera `keycloak/rendered/`, y si la regla `env-whitelist` de `keycloak/policy/keycloak.rego` rechaza la variable, se agrega a `fixed_env` con su caso de mutación, como en U02-T13;
  - una prueba de los renders falla si se quita la opción;
  - la nota H11 queda en BR-U2-16.
- **F-01c (H12)**:
  - `UPDATE_PASSWORD` queda registrada y habilitada en `requiredActions` de los tres realms;
  - `realm-lint` lo exige, con un caso que falla sin ella;
  - `realm-diff` y las pruebas de realm siguen pasando;
  - se regeneran los renders que llevan el realm (`jobs/rendered/`);
  - comprueba contra `keycloak-config-cli` que su modo `managed` no la borra;
  - la nota H12 queda en BR-U2-03 o donde el diseño lista las acciones requeridas.
- **F-02 a F-09**: cada uno se responde por su identificador, como fija el informe.
- **Choque con U02-T13**. La rama `tarea/U02-T13` también cambia estos tres archivos:
  - `keycloak/values/common.yaml` (`extraEnv`);
  - `keycloak/rendered/`;
  - `keycloak/policy/keycloak.rego` (`fixed_env`).

  U02-T14 no espera a U02-T13: haz el cambio mínimo y regístralo en la bitácora. Al fusionar, el orquestador rebasa la rama que entre en segundo lugar y regenera los renders.
- **CA-1 a CA-7** se vuelven a correr; CA-5 y CA-6 en serie.
