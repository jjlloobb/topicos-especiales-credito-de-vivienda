# Ronda 2 — U01-T17

VEREDICTO: VERDE

No queda ningún ROJO ni NARANJA. Corrí yo los seis criterios sobre `487194c` y pasan los seis. El RBAC no deja ningún camino para leer un `Secret` ni para escribir con la identidad nueva. Quedan tres AMARILLO que no bloquean.

Revisé la rama `tarea/U01-T17`. El código de la ronda está en `06f9a02..e0b9942`. Comprobé que `487194c` solo toca `bitacoras/U01-T17.md` y `revisiones/U01-T17/ronda-1-respuesta.md`, y que `f301e8f` solo añade `revisiones/U01-T17/`. El manifiesto RBAC y el fixture de Kyverno no cambiaron en esta ronda. Todo corrió con `KUBECONFIG=/nonexistent` y con un `PATH` sin `/snap/bin` (`which kubectl` sale vacío). No hubo ninguna orden contra el clúster, ni `argocd`, ni `docker`.

## Criterios de aceptación, verificados por mí
| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | `pytest platform -k readonly` (con `--collect-only` y sin él) y `check-tools` | pasa: 48 seleccionadas y `48 passed, 1019 deselected`. En `check-tools`, la fila `ClusterRole//vectra-readonly-agent` sale `Pass` y `make` sale 0 |
| 2 | `generate.py --check`, `grep -c`, `! … grep` y `test_waves.py` | pasa: sale `1`; kind 56, prod 54 y staging 56 en orden |
| 3 | `pytest platform/kind/tests -k readonly_kubeconfig` y `shellcheck` | pasa: `23 passed, 111 deselected`; `shellcheck` sale 0 |
| 4 | `! grep -n -E 'kubectl[^\|#]*\b(apply\|…\|exec)\b' readonly-kubeconfig.sh` | pasa: sale 0 |
| 5 | `grep -c`, `test_links.py` y `test_runbooks.py` | pasa: 1 aparición en cada archivo; 661 Markdown sin enlaces rotos (la bitácora dice 660; el de más es `ronda-1-respuesta.md`, añadido después de su corrida); 56 alertas con runbook |
| 6 | pytest completo de `platform` (con `.tools` fuera y `.charts` dentro) y `make -C platform check` una sola vez | pasa: `1067 passed in 418.41s`, sin ninguna prueba omitida. `make` sale 0 (`pass: 450, fail: 0`). `.tools` quedó devuelto, el mismo enlace |
| — | `test_traceability.py --all` | sale 0 |

## Estado de los hallazgos de la ronda 1
- **F-01 (ROJO): cerrado.** Las cifras de la bitácora coinciden con mis corridas: 48 en CA-1, 23 en CA-3 y 1067 en el pytest completo. Las 101 filas de `check` (25 por ámbito × 4, más `get nodes`) también: mi corrida con un falso dio `Filas: 101`.
- **F-02 (NARANJA): cerrado.** Hice mis propias mutaciones contra `problems_in`, añadiendo una regla `get, list, watch` cada vez:

  | Mutación | Resultado |
  |---|---|
  | `nodes/proxy`, `services/proxy`, `pods/proxy`, `nodes/log`, `nodes/metrics`, `pods/ephemeralcontainers` | RECHAZA |
  | `applications/status` | RECHAZA |
  | `podz` (nombre mal escrito) | RECHAZA |
  | grupo `argoproj.iox` (grupo mal escrito) | RECHAZA |
  | `secrets` en el grupo `apps` | RECHAZA |
  | `configmaps` en el grupo `apps` | RECHAZA |
  | `certificatesigningrequests` | RECHAZA |
  | `resourceNames: [vault-0]` sobre `pods` | ADMITE, y es correcto: estrecha, no amplía |
  | regla solo con `nonResourceURLs` | la prueba se cae con `KeyError`: falla, pero sin decir por qué (ver G-01) |

  - **`applications/status` rechazado:** la regla es correcta, no demasiado estricta. `get` sobre el recurso ya devuelve el `status`, y una lista cerrada de subrecursos es lo que conviene en un rol de seguridad.
  - **Núcleo:** sale de `BUILTIN`, una lista escrita a mano en la prueba. Funciona como lista cerrada: lo que no está ahí se rechaza aunque exista, como `certificatesigningrequests`. El mensaje dice «no existe», cuando en realidad es «no está permitido», pero el efecto es el correcto.
  - **CRD:** se leen con una expresión regular que busca `name: <plural>.<grupo>` en los `.yaml`, `.yml` y `.tpl` de `platform/.charts`. Encuentra 151.
  - **Sin `.charts` no pasa en silencio.** Lo probé con una copia de la prueba sin `.charts` al lado: `2 failed`, con el mensaje «platform/.charts vacio: corre `make -C platform charts`», y nada omitido. La CI baja los charts antes del pytest (`tests.yml:22`: `make -C platform charts render`).
  - **Tabla de `check`:** las 7 filas «no» nuevas están en los cuatro ámbitos, y la prueba de la tabla mínima las fija.
