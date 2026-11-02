# Ronda 3 — U01-T07

VEREDICTO: VERDE

El worktree `wt-U01-T07` está en `96eefb9` (padre `abc2829`). Estaba limpio antes y después de la revisión: `git status --porcelain` no devolvió nada y HEAD es `96eefb92adc1fafd460d612fc292b0cd67123600`. Las mutaciones las hice en una copia, `scratchpad/rev-u01t07-r1/m3`.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | `pg_hba` solo `hostssl` en TCP, con el `reject`, en kind, staging y prod | `uv run pytest platform/tests/test_platform.py -q -k postgres_requires_tls` | pasa: 3 passed. M1 la hace fallar, así que no se salta. |
| 2 | `restore-drill` con `verify-full` y la CA interna montada; el efímero solo admite TLS | `uv run pytest platform/restore-drill/tests -q` | pasa: 27 passed |
| 3 | Render al día y `check-local` | `make -C platform render && git status --porcelain platform/rendered && make -C platform check-local` | pasa: `git status` sin salida; ruff «All checks passed!»; pytest 619 passed, 0 skipped; helm lint 0 failed; trazabilidad de 54 identificadores; runbooks, waves y links OK; rc=0 |

## Mutaciones (todas restauradas después de cada una)
| Mutación | Resultado |
|---|---|
| M1: quitar el `reject` del chart | 3 failed |
| M2: invertir el orden de `hostssl` y `hostnossl` | 3 passed. Es lo esperado: las dos reglas son disjuntas. |
| M3: `host … md5` / M4: `reject`→`trust` / M5: `reject` solo para `10.0.0.0/8` | 3 failed en los tres casos |
| M6: `require` / M7: `verify-ca` / M8: sin `sslrootcert` / M9: otra ruta de CA | 1 failed en cada caso |
| M10: sin `certificates` en el efímero / M11: `dnsNames` que no cubren el host / M12: sin `volumeMount` / M12b: clave del Bundle `ca-bundle.pem` | 1 failed en cada caso |
| M13: efímero sin `reject` | 1 failed |
| M14: `postgresql:`→`postgresqlx:` en el efímero | **1 failed** (en la ronda 2 sobrevivía) |
| M15: efímero con `local all all trust` y `hostnossl … trust` | 1 failed |
| M16: efímero con `hostnossl … trust` antes del `reject` | **1 failed** (en la ronda 2 sobrevivía) |
| M16′: el mismo cambio en el chart | 3 failed |
| M17 (nueva): efímero con `hostssl … trust` en lugar de `scram-sha-256` | 1 failed |

## Comprobaciones pedidas
- **El ayudante `platform/tests/pg_hba_rules.py` no relaja CA-1.** Sus seis aserciones son, línea por línea, las que estaban dentro de `test_postgres_requires_tls` en `1ffa5b6`:
  - hay reglas;
  - cada regla es `hostssl` o `hostnossl`;
  - una regla que no es `hostssl` termina en `reject`;
  - existe `hostnossl all all all reject`;
  - existe una `hostssl … scram-sha-256`.

  Lo comprueban M1, M3, M4, M5 y M16′ en el chart. `test_platform.py` mantiene aparte la aserción de `ssl_min_protocol_version` y la de `len(found) == 4`.
- **La prueba del efímero lee el manifiesto**, no el texto del script. Llama a `manifest()`, que captura lo que el script envía a `kubectl create -f -`, y lo hace para los dos orígenes (`restore-registry`/`registry-db` y `restore-case`/`case-db`). M14 y M16 ahora fallan.
- **pytest lo recoge bien.** Con los flags de `check-local` (`--rootdir=platform --import-mode=importlib`), `--collect-only` da 619 pruebas. Incluye `test_postgres_requires_tls[kind|staging|prod]` y `test_the_ephemeral_cluster_rejects_plain_text_connections`. `pg_hba_rules.py` no se recoge como prueba, que es lo correcto porque no sigue el patrón `test_*`. Ruff y la trazabilidad pasan.
- **Paso 19.** La bitácora añade (e) para el `Cluster` efímero: comprobar `pg_hba_file_rules` del efímero y la lectura del LSN con `verify-full`. Las comprobaciones (a) a (d) siguen ahí. El comentario de `clusters.yaml:34-35` sigue diciendo «POR VERIFICAR en el Paso 19».

## Hallazgos
### F-01 · AMARILLO · platform/tests/pg_hba_rules.py:4 · Mensajes de fallo pobres en el ayudante
pytest no reescribe los `assert` de un módulo que no es de pruebas. Si falla, el mensaje solo muestra la tupla `(name, rule)`, sin la comparación. Bastaría `pytest.register_assert_rewrite("pg_hba_rules")` en un `conftest.py`. No bloquea.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna nueva.

## Pendiente fuera de esta revisión
- El orden real de `pg_hba` en CloudNativePG 1.30.1 no se puede confirmar sin clúster. Queda como verificación del Paso 19, puntos (a) a (e) de la bitácora.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t07-r1/ca3-r3.log
- Copia mutada: /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t07-r1/m3

VEREDICTO: VERDE
AMARILLO|platform/tests/pg_hba_rules.py:4|los assert del ayudante no los reescribe pytest; registrar con pytest.register_assert_rewrite para mensajes útiles
INFORME: revisiones/U01-T07/ronda-3.md
