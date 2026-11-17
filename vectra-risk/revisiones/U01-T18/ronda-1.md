# Ronda 1 — U01-T18

VEREDICTO: NO-VERDE

Los cuatro criterios pasan en mis corridas y el arreglo central es correcto. No hay ningún ROJO. Queda un NARANJA en pie: la decisión de ámbito hace que `check` deje de ver una concesión de `bind clusterroles` en un namespace, que antes sí veía.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | `--subresource` fijado por las pruebas | `uv run pytest platform/kind/tests -q -p no:cacheprovider -k readonly_kubeconfig` y `shellcheck` (PATH sin `/snap/bin`, `which kubectl` vacío, `KUBECONFIG=/nonexistent`) | pasa: `25 passed, 111 deselected in 4.65s`; shellcheck rc 0. `--collect-only`: 25 pruebas, todas de `test_readonly_kubeconfig.py`, ninguna de otro archivo. Las 25 lanzan solo el guion con el `kubectl` falso, con PATH = directorio de falsos y `env` construido desde cero. |
| 2 | Sigue siendo de solo lectura | `! grep -n -E 'kubectl[^|#]*\b(apply\|…\|exec)\b' readonly-kubeconfig.sh` | pasa, rc 0; el filtro no tropieza con el cambio |
| 3 | El documento dice la forma real y los enlaces están bien | `grep -n -c -- '--subresource' readonly-kubeconfig.md`; `uv run python platform/tests/test_links.py` | pasa: 1; `675 archivos Markdown sin enlaces rotos`, rc 0. La bitácora dice 674: la diferencia de 1 cuadra con que la bitácora aún no existía cuando la midió. |
| 4 | Pytest completo sin clúster y luego `make check` | `platform/.tools` movido al scratchpad → pytest de la CI → enlace devuelto (mismo destino, comprobado con `readlink`) → `KUBECONFIG=/nonexistent make -C platform check`, una sola vez | pasa: `1069 passed in 239.36s`, rc 0; `make check` rc 0, `pass: 450, fail: 0` |

## Lo verificado con mis propias corridas y mutaciones
- **Forma de la pregunta.** Ejecuté el guion contra el falso y leí el registro de llamadas: 89 llamadas `auth can-i` y ninguna lleva barra en el recurso (el posicional `$9`).
  - Las 30 filas de subrecurso tienen la forma `can-i <verbo> <recurso> --subresource=<sub> -n <ns>` o `… -A`. Por ejemplo `create serviceaccounts --subresource=token -n vectra-app` y `get nodes --subresource=proxy -A`.
  - Es la forma correcta. `kubectl auth can-i` parte el posicional con `SplitN(arg,"/",2)` en recurso y nombre; `--subresource` va a `ResourceAttributes.Subresource`; `-A` pone el namespace vacío.
  - `escalate`/`bind clusterroles` se resuelven por el RESTMapper a `rbac.authorization.k8s.io`.
  - `applications.argoproj.io` se resuelve a `argoproj.io/applications` porque la CRD está instalada.
  - `users` está en `nonStandardResourceNames`: se pregunta en el grupo núcleo, sin aviso, que es lo que mira la regla de `impersonate`.
  - `delete *` se queda en el grupo núcleo: ver la candidata.
- **Fidelidad del falso.** El guion de `main` (copiado de `32b5d0b`) contra el falso nuevo da rc 1, `Filas: 101; distintas de lo esperado: 16`. Son exactamente `get nodes/proxy`, `get pods/proxy`, `get services/proxy` y `get nodes/log` en los 4 ámbitos, lo mismo que se midió en el clúster. El guion nuevo da rc 0, `Filas: 89; … 0; … 0`. Con las pruebas, el guion de `main` da `5 failed, 20 passed`, igual que en la bitácora.
- **Mutaciones (20, todas en copias).**
  - Mueren:
    - volver a un solo argumento (4 fallos);
    - quitar `--subresource` en una sola fila, probado con `pods/log`, `services/proxy`, `pods/attach`, `serviceaccounts/token` y `nodes/log` (1 a 3 fallos cada una);
    - intercambiar recurso y subrecurso (5);
    - perder `-n` (2);
    - perder `-A` (2);
    - cambiar `-A` por `-n default` (2);
    - quitar la fila `update deployments` o la de `pods/attach` (1 cada una);
    - sacar `clusterroles` de `CLUSTER_SCOPED` o añadir `users` (1 cada una);
    - quitar el corte por la primera palabra (1).
  - Sobreviven 5, que van como G-02.
- **Sin regresiones de U01-T17.**
  - `FAKE_REASON=si` (respuestas `no - motivo`): rc 0.
  - Falso que contesta `yes` a todo: rc 1, con 68 filas distintas (89 menos las 21 de «sí»).
  - Falso que no responde: rc 3, `sin respuesta: 89`.
  - El diff no toca `write_kubeconfig` ni el RBAC: los cambios del guion son solo comentarios, `CLUSTER_SCOPED`, `ask` y el bucle, en 4 archivos.

## Hallazgos
### F-01 · NARANJA · platform/kind/readonly-kubeconfig.sh:122 y readonly-kubeconfig.md:24 · Al quitar `clusterroles` de los namespaces se pierde `bind clusterroles` por namespace, que sí tiene valor
Cuando se crea un RoleBinding que apunta a un ClusterRole, el apiserver autoriza `bind` sobre `clusterroles` **en el namespace del binding** (`BindingAuthorized`, `Namespace: bindingNamespace`). Una RoleBinding en `vectra-app` que conceda `bind clusterroles` solo contesta `yes` con `-n vectra-app`; con `-A` no se ve.

