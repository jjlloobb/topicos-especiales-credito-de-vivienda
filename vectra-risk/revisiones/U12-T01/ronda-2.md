# Ronda 2 — U12-T01

VEREDICTO: VERDE (bajo RL-2: solo ROJO bloquea)

Los cuatro hallazgos que entraron en esta ronda quedaron cerrados: F-01, F-02, F-03 y F-05. No encontré ningún ROJO nuevo.

Encontré cuatro hallazgos NARANJA nuevos (F-06 a F-09), todos fuera de lo que pidió el arbitraje. Por el contrato base del revisor, un NARANJA da NO-VERDE. Aplico RL-2, que el usuario aprobó para la demo («solo ROJO bloqueante»), y el orquestador lo repitió en el encargo, así que los NARANJA van a `CANDIDATAS.md`. Si el orquestador no aplica RL-2 a esta tarea, el veredicto es NO-VERDE por esos cuatro.

Base de la revisión:
- Rama `tarea/U12-T01` @ 6677df3; diff contra 9b18465.
- `git diff 9b18465..HEAD --stat` toca solo lo permitido: `evidence.py`, las 4 pruebas, la bitácora, `revisiones/` y `CANDIDATAS.md`.

## Estado de los hallazgos de la ronda 1
| Hallazgo | Estado | Cómo lo comprobé |
|---|---|---|
| F-01 detector de verbos | **cerrado** | `probe_verbs.py`: las 12 entradas de la ronda 1 dan hallazgo (delete, apply, apply, 3 × `<indirect>`, `--certificate-authority`, `auth --as`, `<expr>`, `<variable>`, `<fstring>`, `<concat>`); `.bash` cubierto por `test_f01_scan_tree_*` |
| F-02 filtro de evidencias | **cerrado** | `probe_ev.py`: en las 9 entradas de la ronda 1, las 6 de cabeceras y campos salen `[REDACTADO]`; PEM escapada, semilla en minúsculas y JWT partido dan `EvidenceError` |
| F-03 PBT-U12-01 | **cerrado** | SM1 a SM4 aplicadas por mí con las semillas 4242, 90210 y 777001: **12 de 12 muertas por PBT**, con los ejemplos fijos deseleccionados (`-k`). SM1 muere por `test_the_seed_changes…`; SM2 por esa misma y `test_normal_is_a_random_draw…`; SM3 por `every_cell…reaches_the_minimum` y `a_short_cell…`; SM4 por `no_repeated_rows…` y `exactly_the_cover_or_the_volume…`. Carga de 3,6 a 13,3 |
| F-05 PBT-U12-04 | **cerrado** | 500 ejemplos de `BATCHES` (ver la sección de generadores) y 2 mutaciones mías con la semilla 6061: `<` por `<=` muere (2 PBT); `max` por `min` muere (3 PBT) |

Medida de los generadores (`gen_stats.py`, 500 ejemplos, semillas 5150 y 8086):
- **sampler:**
  - ejemplos con una celda de 30 filas o más y `min_per_cell` ≥ 10: 10 y 15 (en la ronda 1, 0);
  - ejemplos con celdas llenas y cortas a la vez: 94 y 109 (en la ronda 1, 12);
  - población: p50 de 31 y 32 filas, máximo de 141 y 139.
- **rt2:**
  - p50 de 31 y 7 entradas; p90 = máximo = 2 000;
  - lotes de 1 000 o más: 101 y 105;
  - lotes con empates: 206 y 201; con empate en el mínimo: 195 y 186;
  - la frontera de 1 800 s ±5 µs sigue en `AROUND_LIMIT`, y la mutación `<` la mata.

