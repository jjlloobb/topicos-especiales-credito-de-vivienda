# Ronda 1 — U10-T04

VEREDICTO: NO-VERDE

No hay ningún ROJO. Los nueve criterios pasan con mis propias corridas y las tres demos que pasan por la SPA (D1, D2 y el flujo base) llaman a las rutas reales del BFF. Bloquea un solo NARANJA (F-01): el filtro de fecha de la bandeja manda una forma que el BFF real rechaza. Con RL-2 decide el orquestador. Los demás hallazgos son AMARILLO.

Rama `tarea/U10-T04` en `8ed696f`. El hash de la tarea es `381a3260…`, coincide. `git diff --stat origin/main...HEAD -- console/bff/src contracts identity-edge` sale vacío.

## Criterios de aceptación, verificados por mí (todo en serie, desde `vectra-risk/`)

| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | `npm run -w console/spa test -- views/cases` | pasa: 50/50, se imprime la semilla, 17,9 s (carga 7,6 a 8,5) |
| 2 | `npm run -w console/spa test -- views/governance views/bias` | pasa: 75/75 (carga 10,9). Rojo primero reproducido: con `cro` en `get_freeze`, falla «/congelamientos/:freezeId: roles de get_freeze» |
| 3 | `npx playwright test -c console/spa/playwright.config.ts tests/e2e tests/csp tests/a11y --project=chromium --project=firefox` | pasa: 54 passed, 0 saltadas, 6 min 10 s (carga de 18,6 a 24,5). Foco: Chromium 843 ms, Firefox 532 ms |
| 4 | build + los dos `grep` + `size-limit` | pasa: 164,75 kB con gzip (límite 256 kB); `dist/index.html` sin código en línea |
| 5 | `npm run -w console/spa test -- --coverage` | pasa: 384/384. `stepup` y `decision-validation.ts` al 100 % de ramas; el total da 95,46 % |
| 6 | lint, typecheck, las suites de U10-T03, `forbidden_phrases`, el `grep` enmendado y la PoC en dos navegadores | pasa. El `grep` solo encuentra `src/auth/loginStateStorage.ts:6`; la PoC da 10 passed |
| 7 | el comando del CA tal cual | imprime 7, 4, 18, ninguna línea VACIO y OK; `src/version` conserva `.gitkeep` |
| 8 | `test_traceability.py --unit console --all` | pasa: el primer `grep` no imprime nada y el conteo da **15**, los mismos 15 que lista la tarea. **No corrí la base**: me negaron el permiso para extraer `origin/main` dentro del worktree. Fuera de `console` el diff solo agrega texto, así que no puede crear fallos nuevos |
| 9 | `make -C console check`; `make -C contracts check`; `npm audit --audit-level=high` | `console`: rc=0 en 7 min 15 s (carga de 16,9 a 11,1). `contracts`: rc=2 solo por `bench_gate`, con `derive` p99 = 2,669 ms frente a 2,0 bajo carga 9 a 13. Aislado, `make -C contracts bench` da rc=0 con p99 = 0,539 ms, y `openapi` + `generate` + `git diff --exit-code` dan rc=0. `audit`: rc=0. `test_links.py`: rc=0 |

**Prioridad 1, las demos frente al BFF real.** Comparé cada función de `src/api/endpoints.ts` con `PASSTHROUGH` de `console/bff/src/console_bff/routes.py` y con los modelos de U0. Coinciden ruta, método y cuerpo:
- `frozen-resolution` manda `{action, justification}`, igual que `FrozenResolutionIn`.
- `decision` manda el `DecisionIn` real.
- `explanation-views` va sin cuerpo.

El BFF omite los campos nulos (`app_factory.py:293,320`, `exclude_none=True`). Revisé todos los accesos de las vistas:
- Todos los campos opcionales usan `== null` o `??`: `recommendation`, `decision`, `credit_status`, `free_text`, `rate`, `aggregate`, `model_aggregate`, `resolution`, `validation_report` y `total`.
- Los `=== null` que quedan comparan valores ya normalizados.
- La forma de `implicated` coincide con la que produce U9 (`bias-monitoring/src/vectra_bias/context.py:120`). `data_sources` cae a JSON si cambia.

No encontré ningún desajuste que rompa D1, D2 ni el flujo base. El único desajuste está en un filtro que ninguna demo usa (F-01).

