# Ronda 1 — U01-T02

VEREDICTO: NO-VERDE

Hash de la tarea `8790ff0d4059d3fd033ce33307aa1c1741a2cd14`: coincide. HEAD `f9e3d90`, base `650823f`, un commit. El diff toca solo `values.yaml`, `values-kind.yaml`, `test_upstream_charts.py`, el script nuevo y la bitácora. No hay desborde de alcance.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Dos pasadas contra un MinIO real, bucket nuevo, 1 regla | `bash platform/data/minio/tests/ilm_idempotente.sh` | pasa: rc=0, `loki: 1, tempo: 1`, `reglas tras 2 pasadas: 1`, 2,6 s. Primera pasada con `mc: <ERROR> ... lifecycle configuration does not exist` tolerado. No quedan contenedores ni redes `u01t02-*` |
| 1-rojo | Rojo con los `customCommands` de `650823f` | el mismo script en una copia (`git archive` en scratch) con `values.yaml` de `650823f` | `loki: 2, tempo: 2`, `reglas tras 2 pasadas: 2`, rc=1. El rojo se reproduce |
| 2 | Charts y render | `uv run pytest platform/tests/test_upstream_charts.py -q` | pasa: `20 passed in 20.17s`. El tiempo cuadra con 20 `helm template` reales |

## Verificaciones pedidas por el orquestador
- **¿Shell o no shell? El codificador tiene razón y la nota de la tarea está mal.** Hice `helm template` con values.yaml más values-kind.yaml. El Job renderiza `command: [ "/bin/sh", "/config/custom-command" ]` y el script contiene la línea literal `runCommand ilm rule rm --all --force myminio/loki || true` (línea 777 del render). Es el script `/bin/sh` con `set -e` el que interpreta `||`.
- **El Job, tal como lo corre el chart.** Mi propio arnés (`job.sh`) saca el ConfigMap con `yaml.safe_load` en vez de con el `awk` del codificador. Usa el render de kind completo (5 buckets, incluidos los WORM) y corre `/bin/sh /config/custom-command` en `localhost:5001/mc:dev` contra `localhost:5001/minio:dev`, con los contenedores `rev02-*`. Las dos pasadas dan rc=0 y dejan `loki: 1`, `tempo: 1`.
- **`|| true` no oculta los fallos graves:**
  - Con el bucket `tempo` inexistente, el `rm` se tolera, pero el `add` siguiente falla (`The specified bucket does not exist`) y la pasada termina en rc=1.
  - Con credenciales malas, `connectToMinio` agota 30 intentos y termina en rc=1.
- **El script reproduce el render, no una copia a mano.** Llama a `helm template` sobre el chart real. La salida del `awk` es idéntica a la extracción por YAML, salvo un salto de línea final que no cambia nada.
- **Mutaciones** (script + `test_upstream_charts.py -k minio`, en la copia de scratch):

| Mutación | Script | pytest | Resultado |
|---|---|---|---|
| M1: quitar `\|\| true` en loki (values.yaml) | falla | falla | muere |
| M5: `rm loki` después de `add loki` (values.yaml) | falla | **pasa** | muere solo por el script |
| M2: quitar las líneas `rm` (values-kind) | pasa | pasa | **sobrevive** |
| M3: quitar `\|\| true` (values-kind) | pasa | pasa | **sobrevive** |
| M4: `rm` tras `add` (values-kind) | pasa | pasa | **sobrevive** |
| M6: `rm myminio/lokii` (values-kind) | pasa | pasa | **sobrevive** |
| M7: `--expire-days 9` | pasa | pasa | sobrevive (contenido de la regla, ver candidatas) |
| M8: sin `--noncurrent-expire-days` | pasa | pasa | sobrevive (contenido de la regla, ver candidatas) |
| M9: `\|\| true; true` | pasa | pasa | equivalente, no es defecto |

## Hallazgos
### F-01 · NARANJA · platform/data/minio/tests/ilm_idempotente.sh:23 y platform/tests/test_upstream_charts.py:138 · values-kind.yaml cambió pero ninguna prueba lo cubre
Helm reemplaza las listas, como dice el propio `values-kind.yaml:2`. En kind, `customCommands` viene entero de `values-kind.yaml:53-61` (`apps/kind/minio.yaml:17` lo aplica). El script renderiza solo con `values.yaml`, y `test_minio_kind_has_worm_buckets` no mira las líneas `ilm`. Por eso las cuatro mutaciones de `values-kind.yaml` (M2, M3, M4, M6) pasan las dos pruebas.
- M3 (quitar `|| true` en kind) rompería la primera sync del Job en kind, el único entorno que se ejecuta de verdad.
- M2, M4 y M6 devuelven la acumulación de reglas en kind.

