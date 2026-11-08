# Ronda 1 — U02-T17

VEREDICTO: NO-VERDE

Los seis criterios de aceptación pasan en mi propia ejecución. Aun así hay dos NARANJA: una prueba de U1 se debilitó con una justificación falsa, y se subió el tope de memoria de kind, que es una decisión de capacidad que DD-3 reserva para el Paso 16.

## Criterios de aceptación, verificados por mí
Todo corrido en el worktree, sha 803fabe.

| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Las Applications versionadas coinciden con `components.yaml` | `uv run python vectra-risk-gitops/generate.py --check` | pasa, rc=0 |
| 2 | Las 7 Applications de U2 existen en los 3 entornos con su wave, namespace y fuente | No hay `yq`. Usé un script de PyYAML (`uv run python -I -`) que lee wave, `destination.namespace`, `source.path`, `directory.include` y la ausencia de `automated` en los 21 archivos | pasa: 21/21 OK, ningún `FALTA`. Waves 2,3,3,3,3,4,4. El `path` lleva el entorno correcto, por ejemplo `.../keycloak/rendered/staging`. Los directorios renderizados existen en los 3 entornos |
| 3 | El orden de waves respeta P-U1-12 y las dependencias de U2 | `uv run python platform/tests/test_waves.py` | pasa, rc=0 (kind 48, prod 45, staging 47). Rojo reproducido en una copia en el scratchpad: con keycloak en 2 falla con «keycloak (wave 2) necesita postgres antes»; con valkey en 3 falla con «gateway (wave 3) necesita valkey antes» |
| 4 | Ninguna Application nueva sincroniza sola | `platform/.tools/bin/kyverno test platform/policies/kyverno` | pasa: 81 passed, 0 failed. `u2-keycloak` da pass y `u2-keycloak-auto` da fail como se espera. Además, el `kyverno apply` de `make check` sobre `apps/` da pass 45, fail 0, skip 0 |
| 5 | Las verificaciones de U1 y U2 siguen en verde | `make -C platform check` y `make -C identity-edge check` | pasan los dos, rc=0. Platform: 745 passed en 3 min 05 s (5 min 50 s en total). identity-edge: 2643 passed en 18 min 15 s. Los tiempos son reales: no hay pruebas que se salten en silencio |
| 6 | V1-a: sin values de U2 en GitOps y con la nota en el plan | `test ! -e vectra-risk-gitops/values && grep -c "decisión V1-a" <plan>` | pasa: rc=0, conteo 1 |

El worktree queda limpio después de la revisión (`git status --short` vacío).

## Hallazgos

### F-01 · NARANJA · platform/tests/test_waves.py:20 · Se quitaron entradas de `FIXED_WAVES` con una justificación falsa
El diff borra `valkey: 2`, `keycloak: 3`, `api-gateway: 3` y `rate-limit: 3`. La bitácora dice que esas entradas «pisaban la wave de components.yaml y habrían ocultado el rojo». **Es falso**, y lo comprobé en una copia en el scratchpad:
- **Con las entradas restauradas y keycloak en 2:** la prueba falla dos veces, con «keycloak: wave 2, se esperaba 3» y con «keycloak (wave 2) necesita postgres antes». El rojo no se oculta.
- **Con el `test_waves.py` del diff y keycloak e identity-jobs en wave 4:** la prueba da `rc=0`. Eso contradice P-U1-12, que pone la identidad en la wave 3 (`nfr-design-patterns.md:188`).

`FIXED_WAVES` existe justamente porque «components.yaml no se puede corregir a sí mismo». Así que es un debilitamiento que el diff no necesitaba. Solo `api-gateway` y `rate-limit` tenían nombres obsoletos.

Hoy `EXPECTED_WAVES` de `test_platform.py` todavía atrapa ese caso dentro de `make check`, pero no lo atrapa el comando de aceptación del CA-3.

**Corrección:** renombrar las entradas a `gateway` y `ratelimit` y conservar `valkey` y `keycloak`. Lo ideal es sumar también `identity-jobs: 3`, `identity-rules: 4` e `identity-monitors: 4`. Hay que quitar de la bitácora la afirmación falsa.

