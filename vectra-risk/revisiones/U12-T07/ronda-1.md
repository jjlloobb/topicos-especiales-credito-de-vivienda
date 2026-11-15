VEREDICTO: NO-VERDE

# Ronda 1 — U12-T07

La rama se fusionó en `main` (`656c0b7`, PR #180) mientras se revisaba; el diff revisado es `git diff 656c0b7^1...216082e` (13 archivos, +698 −48). Nada contra `kind-vectra`. Mutaciones en copias. El worktree quedó limpio.

No hay ningún ROJO. **Arbitraje del orquestador (2026-11-15):** F-01 a F-06 se atienden en U12-T08, cuando U01-T13 fije la cifra final del presupuesto.

## Criterios de aceptación, verificados por el revisor

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| 1 | Puerta de la bóveda con el doble | `uv run pytest …test_kind_scripts.py -q -p no:cacheprovider -k vault` | **pasa**: 8 passed. Con el `arranque.sh` de `main` anterior: 1 failed (`test_vault_restarted_and_reseeded_is_a_warning_that_exits_0`) |
| 2 | Sin «pregunta abierta», remite al runbook, los enlaces resuelven | el comando de CA-2 | **pasa**: el `grep` no imprime nada; conteo 22; 612 Markdown sin enlaces rotos |
| 3 | Las cuatro mutaciones de F-04 mueren | `pytest test_kind_guide.py test_kind_inventory.py` → 71 passed; mutaciones repetidas | **pasa** |
| 4 | `make -C system-verification check`, una vez | `/usr/bin/time -v make -C system-verification check` (imagen desde la caché) | **pasa: RC=0** en 31:47. ruff, format, mypy (36 archivos), contratos 11 kept; **1212 passed** (95,80 %), **943 passed** (100 %), **32 passed** (imagen); enlaces. 0 skipped. RSS máximo 780 MB |
| 5 | Kind sin Loki, Tempo ni Alloy, con prueba de mundo cerrado | `grep -n -i -E 'loki\|tempo\|alloy'` y mutaciones | **pasa con un hueco**: F-02 |
| — | Alcance | `git diff --name-only 656c0b7^1...216082e \| grep -E 'src/\|demos/\|Dockerfile\|seccomp/\|platform/'` | **pasa**: ninguno. README: solo la frase de memoria. `CANDIDATAS.md`: un bloque `@@ -806,0 +807,2 @@` |

**La puerta de la bóveda con el doble** (driver propio, sobre una copia):
- **A**, el caso real (`restartCount` 21, 58 ExternalSecret Ready con `refreshTime` posterior al arranque): rc 0 y «AVISO … resembrada».
- **B**, contenedor arrancado después de la última sincronización: rc 1. **C**, un ExternalSecret con `SecretSyncedError`: rc 1. **D**, lista vacía: rc 1. **E y F**, lectura fallida: rc 2.
- Marcas con desfase `-05:00` y `+02:00` y con fracciones: compara bien. Marca ilegible: rc 1. `refreshTime` igual a `startedAt`: 0. Contenedor en `CrashLoopBackOff` sin `startedAt`: rc 1.
- Mutaciones del guion: quitar `refreshed < started` → 3 fallan; quitar `not synced` → 4; quitar `not items` → 3. Sobrevive cambiar `reason == "SecretSynced"` por `True` (inocuo).

**¿Es alcanzable en el caso real del 2026-11-14?** Por lo leído, sí; no está medido. Ningún ExternalSecret del repositorio usa `refreshPolicy`; `refreshInterval` vale `1h` donde se declara y el resto usa el valor por omisión de ESO; `seed-vault.sh` anota todos con `force-sync` (`annotate … --all -A`, línea 30), lo que obliga a ESO a reconciliar y fija `refreshTime` (documentación de ESO, no medición). Si apareciera un `CreatedOnce`, la puerta quedaría en 1 sin salida; hoy no hay ninguno.

**Remisión al runbook** (leído contra `install.md` de `main`): los pasos 1 a 6 enlazan a secciones que existen y dicen lo mismo (inotify 1024 y 1048576; recrear pods en orden; MinIO con 10 usuarios hoy, 12 entonces; Grafana con 512 MiB y `reset-admin-password`; PostgreSQL y Keycloak sin medir). El operador sabe qué ejecutar.

**Las cuatro cifras de F-04:** las cuatro mutaciones y una quinta propia hacen fallar la prueba.

## Hallazgos

### F-01 · NARANJA · `paso-18-kind.md:39,163,243`; `inventario.yaml:47`; `evidence/kind/00-prerrequisitos.md:17,33`; `evidence/cierre-demo.md:33` · La memoria sigue en 11,8 GiB en la guía, el inventario y las plantillas
`grep -rn '11,8' system-verification/docs aidlc-docs/construction/system-verification/evidence` devuelve 7 apariciones. R-4 dice «11,8 GiB de requests en una máquina de 14 GiB»; la línea 163 cita `BUDGET_GIB`, línea 34 (es la 44 y vale 13,9); K-01 en el inventario y sus dos plantillas. Ninguna está atada a `BUDGET_GIB`: volverá a pasar con U01-T12 y U01-T13.

### F-02 · NARANJA · `tests/unit/test_kind_guide.py`, `absent_component_findings` · La prueba de CA-5 deja pasar peticiones de componentes ausentes en un párrafo que ya dice «no instala»
La exención es por línea (en Markdown, un párrafo entero) y solo detecta `name=X`, `sync X` y `get app X`. Inyectado en la línea del paso 13: `port-forward … svc/alloy 12345`, `logs -n vectra-observability deploy/tempo` y `argocd app wait loki --health` **sobreviven**. Mueren `port-forward svc/alloy` en línea propia, `sync loki`, `argocd app sync tempo` y `-l app.kubernetes.io/instance=loki`.

### F-03 · AMARILLO · `docs/kind/arranque.sh:76` · La comparación solo se hace con `restartCount > 0`
Si el pod de la bóveda se recrea, el contador vuelve a 0 y el guion no compara: pod con 0 reinicios, bóveda vacía y ExternalSecret `Ready=True` con `refreshTime` anterior al arranque → rc 0, hasta que ESO refresque (hasta 1 h). Ya estaba así en `main`. Comparar siempre no tiene coste.

### F-04 · AMARILLO · `paso-18-kind.md:42` (R-7) · Dice que `arranque.sh vault` marca el reinicio con cualquier código; ya solo avisa si se resembró

### F-05 · AMARILLO · `arranque.sh:47-49` · Con la lista vacía imprime «1 ExternalSecret no se sincronizaron»

### F-06 · AMARILLO · `test_kind_guide.py`, `runbook_findings` · Los números de paso del runbook que cita la guía no están atados

### README: «14 GiB como mínimo, 16 recomendados»
No es demostrablemente falsa (los requests son reservas, no consumo), pero ya no se sostiene: 13,9 GiB de requests más 1 GiB de la herramienta suman 14,9. La prueba exige el literal (`test_demos_closed_world.py:1181`). Cambiar el mínimo es decisión del usuario.

## Tareas candidatas
- **U1, `seed-vault.sh identity`:** solo fuerza el refresco en `vectra-identity`, `vectra-edge` y `envoy-gateway-system`. Los ExternalSecret de U3 a U11 que leen `identity/clients/*` (en `vectra-app`) fallan tras `seed-vault.sh` y `identity` no los vuelve a anotar: quedan `Ready=False` hasta que ESO reintente. Deducido, no medido. Arreglo: anotar `--all -A` también en `identity`.
- **U1/usuario:** el mínimo de 14 GiB del README y de la guía.
- **U12:** una prueba que falle si aparece un ExternalSecret `CreatedOnce` u `OnChange`.

```
VEREDICTO: NO-VERDE
NARANJA|paso-18-kind.md:39,163,243; inventario.yaml:47; evidence/kind/00-prerrequisitos.md:17,33; evidence/cierre-demo.md:33|la memoria sigue en 11,8 GiB sin atar a BUDGET_GIB en guía, inventario y plantillas
NARANJA|tests/unit/test_kind_guide.py:absent_component_findings|la exención histórica es por línea y solo ve name=/sync/get app
AMARILLO|docs/kind/arranque.sh:76|sin comparar cuando restartCount es 0: pod de la bóveda recreado y vacío da rc 0
AMARILLO|paso-18-kind.md:42|R-7 desfasado
AMARILLO|docs/kind/arranque.sh:47-49|lista vacía informada como «1 ExternalSecret»
AMARILLO|tests/unit/test_kind_guide.py:runbook_findings|los números de paso del runbook citados no están atados
INFORME: revisiones/U12-T07/ronda-1.md
```
