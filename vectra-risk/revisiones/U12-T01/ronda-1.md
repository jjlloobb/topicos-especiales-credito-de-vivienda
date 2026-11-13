# Ronda 1 — U12-T01

VEREDICTO: NO-VERDE

Hay dos ROJOS, ambos en barreras de seguridad. El detector de verbos de `kubectl` deja pasar órdenes encadenadas en una línea. El filtro de evidencias deja escrito en la evidencia el valor de una cookie entre comillas. Todo lo demás lo corrí yo y pasa.

Base: rama `tarea/U12-T01` @ 9b18465 contra `origin/main` 82c1718. El blob de la tarea es 5f125208aefaa3d5127d6f14edb185433c75cccf y coincide. El diff no toca `vectra-risk/platform` (`git diff --stat` vacío).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | import-linter | `uv sync --frozen && uv run lint-imports --config system-verification/.importlinter` | pasa: 3 kept, 0 broken |
| 2 | estructura | el bucle `test -e` de la tarea | pasa (`OK`) |
| 3 | verbos de kubectl | dentro de `make check` (29 pruebas) | pasa, pero se burla: **F-01** |
| 4-7 | guard, credentials, evidence | dentro de `make check` (170 passed, 0 skipped, 0 xfail) | pasan; el filtro se burla: **F-02** |
| 8-11 | PBT-U12-01, 02, 04 y story_map | `HYPOTHESIS_PROFILE=ci pytest <los 4 archivos> --hypothesis-seed=S`, con S = 11, 424242, 987654321, 2026111201 y 31337 | 61 passed en cada semilla (75 a 104 s, carga 11 a 17); el generador de sampler es débil: **F-03** |
| 12 | cobertura 100 % | `make check` | report.py y sampler.py al 100 % de ramas; `grep -c pragma` da 0 |
| 13 | trazabilidad | `test_traceability.py --unit system-verification --all` | rc=1 con 6 líneas: INF-U12-04, INF-U12-05, NFR-U12-02, NFR-U12-31, NFR-U12-42, NFR-U12-50. Todas están en el conjunto admitido y ninguna nombra los identificadores prohibidos |
| 13b | `--all` contra la base | base extraída con `git archive` y comparada con `diff` | sin fallos nuevos en otras unidades. Las líneas de U8 y U10 salen iguales en las dos corridas. Las 4 líneas «solo en code/README.md» de U0 y U1 salen solo en la copia de la base: son un artefacto de la copia |
| 14 | `make -C system-verification check` | `uptime; time make ...; uptime` | rc=0, real 4m02s, carga 10,12 al empezar y 17,57 al terminar (23:00); semilla 331889202 |
| 15 | `make -C platform check` | no lo repetí (el diff no toca `platform/`) | — |
| 16 | lock y alcance | `uv lock --check`; el `grep -vE` de la tarea | lock rc=0; `fuera=1`; `uv.lock` solo agrega `vectra-verification` |
| 17 | plan | el `grep` y el diff de la tarea | pasa: solo las 4 casillas; las reglas de admisión siguen en el plan |
| 18 | enlaces | `uv run python platform/tests/test_links.py` | 529 archivos sin enlaces rotos, rc=0 |

**Mutaciones mías.** Todas son distintas de las del codificador. Las corrí con `--hypothesis-seed=777` y perfil `ci`, y revertí cada una con `git checkout --`.
- **report**, 3 de 3 muertas por las PBT:
  - poner `no ejecutado` antes que `falla` en `_worst`;
  - no comparar los hashes en `_intact`;
  - que la historia mire solo su primera evidencia.
- **rt2_latency**, 3 de 3 muertas por las PBT:
  - `<` en vez de `<=` en el límite;
  - segundos redondeados;
  - usar la mediana en vez del mínimo.
- **story_map**, 2 de 2 muertas:
  - quitar la comprobación de historia desconocida;
  - quitar la comprobación de historia faltante.
- **sampler**: las PBT no matan ninguna de 4. Ver F-03.

## Hallazgos

