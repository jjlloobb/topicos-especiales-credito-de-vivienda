# Ronda 2 — U02-T19

VEREDICTO: VERDE

CA-1 a CA-5 pasan en mis propias corridas, incluido CA-5 completo, y no queda ningún ROJO ni NARANJA. Revisé el sha `546c3eb`. No toqué el clúster. Al terminar, el worktree del codificador quedó limpio (`git status --porcelain` vacío) y en el mismo HEAD. Las mutaciones las hice en una copia con `git archive`, en el scratchpad (`U02-T19-revisor-r2/copy/`). Las herramientas y el venv del worktree están enlazados, porque /tmp no tiene cuota para un venv nuevo.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Job y administrador de arranque solo en kind | `make -C identity-edge check-keycloak-rendered policy-keycloak policy-keycloak-u1`; `grep -c` | pasa: código 0. Kind da 20 coincidencias, con `PostSync` y `BeforeHookCreation` (líneas 1825 y 1826). Staging y prod dan 0 y 0 |
| 1-F01 | Valores renderizados de kind | parseo YAML del Job | contenedor principal: 100m/256Mi de requests y 500m/512Mi de limits, igual que INF-U2-06. Prioridad `vectra-normal`, igual que `logical-components.md:14`. `truststore`: 50m/64Mi y 250m/128Mi. backoffLimit 3, plazo 900, `300s` y `NOMBRE` |
| 1-rojo | Las reglas endurecidas | muto `values/common.yaml`, vuelvo a renderizar y corro `policy-keycloak` | límite de 1Gi, `vectra-low`, truststore de 256Mi y request de 384Mi: cada mutación da 1 fallo `config-cli-security`, con su mensaje. Después restauré y `check-keycloak-rendered` dio 0 |
| 2 | Rutas `identity/` y `edge/valkey` | `vault_paths.py list \| grep` | pasa: 59 líneas. Aparecen ca, 15 clientes, synthetic-users, break-glass, keycloak-admin y edge/valkey |
| 3 | Modo `identity` con dobles | `uv run pytest platform/kind/tests -v -rs` | pasa: 61 aprobadas en 61 s, 0 omitidas |
| 4 | Eco 503 y caso e2e | `pytest identity-edge/tests/unit -k echo -v`; `make collect-e2e \| grep` | pasa: 55 aprobadas en 50 s, 0 omitidas. Aparecen `test_post_to_a_backend_with_503_gets_exactly_one_call` y `test_idempotent_get_with_503_is_not_retried_on_503` |
| 5 | `check` de U2 y de U1 | `make -C identity-edge check && make -C platform check`, en el worktree | **pasa: los dos dan código 0.** U2 tardó 1:01:18 (`2767 passed in 3571.74s`). U1 tardó unos 22 min (`784 passed in 771.11s`), con kyverno test en 81/81 |

Otras comprobaciones:
- **Staging y prod.** `git diff --quiet de70f35 546c3eb -- …/rendered/staging …/rendered/prod` da código 0: no cambia ni un byte.
- **Secretos.** En el diff no hay material de llaves. El único `BEGIN PRIVATE KEY` es una aserción de prueba.
- **Alcance.** El diff no toca `decision-registry/`, `reference-model/`, `flows.yaml` ni el plan.
- **Cuota.** `quotas.yaml` no filtra por prioridad, así que el cambio a `vectra-normal` no la afecta.

## Lo que se pidió comprobar
- **F-01: cerrado.**
  - Los recursos y la prioridad salen como dice el diseño, y la regla los exige. Reproduje el rojo arriba.
  - El `truststore` no sube lo que el pod pide en total: el init corre antes y su máximo (64Mi/128Mi) queda por debajo del contenedor principal.