Lo demostré con un falso que contesta `yes` a `bind clusterroles` solo con `-n vectra-app`:
- guion de `main`: rc 1, la fila `vectra-app bind clusterroles FALLA`;
- guion de este diff: **rc 0**, `Filas: 89; distintas de lo esperado: 0`.

Es una regresión de detección que introduce este diff. Además, el documento justifica el recorte con «la respuesta no añade nada», que es falso para `bind`. Para `nodes`, `nodes/proxy`, `nodes/log` y `escalate clusterroles` el recorte sí es correcto: esas peticiones reales van con namespace vacío.

No lo califico de ROJO porque la tabla nunca fue exhaustiva: `create rolebindings` o `create configmaps` tampoco están en ella. Arreglo mínimo: mantener `bind|clusterroles` en los tres namespaces (89 → 92) y corregir la frase del documento.

### G-01 · AMARILLO · test_readonly_kubeconfig.py:200 · `CLUSTER_SCOPED` duplicado en la prueba
La prueba repite a mano la lista del guion, y con otra forma (incluye los subrecursos). Un cambio en un lado no obliga a revisar el otro de forma evidente. No bloquea.

### G-02 · AMARILLO · test_readonly_kubeconfig.py:207 · La tabla mínima no fija 5 filas de «no» frente a un intercambio
`len(asked) == 89` detecta que se quite una fila, pero no que se cambie por otra cualquiera. Sobreviven las mutaciones que sustituyen `no|list|secrets`, `no|delete|pods`, `no|create|deployments`, `no|update|deployments` y `no|create|pods/attach` por `no|create|configmaps` (25 pruebas pasan en cada caso). Esas cinco filas no están en `must_say_no`, que ya era así en U01-T17. Se cierra comparando con el conjunto exacto de 89 tuplas.

### G-03 · AMARILLO · bitacoras/U01-T18.md (orden para el orquestador) · Falta el directorio de trabajo
`KUBECONFIG=~/.kube/kind-vectra-readonly platform/kind/readonly-kubeconfig.sh check` es la orden correcta y la línea final esperada (`Filas: 89; …`) cuadra con el guion. Pero la ruta es relativa a `vectra-risk/` y no lo dice. Además, el `KUBECONFIG` sobra, porque `check` usa `--kubeconfig "$absolute"` (por omisión `~/.kube/kind-vectra-readonly`). Si se aplica F-01, la cifra pasa a 92.

### G-04 · AMARILLO · readonly-kubeconfig.sh:110 · `impersonate users` se sigue preguntando por namespace
Con el criterio de F-01 esa pregunta no aporta nada: la impersonación se autoriza sin namespace. Es incoherente con la regla de `CLUSTER_SCOPED`, pero no da falsos verdes. Nota menor.

Evidencia: lo que afirma la bitácora (rojo primero 5/20, mutación 4/21, 25 pasan, 1069 pasan, `make check` 450/0) lo reproduje yo y sale de este diff. G-02 de U01-T17 (el marcador del documento) queda cerrado y declarado. No hay desborde de alcance.

## Tareas candidatas (defectos reales fuera de alcance)
- `escalate`/`bind` sobre `roles` (`rbac.authorization.k8s.io`) en cada namespace, y `create rolebindings`: no estaban en la tabla y siguen sin estar. Son la vía de escalada dentro de un namespace.
- `delete *` solo pregunta por el grupo núcleo (`Group ""`): una concesión de `delete` sobre `argoproj.io/*` o `apps/*` no la ve. Haría falta una fila por grupo relevante, o `'*.*'`.
- Si no está instalada la CRD de `applications.argoproj.io` o de `externalsecrets…`, `kubectl` la pregunta como recurso del grupo núcleo y da un rojo en falso. Es anterior a este diff; basta con documentarlo.

## Estado final del worktree
`git status --short` vacío, HEAD `2cc0f4b`. `platform/.tools` devuelto como enlace a `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools`. Las copias `rev-u01t18-*` del scratchpad están borradas (comprobado: 0). No toqué el clúster ni los kubeconfig.

## Rutas de transcripciones largas
- Ninguna conservada: estaban en el scratchpad y se borraron según la regla. Las cifras están arriba.

```
VEREDICTO: NO-VERDE
NARANJA|platform/kind/readonly-kubeconfig.sh:122|quitar clusterroles de los namespaces deja sin ver bind clusterroles por namespace (falso con RoleBinding en vectra-app: main rc 1, diff rc 0)
AMARILLO|platform/kind/tests/test_readonly_kubeconfig.py:200|CLUSTER_SCOPED duplicado a mano en la prueba
AMARILLO|platform/kind/tests/test_readonly_kubeconfig.py:207|la tabla mínima no fija 5 filas de no frente a un intercambio (sobreviven 5 mutaciones)
AMARILLO|bitacoras/U01-T18.md|a la orden para el orquestador le falta el directorio de trabajo (vectra-risk/) y el KUBECONFIG sobra
AMARILLO|platform/kind/readonly-kubeconfig.sh:110|impersonate users sigue preguntándose por namespace, incoherente con CLUSTER_SCOPED
INFORME: revisiones/U01-T18/ronda-1.md
```