**Prioridad 2, los dos defectos de U10-T03.**
- (a) Ni el flujo ni la máquina de estados cambian: solo se espera a `accept` antes de devolver `ok`. Como efecto, un fallo de `storeUser` ahora da `failed` en vez de un `ok` silencioso. `src/stepup/**` sigue al 100 % de ramas.
- Maté (a) en `oidc.ts` (`void accept`): fallan los 2 casos nuevos de `oidc.test.ts`.
- Maté (a) en `wiring.ts` (`void acceptStepUp`): las 384 pruebas unitarias siguen pasando (ver F-04), y las 4 pruebas e2e de «resolver» fallan (2 por navegador).
- (b) Borré el `<meta>` de `index.html`: fallan los 4 recorridos de CSP con `style-src-elem`. El truco se apoya en un detalle interno (`STYLE_ID` en `react-aria/dist/private/interactions/usePress.mjs:103,584`), pero la prueba de CSP lo protege (F-03).

**Prioridad 3, PBT-U10-04.** El oráculo está aparte, en `tests/property/views/cases/decision.test.ts`, sin importar nada de la implementación, y es fiel al de `test_decision.py:59-75`. La prueba exige las 18 filas leídas del archivo de Python.
- Pasa con las 5 semillas que elegí: 11, 4242, 987654, 20261112 y 31337.
- Mutaciones, las tres muertas:
  - `>` cambiado a `>=` en el límite de 2000: muerta por un contraejemplo de 2000 caracteres.
  - U+0085 quitado de `PY_SPACE`: muerta.
  - `sigue` siempre coherente: muerta por un contraejemplo.

**Prioridad 4, CSP y accesibilidad.**
- La cabecera se lee de `routes.yaml` tanto en `vite.e2e.config.ts` como en `csp.spec.ts`.
- El servidor es `vite build` + `vite preview`.
- Una violación real se detecta: con `setAttribute("style")` dentro de `Models.tsx` fallan los recorridos de `ingeniero_riesgo` y `cro` (`style-src-attr`).
- El foco en Chromium pasó 5 de 5 con `--repeat-each=5` (carga de 21 a 23,5): 885, 893, 368, 240 y 387 ms. No es intermitente, pero hay poco margen.

**Prioridad 5, desviaciones.**
- `.size-limit.mjs` es correcto: las únicas claves `src/views/` del manifiesto son entradas dinámicas, y el cierre estático de `index.html` no contiene vistas. Medí aparte todo el JavaScript alcanzable, vistas incluidas: 175,8 KiB con gzip.
- `testTimeout` de 20 s: la prueba más lenta es la PBT-U10-05 de U10-T03, con 9,4 s bajo carga 28. No esconde ningún cuelgue.
- `routeTemplate` está bien conectado en `wiring.ts`.

**Prioridad 6, rutas por rol.** La tabla se compara con C03 leído de `component-methods.md`. `BiasDashboard` lleva el marcador (`entry:false`), y la e2e cuenta cero solicitudes al BFF en «sin acceso».

## Hallazgos

### F-01 · NARANJA · `console/spa/src/views/cases/filters.ts:62-63` · El filtro de fecha de la bandeja da 422 contra el BFF real
`toQuery` manda `created_from: "<día>T00:00:00-05:00"`. El BFF valida la consulta con `CaseFilter` (`app_factory.py:270-284`, `model_validate(strict=False)`), y `Timestamp` exige UTC (`contracts/.../models/base.py:33-36`):
```
CaseFilter.model_validate({'created_from':'2026-11-01T00:00:00-05:00'}, strict=False)
-> Value error, timestamp_not_utc
```
En kind, cualquier filtro «desde» o «hasta» de la bandeja (BR-U10-10, «fecha de creación») sale como `validation_error`. Las pruebas no lo ven:
- `tests/unit/views/cases/cases-inbox.test.tsx:60-61` fija justamente esa forma con `-05:00`.
- La e2e no usa el filtro de fecha.

Ninguna demo lo usa, por eso no es ROJO. El arreglo es convertir el día de Bogotá a UTC con `Z` (`<día>T05:00:00Z`, y `<día+1>T04:59:59Z` para el tope) y agregar una prueba que valide la consulta contra `CaseFilter` o contra el BFF de la e2e.

