# Ronda 1 — U00-T06

VEREDICTO: NO-VERDE

No hay ningún ROJO. La elección del caso (c) es correcta, el workflow sigue fallando y los seis criterios pasan en mis propias corridas. Lo que impide el verde es **un NARANJA**: el guion deja pasar severidades no canónicas (sin severidad, en mayúsculas o desconocidas). Hay además cinco AMARILLOS.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | La auditoría termina en 0 (caso c) | `npm ci && npm audit --audit-level=high`; `uv run python contracts/tools/npm_audit.py`; el mismo con `--today 2026-12-18` | `npm ci` rc 0. `npm audit` rc 1 con un único GHSA (fc5q-39xc-vjpf) y «11 high». Guion: rc 0, exceptúa los 11 paquetes. Con la fecha caducada: rc 1 («caducada»). **Pasa** |
| 2 | El workflow corre la orden y el lockfile es coherente | el comando del CA-2 | Las líneas 77-81 llaman a `uv run python contracts/tools/npm_audit.py`. `npm ci --dry-run` rc 0 y `git diff --exit-code package-lock.json` rc 0. **Pasa** |
| 3 | `contracts/ts` sigue en verde | typecheck, lint y test | rc 0, con 8 de 8 pruebas. **Pasa** |
| 4 | `console/spa` sigue en verde | `make -C console lint-spa test-spa build-spa` | 1.ª corrida, con la carga entre 146 y 217: rc 2, falló `shell.test.tsx` («cumplimiento: `/` lleva a su inicio…», `expected 0 to be greater than 0`). 2.ª corrida, empezando con carga 9.45: rc 0, 388 de 388 pruebas, `size-limit` 164.85 kB de 256 kB. **Pasa.** El fallo de la 1.ª no puede venir del diff: no toca `console/`, `package.json` ni el lockfile |
| 5 | La excepción es de un solo aviso y caduca | `uv run pytest contracts/tests -q -p no:cacheprovider -k "npm_audit"` (y con `--collect-only`) | Selecciona exactamente los 15 ítems de `contracts/tests/unit/test_npm_audit.py` y deselecciona 561. 15 pasan en unos 9 s. **Pasa** |
| 6 | La unidad sigue en verde | `make -C contracts check` | Empezó con carga 9.24 y acabó en 53.6: **rc 0**. 576 pruebas pasan y el bench queda dentro de umbral (pipeline p95 2.553 ms de 5.0; derive p99 0.672 ms de 2.0). No hizo falta correr el bench sobre la base. **Pasa** |

## Lo verificado
- **¿Era de verdad el caso (c)?**
  - Según `npm view picomatch`, la etiqueta `latest` es 4.0.7 y no hay ninguna versión posterior, ni beta ni de otra etiqueta.
  - En `npm audit --json`, el aviso tiene rango `<=4.0.7`. Para `picomatch`, `fixAvailable` propone `vite@6.2.7` (mayor y a la baja); para `vitest`, la 3.1.4, también a la baja.
  - Las últimas versiones de `vite` (8.3.8) y `vitest` (5.1.0) dependen de `picomatch ^4.0.7`, y `tinyglobby` 0.2.17 y `fdir` 6.5.0 también lo arrastran.
  - Conclusión: no hay arreglo (a) y el (b) no basta. **La elección es correcta.**
- **El workflow:**
  - El paso es un `run: |` con el shell por defecto (`bash -e`) y el guion es su última línea, así que si falla, falla el job.
  - No hay `continue-on-error`, `|| true`, `--omit=dev` ni `--audit-level`. La línea de `pip-audit` no cambia.
  - Cuando corre el guion, el job ya ha hecho `npm ci` y `uv sync`, tiene node 22 y trabaja en el directorio `vectra-risk`.
  - No hay `.npmrc` que altere la auditoría.
- **Ataques al guion** (copia en el scratchpad, JSON fabricados por mí):
  - Mueren (dan rojo):
    - otro aviso alto en otro paquete;
    - otro aviso alto en el propio `picomatch`;
    - un aviso crítico;
    - un paquete que depende de `picomatch` y además de otro aviso alto, tanto directo como transitivo;
    - el aviso exceptuado sin URL (solo id), con `/` final o en minúsculas;
    - una cadena colgante sola;
    - `via` como cadena o como objeto (no lista);
    - JSON vacío o inválido, `{}`, `{"error"}`, `error` junto a `vulnerabilities`, formato v1;
    - `npm` ausente (traza, rc 1), rc 127 con salida vacía, avisos de npm impresos antes del JSON;
    - el día siguiente a la caducidad;
    - fechas con zona horaria (argparse sale con rc 2).
  - Dan verde:
    - el mismo día de caducidad (correcto: es inclusiva);
    - los casos del F-01;
    - los casos del F-03, que exigen una salida que npm no emite.
- **Mutaciones:**
  - Las cuatro pedidas mueren:
    - quitar la caducidad: 2 pruebas fallan;
    - aceptar cualquier GHSA: 5 fallan;
    - tratar el error de npm como verde: 3 fallan;
    - ignorar `critical`: 1 falla.
  - También mueren:
    - JSON inválido tratado como verde;
    - la caducidad desplazada un día en cualquiera de los dos sentidos;
    - quitar la recursión transitiva;
    - quitar la condición `not high`;
    - que `main` devuelva siempre 0;
    - `--omit=dev` en la llamada a npm.
  - Sobreviven:
    - quitar `or "error" in report`;
    - que una salida vacía de npm se tome como `{"vulnerabilities":{}}`;
    - usar la fecha local en vez de UTC;
    - mover `EXEMPT_UNTIL` a 2027.
  - Las pruebas no llaman al registro ni ejecutan el `npm` real: lo simulan con monkeypatch o leen el JSON de un archivo.
