# Ronda 1 — U02-T18

VEREDICTO: VERDE

El ritmo RL-1 a RL-5 aplica: solo un ROJO bloquea. No encontré ningún ROJO. Encontré un NARANJA (F-01). Con RL ese hallazgo no bloquea, pero se arregla en la próxima tarea que toque `keycloak.rego` o se lleva a candidatas. El orquestador debe tenerlo en cuenta.

Revisé el worktree en el sha `91a8f6d2b92f01a33d792de78cd206620b40f05d`, con base `c59821b`. Al terminar sigue limpio (`git status --short` vacío).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Trazabilidad U2 | `uv run python platform/tests/test_traceability.py --unit identity-edge` | pasa: «identity-edge: 39 identificadores con trazabilidad», rc=0, ninguna línea «sin trazabilidad» |
| 2 | README y enlaces | `test -f .../identity-edge/code/README.md && uv run python platform/tests/test_links.py` | pasa: «293 archivos Markdown sin enlaces rotos», rc=0 |
| 3 | Correcciones | los dos `grep` de CA-3, más un `git grep` en todo el repo de líneas que tengan a la vez `identity-jobs` y `config-cli` | pasa. Ninguna línea dice que `identity-jobs` contiene `keycloak-config-cli`; las que quedan lo niegan o son históricas (`DECISIONES-LOOP.md:60`). `deployment-architecture.md:68` pone `identity-jobs` en la wave 4 |
| 4a | `make -C platform check` | eso mismo | pasa: rc=0, 745 passed en 695 s, 0 omitidas; kyverno 81/81 y pass 45 con fail 0; 20 min en total |
| 4b | U2 | `make -C identity-edge lint test` (no el `check` completo) | pasa: ruff «All checks passed!» y «2690 passed in 4068.46s», rc=0 |

Por qué corrí `lint test` y no el `check` completo: en `identity-edge/` el diff solo toca comentarios (`#` del Makefile fuera de recetas, rego, YAML y la regla de promtool), docstrings (`conftest.py`, `test_hypothesis_profile.py` y `route_gen.py`) y Markdown (el ADR y el runbook). No cambia ninguna línea ejecutable; lo comprobé con `git diff ... | grep '^[+-]'`.

## Los 7 ids, contrastados con `nfr-requirements.md`
- **NFR-U2-04** (si cae el controlador, el data plane sigue): está en `identity-edge/docs/adr-envoy-gateway.md` §1. La justificación es sustantiva: el data plane es un Deployment aparte y recibe la configuración por xDS. La prueba se nombra en el Paso 16 del plan, ítem 6. Se acepta (ver F-02).
- **NFR-U2-05** (caída de Keycloak, SEV1, `KeycloakDown` probada con promtool): está en la regla, con `severity: SEV1` verificada, en la prueba de promtool y en el runbook. Lo implementa y lo prueba.
- **NFR-U2-21** (fail-closed en `/auth/**` y fail-open en el resto): está en `routes.yaml` `fail_closed`, en `route_gen.envoy_patch_policies` y en la regla `fail-closed-patch` de `edge.rego`. Lo implementan y lo validan.
- **NFR-U2-25** (digest y firma de 4 imágenes): está en la regla `image` de `keycloak.rego`, que exige el digest. La ubicación es legítima pero parcial (F-01 y F-03).
- **NFR-U2-40**: está en el target `test` del Makefile (`HYPOTHESIS_PROFILE=ci`) y en `test_hypothesis_profile.py`. Lo cumplen.
- **NFR-U2-41**: está en el target `kubeconform-gateway` (`-strict` con los CRDs). Lo cumple.
- **NFR-U2-42**: está en el target `e2e` y en el `conftest.py` de e2e. Lo cubre la especificación diferida al Paso 16, como pide la tarea.

Ninguno de los 7 se puso solo para pasar la prueba.

## README
- Todas las rutas entre comillas invertidas existen; ninguna falla.
- Todos los targets de make que cita existen en el Makefile.
- Tiene las 9 secciones que pide la tarea: Keycloak y realm, `realm-lint`, Jobs, gateway y `route-gen`, rate limit y Valkey, flujos y RBAC, observabilidad, e2e y carga, y GitOps.
- Al final tiene la tabla de los 7 ids.