## Regresión, corrida por mí
| Criterio | Comando | Resultado |
|---|---|---|
| CA-14 | `uptime; time make -C system-verification check` | rc=0. **Semilla 2151315519**. 280 passed, 0 skipped, 0 xfail. 3m35s, carga 3,58 → 6,89 |
| CA-1 | dentro de `check` | import-linter: 3 kept, 0 broken |
| CA-12 | dentro de `check` | report y sampler al 100 % (24 y 20 ramas, 0 parciales); `grep -c pragma` = 0 en los dos |
| lint y tipos | dentro de `check` | ruff OK (29 archivos); mypy: Success en 15 archivos |
| CA-18 | `uv run python platform/tests/test_links.py` | 532 archivos sin enlaces rotos, rc=0 (carga 6,36) |

## Formas nuevas probadas
**F-01, shell (32 formas).** Dan hallazgo:
- `out=$(kubectl delete …)`, `"$(kubectl get && kubectl delete)"`, el here-doc;
- `bash -c "kubectl apply"`, `sh -c '… | kubectl replace'`, `env X=1 kubectl delete`;
- `command kubectl`, `/usr/local/bin/kubectl apply`, `alias k=kubectl`;
- `get -o yaml > f && kubectl replace`, `port-forward … & kubectl delete` (con y sin espacio);
- `$(printf apply)`, `KUBECTL=${KUBECTL:-kubectl}`, `kubectl $v`, `while read; do kubectl delete`;
- `-v=6`, `{ …; kubectl annotate; }`, `kubectl-1.30`, `timeout 30 kubectl delete`;
- `--insecure-skip-tls-verify=true apply`, `proxy`, `debug`, `kubectl\tapply`, `kubectl\\\napply`, `|kubectl apply`.

Pasan sin hallazgo, todos AMARILLO:
- `echo delete pod x | xargs -n3 kubectl` y `echo apply -f x | xargs -r kubectl`;
- `` kubectl `printf apply` -f x ``.

**F-01, YAML y Markdown en `demos/`.**
- Dan hallazgo: el bloque de código y `args: ["kubectl apply"]`.
- Pasa sin hallazgo, AMARILLO: la lista YAML en bloque (`command:` con `- kubectl` y `- apply` en líneas aparte).

**F-01, Python (28 formas).** Dan hallazgo:
- cadenas adyacentes `"kube" "ctl apply"`, `shell=True`, `os.system`, `shlex.split`, `getattr(...)([...])`;
- `["kubectl","auth",verbo]` da `auth`, así que **el hueco que se preguntaba no existe**;
- `["kubectl","-n",ns,"apply"]`, `create_subprocess_exec("kubectl",…)`, `execvp`, `join`, `bash -c` en lista;
- la tupla, `base + ["apply"]`, `"--context=" + ctx`, `shutil.which("kubectl")`, `["k" "ubectl","delete"]`.

Pasan sin hallazgo, todos AMARILLO porque exigen ofuscar o algo que hoy no está:
- `[("kube"+"ctl"),"apply"]`;
- la biblioteca `sh` (`kubectl("delete")`, `sh.kubectl.apply`);
- `cmd[1]="delete"`;
- `[KUBECTL,"apply"]` sin ningún literal.

**Juicio sobre la decisión «literales hasta el verbo».** Es sana. Después del primer posicional, `kubectl` no cambia de subcomando. `auth` exige `can-i` literal inmediato, y una bandera con valor variable antes del verbo es `<expr>`.

Las formas legítimas pasan:
- `timeout 30 … get`, `KUBECONFIG=k kubectl get`, jsonpath, go-template con `;`;
- `-n "$NS"`, `--context "$CTX"`, `$(shell kubectl get ns)`;
- `port-forward … 2>&1 &`, `auth can-i --list`, `-l 'app in (a,b)'`, `logs | grep`, `get --raw`, `if kubectl get …; then`.

Hay falsos positivos en formas legítimas: ver F-06.

