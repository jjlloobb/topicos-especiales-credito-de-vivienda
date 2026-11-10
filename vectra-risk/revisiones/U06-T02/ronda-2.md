# Ronda 2 — U06-T02

VEREDICTO: VERDE

Punta revisada: `458d4ad`. Ronda 1 sobre `edc0b8f`. El worktree quedó limpio antes y después de correr las suites (`git status --short` vacío).
Fuente de KServe: `git clone --depth 1 --branch v0.21.0 kserve/kserve` (`d148255`). Sin ROJO ni NARANJA en pie.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Render por perfil, CRD y políticas | `helm template` ×3 + `kubeconform -strict` con el CRD; `conftest test --policy model-serving/policies/conftest` | pasa: Valid 5/3/3; `330 passed`, exit 0. `command` presente en los 5 contenedores; la anotación `storage-initializer-sourceuri` aparece 0 veces |
| 2 | Esquema y los cuatro PR | `pytest test_promotion_renders.py -v`; `test -s` ×2; `helm template … values-invalid.yaml; test $? -ne 0` | pasa: `14 passed in 14.69s`; archivos presentes; el values inválido se rechaza |
| 5 | Cobertura y trazabilidad | dentro de `make -C model-serving check`, más `test_traceability.py --unit model-serving --all` aparte | pasa: `131 passed` (0 omitidas) en 180 s, `Total coverage: 97.91%`, `package_loader.py … 100%`; `model-serving: 24 identificadores`, exit 0 |
| 6 | `check` de la unidad y de U1 | `make -C model-serving check` (3 min 43 s) y `make -C platform check` (6 min 33 s) | pasa: exit 0 y exit 0 (`789 passed`, `81 tests passed`, conftest `707/336 passed`, kyverno `pass: 335, fail: 0`) |
| — | `--all` (§6 con enmienda) | `test_traceability.py --all` en la rama y en `git archive origin/main` (`c90629a`) | ambos dan rc=1. La rama **no agrega** ningún fallo. Quita los 14 de U6 (INF-U6-01/02, NFR-U6-02/10/11/12/20/21/22/30/31/32, P-U6-02/04). Quedan los de U9 y U4, ajenos a la tarea. Coincide con la bitácora |

## Verificaciones pedidas

1. **F-01, contra v0.21.0.** `CustomExplainer.GetContainer` (`pkg/apis/serving/v1beta1/explainer_custom.go:70-95`) agrega
   `--model_name`, `--predictor_host` y `--http_port 8080` (y `--workers` si hay `containerConcurrency`, que el chart no fija).
   `CustomPredictor.GetContainer` (`predictor_custom.go:95-104`) devuelve el `kserve-container` sin tocar `args`. Con
   `command: ["python","-m","vectra_<c>"]`, los `args` se agregan después del módulo y el `CMD` deja de importar: ya no hay
   `CrashLoopBackOff`. En el predictor el `command` es redundante, pero inofensivo. Ninguno de los dos programas lee `sys.argv`: hice
   `grep environ|getenv|argv` en `common/`, `predictor/` y `explainer/`, y solo aparece `os.environ` en `service.py:51-52`.
   `test_entrypoints.py` (2 PASSED) corre `main()` con los `args` de KServe; si alguien agregara `argparse.parse_args()`, la prueba
   fallaría con `SystemExit`. **Regla y mutaciones:** los 4 casos `explicit-command` pasan (explicador y predictor en prod,
   explicador en inactive, predictor en staging), y `test_todas_las_reglas_de_las_politicas_tienen_caso` también. Además apliqué
   mutaciones mías con `conftest` sobre el render de prod: `command` del explicador cambiado a `vectra_predictor` → `explicit-command`
   FAIL; `command: [python]` con el módulo en `args` → FAIL; `STORAGE_URI` distinta en el explicador → `storage-uri-equal` FAIL;
   explicador sin `STORAGE_URI` → `storage-uri-equal` FAIL ×2. La regla es efectiva.
