# Ronda 2 — U01-T18

VEREDICTO: VERDE

Quedan cerrados F-01 y G-02 (con G-01 de paso) en `279c4f3`, y G-03 en la bitácora. Comprobado: `279c4f3..2c5ca9f` no toca nada bajo `platform/`, solo la bitácora, la respuesta y `CANDIDATAS.md`. Los cuatro criterios pasan en mis corridas. Las 29 mutaciones mueren, incluidas las cinco que sobrevivieron en la ronda 1. No queda ningún ROJO ni NARANJA.

## Criterios de aceptación, verificados por mí
Todo con PATH sin `/snap/bin` (`which kubectl` vacío) y `KUBECONFIG=/nonexistent`.

| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Subrecursos con `--subresource`, fijados por las pruebas | `uv run pytest platform/kind/tests -q -p no:cacheprovider -k readonly_kubeconfig` y `shellcheck` | pasa: `26 passed, 111 deselected`; shellcheck rc 0. `--collect-only`: 26 pruebas, todas de `test_readonly_kubeconfig.py` y ninguna de otro archivo |
| 2 | Solo lectura | `! grep -n -E 'kubectl[^|#]*\b(apply\|…\|exec)\b' readonly-kubeconfig.sh` | pasa, rc 0 |
| 3 | Documento y enlaces | `grep -n -c -- '--subresource' readonly-kubeconfig.md`; `uv run python platform/tests/test_links.py` | pasa: 1; `678 archivos Markdown sin enlaces rotos`, rc 0 |
| 4 | Pytest completo sin clúster y `make check` | `platform/.tools` movido al scratchpad (comprobado que ya no estaba en el árbol) → pytest de la CI → enlace devuelto al mismo destino (`readlink` igual) → `make -C platform check`, una sola vez | pasa: `1070 passed in 245.23s`, rc 0; `make check` rc 0, `pass: 450, fail: 0, warn: 0, error: 0` |

## Lo verificado
- **F-01, cerrado.** Corrí el guion contra el falso y leí el registro de llamadas:
  - 92 filas y ninguna barra en el recurso.
  - `bind clusterroles` se pregunta con `-n vectra-app`, `-n vectra-edge`, `-n vectra-data` y `-A`.
  - `escalate clusterroles`, `get nodes`, `get nodes --subresource=proxy` y `get nodes --subresource=log` solo se preguntan con `-A`.
  - Mi falso propio, con un `yes` a `bind clusterroles` solo con `-n vectra-app` y sin usar el mecanismo `@ambito` del codificador, da **rc 1**: `Filas: 92; distintas de lo esperado: 1`, fila `vectra-app bind clusterroles FALLA`. En la ronda 1 daba rc 0.
  - El documento ya no dice «la respuesta no añade nada». Da la razón de que `bind` se pregunte por namespace y la cifra 92 (22×3 + 25 + `get nodes`). Cuadra con el guion.
- **G-02, cerrado; G-01 cerrado de paso.** La prueba compara con el conjunto exacto de 92 tuplas (esperado, ámbito, verbo, recurso), leído de la tabla impresa, y también con las llamadas reales. La lista de filas que solo van en `cluster` es una expectativa independiente, no copia la del guion.
  - Mutaciones en copias, las 29 mueren:
    - las cinco que sobrevivían en la ronda 1 (sustituir `list secrets`, `delete pods`, `create deployments`, `update deployments` o `pods/attach` por `create configmaps`): 1 fallo cada una;
    - un solo argumento (5);
    - quitar `--subresource` en una sola fila, probado con `pods/log`, `services/proxy`, `pods/attach`, `serviceaccounts/token` y `nodes/log` (1 a 5);
    - intercambiar recurso y subrecurso (5);
    - perder `-n` (3);
    - perder `-A`, o cambiarlo por `-n default` (2 cada una);
    - quitar `update deployments` o `pods/attach` (2 cada una);
    - sacar `clusterroles` de `CLUSTER_SCOPED`, o añadir `users` (2 cada una);
    - quitar el corte por la primera palabra (1);
    - quitar la excepción de `bind` (2);
    - extender la excepción a `escalate` (2);
    - cambiar el valor esperado de `no` a `yes` (4), o de `yes` a `no` (4);
    - `CLUSTER_ROWS` con `list nodes` (1);
    - quitar el ámbito `vectra-data` (3);
    - preguntar una fila de más (1);
    - dar todo por `ok` (6);
    - poner `bind roles` en lugar de `bind clusterroles` (2).
  - Contra las pruebas nuevas, el guion de la ronda 1 (`f2bb2e2`) da `2 failed, 24 passed` y el de `main` da `6 failed, 20 passed`.
- **G-03, cerrado.** La orden de la bitácora es `cd vectra-risk && platform/kind/readonly-kubeconfig.sh check`, sin `KUBECONFIG`. Es correcta: `check` usa por omisión `--kubeconfig ~/.kube/kind-vectra-readonly`. La línea final es `Filas: 92; distintas de lo esperado: 0; sin respuesta: 0.`, que cuadra con mi corrida contra el falso. La corrida en el clúster sigue sin medir y la bitácora lo dice.
- **Sin regresiones.**
  - `FAKE_REASON=si` (`no - motivo`): rc 0.
  - Falso que contesta `yes` a todo: rc 1, con 71 filas distintas (92 menos las 21 de «sí»).
  - Falso que no responde: rc 3, `sin respuesta: 92`.
  - El diff completo `32b5d0b..2c5ca9f` solo toca el `.md`, el `.sh` (comentarios, `CLUSTER_SCOPED` con su excepción, `ask` y el bucle), las pruebas, la bitácora, `CANDIDATAS.md` y `revisiones/`. `write_kubeconfig` y el RBAC no cambian, y no hay desborde de alcance.
- **`CANDIDATAS.md`.** Solo 4 líneas añadidas al final (después de la 878) y 0 borradas: G-04 y las tres candidatas de la ronda 1.
- **Cifras de la bitácora.** Mis corridas reproducen todas las cifras: rojo primero `2 failed, 24 passed`, `26 passed`, las cinco mutaciones con `1 failed, 25 passed`, un solo argumento con `5 failed, 21 passed`, `1070 passed` y `make check` 450/0. Los enlaces dan 677 en la bitácora y 678 en mi corrida. La bitácora ya avisa de que la cuenta puede variar con los archivos de documentación de la ronda, y cuadra. Todo puede salir del diff actual.

## Hallazgos
Ninguno en pie.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna nueva. G-04 y las tres de la ronda 1 ya están en `CANDIDATAS.md`.

## Estado final del worktree
`git status --short` vacío, HEAD `2c5ca9f`. `platform/.tools` devuelto como enlace a `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools`. Las copias `rev-u01t18-*` del scratchpad están borradas (comprobado: 0). Nada contra el clúster y ningún kubeconfig leído.

## Rutas de transcripciones largas
- Ninguna conservada: los registros estaban en el scratchpad y se borraron según la regla. Las cifras están arriba.

```
VEREDICTO: VERDE
INFORME: revisiones/U01-T18/ronda-2.md
```