**F-02 (30 formas; secretos cargados: PEM real de 2048 bits, contraseña, 2 semillas de 32 caracteres, token).**
- Redactadas o con error: la cookie con varias y una entre comillas, `AUTHORIZATION   :`, `#access_token=`, el formulario con `%`, la YAML multilínea, la PEM doblemente escapada, el secreto de menos de 8 caracteres, la semilla con espacios cada 4, `otpauth://` en minúsculas, la PEM sin cabeceras (en una línea y en varias), el `repr` de dict, `VAULT_TOKEN=` en env, el `repr` con barra invertida, `refresh_token=`, `Proxy-Authorization`, `user-password`, la clave JSON con salto de línea.
- **Secretos cargados que quedan legibles, AMARILLO** (los dos primeros exigen una contraseña con comilla, `&` o letras no ASCII, y `vault_paths.py:254` las genera alfanuméricas):
  - el sufijo menor de 8 caracteres en JSON doblemente escapado (`\"[REDACTADO]\"x9Zq!k`);
  - el mismo sufijo en YAML con comilla doble (`'[REDACTADO]''x9Zq!k'`);
  - la entidad HTML `&amp;`, el `repr` de bytes UTF-8 y el base64 propio.
- **Valores no cargados que quedan:** la cabecera plegada y `Bearer` sin cabecera (AMARILLO), `code=` y las cabeceras en tupla o en HAR (F-08), y las claves genéricas `secret` y `token` (AMARILLO).
- **Evidencia limpia** (BFF JSON, `kubectl get pods`, Prometheus, respuesta de token de Keycloak, `curl -v`, `can-i`, el YAML de `securityContext`, Loki, `argocd app list`): **pasa** en kind y en staging. Hay falsos positivos fuera de esas: F-07 y F-09.

## Hallazgos nuevos
### F-06 · NARANJA · tests/unit/test_kubectl_verbs.py:119-127 (`_indirect`) y :184-195 · el detector rechaza formas legítimas y comunes
`_indirect` marca cualquier asignación de una sustitución y cualquier envoltorio, aunque el verbo sea legítimo. Estas formas dan hallazgo:
- `PODS=$(kubectl get pods -o name)` da `kubectl <indirect>`. Es la forma más común en un guion de demo; `PODS="$(…)"` sí pasa;
- `watch kubectl get pods` y `nohup kubectl port-forward … &` dan `<indirect>`;
- `kubectl --context "$(ctx)" get pods` da `<unparsable>`;
- en Python, `["kubectl","--context",ctx,"get","pods"]` da `<expr>`. Hay salida: poner el verbo primero;
- la prosa Markdown «El comando kubectl lista…» da `lista`.

Falla cerrado, y para cada forma hay una manera de escribirla que pasa. Pero el Paso 12 lo correrá sobre `demos/` y estos son patrones habituales. Va a CANDIDATAS, destino Paso 12.

### F-07 · NARANJA · src/vectra_verification/evidence.py:126-128 (`_fragments`, `MIN_FRAGMENT`) · las palabras de la armadura PEM cuentan como trozos de secreto
Cuando hay una llave cliente cargada, `-----BEGIN` (10 caracteres), `-----END` (8) y `KEY-----` (8) son «trozos» de 8 o más caracteres. Cualquier certificado en una evidencia da `evidence_contains_secret`, en kind y en staging (`probe_fp.py`, caso «cert in evidence»). Lo introdujo esta ronda. Corregirlo exige excluir la armadura de los trozos.

### F-08 · NARANJA · evidence.py:24-31 · cabeceras en forma estructurada y `code=` quedan visibles
- `[(b'Authorization', b'Bearer …'), (b'Cookie', b'KC=…')]` (tupla de httpx/h11) y `{"name": "Cookie", "value": "KEYCLOAK_SESSION=…"}` (HAR, y U12 usa Playwright) pasan con el valor visible. CA-6 pide que la cookie salga sin su valor.
- `Location: …?code=…` también queda; es el código OIDC que la herramienta canjea.

No son secretos cargados, y un JWT dentro de ellas sí lo detecta `ensure_clean`. Va a CANDIDATAS.

