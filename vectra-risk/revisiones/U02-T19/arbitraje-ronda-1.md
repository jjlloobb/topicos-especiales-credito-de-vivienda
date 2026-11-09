# Arbitraje de la ronda 1 — U02-T19

Orquestador, 2026-11-08. Informe: `revisiones/U02-T19/ronda-1.md`, NO-VERDE por un ROJO. Ritmo RL-2: la ronda 2 es la última. Como esa ronda se abre de todos modos, entran también los arreglos baratos de F-02 y F-06.

## Decisiones

- **F-01 (ROJO) — entra, alineado con el diseño.**
  - El Job de `keycloak-config-cli` toma los recursos de INF-U2-06: requests de 100m y 256Mi, limits de 500m y 512Mi.
  - La prioridad es `vectra-normal` (`nfr-design/logical-components.md`).
  - El init container `truststore` cabe dentro de esas cifras, o lleva los valores mínimos que un `keytool` necesite. Justifica esos valores en la bitácora.
  - La regla `config-cli-security` exige estos valores, no los de la ronda 1.
  - **Rojo primero:** con `vectra-low` o con 1Gi, la regla falla.
  - Si la JVM de `keycloak-config-cli` no cabe en 512Mi, no se sube el límite sin datos: queda como candidata para medir en el Paso 16 (DD-3), y el límite sigue en el valor del diseño.
- **F-02 (NARANJA) — entra.**
  - `backoffLimit`, `activeDeadlineSeconds`, el tiempo de espera de disponibilidad, los recursos y el rodeo `NOMBRE` pasan a `vectra.configCli.*` en los values.
  - El nombre del administrador de arranque se parametriza en la siembra con un valor por omisión.
  - Las reglas siguen validando los valores renderizados.
- **F-06 (AMARILLO) — entra, porque es barato.** En `write_private`, crea los archivos con 0600 antes de escribir el contenido (`os.open` con modo) o escribe a un temporal y usa `os.replace`. Agrega una prueba en la que un archivo preexistente con 0644 termina en 0600 sin haber tenido contenido nuevo con permisos amplios.
- **F-03, F-04 y F-05 (AMARILLO), más las dos candidatas nuevas del revisor** (refrescar `identity/ca` tras la rotación anual; la detección de outliers al repetir el ítem 8): van a `CANDIDATAS.md`.

## Aceptación de la ronda 2

Los CA-1 a CA-5 de la tarea, con **CA-5 completo**: `make -C identity-edge check` y `make -C platform check`, que en la ronda 1 no llegaron a terminar.
