# Ronda 3 — U02-T08

VEREDICTO: VERDE

Revisé el sha `94b0672` sobre `b9577ff`. El diff de la ronda va de `4546f83` a `94b0672`, en tres commits:
- `7da61e8`: la enmienda S3 del orquestador (tarea e INF-U2-09).
- `c368aaa`: el código.
- `94b0672`: la bitácora y la respuesta.

El hash de la tarea coincide (`2eec895c…`). Corrí todo en una copia nueva (`git archive 94b0672` más `.tools`, `.charts` y `.github`). Al terminar, el worktree del codificador sigue limpio.

Los 7 criterios pasan. F-08, F-09, F-10, F-11, D-8 y S3 quedan corregidos, y no hay ningún ROJO ni NARANJA en pie. Los dos agujeros que encontré de nuevo (N-1 y N-2) son límites de S3 tal como está escrito, no defectos del código, así que van como candidatas para el orquestador.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Aceptación del Paso 6 | `uv run pytest …test_realm_diff.py -q -rs && HYPOTHESIS_PROFILE=ci uv run pytest …test_realm_normalize.py -q` | pasa: 204 passed (17,6 s) y 5 passed (28,1 s; cada propiedad tarda entre 3,3 y 11,7 s, no se saltaron) |
| 2 | Reglas de la proyección, con S1, S2 y S3 | `uv run pytest identity-edge/tests/unit/test_realm_diff.py -q -rs` | pasa: 204 passed, 0 omitidas. Están los casos `test_s3_*`, `test_f08_*`, `test_d8_*`, `test_f09_*` y `test_f11_*` |
| 3 | Jobs contra Keycloak y Pushgateway falsos | `uv run pytest identity-edge/tests/unit/test_identity_jobs.py -q -rs` | pasa: 132 passed |
| 4 | Render y políticas | `make -C identity-edge render-jobs policy-jobs && uv run pytest …-k render` | pasa: conftest 555/555 y 5/5 ×3; pytest 98 passed. El nuevo render sale idéntico a `rendered/` |
| 5 | `keycloak-reader` con tres roles | `uv run python …realm_lint.py …realm.*.yaml && uv run pytest …test_realm_lint.py …test_realm_files.py -q` | pasa: 629 passed |
| 6 | Dockerfile y políticas de U1 | `platform/.tools/bin/hadolint … && make -C identity-edge policy-jobs-u1` | pasa: Kyverno `pass: 16, fail: 0` ×3; conftest 35/35 y 3/3 ×3 |
| 7 | Regresión | `uv sync --frozen --offline && make -C identity-edge check && make -C platform check-tools` | pasa: rc=0, 1504 passed, `check-tools` `pass: 239, fail: 0` |

En CA-7 agregué `--offline` porque no hay red.

## Sondas repetidas (sobre `realm_exports.keycloak_view`, que incluye los valores por defecto de 26.8.1)
La base da 0 en los tres entornos. Todas las sondas de las rondas 1 y 2 dan ahora lo esperado:

| Sonda | Ronda | Resultado ahora |
|---|---|---|
| Flujo nuevo con `builtIn: true` | R1 | 1 |
| Ejecución con `priority` repetida | R1 | 4 |
| `break-glass` tras su primer login | R1 | 0 |
| `redirectUri` de más | R1 | 1 |
| U-1 `analista-1` recibe `realm-admin` | R2 | **1** |
| U-2 la cuenta del reader recibe `cro` | R2 | **1** |
| U-3 la cuenta del reader recibe `broker: read-token` | R2 | **1** |
| `connectionUrl` a `ldap://atacante:389` | R2 | **1** |
| `connectionUrl` a `ldaps://otro:636` | R2 | 0 (S3) |
| `service_account` en un cliente público | R2 | **1** |
| `docker auth` con `builtIn: false` | R2 | **1** |
| `default-roles-vectra` con `realm-admin` | R2 | **1** |

## Sondas nuevas sobre lo que cambió
- **Composites:** dan 1 cada uno:
  - `cro` compuesto con `operacion`;
  - `offline_access` con `cro`;
  - `uma_authorization` con `realm-admin`;
  - `default-roles-vectra` con `account: manage-account-links`.
- **Roles como conjunto exacto:**
  - `break-glass` sin `realm-admin` da 1, y un rol repetido en la lista da 1;
  - un rol propio repetido da 1 (duplicado);
  - un contenedor vacío de más da 0, igual que los roles por defecto de un usuario, y es lo correcto.
- **S3:**
  - un path extra antes del sufijo da 1;
  - `webOrigins: ["*"]` da 1;
  - `https://*` da 1;
  - un elemento de más que conserva el sufijo, con los dos marcadores ya usados, da 1.

## Hallazgos
### F-12 · AMARILLO · identity-edge/tools/realm_diff.py:407-427 · El emparejamiento máximo puede señalar el elemento equivocado
Sonda N-4: añado `https://atacante.example/x?/callback` a `vectra-console`. La cuenta es correcta (1), pero la diferencia apunta a `redirectUris["https://resuelto/callback"]`, que es el elemento legítimo, porque el emparejamiento le dio el marcador al del atacante. El job solo registra la ruta, así que el operador iría a mirar el elemento equivocado. Una forma de arreglarlo: cuando varios elementos de Keycloak caben en el mismo marcador, registrarlos todos como candidatos.

### F-13 · AMARILLO · realm_diff.py:378 · `copy_empty` es pública
Es la única función auxiliar sin `_`. Es solo de nombre.

## Tareas candidatas (para el orquestador; S3 permite lo siguiente tal como está escrito)
- **N-2, el más grave.** En los tres entornos, `jwks.string` de los clientes de servicio es `$(env:CLIENT_…_JWKS)`, sin texto literal alrededor, así que cualquier valor conserva «sus literales». Cambiar la llave pública de `keycloak-config-cli`, que tiene `realm-admin`, por una del atacante da **0**. Eso es suplantar a un cliente con `private_key_jwt`. Para cerrarlo, `realm-drift` tendría que recibir los JWKS esperados, por ejemplo por el mismo ExternalSecret que usa `keycloak-config-cli`, o al menos los `kid`.
- **N-1.** `post.logout.redirect.uris` es una cadena con varios valores separados por `##`. `https://resuelto/##https://atacante.example/` empieza y termina con los literales y da **0**. Habría que tratar `##` como separador de lista en ese atributo, o decidirlo en el diseño.
- **N-5 y N-7.** El mismo marcador (`$(env:PUBLIC_HOSTNAME)`) puede resolverse a hosts distintos en cada elemento: un `stepup-callback` hacia `https://atacante/` da 0, y lo mismo pasa con `webOrigins`. Exigir que una misma variable se resuelva igual en todo el realm cerraría esto sin conocer el valor.
- Sigue la candidata de entidades propias de Keycloak. Se le suma un caso: los composites de los roles de cliente de `realm-management` no se leen, así que si `view-users` incorporara `manage-users`, la cuenta del reader quedaría escalada con 0 diferencias.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/logs3/ (ca1, ca3, ca4, ca5, ca6, ca7 y sondas.txt)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/sondas/sonda3.py
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/sondas/marcadores.py

```
VEREDICTO: VERDE
AMARILLO|identity-edge/tools/realm_diff.py:407-427|El emparejamiento máximo puede señalar el elemento equivocado
INFORME: revisiones/U02-T08/ronda-3.md
```

VEREDICTO: VERDE
