# Ronda 2 — U02-T13

VEREDICTO: NO-VERDE

Hice todo en `vectra-risk/`, HEAD 371bac5, con la tarea en el blob 5be4aa20…, el que se esperaba. Los seis criterios pasan con mis ejecuciones. F-02, F-03 y F-04 quedan cerrados. F-01 cierra el falso positivo, pero el riesgo residual que documenta el codificador no es el que mido: el que describe no existe, y el real no está escrito en ninguna parte. El worktree estaba limpio antes y sigue limpio después (`git status --short` vacío). No toqué ningún clúster, ni Docker, ni procesos ajenos, y no queda nada mío en segundo plano.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Reglas válidas; cada alerta dispara y no dispara | `promtool check rules … && promtool test rules …/tests/*.yaml` | pasa: 11 reglas, SUCCESS en los dos archivos, exit 0 |
| 2 | Runbooks | `test_runbooks.py --root identity-edge && … --operational` | pasa: 22 alertas y 10 runbooks operativos, exit 0 |
| 3 | Reglas = diseño | `uv run pytest identity-edge/tests/unit/test_alert_rules.py -q` | pasa: 66 passed en 2.6 s. Solo lee archivos y no depende de estado externo |
| 4 | Imagen con métricas de eventos | `uv run pytest identity-edge/tests/unit/test_keycloak_image.py -q` | pasa: 92 passed en 0.11 s (solo parsea el Dockerfile) |
| 5 | `check` de U2 | `uv sync --frozen && make -C identity-edge check` | pasa: 2464 passed en 15:41, ninguna omitida, exit 0 |
| 6 | U1, en serie después de CA-5 | `make -C platform check-local` | pasa: exit 0 en 2m34s |

## Mutaciones de la regla (43, sobre una copia)
- **Las 30 de la ronda 1 se detectan todas.** Reescribí «sin rama primera» para la expresión nueva.
- **De las 13 nuevas sobre la condición `up`, `offset` e `increase`, se detectan 11.** Las detectadas: quitar `up`, quitar el `offset`, `>= 0`, `on(namespace)`, `on()`, otro job, `offset 1m` u `offset 10m`, `or` en lugar de `and`, `unless … offset 1m` e `increase[1m]`.
- **Sobreviven 2**, que van en F-03 de abajo.

## Comprobación de `job`, `namespace` y `pod`
- **`job="keycloak"`**: el PodMonitor `keycloak` (`monitors.yaml:8-16`) lo fija con `relabelings: [{targetLabel: job, replacement: keycloak}]`.
- **Orden de los relabelings**: lo comprobé en el operator v0.94.2, que es la versión de los CRD de `platform/.charts`. En `pkg/prometheus/promcfg.go`, `generatePodMonitorConfig` aplica primero `namespace` (1625-1626), luego `pod` (1633-1634) y luego el `job` por defecto (1655/1661). Los relabelings del usuario se añaden después (1683), así que `job=keycloak` gana.
- **Etiquetas en ambas series**: son etiquetas del target, así que las llevan tanto `up` como `keycloak_user_events_total`. Esa métrica no trae `pod` ni `namespace` propios, así que no hay conflicto. `and on(namespace, pod)` empareja bien.

## Hallazgos

### F-01 · NARANJA · identity-edge/runbooks/break-glass-login.md (Límites) y CANDIDATAS.md (última entrada) · El riesgo residual documentado de BreakGlassLogin es falso y omite el real
Medí la regla de HEAD con promtool, evaluando cada minuto del 0 al 24. Los escenarios están en `scratchpad/r2b/risk/t.yaml`.

| Escenario | Qué pasa con la regla de HEAD |
|---|---|
| A. Pod nuevo, `up` desde el minuto 0, login en el minuto 2 | dispara en 5-6m |
| A2. Lo mismo, con el login en el minuto 4 | dispara en 5-8m |
| B. El login ya está en el primer scrape (serie y `up` empiezan juntos) | **no dispara nunca** |
| C. Primer login real durante un hueco con up=0 (`up '1x5 0x8 1x10'`, serie `'_x14 1x10'`) | **no dispara nunca** |
| D. Login real durante el hueco, con un contador que ya existía (`'1x5 stale _x8 2x10'`) | **no dispara nunca** |

Qué se deduce de la tabla:
- **Lo que declara el runbook no ocurre.** Dice que «el primer login de un pod que lleva menos de 5 min raspándose no dispara hasta el siguiente login». No es así (casos A y A2): la segunda rama sigue abierta 5 min después de que aparece la serie y dispara en cuanto `up offset 5m` existe, solo que con retraso.
- **El hueco real no está documentado (casos B, C y D).** Ningún login que ocurra antes del primer scrape, o durante un hueco de scrape de más de unos 5 min, dispara nunca. La rama `increase[5m]` no alcanza a cruzar el hueco, y la segunda rama la bloquea `up` a 0 o ausente.
- **Es una regresión frente a la ronda 1** en los casos C y D: antes sí disparaban, aunque junto con falsos positivos.
- **Nadie avisa de que la alerta está ciega.** `defaultRules: { create: false }` (kube-prometheus-stack.yaml:5) y ninguna regla de U1 ni de U2 vigila `up{job="keycloak"}`. `KeycloakDown` usa kube-state-metrics. Por eso, si se rompen el TLS o la NetworkPolicy del puerto 9000, el SEV1 queda mudo en silencio. Es justo el modo de fallo que el runbook dice cubrir con «si `up` falla…»: nadie se entera de que falla.

