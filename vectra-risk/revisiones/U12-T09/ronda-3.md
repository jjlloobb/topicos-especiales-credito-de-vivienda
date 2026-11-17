# Ronda 3 — U12-T09

VEREDICTO: VERDE

G-01 queda cerrado: ya ninguna prueba ejecuta texto extraído de la guía, del README ni de un runbook. Lo único que se ejecuta es una definición fija de `vv`, y ninguno de los textos adversos encuentra un camino para lanzarse. G-03 y G-04 también están cerrados. La fusión de `main` no perdió ninguna entrada. `check-fast` pasa entero y, a diferencia de la ronda 2, `test_f07_a_megabyte…` no falló.

Queda un AMARILLO de esta ronda (una frase contradictoria en la guía) y dos sitios anteriores a la tarea, de la misma clase que R-01, que propongo como candidatas.

Todo lo corrí con `PATH` sin `/snap/bin` y `KUBECONFIG=/nonexistent`, sobre el sha `aedf69f`. Antes de correr la suite leí qué ejecutan `vv_runner.py` y el `conftest.py` cambiado.

## Criterios de aceptación, verificados por mí
| # | Comando | Resultado |
|---|---|---|
| CA-1 | `-k "transient or transitorio"` | pasa, 18 passed. `--collect-only` da 18: 2 de `test_cli` y 16 de `test_transient_reads` (incluidos los 5 4xx nuevos) |
| CA-2 | `-k "resend or reenvi"` | pasa, 18 passed. Son 15 de `test_resend` más 3 pruebas viejas que el filtro arrastra por la palabra «resend» (rt2 y simulador) |
| CA-3 | `-k sincronizacion` | pasa, 6 passed. 5 de U12-T09 más una vieja de `test_kind_guide` |
| CA-4 y CA-5 | dentro de `check-fast` | pasan, incluido shellcheck. Los grep de CA-5 dan rc 0: 3 apariciones de RT3-c y ninguna frase falsa |
| CA-6 | `make -C system-verification check-fast` (una vez) | rc 0. ruff, mypy y 11 contratos en verde. Etapa 1: 1340 passed, cobertura 95,86 %, y los tres archivos de Testcontainers pasan. Etapa 2: 1067 passed, 100 %. 672 Markdown sin enlaces rotos y 22 identificadores |
| — | `test_links.py`, `test_traceability.py --all` | rc 0 y rc 0 |

**Bitácora de la ronda 3.** Las cifras coinciden: 18, 18 y 6; 1340 y 1067; 672; trazabilidad rc 0. La única diferencia es la cobertura de la etapa 1: yo obtuve 95,86 % y la bitácora dice 95,84 %. Es irrelevante.

## Estado de G-01 a G-04
### G-01 · cerrado
- **Todos los lanzamientos de procesos en `tests/`.** De dónde sale el texto que ejecutan:
  - `vv_runner.py:80`: `bash` por ruta absoluta con `VV_DEFINITION` (fija) y una cola de `TAILS` (fija).
  - `test_kind_scripts` (`.sh` del repositorio con dobles), `test_demos_closed_world` (`verify/*.sh`), `test_oracles_rt2_rt3_rt5:481` (`registro-cuerpo.sh`) y `test_prepared_prs` (`git`, más `helm` y `conftest` por ruta) ejecutan guiones del repositorio, no texto recortado de un documento. Los cuatro corren bajo la guarda de `tests/unit/conftest.py`.
  - `integration/conftest.py` llama a `docker ps` (Testcontainers).
  - `test_cli.py:171` usa `python -c` con código de la propia prueba y `PATH=""`.
  - `test_cli.py:1185` corre `journey-7-3.sh 4` con `PATH=/usr/bin:/bin`; el paso 4 solo lee el manifiesto.
  - `test_image.py` corre en la imagen con `docker` (solo en `check`).
  - Dos sitios sí ejecutan texto recortado de un archivo del repositorio que no es la guía: ver H-02.
- **`vv_runner.py`.** La definición es fija, `run_vv` solo acepta una clave de `TAILS` y una lista cerrada de 7 variables, el `PATH` es de un solo directorio (`id` real, `docker` falso y centinelas `kubectl`, `argocd`, `helm` y `gh`), no hay `env`, `bash` ni `sh` enlazados, y el entorno se arma desde cero.
- **Textos adversos, probados contra una copia del módulo con `subprocess.run` espiado y binarios inocuos:**
  - Mis 9 textos de la ronda 2, reescritos con `/usr/bin/uname`, y además `"report "`, `"Report"`, `"report\n/usr/bin/uname"`, `"vv report; /usr/bin/uname -s"` y `"three\n"`: los 14 se rechazan con `NotAFixedCase`, con 0 llamadas a `subprocess` y sin crear siquiera el directorio del `PATH`.
  - Pasar `BASH_ENV`, `PATH` o `KUBECONFIG` en el entorno también se rechaza.
  - Valores con `;` o `$(…)` en `VERIFICATION_IMAGE` y `GATEWAY_ADDRESS` corren como texto literal: llegan tal cual al `docker` falso y no se ejecutan.
