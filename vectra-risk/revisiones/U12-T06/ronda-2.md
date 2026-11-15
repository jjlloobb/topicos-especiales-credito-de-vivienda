VEREDICTO: NO-VERDE

# Ronda 2 — U12-T06

Base: `git diff a6e45d6..d754dce`, punta d754dce. Nada se ejecutó contra `kind-vectra`. Mutaciones y experimentos en una copia (`git archive d754dce`). `make check` corrió una sola vez. El worktree quedó limpio y sin contenedores `u12t06-`.

**Nota del orquestador:** el PR #173 se fusionó en `main` (24feccd) antes de que esta revisión terminara. Los hallazgos se atienden en U12-T07 (`tareas/U12-T07-puerta-de-la-boveda-y-remision-al-runbook.md`, que hace de arbitraje: entran F-01 a F-05).

## Criterios de aceptación, verificados por el revisor

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| 1-9 | Estructura, mundo cerrado, verbos, inventario, guiones, humo, plantillas, coherencia, `check` | `/usr/bin/time -v make -C system-verification check`, una vez; imagen desde la caché; carga 8 al empezar | **pasa**: rc=0 en 33:10. 1192 passed (21:01), 923 passed (10:26) y 32 passed (1:26). 0 skipped y 0 xfail. Cobertura 95,78 % y 100 %. Contracts: 11 kept, 0 broken. shellcheck en 0. RSS máximo 744 MB |
| 10 | Trazabilidad | los tres comandos de CA-10 | **pasa**: 22 identificadores; el grep de «Diferido» no imprime nada; `--all` rc=0 |
| 11 | Cierre y plan | los grep de CA-11 | **pasa**: 4 secciones; Paso 19 `[x]`; Paso 18 `[ ]`; conteo 4 |
| 12 | Enlaces y frases | `test_links.py` y `forbidden_phrases.py` | **pasa**: 600 archivos sin enlaces rotos; frases rc 0 |
| 13 | Lock y alcance | `uv lock --check` y el grep de CA-13 | **pasa**. `fuera=0` solo por `revisiones/U12-T06/{ronda-1,arbitraje-ronda-1}.md`, que no son del codificador. Nada en `src/`, `demos/` ni el README |
| — | Alcance de la ronda 2 | `git diff --name-only a6e45d6..d754dce \| grep -E "src/\|demos/\|Dockerfile\|README\|seccomp/\|platform/"` | **pasa**: ninguno |
| — | `CANDIDATAS.md` solo añade al final | `git diff -U0 a6e45d6..d754dce -- vectra-risk/CANDIDATAS.md` | **pasa**: un bloque `@@ -799,0 +800,5 @@`; 0 borrados |
| 14 | `check` de las otras unidades | — | no se corrió |

## Lo pedido para la ronda 2, comprobado ejecutando

- **F-01, cerrado.** `identidad.sh` con el doble y un retardo del `port-forward`: 0,2 s → rc 0; 0,5 s → rc 0; 3 s → rc 0; 9 s → rc 0 (10,4 s); 12 s → rc 2 en 11,5 s; uno que nunca abre → rc 2 en 11,3 s, sin colgarse. 0 procesos sobrantes.
- **F-02, cerrado en lo pedido.** El selector `name=keycloak` coincide con el render. 20 mutaciones, una a una, contra `test_kind_guide.py` y `test_kind_inventory.py`: mueren las seis de la ronda 1 y diez nuevas de la misma clase (`browser_launch_error` 2→1; contexto inexistente 2→3; sin `--delivery` 3→2; selector `case-worker`→`case`; 23:00→23:30 UTC; (17:00 UTC)→16:00; 02:40→02:10; `OOMKilled` 137→139; `--settle-timeout` 1 800→900; `--operator-timeout` 3 600→7 200). El arreglo es general para códigos, horas UTC, valores de opciones, selectores y nombres de pod. Lo que sobrevive está en F-04.
- **F-03, cerrado** (leído): la advertencia 1 coincide con el experimento de la ronda 1.
- **F-05, cerrado.** `estado-final.sh` con el doble: `connection refused`, `Forbidden` y `TLS handshake timeout` dan rc 2; `NotFound`, rc 1; con las cinco caídas, rc 2 y ningún «FALLA F22».
- **F-06, cerrado** (grep): `humo flujo` lleva `--delivery` en la guía, el inventario y las plantillas; F4 paso 3 pide esperar 30 s.
- **F-04, guion.** `arranque.sh` lee `linkerd-cni` aunque no se pida y marca la bóveda reiniciada con cualquier código de salida. Pero ver F-01 de abajo.

