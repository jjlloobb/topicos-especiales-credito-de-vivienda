# Ronda 1 — U01-T20

VEREDICTO: VERDE

No queda ningún hallazgo ROJO ni NARANJA. Corrí yo los cuatro criterios y todos pasan. Las cuatro mutaciones pedidas mueren. Con la entrada del PR #209, `test_kind_profile.py` pasa entero (33 de 33).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | La regla nueva y sus pruebas | `pytest platform/tests/test_kind_profile.py` entero, en una copia del árbol en el scratchpad (con `.venv/bin/python` del worktree, `KUBECONFIG=/nonexistent`, `PATH` sin `/snap/bin`). La CA-2 también lo incluye, en el worktree. | pasa: 33 passed en la copia con la entrada del #209; en el worktree, dentro de los 1090 de la CA-2 |
| 2 | El pytest de `platform` pasa sin la entrada y con ella | El comando de la CI en el worktree, con `platform/.tools` fuera del árbol y devuelto después; carga 4,66 al empezar | pasa: `1090 passed in 347.37s`, rc 0, sin pruebas omitidas (grep `skipped` = 0). Con la entrada solo corrí `test_kind_profile.py`, como pediste: 33 passed (carga 3,96) |
| 3 | El job `policies` (`check` y `check-rendered`) | No lo corrí aparte con la entrada; el despacho no lo pedía. `check` sin la entrada es la CA-4 | pasa sin la entrada (mío); con la entrada solo está la afirmación del codificador |
| 4 | `make -C platform check` | `KUBECONFIG=/nonexistent make -C platform check`, una vez; carga 7,42 | pasa: rc 0, `pass: 54` y `pass: 450`, `fail: 0` |

## Lo verificado
**1. La regla `peak_with_declared()` (`platform/tests/test_kind_profile.py:224-238`).** Hace lo que dice. Cuenta por perfil cuántos huecos tiene `PEAK_INFERENCE_SERVICES` (prod 2, staging 1). Cada entrada declarada consume un hueco de su perfil, y la que no encuentra hueco se suma al pico. Revisé los casos raros:
- **Un `prod` con recursos distintos de los proyectados:** no es posible. `values.schema.json` exige `additionalProperties: false` y solo admite `modelVersionId`, `storageUri` y `profile`; los recursos salen de `profiles.<perfil>`. Quedarse con la entrada proyectada en vez de la declarada no esconde nada.
- **Perfil desconocido (`canary`):** pasa al exceso, helm lo rechaza por el esquema y salta `CalledProcessError`. Falla cerrado.
- **Entrada sin `profile`:** salta `KeyError`. Falla cerrado.
- **`inferenceServices` ausente o `null`:** `.get(...) or []` lo trata como lista vacía y da el pico de hoy (13,7344 GiB).
- **Entradas duplicadas:** consumen huecos como cualquier otra. Si sobran y repiten un id del pico, helm falla por nombre repetido (rojo). En el archivo real, el render de kind ya rechaza ids repetidos.
- **Mezcla `prod` + `staging` + `inactive`:** el `inactive` siempre cuenta de más.

En todos los casos el pico calculado es, por perfil, el mayor entre lo proyectado y lo declarado. Siempre queda por encima o igual a lo que kind declara de verdad. No encontré ningún caso que dé verde con más memoria o CPU de la que cabe en el tope.

**2. La tabla de casos**, reproducida con mis propias listas e ids distintos a los del codificador. Topes: 13,8 GiB, 10,7 CPU y máquina de 14,8157 GiB.

