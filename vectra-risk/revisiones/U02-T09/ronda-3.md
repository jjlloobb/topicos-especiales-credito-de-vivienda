# Ronda 3 — U02-T09 (head 4c0bd7a)

VEREDICTO: VERDE

Corrí los siete criterios, con CA-6 y CA-7 en serie, y todos pasan. Los hallazgos de la ronda 2 están resueltos en el código y mis dos sondas lo confirman. No queda ningún ROJO ni NARANJA. Quedan tres AMARILLO, ninguno bloquea. El worktree quedó limpio.

## Criterios de aceptación, verificados por mí
| # | Comando (desde `vectra-risk/`) | Resultado |
|---|---|---|
| 1 | `route_gen.py --check && HYPOTHESIS_PROFILE=ci pytest tests/property/test_routes_*.py -q` | pasa: check rc=0, 13 passed en 139 s |
| 2 | `make -C identity-edge schemas-gateway kubeconform-gateway` | pasa: 32 esquemas, 28/28 válidos en cada entorno |
| 3 | `make -C identity-edge policy-gateway && pytest test_route_gen.py -q` | pasa: conftest 4488 y 27×3, pytest 278 passed |
| 4 | `pytest test_route_gen.py -q -k intake` | pasa: 11 passed |
| 5 | `pytest test_route_gen.py -q` | pasa: 278 passed |
| 6 | `install-tools.sh && charts.sh && make -C platform check-tools` | pasa: rc=0. Corrió solo, antes que todo lo demás |
| 7 | `uv sync --frozen && make -C identity-edge check && make -C platform check-local` | pasa: rc=0, 1800 y 619 passed, 210 Markdown sin enlaces rotos, sin pruebas omitidas. Corrió solo, después de CA-1 |

## Hallazgos de la ronda 2, comprobados en el código
- **F-06 / D-6: resuelto.**
  - `routes.yaml` deja `closed_policy.errors: [404]`.
  - En `generated/{kind,staging,prod}`, la política `closed` solo tiene las claves `mergeType`, `responseOverride` y `targetRefs`, y su único override es el 404.
  - El oráculo lo lee del diseño con `closed_errors()`, y hay una alteración «declara 429» que cambia lo esperado.
  - La regla nueva `closed-no-rate-limit` está en `gateway.rego`, con dos casos que fallan: `declares-429` y `declares-rate-limit`.
  - BR-U2-10 e INF-U2-10 dicen lo mismo.
- **AMARILLO-1: resuelto.**
  - La prueba de alteraciones del diseño ya no atrapa excepciones: si el lector falla, la prueba falla. Ahora tiene 48 casos.
  - Repetí `alt.py`: las 48 alteraciones cambian lo esperado y ninguna lanza una excepción (antes eran 5).
  - Repetí `chan.py`: si cambio solo la columna de autenticación a `canal`, el claim y el contador de intake dicen los dos `canal`.
  - Ya no están en el oráculo `"channel"`, `["GET","HEAD"]`, el mapa `closed_profile`, `(404, 429)` ni `"/federate"`+`GET`.
- **AMARILLO-2: resuelto.** La candidata del `Retry-After` de `/auth/**` ya no está en `CANDIDATAS.md`.

## Hallazgos nuevos (todos AMARILLO, no bloquean)
1. **`routes.yaml:192` (regla `federate`) — cambio de comportamiento que nadie pidió.** El codificador quitó `methods: [GET]`, con lo que `/federate` con F09 habilitada acepta cualquier método. También quitó de la prueba el `POST /federate → 404`. Lo hizo para no escribir `GET` a mano en el oráculo. Es coherente con §4, que no fija el método de F09, y no tiene efecto hoy porque F09 está deshabilitada en los tres entornos. Pero una restricción se relajó solo para que el oráculo quedara limpio. Si el usuario quiere «solo `GET`» en F09, tiene que escribirlo en §4.
2. **`tests/strategies/gateway_design.py:496,502` — dos lectores que en el fondo devuelven valores escritos a mano.** `federate_path()` comprueba que la fila existe y devuelve el literal `"/federate"`. `closed_errors()` elige entre `[404, 429]` y `[404]` según aparezca una frase. Si el diseño cambia, los dos fallan a la vista, no en silencio. Además, el oráculo escribe a mano el perfil de cada ruta (`response_headers("api")` y similares) en vez de leerlo de la fila; eso sí lo compara con el diseño PBT-U2-05.
3. **`routes.yaml:67` — `closed_policy.retry_after: "1"` ya no se usa.** Sin el 429, ese valor no aparece en ningún manifiesto.

## Regresiones buscadas
- `CANDIDATAS.md` solo pierde la entrada resuelta.
- En lo generado, el único cambio es que desaparecen los 429 de `closed`.
- `platform/` no cambió en esta ronda.
- Las mutaciones de conftest pasan las 278 pruebas.

Los logs de esta ronda están en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/`: `r3-ca6.log`, `r3-ca17.log` (CA-1) y `r3-ca7.log`. Las sondas son `alt.py` y `chan.py`, en la misma carpeta.

No pude escribir el informe porque no tengo herramienta de escritura. El orquestador debe guardar este texto en `vectra-risk/revisiones/U02-T09/ronda-3.md`.

```
VEREDICTO: VERDE
AMARILLO|identity-edge/gateway/routes.yaml:192|La regla federate ya no restringe el método (se quitó GET para limpiar el oráculo; §4 no lo fija y F09 está deshabilitada)
AMARILLO|tests/strategies/gateway_design.py:496,502|federate_path y closed_errors devuelven valores fijos tras comprobar el diseño; el perfil por ruta sigue escrito en el oráculo (lo cubre PBT-U2-05)
AMARILLO|identity-edge/gateway/routes.yaml:67|closed_policy.retry_after ya no se usa sin el 429
INFORME: revisiones/U02-T09/ronda-3.md
```