## Hallazgos

### F-01 · ROJO · `docs/kind/arranque.sh:42-46` y `paso-18-kind.md:106` · La puerta de «Después de reiniciar la máquina» no se puede pasar: `arranque.sh vault` sigue en 1 después de volver a sembrar
El guion marca la bóveda cada vez que `restartCount > 0`, aunque ya se haya resembrado. El arbitraje pedía marcar «un pod de la bóveda que se reinició **después de la siembra**». Con el doble: un `vault-0` con `restarts=1` y `exitCode 255` da `rc=1`. La prueba (`test_kind_scripts.py:258-259`) muestra que solo vuelve a 0 con `restartCount` 0, es decir, con un pod nuevo. Tras un reinicio de kind el objeto del pod se conserva y el contador no baja (deducido, no medido). Borrar `vault-0` no es salida: está fuera de la lista cerrada y vaciaría otra vez la bóveda.

La guía choca con eso: el paso 7 (`:106`) exige `arranque.sh vault … en 0` como puerta de F0 y dice «no sigas»; K-05 (`:247`) y la puerta de F0 (`:250`) dependen de la misma lectura. Tras cualquier reinicio de la máquina, el operador que sigue la guía se queda parado.

Arreglos cortos: comparar el arranque del contenedor de la bóveda con la siembra (por ejemplo, `startedAt` frente a `refreshTime` de los `ExternalSecret`), o que la puerta acepte esa única línea cuando `identidad.sh` sale 0 y los `ExternalSecret` están sincronizados.

### F-02 · NARANJA · `paso-18-kind.md:96` y `:108` · La guía no aplica la decisión del orquestador: sigue diciendo «pregunta abierta» y no remite al runbook de U1
La decisión fue: órdenes del operador, remitidas al runbook de U1 (U01-T10), sin ampliar la lista cerrada. La guía dice «queda como pregunta abierta para quien mantiene la guía» (`:96`) y «Lo que la lista cerrada no admite (pregunta abierta…)» (`:108`), y no remite al runbook. Paso 4 (MinIO): describe en prosa un Job que fuerza `mc admin user add`, sin manifiesto ni sitio adonde acudir. Paso 1 (inotify): dice que se midió 1024 pero remite a `install.md`, que pedía 512. La lista de lo medido sí es fiel al arbitraje.

### F-03 · AMARILLO · `paso-18-kind.md:106` · «la lista de abajo» se refiere a la de arriba

### F-04 · AMARILLO · `tests/unit/test_kind_guide.py:368-412` · Cifras sin atar
Sobreviven cuatro mutaciones: `rt2_latency ≤ 1 800 s` → 900 s (`:652`); `2 000 / 10` → `/ 20` dentro de la fórmula (`:502`); «≈ 150 s» del lote → 15 s (`:588`); «bias cada 15 min» → 5 min.

### F-05 · AMARILLO · `docs/kind/humo.py:9` y `:418` · `--delivery`
El texto de ayuda dice `humo.py flujo` sin `--delivery`, y el valor por omisión `reference-model/.out` es relativo: dentro de la imagen da 2.

## Tareas candidatas
- U1: el runbook de recuperación debe traer el manifiesto del Job que reescribe las claves de MinIO y el valor de inotify que se aplica.

```
VEREDICTO: NO-VERDE
ROJO|system-verification/docs/kind/arranque.sh:42-46; paso-18-kind.md:106|arranque.sh vault queda en 1 tras resembrar (restartCount no baja): la puerta del paso 7 tras un reinicio es inalcanzable
NARANJA|paso-18-kind.md:96,108|la guía sigue diciendo «pregunta abierta» y no remite al runbook de U1; el paso de MinIO no deja al operador saber qué ejecutar
INFORME: revisiones/U12-T06/ronda-2.md
```
