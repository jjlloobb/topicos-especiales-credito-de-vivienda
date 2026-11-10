# Ronda 1 — U04-T07

VEREDICTO: NO-VERDE

Todavía no se puede fusionar. Todos los comandos de CA pasan cuando los corro yo, CA-5 incluido. Pero el cliente que va dentro del pod pierde el cuerpo JSON de cada llamada que lo lleva. Así, el runbook «ejecutable tal cual» y los escenarios 2, 3, 4 y 7 fallarían en el primer intento del operador.

Revisé el sha 9964785541c8825fee0ada53553d19dda1501fec contra origin/main (ec08f84). El hash de la tarea coincide (00e9bb7b). No corrí nada contra un clúster (AUTONOMIA-01). Al terminar, el worktree está limpio (`git status --short` vacío).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Guía completa | `test -s governance/docs/paso-20-kind.md`; `grep -nE "^## " …` | pasa: 9 secciones, 9 líneas `Evidencia:` |
| 2 | Scripts | `uvx --from shellcheck-py shellcheck governance/docs/kind/*.sh` (0.11.0); `uv run pytest governance/tests/unit/test_kind_scripts.py -v`; `! grep -rnE "kubectl apply\|helm (install\|upgrade)\|argocd app sync" governance/docs/kind/` | pasa: rc 0, 18 pruebas pasan, grep sin coincidencias. La prueba es insuficiente (F-01) |
| 3 | Frontend N/A | `test ! -d governance/frontend` | pasa |
| 4 | Cierre | `make -C governance check` (4m22s); `uv run python platform/tests/test_traceability.py --unit governance --all`; `grep -n "^## " cierre-demo.md` | pasa: rc 0, 585 pruebas pasan, cobertura 97,30 %, 100 % en fsm/policy/evidence. Kyverno da `pass: 19, fail: 0` ×3 y el runbook `pass: 8, fail: 0`. Trazabilidad «34 identificadores», rc 0. Están las 3 secciones |
| 5 | `make -C platform check` | Instalé las herramientas con `platform/install-tools.sh` (rc 0, todos los SHA-256 OK: kubeconform, egctl y k6 incluidos) y luego corrí `make -C platform check` | **pasa**: rc 0 en 5m27s. 802 pruebas pasan, `kyverno test` da 81 de 81, actionlint corre y check-integration da `pass: 354, fail: 0` |
| 6 | Evidencia del operador | Lectura de `evidence/kind/01..09` | sigue pendiente del operador, como permite la tarea. No es un fallo |
| 7 | CA-7 | `make -C governance policy-runbook`; `uv run pytest governance/tests/unit/test_kind_runbook.py -v`; `RUNBOOK=<runbook de origin/main> uv run pytest …` | pasa: `pass: 8, fail: 0`, 15 pruebas pasan, y el runbook anterior sale rojo (2 failed) |

Sobre CA-5: `install-tools.sh` escribió en `platform/.tools/bin` del árbol principal. Es un directorio ignorado por git, y el `platform/.tools` del worktree es un enlace hacia él. Ningún archivo fuente cambió.

## Hallazgos

### F-01 · ROJO · governance/docs/kind/llamar.sh:36-37 y medir-freeze.sh:24,50 · El cliente del pod pierde el cuerpo: stdin se lee con `readline()` y después con `buffer.read()`
- **Causa.** `sys.stdin.readline()` llena el búfer de texto de `TextIOWrapper` con todo lo que ya llegó. Por eso `sys.stdin.buffer.read()` devuelve `b''` cuando el token y el cuerpo llegan juntos. Es el caso normal: kubectl se conecta cuando el pod ya arrancó y la tubería ya tiene las dos líneas.
- **Reproducción.** Usé el cliente exacto de `llamar.sh`, cambiando solo el host por un servidor de prueba en 127.0.0.1. Lo corrí en local y en `python:3.12-slim`:
  ```
  printf 'tok-abc\n{"cutoff":"0.5000"}\n' | python3 -I cliente.py POST /v1/policies
  200 len=0 body=b'' auth=Bearer tok-abc
  ```
  El control funciona: con 0,3 s de pausa entre las dos líneas el cuerpo sí llega. Transcripción en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/repro/`.
- **Alcance, barrido completo.** Fallan todas las llamadas que llevan cuerpo:
  - runbook, paso 2 (`POST /v1/policies`, el `POLICY_ID` saldría vacío) y paso 3 (approval);
  - guía, §5.1 (`POST /v1/models`), §5.3 (approval del modelo), §6 (registro de M2) y §7 (`frozen-resolution`);
  - `medir-freeze.sh`: el `freeze` va vacío, así que no hay cambio de etag y el resultado sería `maximo=999`.
- **Consecuencia.** El runbook no es «ejecutable tal cual», y el arranque P-7 y los escenarios 2, 3, 4 y 7 no pueden pasar.
- **Por qué pasan las pruebas.** `test_kind_scripts.py` nunca ejecuta el Python incrustado: el `kubectl` de prueba solo registra stdin. Hace falta una prueba que corra el cliente con el token y el cuerpo en una sola escritura y compruebe el cuerpo recibido. Arreglo posible: leer todo de `sys.stdin.buffer` y separar por la primera `\n`.

### F-02 · NARANJA · governance/Makefile, objetivos `policy-runbook` y `shellcheck` · Se saltan en silencio con rc 0 y atribuyen la verificación a un CI que no existe
- `env PATH=/usr/bin:/bin make -C governance policy-runbook shellcheck` imprime «se omite … (lo corre el CI)» y termina con **RC=0**.
- Ningún workflow de `.github/workflows/` corre `make -C governance check`. `tests.yml` solo corre pytest, y `policies.yml` corre solo `make -C platform`.
- Resultado: `check` puede quedar verde sin haber verificado CA-7 ni shellcheck. Va contra la regla del propio repo (`platform/Makefile`: «nunca parece aprobado lo que no se ejecuto»). Deberían fallar si falta la herramienta.

### F-03 · AMARILLO · test_kind_runbook.py:23 · El detector no ve un nombre corto sin namespace
Le añadí al runbook un bloque `python3 - <<EOF … http://governance-service:8080/v1/policies` y `test_el_runbook_no_tiene_problemas` siguió pasando.