El argumento de la bitácora («los buckets WORM de values-kind no usan ilm») pasa por alto que el overlay redefine también los comandos de loki y tempo. Se pide cubrir el render de kind: que el script acepte o recorra los dos conjuntos de values, o al menos que la aserción de orden de `test_upstream_charts.py` se aplique también al render de kind.

### F-02 · AMARILLO · platform/tests/test_upstream_charts.py:134-135 · La aserción de orden es débil
`script.index("ilm rule add", removal)` encuentra cualquier `add` posterior, no el del mismo bucket. Con M5 (`add loki; rm loki; rm tempo; add tempo`) pytest pasa, porque el `add` de tempo satisface la condición de loki. Solo el script lo atrapa. Bastaría con buscar `ilm rule add ... myminio/{bucket}` y exigir que no haya otro `add` del mismo bucket entre el `rm` y su `add`.

### F-03 · AMARILLO · platform/data/minio/values.yaml:67,69 · `|| true` tolera cualquier fallo del `rm`
No solo el de «no hay reglas»: un fallo transitorio o de permisos del `rm` se ignora, el `add` funciona y vuelve una regla duplicada sin que nadie se entere. Con `customCommands` no hay forma limpia de discriminar el error, y el comentario de values.yaml:62-63 explica el `|| true`. Lo anoto, no lo bloqueo.

### F-04 · AMARILLO · tarea, sección Notas · La especificación afirma algo falso
«El chart ejecuta cada comando sin shell» es incorrecto (ver la verificación de shell arriba). Esto es para que el orquestador corrija la plantilla de la tarea. El codificador lo detectó y lo documentó bien.

## Afirmaciones de la bitácora comprobadas
- Rojo y verde: reproducidos (IDs distintos, mismas cuentas).
- 20 passed: reproducido.
- `ruff check`: «All checks passed!», reproducido.
- `ruff format --check`: reformatearía el archivo, pero también la versión de `650823f`; es preexistente, reproducido.
- shellcheck: ausente en el PATH, reproducido.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna prueba fija el contenido de las reglas ilm (`--expire-days 90`, `--noncurrent-expire-days 1` en loki): M7 y M8 sobreviven. El script podría leer `Expiration.Days` en `ilm rule ls --json`.
- shellcheck en `platform/.tools/bin` para `platform/**/tests/*.sh`, y `ruff format` de `test_upstream_charts.py` (las mismas que propone el codificador).

## Estado al terminar
- `git -C /home/jjlloobb/IT/PUJ/MINSC/GitHub/wt-U01-T02 status --short` está vacío y HEAD sigue en `f9e3d90c609f701543ba0953d0dbce8fec33bbd3`.
- No quedan contenedores ni redes `rev02-*` ni `u01t02-*`.
- `kind-registry` sigue Up y los nodos `vectra-*` siguen Exited. No toqué ningún clúster.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t02-r1/ con:
  - `ca1.txt`
  - `render-kind.yaml`
  - `job.sh`, `job-kind-ok.txt`, `job-nobucket.txt`, `job-badcreds.txt`
  - `mut.sh`, `mut-M*-sh.txt`, `mut-M*-py.txt`

VEREDICTO: NO-VERDE
NARANJA|platform/data/minio/tests/ilm_idempotente.sh:23|values-kind.yaml (lo que corre en kind) sin cobertura: M2/M3/M4/M6 sobreviven al script y a pytest
AMARILLO|platform/tests/test_upstream_charts.py:134|la aserción de orden rm→add no ata el add al mismo bucket (M5 pasa pytest)
AMARILLO|platform/data/minio/values.yaml:67|`|| true` tolera cualquier fallo de rm, no solo "sin reglas"
AMARILLO|tareas/U01-T02-ilm-idempotente.md:Notas|la nota «sin shell» es falsa: Job = /bin/sh /config/custom-command
INFORME: revisiones/U01-T02/ronda-1.md
