# Ronda 2 — U01-T03

VEREDICTO: NO-VERDE

Worktree `wt-U01-T03`, rama `tarea/U01-T03`, sha `8012ef5`, base `f44ba83`. Nada se ejecutó contra un clúster. El efecto real (que los targets dejen de dar 504) sigue sin comprobar.

Los dos criterios pasan y los dos hallazgos de la ronda 1 quedan cerrados. El bloqueo es nuevo: F130 rompe una prueba existente de `pytest platform` que ninguno de los dos criterios corre.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | NetworkPolicy de ingress y egress de F130 en los 3 entornos, con esos puertos y sin 4143 | `uv run pytest platform/network/tests -q -k f130 -rs` | pasa: `3 passed, 85 deselected in 0.29s`; `--collect-only` da una prueba por entorno (kind, staging, prod) |
| 1b | Lectura de vuelta de `generated/` con un script propio | `yaml.safe_load_all` sobre `generated/{kind,staging,prod}/vectra-observability.yaml` | pasa en los 3: ingress y egress prometheus↔alertmanager [8080], ↔operator [8080], ↔grafana [3000]; identidad mTLS `prometheus.vectra-observability…`; `Server` con su puerto y selector; sin 4143 |
| 2 | Lo generado coincide y el inventario está al día | `uv run python platform/network/generate.py --check && uv run pytest platform/network/tests -q -rs` | pasa: gen rc=0, `88 passed in 4.51s`, pytest rc=0 |

Sobre el tiempo: 0.29 s y 4.5 s, sin omisiones. La suite es pura: construye desde `flows.yaml`, sin estado externo, y `--check` la ata a `generated/`. La mutación T1 lo confirma (abajo).

## Hallazgos de la ronda 1, comprobados

**F-01 (NARANJA): cerrado.** Cada mutación se aplicó en una copia privada, regenerando `generated/` y confirmando el cambio con `git diff --stat`.

| Mutación | `-k f130` | `--check` | Suite `network/tests` |
|---|---|---|---|
| B0, sin mutar | 3 passed | rc=0 | 88 passed |
| M1, puertos cruzados | 3 failed | rc=0 | 3 failed, 85 passed |
| M2, origen `loki` | 3 failed | rc=0 | 3 failed, 85 passed |
| M3, destinos `loki, tempo` | 3 failed | rc=0 | 3 failed, 85 passed |

La prueba también ata `AuthorizationPolicy` y `MeshTLSAuthentication` con la identidad `prometheus`, como pedía la ronda 1. La afirmación de la bitácora sobre M1, M2 y M3 se reproduce.

**F-02 (AMARILLO): cerrado.**
- `make -C platform generate` en la copia dio rc=0 y `git status` quedó con 0 líneas. Usé `UV_OFFLINE=1 UV_FROZEN=1`, sin editar el Makefile.
- `git diff c3f974a 8012ef5` no toca `generated/` ni `flows.yaml`.
- Que el codificador corriera el `make` no se puede demostrar, pero el resultado es idéntico.

## Hallazgos

### F-03 · NARANJA · `platform/tests/test_integration.py:15,185` · F130 rompe `test_flow_ports_are_really_open[alertmanager]`
La prueba exige que cada puerto de un flujo entrante esté declarado por el destino. Para los pods que crea el operador usa `OPERATOR_PORTS = {"prometheus": {9090}, "alertmanager": {9093, 9094}}`, y F130 añade 8080 a alertmanager.

```
AssertionError: ('alertmanager', 'F130', (8080,), {9093, 9094})
```

Comando, con `platform/.charts` copiado del repositorio principal a cada copia:
`uv run pytest platform/tests/test_integration.py platform/tests/test_upstream_charts.py platform/tests/test_kind_profile.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib`

| Copia | Resultado | Fallos |
|---|---|---|
| Base `f44ba83` | 1 failed, 78 passed | `test_repo_root_is_the_monorepo` (artefacto: la copia no tiene `.github`) |
| HEAD `8012ef5` | 2 failed, 78 passed | el mismo artefacto y **`test_flow_ports_are_really_open[alertmanager]`** |