### F-04 · AMARILLO · medir-freeze.sh:72 · Carrera en la espera fija de 3 s (`ESPERA_SONDAS`)
Cada sonda espera a que `token.sh` termine (`uv run`, inicio de sesión de servicio). Si tarda más de 3 s, la sonda lee el etag inicial después del freeze y el escenario da un falso fallo. Esperar las líneas `listo` resolvería la carrera.

### F-05 · AMARILLO · freeze-cuerpo.sh:17-21 · Fechas de ventana incrustadas
Usa 2026-11-01..08 y window_start 2026-10-10 fijos, mientras `computed_at` es la hora actual. Con el tiempo se separarán.

### F-06 · AMARILLO · CANDIDATAS.md y cierre-demo.md · NFR-U4-02 figura como «trazado por la guía», pero la guía solo lo nombra
Está en la línea 245 de la guía, de pasada. No hay ningún paso que lo ejerza. El cierre sí lo deja como «Pendiente de U7»; es la redacción de la candidata la que exagera.

### F-07 · AMARILLO · test_kind_scripts.py:87 · Ternario con dos ramas idénticas
`forbidden = {...} if … else {...}` tiene la misma rama a los dos lados, así que la condición sobra.

Revisé también estos puntos y están bien:
- **Alcance:** el diff solo toca `governance/`, `aidlc-docs/`, `bitacoras/` y `CANDIDATAS.md`, sin código del servicio.
- **Contratos:** el diff coincide con el OpenAPI en `PolicyDecisionIn` (`aprobada`), `ModelApprovalIn` (`aprobado`), `FrozenResolutionIn` (`reactivar`), `ValidationRun.job_name`, `validation_report.initial_disparity.attributes` y `sync_check.passed`.
- **Malla:** las rutas de malla `console` para console-bff cubren `/v1/models*` y `/v1/policies`.
- **CLI y S3:** coinciden la CLI de `promotion-tool` y la convención `s3://model-store/<mv>/<archivo>` de `s3_store.py` y `release.md`.
- **Vigencia normativa:** `reference-policy.json` es vigente desde 2026-01-01 sin fecha de fin, así que cubre la fecha de la demo.
- **Plan:** Paso 20 en `[ ]` con la nota, y Pasos 21 y 22 en `[x]`.
- **Evidencia de la bitácora:** es coherente con lo que obtuve yo (585 pruebas que pasan, `pass: 8`).

## Tareas candidatas (defectos reales fuera de alcance)
- U1: ningún workflow corre los `make -C <unidad> check`. Los objetivos de unidad que dicen «lo corre el CI» no tienen respaldo.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/gov-check.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/platform-check.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/install.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/repro/ (cliente.py, stub.py)

```
VEREDICTO: NO-VERDE
ROJO|governance/docs/kind/llamar.sh:36-37, medir-freeze.sh:24,50|El cliente del pod pierde el cuerpo (readline + buffer.read): propuesta, aprobaciones, registro, freeze y reactivación salen vacíos
NARANJA|governance/Makefile:policy-runbook, shellcheck|Se saltan con rc 0 sin la herramienta y atribuyen la verificación a un CI que no los corre
INFORME: revisiones/U04-T07/ronda-1.md
```
