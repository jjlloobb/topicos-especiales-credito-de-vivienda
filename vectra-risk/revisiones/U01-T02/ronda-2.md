# Ronda 2 — U01-T02

VEREDICTO: VERDE

- **Tarea:** el hash `8790ff0d4059d3fd033ce33307aa1c1741a2cd14` coincide.
- **Rama:** HEAD en `3fc555b`, sobre `336ad23` (informe de la ronda 1) y `f9e3d90`.
- **Diff de la ronda:** toca solo `ilm_idempotente.sh`, `test_upstream_charts.py` y un comentario de `values.yaml`. No hay desborde de alcance.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Dos pasadas contra un MinIO real, bucket nuevo, 1 regla | `bash platform/data/minio/tests/ilm_idempotente.sh` | **pasa** en 5,2 s, rc=0. Las dos variantes (`values.yaml` y `values.yaml + values-kind.yaml`) dan `loki: 1, tempo: 1` y `reglas tras 2 pasadas: 1`. En la primera pasada el error «lifecycle configuration does not exist» se tolera, como se espera. El render de kind aplica las 3 `retention set ... COMPLIANCE`. Al terminar no quedan contenedores `u01t02-*` |
| 1-rojo | Rojo con los dos values de `650823f` | el mismo script en una copia de scratch | **reproducido**: rc=1, y `loki: 2, tempo: 2` en las dos variantes. pytest da 2 failed (base y kind) |
| 2 | Charts y render | `uv run pytest platform/tests/test_upstream_charts.py -q` | **pasa**: `22 passed in 66.05s` (son 20 + 2 casos parametrizados; tiempo coherente con 22 renders reales) |

## Verificaciones pedidas
- **El render de kind es el mismo que aplica Argo.** `apps/kind/minio.yaml` aplica `valueFiles: values.yaml, values-kind.yaml` en ese orden sobre el chart `minio` 5.4.0. El script pasa `-f values.yaml -f values-kind.yaml`, en el mismo orden, sobre `platform/.charts/minio/minio`, cuyo `Chart.yaml` dice `version: 5.4.0`. Staging y prod usan solo `values.yaml`, que corresponde a la variante base.
- **F-01 corregido:** M2, M3, M4 y M6 (todas en `values-kind.yaml`) mueren ahora en el script y en pytest.
- **F-02 corregido:** M5 muere también en pytest.
- **F-03:** la limitación queda documentada en `values.yaml:62-63`, según el arbitraje.
- **Mutaciones.** Cada una se aplicó sobre una copia del árbol en HEAD. Corrí el script y `pytest -k minio` con el venv del worktree, sin caché.

| Mutación | Script | pytest | Resultado |
|---|---|---|---|
| Control sin cambios | rc=0 | rc=0 | vive (esperado) |
| M1 base sin `\|\| true` | rc=1 | rc=1 | muere |
| M2 kind sin `rm` | rc=1 (kind 2/2) | rc=1 | muere |
| M3 kind sin `\|\| true` | rc=1 | rc=1 | muere |
| M4 kind `rm` tras `add` | rc=1 | rc=1 | muere |
| M5 base `rm loki` tras `add` | rc=1 | rc=1 | muere |
| M6 kind `rm myminio/lokii` | rc=1 (kind loki 2) | rc=1 | muere |
| N1 kind `add tempo` duplicado | rc=1 (tempo 2) | rc=1 | muere |
| N2 kind `rm myminio/tempo/` | rc=0 | rc=1 | muere |
| N3 base `rm --force` sin `--all` | rc=1 (loki 2) | rc=1 | muere |
| N8 kind: el `rm` de tempo apunta a loki | rc=1 | rc=1 | muere |
| N9 kind `rm lokii` | rc=1 | rc=1 | muere |
| N5 kind `add ... myminio/tempo \|\| true` | rc=0 | rc=0 | **sobrevive** (F-01 de esta ronda) |
| N7 kind: `ilm rule add` nuevo en `vectra-model-archive` sin `rm` | rc=0 | rc=0 | **sobrevive** (F-02 de esta ronda) |