2. **F-02.** Ya no queda la anotación inerte: 0 apariciones en los tres renders. `source_uri(c)` sale de `env_value(c, "STORAGE_URI")`
   (`inferenceservice.rego:31-32`). La comparación predictor ↔ explicador sigue viva en la segunda regla `storage-uri-equal`.
   `service.py:17` usa `DEFAULT_MODEL_DIR = "/mnt/models"` y el chart fija `MODEL_DIR` = `packageVolume.mountPath` = `/mnt/models`. Eso
   coincide con `DefaultModelLocalMountPath` (`constants.go:522`), y el volumen `kserve-provision-location` coincide con
   `StorageInitializerVolumeName` (`constants.go:213`). **Otros campos que KServe descarte o sobrescriba:** dentro del pod reescribe
   `STORAGE_URI` a `/mnt/models` (`storage_initializer_injector.go:574-579`), algo ya documentado en `docs/values.md:33-36`. No
   duplica el montaje del `kserve-container` ni el volumen: `addVolumeMountToContainer` devuelve `false` si el nombre ya existe
   (`pkg/utils/storage.go:76-82`), así que conserva el `sizeLimit` y el `readOnly` del chart. Del resto de anotaciones de
   componente solo filtra las de `ServiceAnnotationDisallowedList` (`constants.go:548-554`), y ninguna `vectra.io/*` está ahí. El
   Service en modo raw toma `Ports[0]` = `http` 8080 (`service_reconciler.go:118-128`), que es el puerto de inferencia correcto. No
   encontré nada más.
3. **Merge.** `origin/main` (`c90629a`) es ancestro de `HEAD`. Comparé las líneas de `CANDIDATAS.md` con `LC_ALL=C comm`:
   - No falta ninguna línea de `origin/main` en `HEAD`.
   - De las líneas de la rama anterior (`67e7039`) faltan 5. Cuatro son entradas de U4/U5 que ya estaban en la base `bc8158a` y que
     `main` reescribió (está bien que gane `main`). La quinta es la candidata U6 `storageUri`, reescrita a propósito en `3da88f1`
     según F-02.
   - `git diff edc0b8f HEAD` sobre `model-serving`, `vectra-risk-gitops`, `test_platform.py` y el plan muestra cambios solo en los
     5 archivos que tocan F-01 y F-02. No hubo cambios fuera de lo arbitrado.
4. **F-03.** La bitácora (sección «Ronda 2», «F-03 · corrección») describe el pánico con los tres entornos y el `pass: 0` con uno.
   Es fiel a lo que observé en la ronda 1.

## Hallazgos
### F-01 · AMARILLO · `CANDIDATAS.md` · Entradas duplicadas tras agregar las candidatas del revisor
Dos pares de candidatas describen el mismo defecto:
- La credencial `minio-kserve`: la del codificador («Decidir en el Paso 11…») y la del revisor («BLOQUEANTE para U06-T03»).
- `check-chart` con charts de solo CRs: la entrada U1 del codificador y la entrada U1/U6 del revisor.

Conviene fusionar cada par y conservar en la primera la marca de bloqueante, para que U06-T03 no lea dos versiones distintas.

### F-02 · AMARILLO · `inferenceservice.yaml:93`, `inferenceservice.rego:329`, `*/Dockerfile` · El módulo de arranque aparece en tres sitios
`python -m vectra_<componente>` está en el `CMD` de cada imagen, en la plantilla y en la regla. Si se renombra el módulo, hay que
tocar los tres. Las pruebas detectarían un desfase entre la plantilla y la regla, pero no uno entre la plantilla y la imagen. No
bloquea: esos valores no los ve el usuario y la regla los exige a propósito.

## Tareas candidatas (defectos reales fuera de alcance)
- No hay nuevas. Siguen en pie las de la ronda 1, ya registradas en `CANDIDATAS.md`. La credencial S3 de U1 sigue siendo
  **bloqueante para U06-T03**.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/r2-ms-check.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/r2-platform-check.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/trace-branch.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/trace-main.log

VEREDICTO: VERDE
INFORME: revisiones/U06-T02/ronda-2.md
