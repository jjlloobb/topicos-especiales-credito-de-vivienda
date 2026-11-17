# U01-T18 — El `check` del kubeconfig de solo lectura pregunta de verdad por los subrecursos

**Unidad:** U1 — `platform` (solo kind)
**Historias que implementa:** ninguna nueva; corrige un defecto de U01-T17 medido en `kind-vectra` el 2026-11-17.
**Depende de:** U01-T17 (fusionada, PR #199)

---

## Alcance

**Dentro:**

> `platform/kind/readonly-kubeconfig.sh check` pregunta `kubectl auth can-i <verbo> <recurso>` y, para los subrecursos, pasa el texto `pods/proxy`, `nodes/proxy`, `pods/log`, `pods/exec`… como un solo argumento. `kubectl` interpreta esa forma como **`TIPO/NOMBRE`** («el pod que se llama `proxy`»), no como el subrecurso. Las pruebas no lo vieron porque usan un `kubectl` falso que contesta lo que la prueba le dicta.
>
> Medido por el orquestador el 2026-11-17 en `kind-vectra`, con el kubeconfig que escribió `write` (identidad `system:serviceaccount:argocd:vectra-readonly-agent`):
>
> - `check` salió con **rc 1**: `Filas: 101; distintas de lo esperado: 16; sin respuesta: 0.` Las 16 son `get nodes/proxy`, `get pods/proxy`, `get services/proxy` y `get nodes/log` en los cuatro ámbitos: se esperaba `no` y respondió `yes`.
> - La identidad **sí es de solo lectura**. Con la misma identidad:
>   - `kubectl auth can-i get pods --subresource=proxy -n vectra-app` → `no`; lo mismo `services --subresource=proxy` y `pods --subresource=exec`; `pods --subresource=log` → `yes`.
>   - `kubectl get --raw /api/v1/nodes/vectra-worker/proxy/pods` → `Forbidden … cannot get resource "nodes/proxy"`.
>   - `kubectl get secret -n vectra-app` → `Forbidden`; `can-i create pods` → `no`; `can-i '*' '*'` → `no`.
> - `kubectl auth can-i get nodes --subresource=proxy -n vectra-app` escribe en stderr `Warning: resource 'nodes' is not namespace scoped` y contesta igual por stdout.
>
> Consecuencia: hoy **todas** las filas de subrecurso de la tabla son vacías. Las de «no» con `get` fallan en falso; las de «no» con `create` (`pods/exec`, `pods/portforward`, `pods/attach`, `serviceaccounts/token`) y la de «sí» (`get pods/log`) dan lo esperado por casualidad, porque la respuesta sobre «el pod llamado `exec`» coincide. `check` no puede dar verde con una identidad correcta, y si diera verde no probaría lo que dice.
>
> Lo que se quiere:
>
> 1. **`check` pregunta por el subrecurso.** Toda fila `recurso/subrecurso` se traduce a `kubectl auth can-i <verbo> <recurso> --subresource=<subrecurso>`. La tabla sigue escrita con la forma `recurso/subrecurso` (es la que se lee) y sigue imprimiéndose así.
> 2. **Una prueba que habría visto el defecto.** El `kubectl` falso de `platform/kind/tests/test_readonly_kubeconfig.py` debe comportarse como el real en lo que importa: ante un argumento posicional `a/b` contesta como `TIPO/NOMBRE` (la respuesta del recurso `a`, sin mirar `b`) y solo mira el subrecurso cuando llega `--subresource`. Con ese falso, el guion de hoy debe dar rojo (las 16 filas) y el corregido verde. Además, una prueba fija que ninguna llamada `auth can-i` del guion lleva una barra en el argumento del recurso.
> 3. **Los recursos de ámbito de clúster en un namespace.** Decide qué hace `check` con `nodes` (y `clusterroles`) en los ámbitos `vectra-app`, `vectra-edge` y `vectra-data`: preguntar igual (la respuesta es válida y el aviso va a stderr) o preguntar esas filas solo en el ámbito `cluster`. Si cambias el número de filas, dilo y actualiza la cifra en el documento y en tu bitácora (la de U01-T17 no se edita).
> 4. **El documento** `platform/kind/readonly-kubeconfig.md` dice la forma real de la pregunta y el número de filas que `check` imprime.

**Fuera:**

- El `ClusterRole` y el resto del RBAC: están bien (medido arriba). No los toques.
- `write`, salvo que el arreglo lo exija (no debería).
- `.claude/settings.json` y `.claude/agents/*.md`.
- Los AMARILLO G-01 a G-03 de la ronda 2 de U01-T17 (ya están en `CANDIDATAS.md`); puedes cerrar G-02 (el marcador que se pierde si `kubectl config` reescribe el archivo: decirlo en el documento) si te queda de paso, y dilo.
- Cualquier orden contra el clúster.

---

## Archivos de contexto

- `platform/kind/readonly-kubeconfig.sh` (`ROWS`, `SCOPES`, `CLUSTER_ROWS`, `ask`), `platform/kind/readonly-kubeconfig.md`
- `platform/kind/tests/test_readonly_kubeconfig.py` (el `kubectl` falso y la prueba de la tabla mínima), `platform/kind/tests/conftest.py`
- `revisiones/U01-T17/` (`ronda-1.md` F-02 y F-04, `ronda-2.md`), `bitacoras/U01-T17.md`

---

## Criterios de aceptación

- [ ] **CA-1** — `check` pregunta por los subrecursos con `--subresource` y las pruebas lo fijan.
  ```bash
  cd vectra-risk && uv run pytest platform/kind/tests -q -p no:cacheprovider -k "readonly_kubeconfig" && shellcheck platform/kind/readonly-kubeconfig.sh
  ```
  Esperado: pasa. **Rojo primero, y pegado en la bitácora:** con el falso nuevo y el guion de `main`, la prueba del caso «identidad correcta» falla nombrando las filas de `…/proxy` y `nodes/log`. Mutación que debe fallar: volver a pasar `recurso/subrecurso` como un solo argumento. Comprueba con `--collect-only` qué selecciona el filtro.

- [ ] **CA-2** — `check` sigue siendo de solo lectura.
  ```bash
  cd vectra-risk && ! grep -n -E 'kubectl[^|#]*\b(apply|delete|patch|annotate|create|edit|replace|scale|rollout|exec)\b' platform/kind/readonly-kubeconfig.sh
  ```
  Esperado: rc 0. Ojo: los verbos de la tabla (`create`, `delete`…) son datos de `ROWS`, no órdenes; si el filtro tropieza con tu cambio, dilo y no lo relajes sin justificarlo.

- [ ] **CA-3** — El documento dice la forma real y enlaza bien.
  ```bash
  cd vectra-risk && grep -n -c -- '--subresource' platform/kind/readonly-kubeconfig.md && uv run python platform/tests/test_links.py
  ```
  Esperado: al menos 1 y rc 0.

- [ ] **CA-4** — El pytest completo de `platform` pasa como lo corre la CI y sin clúster.
  ```bash
  cd vectra-risk && NOKUBE="$(echo "$PATH" | tr ':' '\n' | grep -v -E '^/snap/bin$' | paste -sd:)" && PATH="$NOKUBE" KUBECONFIG=/nonexistent uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider -q && KUBECONFIG=/nonexistent make -C platform check
  ```
  Esperado: pasan. (Con `platform/.tools` movido FUERA del árbol para el pytest y devuelto antes de `make check`; `make check` una sola vez, al final.)

---

## Plan de pruebas

Las de CA-1. **Rojo primero**; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`, ni lecturas.** Corre TODO con `KUBECONFIG=/nonexistent` y con un `PATH` sin `kubectl` real (está en `/snap/bin`; compruébalo con `which`). Existe `~/.kube/kind-vectra-readonly`: no lo uses ni lo leas; lleva un token.
- Las pruebas del guion lo lanzan con un `PATH` que contiene solo el directorio de falsos y los binarios inofensivos, y con `env` construido desde cero. Ninguna prueba ejecuta texto sacado de un documento.
- Ningún token ni valor secreto en pruebas, bitácora ni salidas.
- Lo que no puedes medir sin clúster dilo como «no medido»: el orquestador corre `check` en el clúster, con aprobación del usuario, cuando la tarea esté fusionada. Deja en la bitácora la orden exacta y la línea final que debe ver (`Filas: N; distintas de lo esperado: 0; sin respuesta: 0.`).
- `platform/.tools`: enlázalo a `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools`; `platform/.charts`: cópialo de `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u01-t13/vectra-risk/platform/.charts`. No van en el commit.
- La máquina tiene poca memoria y un clúster de kind completo corriendo: una sola corrida pesada a la vez.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u01t18-`, y borra tus copias al terminar.
- `CANDIDATAS.md`: solo añadir al final. Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