### F-09 · NARANJA · credentials.py:153-158 junto con `ensure_clean` · en kind, el token de Vault es `root`
`platform/operators/vault-kind.yaml:3` lo fija en `devRootToken: root`, y `secret_values()` lo incluye. Por eso falla cualquier evidencia de kind que contenga `root`: `/dev/root` de cAdvisor, o el logger `root` de Python en `kubectl logs`. Viene de la ronda 1 (la búsqueda literal ya existía); no lo trae este diff. Hace falta un largo mínimo, o excluir el token de desarrollo. Va a CANDIDATAS, destino U12-T02.

### F-10 · AMARILLO · tests/property/test_sampler.py:61-64 · el generador casi no llega al rango que declara
Declara poblaciones de 30 a 400 filas. Medido: máximo de 141, y solo 2-3 % de los ejemplos con una celda de 30 o más y `min ≥ 10`. Aun así mata las 4 mutaciones.

### F-11 · AMARILLO · test_kubectl_verbs.py · evasiones que exigen intención
`xargs -n3 kubectl` o `xargs -r kubectl` con el verbo por stdin, el verbo entre comillas invertidas, la lista YAML en bloque, la biblioteca `sh`, `"kube"+"ctl"` y la mutación de la lista. Son una sola clase.

### F-12 · AMARILLO · evidence.py · fugas parciales con contraseñas no alfanuméricas
El sufijo menor de 8 caracteres con JSON doblemente escapado o con YAML `''`, la entidad HTML, el `repr` de bytes no ASCII, el base64, la cabecera plegada y el `Bearer` suelto.

## Tareas candidatas (defectos reales fuera de alcance)
- F-06, para el Paso 12: aceptar `VAR=$(kubectl <verbo permitido> …)`, `watch` y `nohup` con un verbo permitido.
- F-07: excluir la armadura PEM de `_fragments`.
- F-08: reconocer cabeceras en forma de tupla y HAR, y añadir `code` a los campos de URL.
- F-09, para U12-T02: el token de desarrollo `root` en kind frente a `ensure_clean`.
- F-10, F-11 y F-12, como mejoras.

## Estado del worktree
- `git status --short` sale **vacío** al final. Las mutaciones las deshice con `git checkout -- <archivo>`; no usé `git stash`.
- No moví, copié ni borré archivos ajenos. Todo lo mío está en un subdirectorio nuevo del scratchpad.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u12-t01-r2/`:
- `make-check.log`, `mut-sampler.log`, `mut-rt2.log`, `gen_stats.out`, `links.log`
- `probe_verbs.out`, `probe_legit.out`, `probe_ev.out`, `probe_fp.out`
- los scripts `probe_*.py` y `gen_stats.py`

```
VEREDICTO: VERDE
NARANJA|system-verification/tests/unit/test_kubectl_verbs.py:119|formas legítimas y comunes (PODS=$(kubectl get …), watch, nohup, --context "$(…)") dan hallazgo
NARANJA|system-verification/src/vectra_verification/evidence.py:126|la armadura PEM (-----BEGIN, -----END, KEY-----) cuenta como trozo de secreto: un certificado bloquea la evidencia
NARANJA|system-verification/src/vectra_verification/evidence.py:24|cabeceras en tupla/HAR y code= en URL quedan con el valor visible
NARANJA|system-verification/src/vectra_verification/credentials.py:153|el token de Vault de kind es "root" y bloquea evidencias que contengan esa palabra (preexistente)
AMARILLO|system-verification/tests/property/test_sampler.py:61|el generador llega a 141 filas como máximo y solo 2-3 % de los ejemplos tienen celda ≥30 con min ≥10
AMARILLO|system-verification/tests/unit/test_kubectl_verbs.py|evasiones que exigen intención (xargs -r con el verbo por stdin, comillas invertidas, lista YAML en bloque, sh, "kube"+"ctl")
AMARILLO|system-verification/src/vectra_verification/evidence.py|fugas parciales con contraseñas con comilla, & o letras no ASCII; base64; cabecera plegada
INFORME: revisiones/U12-T01/ronda-2.md
```