### F-02 · NARANJA · platform/tests/test_kind_profile.py:10 · Se sube `BUDGET_GIB` de 5.0 a 5.5: es una decisión de capacidad tomada en el diff
- **Medición mía:** `requested_gib()` da **5.473** contra un tope de 5.5. El margen es de 0,027 GiB, así que el tope se ajustó a la medida justa para que la prueba pase.
- **Origen del 5.0:** no viene de ningún diseño de U1. No tiene ID INF ni NFR. Sale del commit a1e53b3, «lean kind profile for a 14 GiB machine» (2026-11-01, a pedido del usuario). El plan de U1 (`platform-foundation-code-generation-plan.md:383`) y `audit.md:4177-4184` registran ese perfil con 3,95 GiB pedidos. El número 5.0 solo vive en la prueba, como guardia de la máquina de 14 GiB.
- **Choque con DD-3:** DD-3 dice «b primero: medir la memoria con U1 + U2 al cerrar el Paso 16, proyectar por unidad y pasar a la a solo si no cabe». Subir el tope ahora decide la capacidad antes de medir en el clúster y deja sin guardia a U3 y las siguientes.
- **Atenuante:** es una regresión que causa el propio diff, porque los renders de U2 entran al perfil kind al agregar las entradas. Además, la bitácora lo señala.
- **Lo que falla:** la candidata quedó solo en la bitácora y **no** se anotó en `vectra-risk/CANDIDATAS.md`. Ese archivo **sí existe** (148 líneas, último commit f5eea1a), así que la afirmación del codificador de que no existe es falsa.

**Corrección:** que el usuario apruebe explícitamente el 5.5 como valor provisional atado a DD-3/T6, o dejar la prueba en rojo y escalar. En los dos casos hay que anotar la candidata en `CANDIDATAS.md` y referenciar DD-3 en el comentario del literal.

### F-03 · AMARILLO · platform/tests/test_integration.py:305 · `banco-ca` aceptado como emisor externo
Lo respalda el diseño: INF-U2-01, enmienda del 2026-11-03, `infrastructure-design.md:31`. El nombre ya figura como provisional en `CANDIDATAS.md:63`, así que no es un debilitamiento indebido. Dos detalles:
- el literal está duplicado respecto a los values de `identity-edge/`;
- la excepción vale para cualquier entorno: nada impide que kind referencie `banco-ca`.

Se podría leer el nombre de los values de staging y prod.

### F-04 · AMARILLO · platform/tests/test_integration.py:369 · Esquema de los CRDs de Gateway API
Este cambio refuerza la prueba en lugar de debilitarla. Sin él, el HTTPRoute de U2 quedaba sin esquema. Es una regresión que causa el diff y le corresponde a la tarea. El detalle es que la ruta está fijada a la estructura interna del subchart `envoy-gateway/gateway-helm/charts/crds/crds/` dentro de `.charts`, que git ignora, y se rompe si el chart reorganiza esa estructura.

### F-05 · AMARILLO · platform/policies/kyverno/fixtures/resources.yaml · Fixture copiado a mano
`u2-keycloak` es una copia a mano de la Application de staging y puede desviarse de la real. La cobertura real de las 21 Applications la da el `kyverno apply` de `make check` sobre `apps/`.

### Sobre `test_platform.py` (`EXPECTED_WAVES`)
Es una regresión que causa el diff, porque la prueba exige igualdad exacta. Suma las 7 Applications en las waves de P-U1-12 y de la decisión B6. Es correcta y no debilita nada.

### Alcance
No hay desborde. `generate.py` no cambió, no hay renders ni values de `identity-edge/` en el diff, y `vectra-risk-gitops/values` no existe. El extra `secret-store → ratelimit` en STRICT es razonable.

## Tareas candidatas (defectos reales fuera de alcance)
- Presupuesto de memoria de kind para U1 + U2 (5,47 GiB pedidos): decidirlo con DD-3/T6 al cerrar el Paso 16. Va en `CANDIDATAS.md` (ver F-02).
- `test_platform.EXPECTED_WAVES` y `test_waves.FIXED_WAVES` son dos tablas de waves que se solapan. Conviene unificarlas.

```
VEREDICTO: NO-VERDE
NARANJA|platform/tests/test_waves.py:20|FIXED_WAVES quitado con justificación falsa; keycloak en wave 4 pasa test_waves
NARANJA|platform/tests/test_kind_profile.py:10|BUDGET_GIB 5.0->5.5 decide capacidad antes de DD-3 y sin anotarlo en CANDIDATAS.md (que sí existe)
AMARILLO|platform/tests/test_integration.py:305|banco-ca literal y aceptado en cualquier entorno
AMARILLO|platform/tests/test_integration.py:369|ruta fija al subchart de CRDs de Gateway API
AMARILLO|platform/policies/kyverno/fixtures/resources.yaml|fixture u2-keycloak copiado a mano
INFORME: revisiones/U02-T17/ronda-1.md
```
