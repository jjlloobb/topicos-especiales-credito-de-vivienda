# Ronda 2 — U00-T06

VEREDICTO: NO-VERDE

Ningún ROJO. Ningún verde indebido sale de una salida que npm pueda emitir. Con el `npm audit --json` real de hoy, el guion da rc 0 (11 exceptuados); con `--today 2026-12-18` da rc 1. Los avisos `low` y `moderate` reales no bloquean. CA-5 y CA-6 pasan en mis corridas.

Lo que impide el verde es **un NARANJA**: F-01 queda cerrado solo a medias. Si un paquete tiene una severidad permitida, el guion ya no mira sus avisos. La tabla del arbitraje pedía bloquear «tanto en el paquete como en cada aviso de `via`».

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | La auditoría termina en 0 (caso c) | `npm audit --json` real; `uv run python contracts/tools/npm_audit.py`; el mismo con `--today 2026-12-18` y con `--today 2026-12-17` | npm: rc 1, 11 `high` de un solo GHSA (fc5q-39xc-vjpf, `<=4.0.7`). Guion: rc 0 y exceptúa 11 paquetes. Con 12-18: rc 1 («caducada»). Con 12-17: rc 0. **Pasa** |
| 1b | Lo bajo no bloquea | lockfile de prueba en el scratchpad (`cookie@0.6.0` low; `follow-redirects@1.15.5` y `esbuild@0.24.0` moderate), con `npm audit --json` real, solo, y mezclado con el JSON real del repositorio | Solo: npm `--audit-level=high` rc 0 y guion rc 0. Mezclado: guion rc 0, y rc 1 con 12-18. Un `high` real ajeno (`postcss@8.4.30`, `nanoid@3.3.7`) mezclado con el real da rc 1. **Pasa** |
| 2 | No se tocan package.json, lockfile ni workflow | `git diff --stat 75408b5..6ab6a4f -- package.json package-lock.json .github/` | Diff vacío. **Pasa** |
| — | `CANDIDATAS.md` solo crece al final | `git diff origin/main..6ab6a4f -- CANDIDATAS.md` (`origin/main` = 32b5d0b = merge-base) | Solo 3 líneas `+` tras la última. **Pasa** |
| 3, 4 | No se repiten (encargo) | — | El diff no toca esos árboles |
| 5 | La excepción es de un solo aviso y caduca | `uv run pytest contracts/tests -q -p no:cacheprovider -k "npm_audit"` (antes, `--collect-only`) | Selecciona exactamente los 50 ítems de `contracts/tests/unit/test_npm_audit.py` (50 de 611, 561 deseleccionadas). 50 passed en 1.18 s. Ese tiempo se explica: son funciones puras con `npm`/`subprocess` simulados y no dependen de estado externo. No hay `skip` ni `xfail`. **Pasa** |
| 6 | La unidad sigue en verde | `make -C contracts check`, una sola vez | Carga 9.06 al empezar y 11.71 al acabar. **rc 0**: 611 passed en 250 s, cobertura 97.85 % (límite 95), bench pipeline p95 0.722/5.0 ms y derive p99 0.313/2.0 ms, `contracts/ts` con 8/8 pruebas. **Pasa** |

## Estado de los hallazgos de la ronda 1
- **F-01 (NARANJA): cerrado a medias.** Ver F-06.
  - Mueren, con la severidad en el paquete: `High`, `CRITICAL`, `severe`, sin severidad y `None`.
  - Mueren, con la severidad en el aviso junto al exceptuado: `Critical`, sin severidad y `severe`.
  - La lista de permitidos funciona mientras la severidad del paquete no esté permitida.
- **F-03 (AMARILLO): cerrado.** Dan rojo:
  - el aviso exceptuado en `critical`;
  - el mismo id en `lodash`;
  - otro host, una `/` final y la URL en mayúsculas;
  - una URL que no es cadena y el nombre `"picomatch "`;
  - una `via` colgante junto a `picomatch`, una `via` que no es lista o es un objeto, y elementos `None` o `3` en `via`;
  - una entrada que no es objeto;
  - una dependencia de `picomatch` con otro aviso alto;
  - una `via` hacia un `picomatch` ausente.
- **F-04 (AMARILLO): cerrado.** Los cuatro mutantes de la ronda 1 mueren:
  - sin `"error" in report`;
  - salida vacía tratada como `{}`;
  - `date.today()` en vez de la fecha en UTC;
  - `EXEMPT_UNTIL` en 2027.
- **F-05 (AMARILLO): cerrado.**
  - `""`, `[]`, `null`, `7` y `"x"` dan un mensaje de una línea y rc 1.
  - Sin `npm` en el `PATH` sale «no se pudo ejecutar npm audit: [Errno 2] …» y rc 1, sin traza.