**¿Es aceptable para un SEV1? No tal como está**, porque el operador lee un límite equivocado.

Sí hay una expresión que cierra los dos modos de fallo (falso positivo tras un hueco y pod recién arrancado) y además los casos C y D. Con `N = (X > 0 unless X offset 5m)`:
```
(increase(X[5m]) > 0) or (N > (last_over_time(X[1h] offset 5m) or X * 0)) or (N and on(namespace, pod) (up{job="keycloak"} offset 5m == 1))
```
- **Contra los escenarios**: A dispara en 2-6m, B en 1-4m, C en 14-18m y D en 15-19m.
- **Contra la suite del codificador**: pasa los dos casos de hueco (16m, no dispara), con la serie del revisor y `up` a 0 o ausente.
- **Dónde choca**: falla solo los casos «up de otro pod» y «sin up» (7m). Choca a propósito, porque trata como nueva una serie que no se vio en la última hora.
- **Sus límites**: un falso positivo si el hueco dura más de la ventana (1h, ajustable), y una omisión si el pod se reinicia durante el hueco y luego hay un login.

Lo que pido: la expresión es decisión del orquestador. Como mínimo, el runbook y CANDIDATAS.md tienen que describir el comportamiento medido (casos B, C y D, y que A solo se retrasa), y hace falta una candidata para alertar sobre `up{job="keycloak"} == 0`.

### F-02 · AMARILLO · identity-edge/observability/rules/tests/identity-edge-rules-test.yaml · Dos mutaciones de la condición `up` sobreviven
- `on(namespace, pod)` → `on(pod)`: no hay ningún caso con el mismo pod en otro namespace.
- `up{job="keycloak"}` → `up`: no hay ningún caso con un `up` de otro job sobre el mismo pod.

Hoy no tienen efecto: Keycloak solo vive en `vectra-identity`, y ningún monitor de U1 raspa los pods de Keycloak con otro job (no hay `linkerd-proxy`). Aun así, la etiqueta que se pidió verificar no tiene ninguna prueba que la fije.

### F-03 · AMARILLO · bitácora, Ronda 2 · Afirmación de mutaciones sin artefacto
La bitácora cita `mut2.py` y `mut-final.txt`, pero ninguno de los dos está en el repo ni tiene ruta. Mi corrida coincide con la suya en las 30 originales y en 5 de sus condiciones `up`, así que la afirmación queda verificada por mí y no por la evidencia que aporta.

### Cierre de los hallazgos de la ronda 1
- **F-02 cerrado**: las 10 mutaciones que sobrevivían ahora se detectan.
- **F-03 cerrado**:
  - los literales de `test_alert_rules.py` se comparan contra el texto de la fila;
  - el 19001 sale de F60, el único puerto de `api-gateway`;
  - el `"clientId"` que queda en `test_keycloak_deploy.py` es justo el que exige el arbitraje.
- **F-04 cerrado**: la entrada de `error=""` ya no está.
- **F-05**: está en CANDIDATAS.md.

## Tareas candidatas (defectos reales fuera de alcance)
- Una alerta de scrape para `up{job="keycloak"} == 0` o ausente. Sin ella, BreakGlassLogin (SEV1) puede quedar ciega sin que nadie lo sepa. Hoy no la hay en U1 (`defaultRules` apagado) ni en U2.
- Revisar B10 de P-U2-09 con la expresión alternativa de F-01, o con el ruler de Loki, para cubrir los logins durante un hueco de scrape.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/r2b/ca5.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/r2b/ca6.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/r2b/mut.txt (script: /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/scripts/mut2.py)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/19885ad1-0bf0-4041-a101-67f9ccd39813/scratchpad/r2b/risk/ (t.yaml con los escenarios y alt.yaml con la expresión alternativa)

No escribí `revisiones/U02-T13/ronda-2.md` porque mis herramientas son de solo lectura sobre el repositorio. El orquestador registra este texto.

```
VEREDICTO: NO-VERDE
NARANJA|identity-edge/runbooks/break-glass-login.md (Límites) y CANDIDATAS.md|el riesgo residual documentado de BreakGlassLogin es falso; los logins antes del primer scrape o durante un hueco no disparan nunca, y no está documentado
INFORME: revisiones/U02-T13/ronda-2.md
```
