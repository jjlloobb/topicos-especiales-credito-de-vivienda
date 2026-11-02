# Ronda 1 — U01-T07

VEREDICTO: NO-VERDE

Hash de la tarea `b83152fb89c0d444bb9bb4d2f6d0ccfcd9268353`: coincide. Worktree `wt-U01-T07` en `d94d011` (base `d95782a`), **limpio** antes y después de la revisión (`git status --porcelain` → nada).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | `pg_hba` solo `hostssl` en TCP, sobre el render, en los 3 entornos | `uv run pytest platform/tests/test_platform.py -q -k postgres_requires_tls -v` | pasa: 3 passed en 0,90 s. El tiempo cuadra con 3 `helm template` locales y no hay skips. **Pero la prueba no protege la propiedad (F-01).** |
| 2 | `restore-drill` con `verify-full` y la CA interna montada | `uv run pytest platform/restore-drill/tests -q` | pasa: 26 passed |
| 3 | Render al día y `check-local` | `make -C platform render && git status --porcelain platform/rendered && make -C platform check-local` | pasa: `git status` sin salida; ruff OK; pytest 618 passed, 0 skipped; helm lint 0 failed; trazabilidad, runbooks, waves y links OK; rc=0 |
| — | Rojo primero | En una copia restauré `clusters.yaml`, `drill.py`, `cronjob.yaml` y `restore-cluster.sh` de `d95782a` y corrí las pruebas nuevas | Se reproduce: CA-1 da 3 failed (KeyError `pg_hba`) y CA-2 da 2 failed, igual que la bitácora |

## Mutaciones (en la copia `scratchpad/rev-u01t07-r1/m`)
| Mutación | CA-1 | CA-2 |
|---|---|---|
| M1: quitar `hostnossl all all all reject` | **3 passed (sobrevive)** | — |
| M2: invertir el orden (`hostssl` primero y `reject` después) | 3 passed. **Es correcto que sobreviva**: `hostssl` y `hostnossl` son disjuntos, así que su orden relativo no cambia nada. Lo que importa es que el `reject` quede antes de la regla por defecto del operador. | — |
| M3: añadir `host all all all md5` | 3 failed (la mata) | — |
| M4: cambiar el `reject` por `trust` | 3 failed (la mata) | — |
| M6: volver a `sslmode=require` | — | 1 failed (la mata) |
| M7: `verify-ca` | — | 1 failed |
| M8: quitar `sslrootcert` | — | 1 failed |
| M9: ruta de la CA distinta | — | 1 failed |
| M10: quitar `certificates` del Cluster efímero | — | 1 failed |
| M11: `dnsNames` que no cubren `*-rw.vectra-restore-drill.svc` | — | 1 failed |
| M12: quitar el `volumeMount` | — | 1 failed |

## Hallazgos

### F-01 · NARANJA · platform/tests/test_platform.py:137 · La prueba de CA-1 no detecta que falte el `reject`, que es justo lo que hace cumplir NFR-U1-22
`test_postgres_requires_tls` exige que cada regla sea `hostssl`, o `hostnossl … reject`, y que exista una `hostssl … scram-sha-256`. No exige que exista el rechazo de `hostnossl`.

Con M1 (quitar la línea `hostnossl all all all reject` de `clusters.yaml:37`), la prueba sigue en 3 passed. Sin esa línea, la regla por defecto que CloudNativePG añade al final (`host all all all scram-sha-256`) vuelve a admitir conexiones TCP en texto plano. La tarea pide que los `Cluster` **rechacen** conexiones sin TLS, y la propia docstring dice «sin `host` en texto plano». La prueba solo vigila lo que el usuario escribe, no lo que el operador añade después.

Arreglo: afirmar que, en el render, hay una regla `hostnossl all all all reject` (o equivalente que cubra todas las bases de datos, usuarios y direcciones). No hace falta comprobar su orden frente al `hostssl` (ver M2).

### F-02 · AMARILLO · platform/data/chart/templates/clusters.yaml:34-35 · El comentario afirma como hecho un comportamiento del operador que nadie verificó
Lo que hay localmente sobre el orden de `pg_hba`:
- La versión pinneada es el chart 0.29.1 y el operador 1.30.1 (`platform/.charts/cloudnative-pg/cloudnative-pg/Chart.yaml`).
- En los CRD (`templates/crds/crds.yaml:5368`), la descripción de `spec.postgresql.pg_hba` solo dice «lines to be appended to the pg_hba.conf file». No dice nada de la regla por defecto.
- No hay código fuente ni imagen del operador en el disco: busqué en los charts, el home, el scratch y las imágenes de podman.

**No se puede confirmar sin red.** Por la documentación upstream que conozco, el archivo que genera CloudNativePG es este:
1. `local all all peer map=local`
2. `hostssl postgres streaming_replica all cert`, `hostssl replication streaming_replica all cert` y `hostssl all cnpg_pooler_pgbouncer all cert`
3. las reglas del usuario
4. `host all all all scram-sha-256`

