# Arbitraje de la revisión de código del PR 78 — U02-T17

Orquestador, 2026-11-08. Informe: `revisiones/U02-T17/revision-codigo-pr78.md`.

## Decisión del usuario: ronda 3 acotada a C-01 y C-05

Los dos afectan el orden real de instalación del Paso 16. El resto no se corrige en esta tarea.

### C-01 — entra

En `platform/tests/test_waves.py`, sumar a `STRICT` los pares que el informe nombra. Antes de agregar cada uno, comprueba en los renders que la dependencia existe:

- `secret-store` → `valkey`, `keycloak`, `identity-jobs`: busca `ExternalSecret` con `ClusterSecretStore` en `identity-edge/charts/valkey/rendered/`, `identity-edge/keycloak/rendered/` e `identity-edge/jobs/rendered/`;
- `mesh-certificates` → `keycloak`, `gateway`: `Certificate` con `issuerRef` `vectra-internal-ca` en kind. Confirma que `mesh-certificates` es el componente que crea ese `ClusterIssuer`; si es otro, usa ese y regístralo en la bitácora;
- `keycloak` → `identity-monitors`: el `PodMonitor` que monta `identity-ca`. Si el Secret lo crea otro componente, el par es con ese.

Un par cuya dependencia no aparezca en los renders no se agrega. Se anota en la bitácora con la búsqueda que hiciste.

**Rojo primero:** con `valkey` en la wave 1 (en `components.yaml` y en `FIXED_WAVES`), `test_waves.py` falla y nombra `secret-store`. Haz lo mismo para un par de `mesh-certificates`.

### C-05 — entra, con la wave 4

Dentro de una wave, Argo CD aplica las Applications juntas y no las ordena por salud. Por eso `SAME_WAVE_OK` no garantiza que `identity-jobs` corra después de `keycloak`. La decisión:

- `identity-jobs` pasa a la **wave 4**, en `components.yaml`, `FIXED_WAVES` y `EXPECTED_WAVES`;
- el par `("keycloak", "identity-jobs")` sale de `SAME_WAVE_OK` y entra en `STRICT`;
- nota en el Paso 12 del plan de U2: «Nota del 2026-11-08 (decisión del usuario tras la revisión de código del PR 78, C-05): `identity-jobs` (`keycloak-config-cli`, `realm-drift`, `signing-key-age`) va en la wave 4, no en la 3, porque dentro de una wave Argo CD no espera a que Keycloak esté sano.»;
- se regeneran las Applications con `generate.py`.

**Rojo primero:** con `identity-jobs` de vuelta en la wave 3 y el par en `STRICT`, `test_waves.py` falla.

El comentario de `SAME_WAVE_OK` («espera a que cada una esté sana») es de U1 y es inexacto. No se toca en esta tarea; va como candidata.

### C-06 — candidata

`generate.py` omite los values automáticos de los componentes ya renderizados, y el README se ajusta a V1-a.

### Ya en `CANDIDATAS.md`

C-02, C-03, C-04, C-07 y C-08. No se repiten.

## Aceptación de la ronda 3

Los CA-1 a CA-6 de la tarea. En CA-2, `identity-jobs` va en la wave 4: el orden esperado por entorno es 2, 3, 3, 3, 4, 4, 4 para `valkey`, `keycloak`, `gateway`, `ratelimit`, `identity-jobs`, `identity-rules` e `identity-monitors`.

Agrega a `CANDIDATAS.md`:
- C-06;
- el comentario inexacto de `SAME_WAVE_OK` en U1.

En la bitácora, sección «Ronda 3», van los comandos y las salidas de todos los CA. La ronda 2 los referenciaba sin incluirlos (AMARILLO de la ronda 2).