- **F-03 (AMARILLO): cerrado.** `components.yaml` y el documento dicen ahora «misma wave que `kyverno-policies`» y explican por qué no importa.
- **F-04 (AMARILLO): cerrado.** Con un falso que contesta `no - RBAC: denied` en todas las filas «no», `check` sale 0. Con un falso que contesta `yes` a todo (el caso del kubeconfig de administrador) sale 1, con 80 filas distintas de lo esperado.
- **F-05 (AMARILLO): cerrado.** Lo comprobé con un `kubectl` falso:
  - **Ante una señal:** un `SIGTERM` durante un `chmod` lento sale 143 y borra el temporal.
  - **El archivo final se conserva:** el `trap` borra solo la ruta del temporal, que ya no existe tras el `mv`, y reescribir el archivo propio sale 0 con el archivo en su sitio.
  - **Se niega con rc 2, sin tocar el archivo, en cuatro casos:** `~/.kube/config`; un archivo de una lista `KUBECONFIG=/x:<adm>`; un enlace simbólico que apunta al de administrador; y un archivo ajeno, sin marcador. Con una ruta de `KUBECONFIG` que tiene espacios, la partición de palabras falla, pero la negativa por falta de marcador lo cubre igual.
  - **El marcador** es un comentario YAML en la primera línea, válido para el parser de `kubectl`. Lo confirmé leyendo; la prueba además lo carga con `yaml.safe_load`.
  - **Sigue igual que en la ronda 1:** el archivo queda 0600 y la escritura es atómica. El token no aparece en la salida y solo pasa por `printf` integrado, no por argv.
- **F-06 (AMARILLO): cerrado.** El documento dice que revocar exige una sincronización manual. «Qué NO resuelve» añade que la identidad lee la spec de los pods y `pods/log`, con el ejemplo de `root` en Vault.
- **Regresiones:** ninguna. Las pruebas siguen con un `PATH` solo de falsos (se añadió `rm`) y `env` desde cero. El falso sigue dejando constancia de los verbos inesperados: mis corridas no dejaron ninguna marca `UNEXPECTED`. La Application sigue solo en kind.

## Hallazgos nuevos
### G-01 · AMARILLO · `platform/tests/test_readonly_agent.py`, `problems_in` · Una regla sin `resources` hace caer la prueba con `KeyError`
Con una regla solo de `nonResourceURLs`, `problems_in` lanza `KeyError: 'apiGroups'` antes de llegar a la comprobación de `nonResourceURLs`. La prueba falla, que es el resultado correcto, pero sin un mensaje claro. Bastaría con usar `rule.get(...)`.

### G-02 · AMARILLO · `platform/kind/readonly-kubeconfig.sh:82` · El marcador se pierde si `kubectl config` reescribe el archivo
Si `kubectl config` reescribe el archivo (por ejemplo `use-context` o `set-*` con ese `KUBECONFIG`), se borra el comentario de la primera línea. El siguiente `write` sale 2 y hay que borrar el archivo a mano. El mensaje lo explica; conviene que el documento lo diga también.

### G-03 · AMARILLO · `test_readonly_agent.py`, `crd_names` · La expresión regular de los CRD es amplia
Toma cualquier `name: a.b` de los charts, no solo los nombres de CRD. Eso solo podría ampliar la lista de nombres admitidos con una cadena `recurso.grupo` exacta que no fuera un CRD; el riesgo es mínimo. Detalle menor: la bitácora dice que lo que sigue a `e0b9942` toca «bitácora, respuesta y CANDIDATAS», pero `CANDIDATAS.md` no cambia.

## Al cerrar
- `git status --short` sale vacío; HEAD sigue en `487194c`.
- Las copias `rev-u01t17-*` del scratchpad están borradas.

```
VEREDICTO: VERDE
AMARILLO|platform/tests/test_readonly_agent.py problems_in|una regla sin resources cae con KeyError en vez de dar un mensaje claro
AMARILLO|platform/kind/readonly-kubeconfig.sh:82|si kubectl config reescribe el archivo se pierde el marcador y write sale 2
AMARILLO|platform/tests/test_readonly_agent.py crd_names|la expresión regular de los CRD acepta cualquier name: a.b de los charts
INFORME: revisiones/U01-T17/ronda-2.md
```