- **F-02: cerrado.**
  - `backoffLimit`, `activeDeadlineSeconds`, `availabilityTimeout`, `priorityClassName`, `resources`, `truststoreResources` y `commentPlaceholder` salen de `vectra.configCli.*`.
  - Rendericé con otros valores en esos cinco campos (111, `vectra-x`, 777Mi, 11m, `OTRO`) y todos llegan al render.
  - `VECTRA_KC_ADMIN_USER` funciona. La mutación que vuelve a `return "admin"` hace fallar `test_the_admin_user_is_a_parameter_with_a_default`.
- **F-06: cerrado.**
  - `write_private` escribe en un temporal creado con `O_EXCL` y modo 0600, y lo cambia por el destino con `os.replace` (`Path.replace`).
  - Probé tres mutaciones y en las tres falla `test_a_preexisting_loose_file_is_replaced_without_the_new_content_ever_being_loose`: (a) la de la ronda 1, con `O_TRUNC` sobre el destino y `chmod` después; (b) un temporal en 0644 con `chmod` antes de `replace`; (c) `write_text` y luego `chmod`.

## Hallazgos (ninguno bloquea)
### F-01 · AMARILLO · `tests/unit/test_config_cli.py` (`test_the_job_parameters_come_from_the_values_not_from_the_template`) · La prueba con otros valores cubre 2 de 7 parámetros
Solo cambia `backoffLimit` y `availabilityTimeout`. Para los recursos, la prioridad y `commentPlaceholder`, la prueba solo comprueba que el literal falta en el template. Yo comprobé a mano que esos campos también llegan al render. Conviene que la prueba también cambie esos tres.

### F-02 · AMARILLO · bitácora, ronda 2, F-01 · Las cifras del `truststore` no están medidas con su límite
La bitácora dice que `keytool` «usa pocas decenas de MiB (la ronda 1 lo probó con la imagen real)». Esa prueba de la ronda 1 se hizo con `docker run` sin `--memory`, así que no muestra que quepa en 128Mi. Es muy probable que quepa, porque la JVM toma por omisión el 25 % de la memoria del contenedor como heap. Se cierra en el Paso 16, junto con la candidata de los 512Mi (DD-3).

### F-03 · AMARILLO · `platform/kind/vault_paths.py:267` y `identity-edge/docs/paso-16-kind.md` · `VECTRA_KC_ADMIN_USER` no está documentado
El operador puede cambiar ese valor, pero ni la guía del Paso 16 (§4) ni el uso de `seed-vault.sh` lo mencionan.

### F-04 · AMARILLO · `rendered/kind/keycloak.yaml:1856,1891` · Sangría inconsistente
`nindent 16` deja los hijos de `resources:` 6 columnas más adentro que la clave. El YAML es válido y las políticas lo leen bien, pero es feo de leer. Se arregla con `nindent 12`.

### F-05 · AMARILLO · `vault_paths.py` (`write_private`) · Un temporal huérfano si la escritura falla
Si `handle.write` lanza una excepción, el `.env.<hex>.tmp` queda en el directorio, aunque en 0600. Lo resuelve un `try/except` que lo borre.

## Tareas candidatas
- Ninguna nueva. F-02 cabe en la candidata ya registrada de medir la JVM en el Paso 16.

```
VEREDICTO: VERDE
AMARILLO|identity-edge/tests/unit/test_config_cli.py|La prueba con otros valores cubre 2 de 7 parámetros
AMARILLO|bitacoras/U02-T19.md (ronda 2, F-01)|Las cifras del truststore no están medidas con su límite
AMARILLO|platform/kind/vault_paths.py:267|VECTRA_KC_ADMIN_USER no está documentado
AMARILLO|identity-edge/keycloak/rendered/kind/keycloak.yaml:1856,1891|Sangría inconsistente
AMARILLO|platform/kind/vault_paths.py (write_private)|Un temporal huérfano si la escritura falla
INFORME: revisiones/U02-T19/ronda-2.md
```

Nota del orquestador: F-03 lo corrigió el orquestador en este PR, en la guía del Paso 16 §4. El resto pasa a `CANDIDATAS.md`.
