# Ronda 1 — U01-T19

VEREDICTO: VERDE

Veredicto: corrí los cuatro criterios yo mismo y los cuatro pasan. No queda ningún ROJO ni NARANJA. Hay cuatro AMARILLOS que no bloquean y cuatro tareas candidatas. Worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u01-t19`, HEAD `a2bad40`, base `9c0805b` (igual a `origin/main`).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Sondas con margen y una prueba que lo fija | `uv run pytest platform/tests -q -p no:cacheprovider -k probe_margin`, primero con `--collect-only` | pasa: 17 passed en 27,6 s (carga 2,9). El filtro selecciona 17 de 671, todas de `test_probe_margin.py` |
| 1-rojo | Falla con los values de la base | La prueba en una copia en el scratchpad, con los cuatro `-kind.yaml` de `9c0805b` | 9 failed y 8 passed. Fallan los 8 contenedores que dice la bitácora, cada uno con su nombre y la regla rota, más la prueba de mutación |
| 2 | Producción rinde idéntico | `helm template` con los values sin `-kind`, base contra rama, de argo-cd, cert-manager, kyverno, cloudnative-pg y trust-manager | pasa: los sha256 son idénticos en los cinco (p. ej. argo-cd `1a7881cc…`, kyverno `dd959961…`). metrics-server solo se instala en kind |
| 3 | Tabla por contenedor y lista de lo intocable | Mi render de kind comparado con la tabla de la bitácora | pasa: coincide fila por fila (ver abajo) |
| 4 | pytest de `platform` como la CI, y `make check` | `PATH` sin `/snap/bin`, `KUBECONFIG=/nonexistent`, `platform/.tools` fuera del árbol durante el pytest y devuelto después; luego `make -C platform check` | pasa: 1087 passed en 380 s (carga 5,4 al empezar y 12,1 al terminar). `make check` rc=0 (ruff limpio, 1087 passed, kyverno pass 54 y pass 450 con fail 0, conftest 707/3/385 sin fallos), carga 10,2 al empezar |

## Lo verificado
**Mutaciones sobre los values nuevos**, en una copia en el scratchpad, una corrida del archivo de prueba por mutación:
- **Mueren** (la prueba falla):
  - M1: quitar `timeoutSeconds` de la sonda de vida de server y repo-server de Argo CD.
  - M2: quitar `failureThreshold` en metrics-server.
  - M3: margen de repo-server en 7×17 = 119 s.
  - M4: Kyverno con 30×3.
  - M5: clave renombrada `webhook.livenesProbe` en cert-manager. Muere porque `values.schema.json` la rechaza («additional properties 'livenesProbe' not allowed»), y con ella caen las tres pruebas de cert-manager.
  - M6: `timeoutSecond` mal escrito en metrics-server, que no tiene esquema. Muere por el render: el plazo queda en 1 s.
  - M9: bloque `controller:` de Argo CD renombrado.
- **Sobreviven, y es lo correcto**:
  - M7: quitar `timeoutSeconds` de Kyverno (el chart ya trae 5).
  - M8: quitar `timeoutSeconds` del controller de cert-manager (el chart ya trae 15).

  Son claves redundantes. La prueba mira el render real de `helm template` (con `integration.helm`, values más `kind_values`), no el YAML de values.

**Tabla real de kind en la rama** (plazo / periodo × fallos):

| Contenedor | Vida | Disponibilidad |
|---|---|---|
| argo repo-server | 5 / 10×12 | 5 / 10×3 |
| argo server | 5 / 10×12 | 5 / 10×3 |
| argo application-controller | sin sonda | 5 / 10×3 |
| cert-manager controller | 15 / 10×12 | sin sonda |
| cert-manager webhook | 5 / 10×12 | 5 / 5×3 |
| cert-manager cainjector | sin sonda | sin sonda |
| kyverno admission y cleanup | 5 / 30×4 | 5 / 10×6 |
| kyverno background y reports | sin sonda | sin sonda |
| metrics-server | 5 / 10×12 | 5 / 10×3 |
| cnpg manager (sin cambio) | 1 / 10×3 | 1 / 10×3 |
| trust-manager (sin cambio) | sin sonda | 1 / 7×3 |

Antes y después coinciden con la bitácora.

**Intocables, comprobado en las plantillas:**
- cnpg 0.29.1, `templates/deployment.yaml:101-124`: solo escribe `initialDelaySeconds` en las sondas de vida y de disponibilidad.
- trust-manager v0.26.0, `templates/deployment.yaml:84-89`: fija `initialDelaySeconds: 3` y `periodSeconds: 7`, y solo deja elegir puerto y ruta.

Las dos afirmaciones son ciertas. `UNTOUCHABLE` se indexa por (componente, contenedor, sonda) y solo cubre esas tres sondas, que hoy ya incumplen, así que no puede esconder una regresión de otro contenedor (con un matiz en F-02).

**Efectos no pedidos:** comparé el render de kind de la base con el de la rama, operador por operador. Las únicas líneas que cambian son `timeoutSeconds` y `failureThreshold`: 7 líneas en argo-cd, 4 en cert-manager, 2 en kyverno, 3 en metrics-server, y 0 en cnpg y trust-manager. Mover `replicas` dentro de los bloques no altera nada.

**Detección de un operador colgado:** las sondas de disponibilidad conservan su periodo y sus fallos, así que un pod colgado sale de los endpoints igual que antes. Lo que cambia es el reinicio por la sonda de vida:
- Webhook de Kyverno: pasa de 60 s a 120 s. Con una sola réplica y `failurePolicy: Fail`, las admisiones se rechazan durante ese tiempo con o sin este cambio.
- Webhook de cert-manager: pasa de 30 s a 120 s.

Es solo kind y es justo lo que pide la tarea. Lo valoro aceptable y no levanto hallazgo.

**CANDIDATAS.md** solo crece al final: el archivo de `origin/main` es prefijo exacto del de la rama (887 líneas → 893, +6).

## Hallazgos
### F-01 · AMARILLO · bitácora, «Órdenes para el orquestador» · Falta la precondición y la espera no tiene tope
- Las Applications de kind apuntan a `targetRevision: main` y no tienen sincronización automática (`vectra-risk-gitops/apps/kind/metrics-server.yaml`). `argocd app sync` antes de fusionar y hacer push no cambia nada, y la bitácora no lo dice.
- `argocd app wait … --health` va sin `--timeout`; el runbook usa `--timeout 900` (`platform/runbooks/install.md:100`).
- El efecto sobre Kyverno es más pesimista que el real: Kyverno rueda con `maxSurge: 1` y `maxUnavailable: 40%` (que con una réplica es 0), así que el pod nuevo arranca antes de que se vaya el viejo. Solo habría corte si el pod nuevo no llega a estar listo, por ejemplo por su sonda de arranque con plazo de 1 s en plena racha.

El orden en sí es prudente: metrics-server, cert-manager, kyverno y Argo CD el último, esperando `Healthy` entre cada uno.

### F-02 · AMARILLO · `platform/tests/test_probe_margin.py:90-95` · El aviso de `UNTOUCHABLE` promete más de lo que hace
Tanto `CANDIDATAS.md` como el docstring dicen que la prueba «avisa el día que el chart los exponga». En realidad solo falla si el render trae `timeoutSeconds`. Si el chart añade la clave con una guarda `if`, como ya hace cnpg con `initialDelaySeconds`, la prueba sigue en verde. Además `violations()` se salta por completo esas sondas, incluida la regla del margen.

### F-03 · AMARILLO · `test_probe_margin.py:69` · Una sonda que desaparece pasa en verde
Por `if probe not in spec: continue`, apagar la sonda de vida de un operador de la lista (p. ej. `server.livenessProbe.enabled: false`) no rompe la prueba. No es una regresión del margen, pero sí una forma de esquivar la regla.

### F-04 · AMARILLO · CA-1, `--collect-only` · El codificador no lo corrió
La bitácora dice que no lo corrió. Lo corrí yo: selecciona exactamente las 17 pruebas de `test_probe_margin.py`. No tiene efecto en el resultado.

## Tareas candidatas (defectos reales fuera de alcance)
- Sondas de arranque con plazo por defecto de 1 s:
  - Kyverno admission y cleanup: 1 / 6×20. El chart las expone enteras en `admissionController.startupProbe` y `cleanupController.startupProbe`.
  - cnpg manager: 1 / 5×6. El chart solo expone `periodSeconds` y `failureThreshold`.

  En una racha, un pod recién reiniciado puede entrar en bucle. La tarea solo cubría vida y disponibilidad, y ni la bitácora ni `CANDIDATAS.md` lo mencionan.
- `test_probe_margin.py`: que `UNTOUCHABLE` compare la sonda entera del render (no solo `timeoutSeconds`) y que se exija la presencia de las sondas que hoy existen (F-02, F-03).
- trust-manager: no tiene sonda de vida, así que sus 58 reinicios no vienen de una sonda. Hay que confirmar si vienen de la elección de líder (`app.leaderElection.renewDeadline`). Está insinuado en la candidata del codificador; conviene medirlo.
- El runbook de kind en `platform/docs/` (citado como contexto en la tarea) no cuenta qué hacer si los operadores se reinician en una racha. No lo exigía ningún criterio.

## Estado final del worktree
- `git status --short` sale vacío y el HEAD sigue en `a2bad40`.
- `platform/.tools`: lo saqué del árbol durante el pytest y lo devolví. Sigue siendo el enlace original. `platform/.charts` no lo toqué.
- `make check` escribe `report.txt` dentro de `.tools/integration`, es decir, en el `.tools` del checkout principal (por el enlace). Es estado compartido e ignorado por Git.
- Copias del scratchpad `rev-u01t19-*` borradas. No usé `git stash`. No hubo ninguna orden contra el clúster ni lectura de `~/.kube`. Ningún secreto en la salida.

```
VEREDICTO: VERDE
AMARILLO|bitácora, órdenes para el orquestador|falta «tras fusionar en main», wait sin --timeout, efecto en Kyverno exagerado
AMARILLO|platform/tests/test_probe_margin.py:90-95|UNTOUCHABLE solo avisa si el render trae timeoutSeconds y se salta la regla del margen
AMARILLO|platform/tests/test_probe_margin.py:69|una sonda de vida que desaparece pasa en verde
AMARILLO|CA-1 --collect-only|el codificador no lo corrió (verificado por el revisor: 17 pruebas)
INFORME: revisiones/U01-T19/ronda-1.md
```