## Correcciones del PR 79
- La nota del Paso 12 tiene el texto literal que pide la tarea, conserva la fecha y la referencia a C-05.
- El Paso 15 está marcado `[x]` con `(U02-T18)`.
- En U02-T17 están los tres cambios: la fila con la wave 4 sin `keycloak-config-cli`, la sección «Orden» con `STRICT` y la frase de la demo fuera de la enmienda.
- Las dos tablas de waves tienen la fila de la wave 4 y la nota «(revisión de código del PR 79, 2026-11-08)».
- Las 4 candidatas nuevas están sin duplicados. La de `EXPECTED_WAVES`/`FIXED_WAVES` ya existía (línea 170) y no se repitió.

## Alcance
`git diff --name-only` no toca `test_waves.py`, `components.yaml`, `decision-registry/`, `reference-model/` ni `test_traceability.py`, y no hay desborde.

## Hallazgos
### F-01 · NARANJA · `identity-edge/keycloak/policy/keycloak.rego:364` · la afirmación sobre la firma es falsa
El comentario dice «la firma la exigen las políticas de U1, que `policy-keycloak-u1` aplica». En realidad `policy-keycloak-u1` copia solo `STATIC_POLICIES` (`identity-edge/Makefile:11`), y esa lista no incluye `verify-images.yaml`. La firma la exige `platform/policies/kyverno/verify-images.yaml` (`verifyImages`) en el momento de la admisión, no en `check`. La evidencia de trazabilidad queda mal descrita, aunque el id está bien ubicado por la parte del digest. Arreglo: decir que la firma la exige `verify-images` de U1 en la admisión.

### F-02 · AMARILLO · README, tabla de los 7 ids · NFR-U2-04 no nombra la configuración que lo hace posible
El modo `GatewayNamespace` vive en `platform/operators/envoy-gateway.yaml:34` (U1) y lo prueba `platform/tests/test_unit_plans.py:47`. La fila podría citarlo, junto con el ítem 6 del Paso 16.

### F-03 · AMARILLO · NFR-U2-25 · cobertura parcial
El id solo marca Keycloak. Los digests de Envoy (`edge.rego:23/182`), del rate limit (`ratelimit.rego:12/118`) y de Valkey (`valkey.rego:13`) también lo cumplen y no llevan el id; el README tampoco los nombra.

### F-04 · AMARILLO · `CANDIDATAS.md:173` · referencia ambigua
«se suma a la de `secret-store` y `mesh-certificates` de la ronda 3» parece remitir a una candidata que no existe. Se refiere a los pares que se agregaron a `test_waves.py` en la ronda 3.

### F-05 · AMARILLO · README · el título difiere del formato de contracts
La tabla se titula «sin referencia directa» y no «sin referencia en él», y lista ids que sí están en `identity-edge/`. Es inofensivo, pero se aparta del formato de `contracts/code/README.md`.

## Tareas candidatas
- `policy-*-u1` no puede validar firmas de forma estática. Conviene decidir si se documenta en `check` que la firma solo se verifica en la admisión, o si se agrega una prueba de admisión en kind (Paso 16).

```
VEREDICTO: VERDE
NARANJA|identity-edge/keycloak/policy/keycloak.rego:364|El comentario atribuye la verificación de firma a policy-keycloak-u1, que no aplica verify-images (no bloquea con RL)
AMARILLO|README tabla de ids|NFR-U2-04 sin citar platform/operators/envoy-gateway.yaml:34 ni el ítem 6 del Paso 16
AMARILLO|NFR-U2-25|Solo Keycloak; los digests de Envoy, ratelimit y Valkey no llevan el id
AMARILLO|CANDIDATAS.md:173|Remite a una candidata de secret-store/mesh-certificates que no existe
AMARILLO|README|El título de la tabla difiere del formato de contracts/code/README.md
INFORME: revisiones/U02-T18/ronda-1.md
```