### F-01 · ROJO · tests/unit/test_kubectl_verbs.py:90 · el detector no ve un verbo prohibido en una orden encadenada
La expresión `re.finditer(r"\bkubectl\b(.*)", line)` es codiciosa. El primer `kubectl` se traga el resto de la línea, así que solo se juzga el primer verbo y el segundo `kubectl` nunca se busca.

Probé `scan_text` y `scan_python` con un script de prueba (`probe_verbs.py`). Estas entradas salen **SIN HALLAZGO**:
- `kubectl get pods && kubectl delete pod x`
- `kubectl get ns; kubectl apply -f x.yaml`
- `kubectl get deploy x -o yaml | kubectl apply -f -`

Es un caso de una clase repetible. Las demás formas de la misma clase, que también salen sin hallazgo:
- **Shell:**
  - el binario en una variable: `K=kubectl` y en la línea siguiente `$K apply`;
  - `echo apply -f x | xargs kubectl`;
  - una bandera con valor que no está en `GLOBAL_WITH_VALUE`: `kubectl --certificate-authority get apply`;
  - `kubectl auth --as can-i reconcile`;
  - `A=argocd` y luego `$A app sync`.
- **Python:**
  - `["kubectl"] + ["apply", ...]`;
  - `[K, "delete", ...]` con `K = "kubectl"`;
  - `f"kubectl {v} -f x"`;
  - `"kubectl " + v`.
- **Archivos:** `scan_tree` no recorre `.bash` (`demos/x.bash` con `kubectl delete` no da hallazgo).

Por qué bloquea: es la barrera estática de BR-U12-09 y NFR-U12-43, y el Paso 12 la reutiliza sobre `demos/` sin tocarla. Una tubería `get | apply` en una demo pasaría la prueba.

### F-02 · ROJO · src/vectra_verification/evidence.py:17-22 · el filtro deja cookies y contraseñas entre comillas en la evidencia
En `_HEADERS` el valor sin comillas es `[^\r\n"']*` y en `_FIELDS` el valor entre comillas es `"[^"]*"`. Los dos cortan en la primera comilla.

Probé `evidence.prepare` con un script de prueba (`probe_ev.py`) y estas entradas **pasan** sin error:
- `Cookie: KEYCLOAK_SESSION="opaque-sess-123"` queda como `Cookie: [REDACTADO]"opaque-sess-123"`. Las comillas en el valor de una cookie son legales según RFC 6265, y CA-6 pide que la cookie salga sin su valor.
- `Set-Cookie: AUTH_SESSION_ID="opaque-777"` queda igual de expuesto.
- La contraseña cargada `pw"secret-1`, escrita en JSON, queda como `"[REDACTADO]"secret-1"`. El sufijo de la contraseña cargada se filtra a la evidencia, y `ensure_clean` no lo detecta porque busca el secreto completo.

En el mismo barrido, otras formas que pasan sin error:
- `authorization=Bearer <opaco>`;
- `X-Vault-Token: <otro token>`;
- `client_secret=...`;
- una llave PEM cargada que aparece escapada en JSON (`\n`);
- la semilla cargada escrita en minúsculas;
- un JWT partido por un salto de línea.

### F-03 · NARANJA · tests/property/test_sampler.py:33 y 74-79 · PBT-U12-01 casi no ejerce la propiedad
Muestreé 500 ejemplos de `stratified_inputs()` (script `gen_stats.py`, no lo conservé). Resultado:
- Poblaciones con mediana de 5 filas, p90 de 14 y máximo de 28. Ninguna celda llega a 30 filas.
- En 0 de 500 ejemplos hay una celda con datos suficientes y `min_per_cell` ≥ 10.
- Solo 12 de 500 ejemplos tienen a la vez celdas llenas y celdas cortas.

Ninguna de mis 4 mutaciones la mata una PBT:
- **SM1** `Random(0)`, es decir, la semilla ignorada en `stratified`: 15 passed.
- **SM2** `normal` sin barajar: 15 passed. Ninguna prueba exige que la semilla influya ni que `normal` sea al azar.
- **SM3** tope de 10 por celda: la matan solo dos ejemplos fijos.
- **SM4** relleno final con una fila de menos: la matan solo dos ejemplos fijos. Además, la aserción `volume <= len(ids)` de la PBT nunca encontró ese caso.

