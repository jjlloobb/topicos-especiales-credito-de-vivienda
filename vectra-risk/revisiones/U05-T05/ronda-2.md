# Ronda 2 — U05-T05

VEREDICTO: NO-VERDE

Rama `tarea/U05-T05` en `7fa9ce2`: `c6ccfee` (ronda 2 del codificador) más el merge de `origin/main` (`bc8158a`). Base de la evidencia: `bb86d71`. El worktree estaba limpio antes y después (`git status --short` vacío). Este informe es el único archivo nuevo y no tiene commit. Mis releases y archivos temporales estaban en `scratchpad/rev-r2/` y los borré al terminar.

## Criterios verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1a | Tabla de ids main → rama | `python -m vectra_reference.release --out …` sobre `git archive bb86d71` y sobre la rama | pasa. main: base `51241dc4` (4.6119 pp), proxy `7241d354, fa147805, d2baab53, 2a799484, ea69c19d` (11.6579 pp). Rama: base `8a98ab02` (4.61 pp), proxy `f12bfeaf, bed07b8f, c8d04261, eb22dae6, 253e325d` (25.41 pp). Coinciden con la tabla |
| 1b | Archivos fuera de `proxy/`: 26 cambian y 14 idénticos | `sha256sum` de cada árbol, `join` por ruta | pasa. 40 por lado, 26 cambian y 14 iguales con los prefijos citados. Mis SHA de esos 40 coinciden byte a byte con `sha-main.txt` y `sha-head.txt` del codificador |
| 1c | Dentro de `proxy/`: «los 5 idénticos son los `predictor.json`» | el mismo `join` en `proxy/` | **falla** (F-01) |
| 2 | F-02 | lectura de `cierre-demo.md` y `CANDIDATAS.md`; regeneré `u5_counts.json` desde `git archive 0da820f` (con un `git` falso que solo devuelve el sha) y comparé con `diff` | pasa. «Pendiente de U9» ya no está. La candidata de U9 queda solo con `DSTAR_T`. El `u5_counts.json` regenerado es **idéntico** al de la rama. `0da820f` contiene `a870276`, y entre `72c84d6` y `0da820f` solo cambian revisiones |
| 3a | El merge no perdió nada de `CANDIDATAS.md` | cada línea de `c6ccfee` y de `bc8158a` buscada en el resultado | pasa. Están las 9 entradas de U6. Las 3 líneas de main que «faltan» son las que la rama marcó «Resuelta (U05-T05)», y main no las tocó (`git diff bb86d71 bc8158a` solo añade). No quedan marcas de conflicto |
| 3b | `uv lock --check` | `uv lock --check` | pasa (rc 0) |
| 3c | `test_predictor.py` de U6 con el id base nuevo | `uv run pytest model-serving/tests/integration/test_predictor.py -v` | pasa: 7 passed en 56,7 s, ninguno saltado. La ruta acepta cualquier `{model_name}` y la versión se lee del manifiesto |
| 3d | U6 y governance | `make -C model-serving check`, `make -C governance check` | pasa: rc 0 (36 passed, 82 s) y rc 0 (258 passed, 153 s) |
| 4 | Checks de la tarea | `make -C reference-model check`, `make -C bias-monitoring check`, `make -C platform check` | pasa. reference-model: 141 passed y 2 deselected, cobertura 92,93 %. bias-monitoring: 34, 43 (100 %) y 6 passed. platform: pass 335, fail 0 |
| 4b | `--all` (§6 con la enmienda) | `python3 platform/tests/test_traceability.py --all` en la rama y en `git archive origin/main` | pasa. rc 1 en los dos lados con **el mismo** conjunto de fallos (`diff` vacío). Son 18 de U4, 14 de U6 y 23 de U9, unidades sin `cierre-demo.md`. reference-model tiene 11 ids trazados |

Sobre los tiempos: las 34 pruebas unitarias de bias-monitoring tardan 0,12 s porque solo leen el doble JSON y no dependen de estado externo. Las suites que construyen la entrega de U5 tardan minutos.

## Hallazgos
### F-01 · ROJO · `cierre-demo.md:70` y `bitacoras/U05-T05.md:109` · La lista de archivos idénticos de `proxy/` está invertida
El arbitraje (punto 1) pide la lista de archivos que cambian y de los que quedan idénticos byte a byte, contra `bb86d71`. Los dos documentos dicen: «En `proxy/` cambian 30 de 35 archivos; los 5 idénticos son los `predictor.json`». Mi comparación da otra cosa:
```
./proxy/run-1/background.csv   ebaf69990677 == ebaf69990677  IGUAL
./proxy/run-1/predictor.json   602cefc5af19 -> 893958609caa  cambia
```
Lo mismo pasa en run-1 a run-5. Los idénticos son los 5 `background.csv` (`ebaf6999…`). Los `predictor.json` cambian (`602cefc5…` pasa a `893958609…`), cosa obligada porque la variante más fuerte se reentrenó: es el objeto mismo de la tarea. Los propios `out-main/` y `out-head/` del codificador en `scratchpad/r2/` dan el mismo resultado. Sus `sha-*.txt` solo cubren los 40 archivos fuera de `proxy/`, así que esa frase no salió de ninguna medición. Es evidencia falsa en el punto central de esta ronda, de la misma clase que F-01 de la ronda 1. Corrección: «cambian 30 de 35; los 5 idénticos son los `background.csv` (`ebaf6999…`); los `predictor.json` cambian (`602cefc5…` → `893958609…`)», en los dos archivos.

### F-02 · NARANJA · `cierre-demo.md:73` y `bitacoras/U05-T05.md` («U6: … no existe en esta rama») · Evidencia que el merge dejó desactualizada
Las dos afirmaciones eran ciertas en `c6ccfee` (`git cat-file -e c6ccfee:…/test_predictor.py` falla). Después del merge `7fa9ce2` dejaron de serlo:
- «`model-serving/tests/integration/test_predictor.py` (U6) no existe en esta rama»: ahora existe.
- «El resto del repositorio ya no las cita»: `model-serving/tests/integration/test_predictor.py:18` tiene `URL = "/v1/models/isvc-51241dc4:predict"`.

El punto 2 del arbitraje pedía correr esa prueba y registrar el resultado. Ese registro no está. Hay que registrar 7 passed (corrida mía, arriba) y la decisión de no tocar la URL: la prueba pasa porque la ruta ignora `model_name`, y `model-serving/` está fuera del alcance de la tarea. Esto vale para el documento que se va a fusionar.

### F-03 · AMARILLO · `cierre-demo.md:70-71` · Los SHA-256 de los archivos que cambian solo están en el scratchpad
El arbitraje pide el SHA-256 «de cada lado». Para los archivos idénticos el documento da prefijos. Para los 26 que cambian remite a `sha-main.txt` y `sha-head.txt` del scratchpad, que es efímero. Conviene incluir al menos los prefijos de `package/manifest.json` y `adversarial/manifest.json` en los dos lados.

## Tareas candidatas (defectos reales fuera de alcance)
- U6, `test_predictor.py:18`: la URL `isvc-51241dc4` nombra el id base viejo. Funciona porque la ruta ignora `{model_name}`, pero es un literal engañoso. Conviene derivarla de `version_of(package_dir)` o usar un nombre neutro.

## Rutas de transcripciones largas
Transcripciones del codificador que usé para contrastar: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/r2/` (`sha-*.txt`, `out-main/`, `out-head/`). Las mías estaban en `scratchpad/rev-r2/` y las borré como pidió el orquestador. Las cifras clave están copiadas arriba.