- **Mutaciones de la guía**, hechas con un plugin que cambia `GUIDE_TEXT`; las cinco mueren:

| Mutación | Pruebas que fallan |
|---|---|
| `vv` sin `--read-only` | 2 (`test_coherence…` y `test_r01_g01_the_fixed_definition…`) |
| `vv` con `${GATEWAY_ADDRESS:-` | 2 |
| `EVID` sin la guarda | 2 |
| `EVID` en `$PWD` | 1 |
| `EVID` recalculado en cada terminal | 2 |

- `safe_shell.py` ya no existe y nada lo importa (grep vacío; una prueba lo afirma).

### G-02 · candidata (arbitraje)
No falló en esta corrida.

### G-03 · cerrado
`TOOLS` en `tests/unit/conftest.py` incluye `helm`. La guarda de `tests/integration` queda como candidata, según el arbitraje.

### G-04 · cerrado
F0 paso 9 y «Red» del README dicen el dato medido y dejan `--add-host` con `--network host` como no medido. `vv` no cambió. Queda una contradicción en la misma frase: H-01.

## Fusión de `main` (`a5a5fe9`)
- Según `--remerge-diff`, el único conflicto fue en `CANDIDATAS.md`.
- HEAD es exactamente el `CANDIDATAS.md` de `origin/main` (`d79a861`, 861 líneas) seguido de 15 líneas no vacías nuevas al final.
- Comparación línea por línea en Python: 0 líneas perdidas frente a `origin/main` y 0 frente a `040a468`.

## Hallazgos nuevos
### H-01 · AMARILLO · docs/paso-18-kind.md, F0 paso 9 (párrafo de `EVID`) · Una frase contradice el dato medido
El paréntesis «(`vv` se niega a arrancar sin ella: con `--network host` y sin `--add-host`, `vectra.localtest.me` sería `127.0.0.1` y nada responde)» sigue ahí. La frase siguiente dice lo medido: con la línea en `/etc/hosts`, el contenedor la usa y llega al gateway sin `--add-host`. El paréntesis solo es cierto si falta esa línea.

### H-02 · AMARILLO · fuera de alcance, de 2026-11-13 · Dos pruebas ejecutan texto recortado de archivos del repositorio
Es la misma clase que R-01, y ninguno de los dos sitios está en el diff:
- `test_prepared_prs.py:326` corre con `sh -c` una línea recortada de `case-management/Makefile` (la que contiene `! grep -rn "runId"`).
- `test_rt5_job_script.py:22-66` corre con `python -c` un guion recortado de `case-management/chart/templates/rt5-demo-job.yaml`.

Los dos corren con `{**os.environ}` bajo la guarda unitaria: centinelas delante del `PATH` y `KUBECONFIG=/nonexistent`. Hoy esos textos no lanzan herramientas del clúster. Para ser exactos: no son documentos en el sentido del arbitraje (guía, README, runbook), pero si mañana alguien edita la línea del Makefile o el guion del chart, la prueba ejecuta lo que se escriba. Tendría que haberlo señalado en la ronda 2. Lo propongo como candidata, no se exige aquí.

## Tareas candidatas
- H-02: que esas dos pruebas comprueben el texto sin ejecutarlo, o que lo ejecuten en un entorno armado desde cero, como `run_vv`.
- Ya anotadas por el codificador: G-02, la guarda de `tests/integration` y la orden `mc`.

## Estado final
- El worktree quedó limpio (`git status --short` vacío) y HEAD sigue en `aedf69f`.
- Borré las copias `rev-u12t09-*` del scratchpad.
- No toqué el clúster ni construí imágenes; Docker solo a través de Testcontainers.

```
VEREDICTO: VERDE
AMARILLO|docs/paso-18-kind.md F0 paso 9|el paréntesis «sin --add-host sería 127.0.0.1» contradice el dato medido de /etc/hosts
AMARILLO|tests/unit/test_prepared_prs.py:326, tests/unit/test_rt5_job_script.py:22|ejecutan texto recortado de case-management/Makefile y de la plantilla del Job (anterior a la tarea; candidata)
INFORME: revisiones/U12-T09/ronda-3.md
```