### F-02 · AMARILLO · `vite.config.ts:49` · El 80 % de ramas se mide sobre el total, no por archivo
Por archivo, varios archivos quedan bajo el 80 %:
- `ResolveFrozenDialog.tsx` (el diálogo de D2): 78,57 %, línea 59, el cierre por `onOpenChange`.
- `ApiProvider.tsx`: 50 %.
- `endpoints.ts`: 50 %.
- `Layout.tsx`: 75 %.

El diseño viene de U10-T03 y el CA pasa, pero el Paso 16 habla de «umbrales por archivo».

### F-03 · AMARILLO · `index.html:10`, `tests/unit/build-config.test.ts:44` · El `<meta>` depende del id interno de react-aria
La prueba unitaria solo comprueba el HTML y el CSS, no que react-aria siga usando `react-aria-pressable-style`. Hoy la red real es la CSP en e2e, y lo comprobé quitando el `<meta>`. Sería más barato leer la constante desde `node_modules/react-aria/dist/private/interactions/usePress.mjs` en la prueba unitaria.

### F-04 · AMARILLO · `src/wiring.ts:79` · La mitad del arreglo (a) que está en `wiring` solo la cubre la e2e
Con `void acceptStepUp` las 384 pruebas unitarias siguen pasando, y solo `views.spec.ts` (los 2 casos de «resolver») lo detecta.

### F-05 · AMARILLO · `filters.ts:10`, `endpoints.ts:60` · Literales en puntos de decisión
- `KNOWN_CHANNELS = ["web","manual"]` limita el filtro a dos canales mientras `channel` es texto libre (`Str40`). Ya está como candidata en `CANDIDATAS.md`.
- `page_size: 100` en `listModels` recorta en silencio cuando hay más de 100 modelos.

### F-06 · AMARILLO · `tests/e2e/tour.ts` · El recorrido de CSP y axe de `cumplimiento` no pasa por `/modelos`
Con el estilo en línea dentro de `Models.tsx`, el recorrido de `cumplimiento` pasó, a pesar de que ese rol tiene la vista. Los de `cro` e `ingeniero_riesgo` sí la cubren.

## Tareas candidatas (defectos reales fuera de alcance)
- `contracts` `bench_gate`: `derive` p99 superó 2,0 ms bajo carga 9 a 13 (2,669 ms). Aislado da 0,539 ms. El diff no toca Python de U0.
- CA-8: correr `--all` sobre la base desde una copia limpia de `origin/main`. No pude hacerlo porque me negaron el permiso de extracción.

## Estado del worktree
- Mutaciones: 3 en `decision-validation.ts`, 1 en `routes.ts`, 1 en `oidc.ts`, 2 en `wiring.ts` (una para la suite unitaria y otra para la e2e), 1 en `index.html` y 1 en `Models.tsx`. Todas deshechas con `git checkout --`.
- Al terminar, `git status --short` sale vacío y HEAD sigue en `8ed696f`.
- Mis logs temporales (`console/spa/.rev-u10t04/*.log`) están borrados. Los `.ca*.log` ignorados que quedan son del codificador.

## Rutas de transcripciones largas
- Bitácora del codificador: `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u10-t04/vectra-risk/bitacoras/U10-T04.md`
- Mis logs se borraron al terminar, como pediste. Las cifras de arriba son las de mis corridas.

```
VEREDICTO: NO-VERDE
NARANJA|console/spa/src/views/cases/filters.ts:62-63|El filtro de fecha de la bandeja manda -05:00 y el BFF real responde 422 (timestamp_not_utc)
AMARILLO|console/spa/vite.config.ts:49|El 80 % de ramas se mide sobre el total; ResolveFrozenDialog 78,57 %, ApiProvider, endpoints y Layout por debajo
AMARILLO|console/spa/index.html:10|El <meta> depende del STYLE_ID interno de react-aria; solo lo protege la CSP e2e
AMARILLO|console/spa/src/wiring.ts:79|El await de acceptStepUp solo lo cubre la e2e, no las pruebas unitarias
AMARILLO|console/spa/src/views/cases/filters.ts:10|Literales KNOWN_CHANNELS y page_size 100
AMARILLO|console/spa/tests/e2e/tour.ts|El recorrido de cumplimiento no visita /modelos
INFORME: revisiones/U10-T04/ronda-1.md
```
