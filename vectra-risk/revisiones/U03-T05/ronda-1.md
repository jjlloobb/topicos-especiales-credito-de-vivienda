# Ronda 1 — U03-T05

VEREDICTO: NO-VERDE

No hay ningún ROJO atribuible al codificador. Dos cosas impiden el VERDE:
- **CA-11 no se cumple en su mitad de U1.** `make -C platform check` sale con 2 por el presupuesto de memoria de kind. Es la detención que la propia tarea prevé, así que no es un ROJO del codificador, pero un CA que no pasa no permite el VERDE. La decisión es del usuario.
- **Hay un NARANJA en pie (F-01).**

Con RL-2 (solo un ROJO bloquea), la decisión de fusionar es del orquestador. Yo no suavizo el veredicto.

## Criterios de aceptación, verificados por mí
Worktree en `ad868d4`, limpio antes y después. Tarea con blob `ce810fc…`, que coincide.

| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Chart y conftest | `make -C decision-registry policy-chart && uv run pytest decision-registry/tests/unit/test_chart.py -v -rs` | pasa: conftest da 1260/1260 y 9/9; pytest da 136 passed en 28 s, ninguna omitida. Están todas las mutaciones mínimas que pide el CA: HPA 1/7, CPU 80, sin spread o con spread por hostname, sin PDB, `vectra-high`, recursos, DSN con clave, ServiceMonitor en `http`, migración sin hook / con otra SA / sin workload / con 900 s / con `vectra-high`, Jobs rebuild/reset/x06-probe, Secret y ExternalSecret. `test_todas_las_reglas_…` está en verde |
| 2 | Render por entorno | `integration.py --env {kind,staging,prod} --out <scratchpad>` y `grep -c` | pasa en sustancia: tres archivos `decision-registry-<env>.yaml` y un solo documento `Deployment` en cada uno (lo leí con yaml). El HPA de kind tiene 2/6. El `grep -c "kind: Deployment"` literal da **2**, porque cuenta también `scaleTargetRef` (F-02) |
| 3 | Admisión U1 ×3 | `make -C decision-registry policy-chart-u1` (dentro de `check`) | pasa: en kind, staging y prod, Kyverno da `pass: 26, fail: 0`, rego 98/98 y `hpa` 3/3 |
| 4 | Flujos | `network/generate.py --check`, `pytest platform/network/tests`, bucle de IDs y grep de F60 | pasa: rc 0, 211 passed, ningún «falta». F60 aparece en la línea 221 con `port: 8081` |
| 5 | ServiceMonitor | `helm template … \| uv run python …` (no hay `yq`) | pasa: `metrics`, que en el Service es 8081 → `targetPort: metrics` y en el contenedor `containerPort: 8081` |
| 6 | Application | `generate.py --check`, `test_waves.py`, `kyverno apply` ×3, `kyverno test`, grep `sync-wave` | pasa en sustancia: rc 0, waves en orden, `pass: 1, fail: 0` ×3, 81/81 y `sync-wave: '5'` ×3. No hay `automated` ni `decision-registry-rebuild.yaml`. El paso literal `git ls-files --others … \| grep` da **rc=1**, porque los archivos ya están commiteados; `git ls-files` sí los lista (F-02) |
| 7 | Sin rebuild/x06 y con hook | el grep del CA sobre mis renders | pasa: no sale ningún Job prohibido. Por entorno salen **dos** líneas `argocd.argoproj.io/hook`, `Sync` y `hook-delete-policy`, las dos del Job `registry-migration` (F-02) |
| 8 | Cobertura | target `coverage`, dentro de `make -C decision-registry check` | pasa: 669 passed en 454 s, ninguna omitida. Total 95,93 %. `chain`, `verify` y `append` en 100 % (481/0, 146/0). El informe solo muestra módulos de `vectra_registry` |
| 9 | Trazabilidad | las tres órdenes del CA | pasa: 41 identificadores, rc 0; `test_traceability_cli.py` 6 passed; `--all` rc 0. La lista tiene 11 filas, cada una con paso y cita, y ninguna de los Pasos 13, 15 o 16. Ver F-01 y F-04 |
| 10 | BR-U3 → prueba | el bucle `git grep` | pasa: no imprime ninguna línea |
| 11a | `make -C decision-registry check` | el mismo | pasa, EXIT=0, en 7 min 43 s: ruff, mypy, import-linter, coverage, policy-chart, policy-chart-u1 ×3 y trazabilidad |
| 11b | `make -C platform check` | el mismo | **EXIT=2**: `test_kind_profile.py::test_the_profile_requests_fit_the_budget`, `assert 6.01171875 <= 5.5`. Las otras 788 pasan. Corrí a mano el resto de `check-local` (helm lint, trazabilidad, runbooks, waves, links) y todo `check-tools`; todo pasa (Kyverno de integración `pass: 335, fail: 0`). Es la detención prevista; ver abajo |
| 12 | Estado del plan | `git diff origin/main -- <plan>` (`origin/main`=`9352400`) | pasa en sustancia: 13, 15 y 16 en `[x] (U03-T05, acotado a la demo)`; 14 y 17 en `[ ]` con la nota de diferido. Solo cambian esas 5 líneas. El grep literal del CA no casa las líneas `[x]`, porque el texto «(U03-T05…)» queda entre `]` y `**Paso` (F-02) |
| 13 | Imagen | `make -C decision-registry image`, `--help`, `inspect`, `OK-runtime` y grep de `FROM` | pasa: el build da rc 0 (todo en caché, mismo ID `36fabc35…`, así que el contenido coincide con el árbol actual). `--help` lista `verify`, `archive` y `aggregator`. Usuario `65532:65532`. Sale `OK-runtime`. Los 2 `FROM` están fijados por digest. Además, con `--read-only`: importa `service`, `alembic` y `psycopg` (binary), no hay pytest, hypothesis ni hatch, y están `alembic` y `vectra-registry` |

