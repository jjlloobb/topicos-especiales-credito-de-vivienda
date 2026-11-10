# Ronda 2 — U04-T07

VEREDICTO: VERDE

F-01 está corregido en `llamar.sh` y en `medir-freeze.sh`. La prueba nueva sale roja si se revierte el arreglo, y ni `make -C governance check` ni `make -C platform check` muestran regresiones. F-02 a F-07 y la candidata de U1 están registrados en `CANDIDATAS.md`, como pidió el arbitraje.

Revisé el sha 0c7caacd672cf6cdcc5bc51a2ac14edd77e3fa6f, cuyo padre es e1372ca. No corrí nada contra un clúster. Al terminar, el worktree está limpio (`git status --short` vacío).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Guía completa | El diff de la ronda 2 no toca la guía; verificado en la ronda 1 | pasa |
| 2 | Scripts | `uvx --from shellcheck-py shellcheck governance/docs/kind/*.sh`; `uv run pytest governance/tests/unit/test_kind_scripts.py governance/tests/unit/test_kind_runbook.py -q`; `! grep -rnE "kubectl apply\|helm (install\|upgrade)\|argocd app sync" governance/docs/kind/` | pasa: rc 0, 35 pruebas pasan, grep sin coincidencias |
| 3 | Frontend N/A | El diff no lo toca; verificado en la ronda 1 | pasa |
| 4 | Cierre | `make -C governance check` | pasa: RC=0, 587 pruebas pasan, cobertura 97,17 %. Kyverno da `pass: 19, fail: 0` ×3 y el runbook `pass: 8, fail: 0`. Trazabilidad «34 identificadores». No hubo ningún «se omite» (`grep -c` = 0) |
| 5 | `make -C platform check` | Con las herramientas ya instaladas en la ronda 1 | pasa: RC=0. 802 pruebas pasan, `kyverno test` da 81 de 81 y check-integration `pass: 354, fail: 0` |
| 6 | Evidencia del operador | — | sigue pendiente del operador, como permite la tarea |
| 7 | CA-7 | `policy-runbook` dentro de `check`; `test_kind_runbook.py` | pasa: `pass: 8, fail: 0`, 15 pruebas pasan |

## Verificación de F-01
1. **El arreglo está en los dos scripts.** `llamar.sh:36-37` y `medir-freeze.sh:24-25,51` ahora leen todo de una vez con `sys.stdin.buffer.read().partition(b"\n")`, y `freeze` envía `resto`.
2. **Mi reproducción de la ronda 1 ya pasa.** Corrí el cliente nuevo de `llamar.sh` en local y en `python:3.12-slim`, con el token y el cuerpo en una sola escritura. El servidor de prueba recibe `len=20 body=b'{"cutoff":"0.5000"}\n' auth=Bearer tok-abc`. En la ronda 1 recibía `body=b''`.
3. **La prueba nueva sale roja al revertir.** Copié la prueba de HEAD al scratchpad dos veces: una con los scripts de 9964785 (antes del arreglo) y otra con los de HEAD. Así no toqué el worktree.
   - Con los scripts viejos, `-k incrustado` da `2 failed` (llamar.sh y medir-freeze.sh).
   - Con los de HEAD da `2 passed`.
   - La prueba sí ejecuta el Python incrustado contra un servidor HTTP local.

## Hallazgos
Ninguno ROJO ni NARANJA en pie. Los de la ronda 1 quedaron así:
- **F-01:** cerrado.
- **F-02 a F-07:** registrados en `CANDIDATAS.md:434-439`, cada uno con su severidad y la ruta del informe.
- **Candidata de U1:** registrada en la línea 440.

F-02 era NARANJA. Pasó a candidata solo porque el orquestador lo decidió por RL-2, no porque se haya corregido. Sigue siendo cierto que `policy-runbook` y `shellcheck` se saltan con rc 0 en una máquina sin `kubectl` ni `uvx`.

Nota menor, sin severidad: la sonda `sondear` de `medir-freeze.sh` ahora espera el fin de stdin antes de leer el token. Funciona porque `kubectl exec -i` cierra stdin cuando `token.sh` termina. Si en kind la sonda se queda colgada, mirar eso primero.

## Tareas candidatas (defectos reales fuera de alcance)
- No hay ninguna nueva; las de la ronda 1 ya están registradas.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/gov-check-r2.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/platform-check-r2.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/r2-viejo/ y /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/r2-nuevo/ (prueba contra los scripts revertidos y contra los arreglados)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/repro/cliente2.py

```
VEREDICTO: VERDE
INFORME: revisiones/U04-T07/ronda-2.md
```