Con ese orden, la apuesta del codificador es correcta. Pero es conocimiento mío, no evidencia. El comentario debería decir que está por verificar en el Paso 19.

Propuesta para el Paso 19, en kind:
- (a) Comprobar el orden: `SELECT line_number,type,database,user_name,address,auth_method FROM pg_hba_file_rules ORDER BY 1;` en la primaria. El `hostnossl … reject` debe tener un `line_number` menor que el de `host all all all scram-sha-256`.
- (b) Comprobar que el plano se rechaza: `psql "host=registry-db-rw.vectra-data.svc dbname=registry user=registry_verifier sslmode=disable"` debe fallar con «pg_hba.conf rejects connection … no encryption».
- (c) Comprobar que TLS verificado entra: lo mismo con `sslmode=verify-full sslrootcert=<Bundle vectra-internal-ca>` debe conectar.
- (d) Comprobar que las réplicas siguen vivas: `pg_stat_replication` con 2 réplicas `streaming` y `kubectl get cluster` en estado sano.

### F-03 · AMARILLO · platform/restore-drill/tests/test_drill.py:200,277 · La ruta de la CA está escrita dos veces sin relación entre sí
La prueba compara `sslrootcert == "/etc/vectra/ca/ca.crt"` y `mountPath == "/etc/vectra/ca"` con dos literales separados. Tampoco liga el nombre de archivo `ca.crt` con `target.configMap.key` del Bundle (`mesh/certificates.yaml:85`). Si alguien cambiara la clave del Bundle, la prueba no lo detectaría. No bloquea.

## Comprobaciones pedidas por el orquestador
- **Conexiones internas de CNPG:**
  - `streaming_replica` (replicación y `postgres`) y el pooler usan reglas fijas `hostssl … cert`, que van antes de las del usuario. No las alcanza `hostnossl reject`, y además ya van por TLS.
  - El usuario `postgres` local, la instance manager y los backups usan socket Unix (`local … peer`), que `hostnossl` no cubre.
  - No hay `Pooler` en el repositorio (grep de `kind: Pooler` y `pgbouncer` sin resultados).
  - Todo esto se basa en el conocimiento upstream, no verificado localmente; lo cubre el (d) del Paso 19.
- **Exporter en 9187:** es el exporter integrado de la instance manager (F60). Consulta por socket local, así que el `reject` no lo afecta.
- **`registry_verifier`:** su único cliente en U1 es `drill.py`, ahora con `verify-full`. El otro consumidor (`vectra-app`) es de U2 a U12 y queda fuera de alcance. No hay más cadenas de conexión a PostgreSQL en el repositorio (grep de jdbc, `KC_DB`, `postgres://` y `sslmode` sin otros resultados).
- **Coherencia del `verify-full`:**
  - El `Certificate` `restore-postgres-server` lo firma el `ClusterIssuer` `vectra-internal-ca` (existe en `mesh/certificates.yaml:21`).
  - El `dnsName` `*.vectra-restore-drill.svc` cubre `restore-registry-rw.vectra-restore-drill.svc`.
  - El Bundle publica la clave `ca.crt` en los namespaces con `vectra.io/mesh: enabled`, y `vectra-restore-drill` está en `namespaces/values.yaml` como `meshed`.
  - Montarlo en `/etc/vectra/ca` da `/etc/vectra/ca/ca.crt`. Es coherente.
- **Alcance:** la unificación del bloque `postgresql` en `clusters.yaml` no cambia el render más allá de las 20 líneas de `pg_hba` (5 por cada uno de los 4 `Cluster`; el diff de `rendered/*/data.yaml` es +20/−0). El `Certificate` y el montaje de la CA entran en el alcance por el arbitraje. No hay desborde.

## Tareas candidatas (defectos reales fuera de alcance)
- El `Cluster` efímero de `restore-cluster.sh` no lleva el `hostnossl … reject`, así que acepta texto plano durante el simulacro. NFR-U1-22 podría extenderse a él.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t07-r1/ca3.log
- Copia mutada: /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t07-r1/m

VEREDICTO: NO-VERDE
NARANJA|platform/tests/test_platform.py:137|test_postgres_requires_tls sobrevive a quitar `hostnossl all all all reject`: no protege el rechazo de texto plano
AMARILLO|platform/data/chart/templates/clusters.yaml:34|el comentario afirma el orden de pg_hba de CNPG sin verificarlo (CRD solo dice «appended»); comprobar con pg_hba_file_rules en el Paso 19
AMARILLO|platform/restore-drill/tests/test_drill.py:200|la ruta de la CA está duplicada como literal y no se liga a la clave `ca.crt` del Bundle
INFORME: revisiones/U01-T07/ronda-1.md