Corrida completa de `pytest platform` sobre una exportación de todo el monorepo en HEAD: `2 failed, 595 passed`.
- El primer fallo es F-03.
- El segundo es `test_no_platform_or_gitops_file_is_git_ignored`, artefacto de la exportación: `git ls-files` falla con `CalledProcessError` porque no hay repositorio.

**Consecuencia:** el mismo comando corre en `make check-local` y en `.github/workflows/evidence.yml:46`, así que ambos deberían fallar. No corrí ninguno de los dos completos, ni comprobé qué flujos llaman a `evidence.yml`.

**Por qué es NARANJA y no ROJO:** CA-1 y CA-2 solo corren `platform/network/tests` y pasan, pero es una regresión real del diff.

**Origen:** no la introdujo el retrabajo. `flows.yaml` no cambió desde `676458d`, así que ya estaba en la ronda 1. Esa ronda no corrió `pytest platform` y lo declaró en «Sin ejecutar». Por eso sale ahora.

**Por qué no se ve sin charts:** el worktree no tiene `platform/.charts` (ignorado por Git). Sin charts, la prueba falla igual en la base y en HEAD, así que el fallo queda oculto entre los otros.

**Corrección probada solo en mi copia:** con `"alertmanager": {8080, 9093, 9094}`, `test_flow_ports_are_really_open` da `10 passed`. El 8080 corresponde a `reloader-web`, según el render de la ronda 1; no lo volví a renderizar. La decisión es del codificador. Tras corregir, debe correr `pytest platform` con charts y registrar la salida.

### F-04 · AMARILLO · `platform/network/tests/test_flows.py:440` · La prueba solo mira F130 en `vectra-observability`
Mutación N17: añadir `{ id: F130, from: [api-gateway], to: [case-service], port: 8080 }` da `-k f130` 3 passed, `--check` rc=0 y 88 passed. Los targets siguen correctos, y cualquier flujo nuevo con otro id también pasaría, así que no es propio de F130. No bloquea.

### F-05 · AMARILLO · `platform/network/tests/test_flows.py:455` · Solo se lee `requiredAuthenticationRefs[0]`
Mutación G4: el generador añade una segunda referencia inexistente a las autorizaciones de F130. Pasa `-k f130` y las 88 pruebas. Solo se alcanza cambiando `generate.py`, que este diff no toca. Basta comparar la lista completa.

### F-06 · AMARILLO · `platform/network/tests/test_flows.py:426-430` · `F130_TARGETS` repite la clave en la tupla
En las tres entradas, `target` y `label` son iguales. Sobra el primer elemento de la tupla.

## Mutaciones nuevas detectadas
Todas se aplicaron en la copia privada, con `generated/` regenerado salvo en T1.

| Mutación | `-k f130` | Suite `network/tests` |
|---|---|---|
| Sin F130 | 3 failed | 4 failed (incluye el inventario) |
| Grafana en 3100 | 3 failed | 3 failed |
| 4143 añadido | 3 failed | 3 failed |
| Solo en kind | 2 failed, 1 passed | 2 failed |
| Sin el destino operator | 3 failed | 3 failed |
| Origen extra `loki` | 3 failed | 3 failed |
| Destino extra `loki` | 3 failed | 3 failed |
| Puerto extra 9090 | 3 failed | 3 failed |
| `env_disabled` en prod | 1 failed, 2 passed | 2 failed |
| `enabled: false` en grafana | 3 failed | 3 failed |
| `target_port: 9999` | 3 failed | 3 failed |
| `also: [[loki, grafana]]` | 3 failed | 3 failed |
| SA de prometheus cambiada | 3 failed | 6 failed |
| Etiqueta de grafana errada | 3 failed | 3 failed |
| Etiqueta de prometheus errada | 3 failed | 3 failed |
| `vectra-observability` fuera de la malla | 3 failed | 7 failed |
| Origen externo añadido | 3 failed | 3 failed |
| G1, generador: puerto del `Server` de F130 errado | 3 failed | 6 failed |
| G2, generador: selector del `Server` de F130 errado | **3 passed** | 3 failed (`test_one_server_per_pod_and_port`) |
| G3, generador: `kind` errado en `targetRef` | **3 passed** | 3 failed (`test_every_authorization_targets_an_existing_object`) |
| T1, `generated/kind` editado a mano | 3 passed | 1 failed (`test_generated_check_matches`), `--check` rc=1 |