- **F-02 (AMARILLO): cerrado.** Lo comprobé con `npm view`: `size-limit@14.3.0` depende de `lilconfig` y `nanospinner`, y `@size-limit/file@14.3.0` no tiene dependencias. `picomatch` `latest` sigue en 4.0.7. La corrección está debajo, en «Ronda 2», sin reescribir lo anterior.

## Hallazgos
### F-06 · NARANJA · vectra-risk/contracts/tools/npm_audit.py:69-70 · Una severidad permitida en el paquete tapa los avisos de su `via`
Las líneas 69-70 hacen `if isinstance(vuln, dict) and vuln.get("severity") in ALLOWED: continue`, antes de mirar los avisos. Contra una copia del guion, estos casos dan **verde**:
- `x: {severity:"moderate", via:[{severity:"high"}]}`;
- `x: {severity:"low", via:[{severity:"critical"}]}`;
- por la misma vía, un aviso no canónico (`"HIGH"`, `"Critical"`) bajo un paquete `moderate`.

Hay un caso hermano: `picomatch: {severity:"critical", via:[<aviso exceptuado en high>]}` también queda exceptuado, porque nadie contrasta la severidad del paquete con la de sus avisos.

La tabla del arbitraje pedía que cualquier severidad no permitida bloquee «tanto en el paquete como en cada aviso de `via`», y en este caso el aviso no bloquea.

No es ROJO por dos razones:
- npm calcula la severidad del paquete como el máximo de sus avisos y el registro las devuelve en minúsculas, así que no puede emitir estas entradas.
- El propio `npm audit --audit-level=high` decide igual, por la severidad del paquete.

Es la misma clase que el F-01 de la ronda 1, y con la misma severidad. Arreglo posible: mirar los avisos de todo paquete, sin el `continue` previo, y bloquear si la severidad del paquete es menor que la de algún aviso o no coincide con ella. Ninguna prueba cubre el caso.

### F-07 · AMARILLO · vectra-risk/contracts/tests/unit/test_npm_audit.py · Mutantes nuevos que sobreviven
Lancé 28 mutantes contra el guion nuevo. Mueren 22, entre ellos:
- toda la lista de permitidos: añadir `high` o quitar `info`, `low` o `moderate`;
- volver a la lista de bloqueantes;
- quitar la atadura a `picomatch`, a `high` o a la URL exacta (por sufijo o por contenido);
- quitar la variable `dangling` o ponerla a `False`;
- `<` en la caducidad;
- `OSError` tratado como verde;
- quitar la recursión;
- `main` que devuelve siempre 0.

Sobreviven 6:
- **Quitar `not strong`** (línea 74). Un paquete `high` con `via: []`, o un ciclo `a↔b` sin avisos, pasa a **verde**. Es una regresión de la prueba: en la ronda 1 `test_a_high_package_with_no_advisory_is_red` mataba este mutante. Ahora usa `via:["ghost"]`, que ya bloquea por colgante, así que no ejercita la condición.
- **Saltar las entradas que no son objeto** (línea 69). `x:"high"` da verde.
- **Que la colgante no se propague** desde un subpaquete (línea 46).
- **`.lower()` en el paquete o en el aviso.** Afecta a `Moderate`/`MODERATE`; ninguna prueba usa una severidad baja no canónica.
- **`via` no lista → `[]`.** Es casi equivalente.
- **La raíz que no es objeto pasa a `evaluate`.** También da rc 1, así que es equivalente.

Ninguno da verde con una salida que npm emita.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna nueva. Las tres que se añadieron a `CANDIDATAS.md` son correctas.

## Estado final del worktree
- `git status --short` está vacío y HEAD sigue en `6ab6a4f`.
- He borrado el directorio del scratchpad `rev-u00t06-r2` (copias, mutantes, lockfile de prueba y JSON).
- Todo corrió con `KUBECONFIG=/nonexistent` y `PATH` sin `/snap/bin`. No he hecho nada contra el clúster.
- Hacia fuera solo salieron `npm audit` y `npm view` contra el registro.
- La salida de CA-6 está en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/4ae739e1-8e17-45a7-86d4-a1f29d9f6082/tasks/bidxbgzt2.output`.

```
VEREDICTO: NO-VERDE
NARANJA|vectra-risk/contracts/tools/npm_audit.py:69-70|severidad permitida en el paquete salta sus avisos: moderate/low con aviso high/critical/HIGH da verde; critical con solo el exceptuado high, exceptuado (npm no lo emite)
AMARILLO|vectra-risk/contracts/tests/unit/test_npm_audit.py|sobreviven 6 mutantes nuevos, entre ellos quitar `not strong` (via [] o ciclo sin avisos dan verde; regresión de la prueba de la ronda 1) y saltar entradas que no son objeto
INFORME: revisiones/U00-T06/ronda-2.md
```