- **La bitácora:**
  - Es cierto que `picomatch` no llega a la imagen final. El `Dockerfile` tiene dos etapas, la final es nginx y solo copia `dist/`. Además, `grep picomatch|extglob` sobre `dist/` no encuentra nada y no hay uso de glob en `console/spa/src` ni en `contracts/ts/src`.
  - Una afirmación es inexacta: la del F-02.

## Hallazgos
### F-01 · NARANJA · vectra-risk/contracts/tools/npm_audit.py:51-53 · El guion deja pasar severidades no canónicas
`BLOCKING` es una lista de lo que bloquea, no de lo que se permite. Esto da **verde**:
- un paquete con severidad `"High"`, `"CRITICAL"`, `"severe"` o sin severidad: se descarta en la línea 51;
- un segundo aviso dentro de `picomatch` con severidad `"Critical"`, desconocida o ausente: el filtro `high` de la línea 52 lo saca de `others` y el paquete queda exceptuado.

No lo marco ROJO porque npm no produce estas entradas: el registro devuelve severidades en minúsculas. Además, el `exit-code.js` de npm (`severities.has(sev)`) ignora igual las severidades desconocidas, así que el guion no es más débil que `npm audit --audit-level=high`.

Aun así, es una puerta de seguridad: debería bloquear todo salvo `info`, `low` y `moderate` en minúsculas, también por aviso. Ninguna prueba cubre el caso. Si el orquestador aplica al pie de la letra la regla «severidades en otra capitalización… ningún verde indebido», puede subirlo a ROJO.

### F-02 · AMARILLO · vectra-risk/bitacoras/U00-T06.md (sección «Elección: (c)», punto (b)) · Afirmación inexacta
Dice que ninguna versión de `size-limit` evita `picomatch`. No es así: `size-limit` 14.3.0 solo depende de `lilconfig` y `nanospinner`, y `@size-limit/file` 14.3.0 no tiene dependencias. Subirlos quitaría unas 3 de las 11 entradas, pero `vite` y `vitest` seguirían, así que la conclusión (c) se mantiene.

### F-03 · AMARILLO · vectra-risk/contracts/tools/npm_audit.py:39-40,51 · La excepción no se ata a `picomatch`
- La excepción se identifica solo por el último segmento de la URL: no se comprueba el host ni que el paquete sea `picomatch`.
- Una `via` colgante junto a `picomatch` da verde (`x: via ["picomatch","ghost"]`).
- Si el aviso sube a `critical`, sigue exceptuado.

npm no produce nada de esto hoy.

### F-04 · AMARILLO · vectra-risk/contracts/tests/unit/test_npm_audit.py · Mutantes que sobreviven
Sobreviven los cuatro mutantes listados arriba. Ninguno da verde con un JSON que npm emita hoy, pero ninguna prueba fija la ruta de npm con salida vacía ni el caso de `error` junto a `vulnerabilities`.

### F-05 · AMARILLO · vectra-risk/contracts/tools/npm_audit.py:76-77 · Errores sin mensaje
Una raíz JSON que no es un objeto, o `npm` ausente, acaban en una traza (rc 1) en vez de en un mensaje. El resultado es seguro, pero confuso en la CI.

## Tareas candidatas (defectos reales fuera de alcance)
- `console/spa/tests/unit/views/governance/shell.test.tsx` («cumplimiento: `/` lleva a su inicio…») es inestable con la máquina cargada. Falló con carga de 146 a 217 y pasó con carga 9.45, sin cambios de código entre medias.
- Subir `size-limit` y `@size-limit/file` a 14.3.0 para que dejen de arrastrar `picomatch`.

## Estado final del worktree
`git status --short` está vacío y HEAD sigue en `75408b5`. Solo quedan cachés ignoradas (`node_modules`, `.venv`, `dist/`, `benchmark.json`, `.coverage` y otras). He borrado el directorio del scratchpad con prefijo `rev-u00t06-`. No he tocado el clúster.

```
VEREDICTO: NO-VERDE
NARANJA|vectra-risk/contracts/tools/npm_audit.py:51-53|severidad sin, en mayúsculas o desconocida (paquete o aviso junto al exceptuado) da verde; usar lista de permitidos info/low/moderate y probarlo
AMARILLO|vectra-risk/bitacoras/U00-T06.md (Elección (c), punto b)|size-limit 14.3.0 no usa picomatch; la conclusión (c) se mantiene
AMARILLO|vectra-risk/contracts/tools/npm_audit.py:39-40,51|excepción por último segmento de URL, sin atar a picomatch; via colgante con picomatch da verde
AMARILLO|vectra-risk/contracts/tests/unit/test_npm_audit.py|sobreviven 4 mutantes: error junto a vulnerabilities, salida vacía de npm, fecha local, EXEMPT_UNTIL en 2027
AMARILLO|vectra-risk/contracts/tools/npm_audit.py:76-77|raíz JSON no objeto o npm ausente acaban en traza, no en mensaje
INFORME: revisiones/U00-T06/ronda-1.md
```
