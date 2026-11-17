# U12-T09 — Arbitraje de la ronda 2 (orquestador, 2026-11-17)

Informe: `ronda-2.md`. NO-VERDE con **un ROJO** (G-01) y tres AMARILLO. Todo lo demás de la tarea quedó cerrado: F-01 a F-06, M-01 a M-03 y CA-1 a CA-5.

**Decisión: ronda 3, acotada. Es una excepción a RL-2 (máximo dos rondas) que el usuario autorizó el 2026-11-17**, con la opción 1 de las tres que se le presentaron. No se endurece el filtro de shell: se deja de ejecutar texto de documentos.

| Hallazgo | Decisión | Qué se pide |
|---|---|---|
| G-01 ROJO: la comprobación previa de `tests/doubles/safe_shell.py` se burla y el `PATH` aislado se escapa | Ronda 3 | **Ninguna prueba ejecuta texto extraído de un documento** (guía, README, runbook). Las pruebas de la guía comprueban el texto sin lanzarlo: análisis estático de las órdenes, de su orden y de sus argumentos. La única ejecución que queda es la de la función `vv`, y su cuerpo **no se extrae del documento**: vive como definición fija en el repositorio (un archivo de `tests/` o del propio código), corre con un `docker` falso, un `PATH` de un solo directorio sin `env`, `bash` ni `sh` enlazados, y `env` armado desde cero; una prueba aparte compara, como texto, que la guía trae esa misma definición. `safe_shell.py` se borra o se reduce a ese único uso; si queda, no acepta texto arbitrario. Los nueve textos adversos de la tabla del revisor no deben tener ningún camino por el que ejecutarse: dilo en la respuesta, sitio por sitio |
| G-03 AMARILLO: `helm` fuera de los centinelas; `tests/integration` sin guarda | Ronda 3, solo `helm` | Añade `helm` a `TOOLS` en `tests/unit/conftest.py`. La guarda de `tests/integration` queda como candidata |
| G-04 AMARILLO: falta un dato medido en la guía | Ronda 3 | En F0 paso 9 de `docs/paso-18-kind.md` y en «Red» del README: medido por el orquestador el 2026-11-16, con `--network host` el contenedor usa el `/etc/hosts` de la máquina; `humo login` pasó 5 de 5 con la línea `<dirección> vectra.localtest.me` en `/etc/hosts` y sin `--add-host`. Lo demás sigue como «no medido». No cambies el comportamiento de `vv` |
| G-02 AMARILLO: `test_f07_a_megabyte…` inestable con carga | Candidata | Anterior a la tarea. A `CANDIDATAS.md`, al final |

También a `CANDIDATAS.md`, al final: la orden `mc` de `reference-model/docs/release.md` y de `model-serving/docs/paso-11-kind.md` necesita `--tmpfs /tmp` y `--config-dir /tmp/mc` (medido por el orquestador).

**Antes de empezar:** fusiona `origin/main` en la rama (entraron U01-T17 y la preparación de U04-T12). `CANDIDATAS.md` solo crece al final: primero las entradas de `main`, después las de esta rama.

**Fuera de la ronda 3:** todo lo cerrado en la ronda 2. No se reabre.