## Hallazgos
### F-01 · AMARILLO · platform/tests/test_upstream_charts.py:144 · Un `add` tolerante pasa la prueba
El filtro acepta líneas que terminan en `myminio/{bucket} || true` sin mirar si son `rm` o `add`. Por eso un `ilm rule add ... || true` cumple `["rm","add"]` (N5). Ese cambio quitaría el `set -e` justo en el comando que crea la regla: si el `add` fallara, el bucket quedaría sin lifecycle y el Job terminaría en verde. Basta con exigir también que `mine[1]` no termine en `|| true`.

### F-02 · AMARILLO · platform/tests/test_upstream_charts.py:143 y ilm_idempotente.sh:73-74 · Buckets fijos en la prueba
Tanto la prueba como el conteo del script recorren solo `("loki", "tempo")`. Un `ilm rule add` nuevo sobre otro bucket, sin su `rm`, acumularía reglas sin que nada falle (N7). La prueba podría sacar el conjunto de buckets de las propias líneas `runCommand ilm rule add`. Hoy no es un defecto, porque solo hay dos buckets con ilm.

### F-03 · AMARILLO · platform/data/minio/tests/ilm_idempotente.sh:22,42 · Comentario falso y fixture distinto de los values
- El comentario dice «el primero con lock», pero el bucle crea **todos** los buckets con `--with-lock`.
- `tempo` tiene `objectlocking: false` en `values.yaml:38` y en `values-kind.yaml:15`, así que el fixture no reproduce el bucket real.

En la ronda 1, tanto el script original como mi arnés crearon `tempo` sin lock y el resultado fue el mismo, así que no cambia el veredicto. Aun así, el comentario es inexacto.

### F-04 · AMARILLO · ilm_idempotente.sh:57 y bitácora, «Ronda 2» · Fallo sin diagnóstico
Si un bucket queda con 0 reglas (M5), `mc ilm rule ls` sale con un código distinto de cero. Con `pipefail`, la asignación `loki="$(count loki)"` aborta el script sin imprimir conteo ni mensaje, y no corre la variante kind. La mutación muere igual, pero no por la razón que da la bitácora: allí dice «el conteo es 0 líneas filtradas», y en realidad nunca se llega a contar.

## Tareas candidatas (defectos reales fuera de alcance)
- Siguen en pie las de la ronda 1:
  - Ninguna prueba fija el contenido de las reglas (`--expire-days`, `--noncurrent-expire-days`).
  - shellcheck en `.tools`.
  - `ruff format` de `test_upstream_charts.py` (preexistente).

## Estado al terminar
- El worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/wt-U01-T02` queda limpio (`git status --short` vacío) y HEAD sigue en `3fc555b608f718ada0f616cb3e6a0bc22200b1a0`.
- No quedan contenedores ni redes `u01t02-*` ni `rev02-*`.
- `kind-registry` sigue Up y `vectra-*` siguen Exited. No toqué ningún clúster.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t02-r2/` (`ca1.txt`, `mut.sh`, `mut-*-sh.txt`, `mut-*-py.txt`)

VEREDICTO: VERDE
AMARILLO|platform/tests/test_upstream_charts.py:144|un `add ... || true` cumple [rm, add] y sobrevive (N5)
AMARILLO|platform/tests/test_upstream_charts.py:143|buckets fijos loki/tempo: un ilm add nuevo sin rm sobrevive (N7)
AMARILLO|platform/data/minio/tests/ilm_idempotente.sh:22|comentario «el primero con lock» falso; tempo con lock a diferencia de los values
AMARILLO|platform/data/minio/tests/ilm_idempotente.sh:57|con 0 reglas el script aborta en count() sin diagnóstico; la explicación de la bitácora es inexacta
INFORME: revisiones/U01-T02/ronda-2.md