G2 y G3 los detecta el resto de la suite, así que no son hallazgo. Solo N17 (F-04) y G4 (F-05) escapan a todo.

## Comprobado sin hallazgo
- **Alcance del retrabajo:** `c3f974a..8012ef5` toca solo `test_flows.py`, la bitácora y `ronda-1-respuesta.md`.
- **Fila del inventario:** el orden `8080 / 3000 / 8080` corresponde a Alertmanager, Grafana y operator.
- **Hash de la tarea:** `ca0a613…` coincide con `git hash-object`.
- **Otras comprobaciones en la copia:** `vectra-risk-gitops/generate.py --check` rc=0, `quotas/render.py --check` rc=0, `test_waves` rc=0, `test_links` rc=0, `ruff check platform vectra-risk-gitops` limpio.
- **`test_traceability`:** rc=1 con el mismo mensaje que en la base según la ronda 1 (NFR-U1-40). Preexistente; esta ronda no lo volvió a correr en la base.
- **Bitácora:** sus cifras de la ronda 2 se reproducen en resultado, aunque los tiempos varían. Declara con honestidad que la prueba anterior no se volvió a correr. No afirma nada sobre el clúster.

## Sin ejecutar
- `make check-local` completo (`charts`, `render`, `helm lint`, `test_runbooks`).
- `make check-tools` y `check-integration`.

## Tareas candidatas (defectos reales fuera de alcance)
- **Señal sobre la especificación:** CA-2 solo cubre `platform/network/tests`, así que un flujo nuevo puede cumplir todos los criterios y romper `test_integration`. Las tareas de flujos deberían incluir `pytest platform/tests/test_integration.py` con charts.
- `platform/tests/test_traceability.py` falla en la base (NFR-U1-40). Viene de la ronda 1.
- prometheus→prometheus en 8080 y 9090 sin declarar. Viene de la ronda 1, sin comprobar.

## Notas sobre mi ejecución
- **Worktree:** `git status --short` da 0 líneas y HEAD sigue en `8012ef5`. Allí solo corrí los criterios y lecturas, con su propio `.venv`, lo que escribe solo cachés ignorados.
- **Copias:** las mutaciones y la corrección de prueba se hicieron en copias bajo el directorio temporal, con venv propio.
- **Repositorio principal:** solo copié de él `platform/.charts`; no lo modifiqué.
- **No guardé el informe:** el orquestador lo guarda en la ruta indicada abajo.
- **Orden del bloque final:** como en la ronda 1, dejo la línea de veredicto al final porque así lo pediste.

## Rutas de transcripciones largas
Todas bajo `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/`:
- `tasks/bajvryc1l.output` (matriz de mutaciones)
- `scratchpad/rev-u01t03-r2-2E10G1/tools/int-vectra-risk.out` (HEAD con charts)
- `scratchpad/rev-u01t03-r2-2E10G1/tools/int-base_vectra-risk.out` (base con charts)
- `scratchpad/rev-u01t03-r2-2E10G1/tools/mono.out` (`pytest platform` sobre el monorepo)

NARANJA|platform/tests/test_integration.py:15,185|F130 rompe test_flow_ports_are_really_open[alertmanager]
AMARILLO|platform/network/tests/test_flows.py:440|La prueba solo mira F130 en vectra-observability
AMARILLO|platform/network/tests/test_flows.py:455|Solo se lee requiredAuthenticationRefs[0]
AMARILLO|platform/network/tests/test_flows.py:426-430|F130_TARGETS repite la clave en la tupla
INFORME: revisiones/U01-T03/ronda-2.md
VEREDICTO: NO-VERDE