## Detención (CA-11b): presupuesto de kind
Con la entrada de `decision-registry` el perfil pide **6,012 GiB**; sin ella pedía 5,473. El tope es `BUDGET_GIB = 5.5`. El codificador no tocó el tope ni el perfil, como manda la tarea, y dejó en la bitácora las cifras y 4 opciones. Las comprobé: según su cuenta, solo subir el tope (por ejemplo a 6,1) deja pasar la prueba. Decide el usuario.

## Hallazgos
### F-01 · NARANJA · `decision-registry/tests/unit/test_chart.py:400` · NFR-U3-41 queda trazado con una mención que no lo prueba
NFR-U3-41 (`nfr-requirements.md:68`) es el egress a la bóveda (F99), y su prueba es que la solicitud de firma lleve solo `{checkpoint_seq, checkpoint_hash, recorded_at}`. La única mención en el código es el docstring de `test_los_pods_llevan_las_etiquetas_que_espera_flows_yaml`. Esa prueba comprueba etiquetas y SA del servicio, del agregador y de la migración, y ninguno de los tres habla con la bóveda. Además, `grep -rn F99 decision-registry/tests` no devuelve nada.

La herramienta da el identificador por trazado por un grep, así que CA-9 pasa sin evidencia real. Hay dos salidas:
- trazarlo en una prueba que de verdad compruebe F99 contra `flows.yaml` y dejar la parte del payload a la lista;
- llevarlo entero a «Diferido por la demo» (Paso 11 `checkpoint`, T5) y quitar la mención.

### F-02 · AMARILLO · CA-2, CA-6, CA-7 y CA-12 · la redacción de los CA no casa con el estado commiteado (barrido de clase)
Hay cuatro órdenes literales cuya salida no es la que el CA espera, aunque la lectura de vuelta confirma lo que piden:
- CA-2: `grep -c` da 2, por el HPA.
- CA-6: `ls-files --others` da rc=1 después del commit, y eso rompe la cadena `&&`.
- CA-7: salen dos líneas de hook.
- CA-12: el regex no casa `[x] (U03-T05…)`.

Es un defecto de la especificación, no del codificador; tres de los cuatro ya están en `CANDIDATAS.md`, y falta la de CA-6.