| Declarado | GiB | CPU | Resultado |
|---|---|---|---|
| nada / `null` | 13,7344 | 10,6650 | cabe |
| 1 prod (entrada del #209) | 13,7344 | 10,6650 | cabe |
| 2 prod + 1 staging | 13,7344 | 10,6650 | cabe |
| 3 prod | 14,8125 | 11,1450 | rojo en tope y CPU; cabe en la máquina |
| 2 staging | 14,0039 | 10,7850 | rojo |
| 1 inactive | 14,2734 | 10,9050 | rojo en el tope; cabe en la máquina |
| 2 prod + 1 staging + 1 inactive | 14,2734 | 10,9050 | rojo |

La suma vieja con 1 prod da 14,8125 GiB y 11,145 CPU, las mismas cifras que trae la tarea. Todo coincide con la bitácora.

**3. Rojo primero y mutaciones.** Las corrí en la copia del scratchpad con `-k "declared or declaring or inactive or fit_the or machine"`, que recoge 6 pruebas: las 3 nuevas y las 3 de presupuesto. Las cuatro mutaciones mueren:
- **Volver a sumar (`[*declared, *PEAK]`, igual que `main`):** 2 failed, `test_declared_models_fill…` y `test_declaring_more…`. Rojo primero confirmado.
- **Ignorar lo declarado (`list(PEAK)`):** 2 failed, `test_declaring_more…` y `test_a_declared_inactive…`.
- **No contar el exceso de `prod`:** 1 failed, `test_declaring_more…`.
- **No contar `inactive`:** 1 failed, `test_a_declared_inactive…`.

Las cargas durante estas corridas fueron entre 3,8 y 8,8.

**4. Lo que no debía cambiar.**
- `BUDGET_GIB`, `CPU_BUDGET` y `MACHINE_GIB` no tienen ninguna línea `+` ni `-` en el diff contra `origin/main`.
- `vectra-risk-gitops/values/kind/model-serving.yaml` no aparece en el diff.
- `CANDIDATAS.md` tiene un único bloque `@@ -895,3 +895,6 @@`, con 3 líneas añadidas y ninguna quitada: solo crece al final (897 → 900 líneas).
- `kind_serving_kyverno.py` no suma lo declarado: usa `PEAK` más un `inactive` fijo, y el overlay reemplaza la lista. El codificador hace bien en no tocarlo.

**5. El caso real.** Copié el árbol (71 MB, sin `.venv` ni `.tools`) y sustituí `inferenceServices: []` por la entrada del #209. Ahí `test_kind_profile.py` dio `33 passed in 150.06s`.

## Hallazgos
### F-01 · AMARILLO · `bitacoras/U01-T20.md`, sección CA-4 · CA-4 no se corrió «una vez al final»
La bitácora reutiliza el `make check` de la CA-3 («No se corrió una tercera vez»). Además, para la CA-1 del archivo entero cita una corrida anterior, hecha con la prueba de 3 `prod` todavía con el id repetido. La CA-2 de 1090 sí cubre el código final, y mis propias corridas de la CA-1 y la CA-4 pasan, así que esto no cambia el resultado. Es solo higiene de la evidencia.

### F-02 · AMARILLO · `test_kind_profile.py`, `test_declared_models_fill…` · el caso del #209 solo comprueba memoria
La aserción explícita del caso del #209 mira solo GiB. La CPU queda cubierta de forma indirecta por el bucle con `[PROD]`, así que no se pierde nada.

Aparte: `ruff format --check` marca el archivo, pero ya lo marcaba en `origin/main`. No es de este diff.

## Tareas candidatas (defectos reales fuera de alcance)
- U1/U6: con esta regla un modelo `inactive` siempre cuenta encima del pico y pone el presupuesto en rojo (14,27 GiB frente a 13,8). El primer PR de `promotion-tool` que pase M1 a `inactive` volverá a romper `tests` y `policies`, aunque el estado real (1 prod + 1 inactive) cabe de sobra. Lo que la tarea pedía era que cuente de más, y así lo hace. Pero DECISIONES-LOOP §7 no dice dónde cabe el `inactive` del rollback de D2, y `kind_serving_kyverno.py` sí lo prevé. Conviene decidir si el pico incluye ese `inactive` antes de la segunda promoción.

## Estado final del worktree
- HEAD `ffe4755`; `git status --short` vacío.
- `platform/.tools` (enlace) devuelto a su sitio y `platform/.charts` intacto.
- `make check` escribe su informe en `.tools/integration/report.txt`, que apunta al checkout principal. Al codificador le pasa lo mismo.
- Copias del scratchpad (`rev-u01t20-*`) borradas.
- No corrí nada contra el clúster.

## Rutas de transcripciones largas
- Ninguna. Borré los logs junto con el scratchpad; las cifras clave están arriba.

```
VEREDICTO: VERDE
AMARILLO|bitacoras/U01-T20.md (CA-4)|CA-4 reutiliza la corrida de CA-3 en lugar de correrse una vez al final
AMARILLO|platform/tests/test_kind_profile.py (test_declared_models_fill…)|el caso del #209 solo comprueba memoria de forma explícita
INFORME: revisiones/U01-T20/ronda-1.md
```
