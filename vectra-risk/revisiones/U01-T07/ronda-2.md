# Ronda 2 — U01-T07

VEREDICTO: NO-VERDE

Worktree `wt-U01-T07` en `1ffa5b6` (padre `a510d39`, tras `d94d011`). Estaba **limpio** antes y después de la revisión (`git status --porcelain` → nada; HEAD = `1ffa5b640d697d0fd54d28df66ef8487f188922a`). Las mutaciones las hice en la copia `scratchpad/rev-u01t07-r1/m2`.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | `pg_hba` solo `hostssl` en TCP, con el `reject`, en los 3 entornos | `uv run pytest platform/tests/test_platform.py -q -k postgres_requires_tls` | pasa: 3 passed. M1 la hace fallar, así que no se salta. |
| 2 | `restore-drill` con `verify-full` y la CA interna montada | `uv run pytest platform/restore-drill/tests -q` | pasa: 27 passed |
| 3 | Render al día y `check-local` | `make -C platform render && git status --porcelain platform/rendered && make -C platform check-local` | pasa: `git status` sin salida; ruff OK; pytest 619 passed, 0 skipped; helm lint 0 failed; rc=0 |

## Mutaciones
| Mutación | Resultado |
|---|---|
| M1: quitar el `reject` del chart | **3 failed**. F-01 de la ronda 1 queda cerrado. |
| M2: invertir `hostssl` y `hostnossl` | 3 passed. Es correcto que pase: las dos reglas son disjuntas. |
| M3: `host … md5` / M4: `reject`→`trust` / M5: `reject` solo para `10.0.0.0/8` | 3 failed en los tres casos |
| M6: `require` / M7: `verify-ca` / M8: sin `sslrootcert` / M9: otra ruta de CA | 1 failed en cada caso |
| M10: sin `certificates` en el efímero / M11: `dnsNames` que no cubren el host / M12: sin `volumeMount` | 1 failed en cada caso |
| M12b: cambiar la clave del Bundle a `ca-bundle.pem` | **1 failed**. F-03 queda cerrado. |
| M13: quitar el `reject` del Cluster efímero | 1 failed |
| M14: renombrar `postgresql:` a `postgresqlx:` en el efímero | **27 passed (sobrevive)** |
| M16: en el efímero, `hostnossl all all all trust` justo antes del `reject` | **27 passed (sobrevive)** |
| M16′: el mismo cambio en el chart | 3 failed. CA-1 sí lo detecta. |

## Hallazgos

### F-01 · NARANJA · platform/restore-drill/tests/test_drill.py:290 · La prueba del Cluster efímero busca subcadenas en el script, no lee el manifiesto que el script produce
`test_the_ephemeral_cluster_rejects_plain_text_connections` comprueba tres cosas sobre el texto del archivo `restore-cluster.sh`:
- que contenga `"      - hostnossl all all all reject\n"`;
- que contenga `"      - hostssl all all all scram-sha-256\n"`;
- que no contenga `"      - host "`.

Esto deja dos huecos, demostrados con mutaciones:
- **M16:** si se añade `hostnossl all all all trust` antes del `reject`, todo el texto plano entra con `trust`, porque en `pg_hba` gana la primera regla que coincide. La prueba sigue en 27 passed. La misma mutación en el chart sí la detecta CA-1 (M16′), porque allí cada regla debe ser `hostssl`, o `hostnossl … reject`. El Cluster efímero que entró por arbitraje queda protegido con un criterio más débil que los del chart.
- **M14:** si `pg_hba` cae bajo otra clave, la prueba también pasa.

El propio archivo ya tiene el patrón de lectura de vuelta: `manifest()` en `test_drill.py:217` captura el `Cluster` que el script envía a `kubectl create -f -` y lo parsea. Arreglo: usar `manifest(...)["spec"]["postgresql"]["pg_hba"]` y aplicarle las mismas aserciones que CA-1:
- cada regla es `hostssl`, o `hostnossl … reject`;
- existe `hostnossl all all all reject`;
- existe un `hostssl … scram-sha-256`.

Lo ideal es un único ayudante compartido con `test_postgres_requires_tls` para que las dos pruebas no diverjan.

## Comprobaciones pedidas
- **F-02, el comentario de `clusters.yaml:34-35`:** ahora dice «Se supone que…» y «POR VERIFICAR en el Paso 19 (`pg_hba_file_rules`)». Correcto.
- **La bitácora («Ronda 2», «Pendiente del Paso 19»):** recoge (a)–(d) con los mismos comandos que propuse, marcados «requiere clúster; NO ejecutado». Correcto.
  - Matiz (no bloquea): (a)–(d) solo nombran `registry-db`. Al Cluster efímero (`restore-registry`) lo ejercitaría la corrida del simulacro en kind. Convendría añadir en (a) o (b) una línea para él, o dejar dicho que lo cubre la corrida de `restore-drill`.
- **La línea 31 de la bitácora (Límites de la ronda 1):** sigue diciendo «se asume…». Es histórica y la sección de la ronda 2 la matiza, así que no la marco.
- **La candidata arbitrada:** `restore-cluster.sh:44-48` añade el mismo `pg_hba` bajo `spec.postgresql`, con la indentación correcta. M13 confirma que al menos el `reject` está vigilado. El hueco es F-01.
- **El render:** solo cambió el comentario en `rendered/*/data.yaml`; no hay cambios funcionales.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna nueva.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t07-r1/ca3-r2.log
- Copia mutada: /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t07-r1/m2

VEREDICTO: NO-VERDE
NARANJA|platform/restore-drill/tests/test_drill.py:290|la prueba del Cluster efímero busca subcadenas en el script en vez de leer el manifiesto con manifest(); sobreviven M16 (hostnossl trust antes del reject) y M14 (pg_hba bajo otra clave)
INFORME: revisiones/U01-T07/ronda-2.md