### F-03 · AMARILLO · `platform/tests/test_platform.py:285` · se edita un archivo de U1 que la tarea no nombra
Se agrega `decision-registry` a `EXPECTED_WAVES[5]`. Sin ese cambio, la entrada de `components.yaml`, que sí está en alcance, rompe `make -C platform check`. Es la consecuencia mecánica de esa entrada y está declarada en la bitácora, así que no lo cuento como desborde. Lo dejo anotado.

### F-04 · AMARILLO · `evidence/cierre-demo.md:7` y `test_traceability.py` (`deferred_rows`) · la lista promete más de lo que la herramienta comprueba
- El texto dice: «Un identificador de esta lista no puede tener código ni prueba: si los tiene, la prueba falla». No se cumple para BR-U3-08 y BR-U3-13b: tienen menciones en las pruebas (`test_cli.py:1`, `test_integrity_api.py:31`) y la comprobación no salta, porque `wanted` no incluye las BR-U3.
- `deferred_rows` acepta cualquier identificador con forma válida, aunque no sea de la unidad. Una fila con una errata pasa sin aviso.

### F-05 · AMARILLO · `tests/unit/test_service.py` (`test_build_app_…`) · la aserción siempre es verdadera
`assert app.title or app.routes` no distingue una app vacía de una armada. La prueba solo existe para la cobertura.

### F-06 · AMARILLO · `chart/values.yaml` (`keycloak.caConfigMap`) · en staging y prod, la CA montada no es la del emisor
Los tres entornos montan `vectra-internal-ca`, pero en staging y prod el emisor es `banco-ca`. Ahí el pod no arrancaría. El codificador lo dejó en `CANDIDATAS.md` para el Bloque H.

### F-07 · AMARILLO · `chart/templates/service.yaml` y `servicemonitor.yaml` · literales fijos en la plantilla
Periodos y umbrales de las sondas, `interval: 30s`, `runAsUser: 65532`, `rollingUpdate` y `sizeLimit: 1Mi` están en la plantilla, sin values ni cita. No son visibles para el usuario. Es la misma clase que el F-06 de U03-T04.

### F-08 · AMARILLO · `decision-registry/Dockerfile:14` · la imagen no se instala desde `uv.lock`
`pip install` solo respeta los `==` de cada pyproject. Las dependencias transitivas quedan libres, así que la imagen puede divergir del entorno con el que se probó.

Nota sin hallazgo: el único cambio en `src/` es `verify.sample_segments`, que quita una rama inalcanzable. `sorted(set(...))` garantiza valores distintos y crecientes, y las pruebas de `verify` y las de propiedad siguen en verde.

## Tareas candidatas (defectos reales fuera de alcance)
- Decidir `BUDGET_GIB` y el perfil DD-3 (es la detención de CA-11b).
- Corregir los comandos de CA-2, CA-6, CA-7 y CA-12 en la plantilla de tareas, contando `^kind:` y usando `git ls-files` sin `--others` sobre el árbol commiteado.
- Que `test_traceability.py` vea las BR-U3 y valide que los identificadores de la lista sean de la unidad (F-04).
- `keycloak.caConfigMap` por entorno, con `banco-ca` (F-06).
- Construir la imagen desde `uv.lock` (`uv export --frozen` o `uv sync --no-dev`) (F-08).

## Rutas de transcripciones largas
Las cuatro están en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/5282962e-b894-499b-8246-ba5c297470a1/scratchpad/`:
- `u3-check.log`
- `platform-check.log`
- `platform-rest.log`
- `ca1.log`

Los renders de CA-2 están en la misma carpeta, en `u3-kind/`, `u3-staging/` y `u3-prod/`.

No escribí `revisiones/U03-T05/ronda-1.md`: soy de solo lectura. El orquestador puede guardar este texto en esa ruta.

```
VEREDICTO: NO-VERDE
NARANJA|decision-registry/tests/unit/test_chart.py:400|NFR-U3-41 queda trazado con una mención que no lo prueba (sin prueba de F99 ni del payload a la bóveda)
INFORME: revisiones/U03-T05/ronda-1.md
```