Cómo corregirlo:
- un generador de poblaciones grandes y concentradas (por ejemplo, `min_size` y códigos con sesgo);
- una propiedad que diga que semillas distintas dan muestras distintas.

### F-04 · AMARILLO · guard.py:79,86,106; credentials.py:116,124 · la barrera compara por `environment.name`
Un `Environment("kind", "vectra.banco.internal", ...)` construido a mano pasa `check_section(..., "rt2")` y recibe la credencial de `cumplimiento-1`. Hoy ninguna entrada externa lo produce. Conviene exigir que el entorno sea uno de los de `ENVIRONMENTS` (con `is`).

### F-05 · AMARILLO · tests/property/test_rt2_latency.py:16 · lotes chicos
Los lotes miden como máximo 25 entradas (p50 de 5), frente a los 1 a 2 000 que dice CA-10. Los empates (316 de 500) y la frontera de 1 800 s (201 de 500) sí quedan cubiertos.

### Decisiones no previstas: ninguna contradice el plan ni el diseño
- **(a)** `story_map` valida contra `STORY_IDS` y `ELEMENT_IDS`, que viven en `report`. La prueba compara el YAML real fila por fila con la tabla §4.2.
- **(b)** El volumen como piso es coherente con BR-U12-06 («~1 500… ≥ 30 por celda; el volumen se ajusta»).
- **(c)** Rechazar un reloj sin zona es fail-closed.
- **(d)** La etiqueta `demostrada` es la de domain-entities §4.2.

`credentials` está bien:
- `cumplimiento-1` en staging da 0 solicitudes, también después de haber llenado la caché;
- las mayúsculas y `cumplimiento-2` se rechazan sin solicitud;
- 4 lecturas hacen 2 solicitudes;
- `repr` no muestra secretos.

`guard` rechaza las variantes que probé: barra final en el `iss`, host en mayúsculas, `:443`, `user:pw@`, punto final y combinaciones cruzadas.

## Tareas candidatas (defectos reales fuera de alcance)
- F-04 para U12-T02: atar `Credentials` al entorno que devuelve `check_environment` y a un `VAULT_ADDR` permitido.
- Bitácora, CA-15: `make -C platform check` no terminó con rc=0 en una sola corrida (cuota de `/tmp`). No lo repetí porque el diff no toca `platform/`.

## Estado del worktree y de los temporales
- `git status --short` sale vacío. Borré mi directorio temporal `platform/.tools/tmp/rev-u12`.
- Un error mío en el scratchpad compartido: al guardar mis logs moví por equivocación los `*.log` de la raíz del scratchpad (de otras sesiones) a `rev-u12-t01/`. Los devolví a la raíz con `mv -n`, que conserva las fechas. No puedo descartar que mi `cp` previo haya sobrescrito un archivo de otra sesión con alguno de estos nombres en esa raíz: `make-check.log`, `seeds.log`, `mut-*.log`, `trace-*.log`.

## Rutas de transcripciones largas
Todo está en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u12-t01/`:
- `make-check.log` (CA-14)
- `seeds.log` (CA-8 a CA-11)
- `mut-sampler.log`, `mut-report.log`, `mut-rt2-story.log`
- `trace-unit.log`, `trace-all-rama.log`, `trace-all-base.log`
- `probe_verbs.py`, `probe_ev.py`, `probe_cred.py`

```
VEREDICTO: NO-VERDE
ROJO|system-verification/tests/unit/test_kubectl_verbs.py:90|el detector no ve un verbo prohibido en una orden encadenada (&&, ;, |) ni en otras 10 formas
ROJO|system-verification/src/vectra_verification/evidence.py:17-22|cookies y contraseñas entre comillas pasan el filtro y quedan en la evidencia
NARANJA|system-verification/tests/property/test_sampler.py:33|PBT-U12-01 con poblaciones de 28 filas o menos: 0 de 4 mutaciones muertas por las PBT
AMARILLO|system-verification/src/vectra_verification/guard.py:79|la barrera compara por environment.name
AMARILLO|system-verification/tests/property/test_rt2_latency.py:16|lotes de 25 entradas como máximo, frente a 1..2000
INFORME: revisiones/U12-T01/ronda-1.md
```
