VEREDICTO: NO-VERDE

# Ronda 1 — U00-T05

**Nota del orquestador (2026-11-16):** el informe del revisor llegó en inglés; esta es su traducción, sin cambios de contenido. El PR #187 se fusionó en `main` (565ff2c) antes de que la revisión terminara.

El arreglo es correcto y no se encontró ninguna regresión de seguridad. Es NO-VERDE solo por F-01 (NARANJA): la propiedad central, «una llave `use: enc` nunca verifica una firma», no está fijada por ninguna prueba. No hay ROJO. CA-1 a CA-4 pasan con ejecuciones del revisor.

Revisada la punta 7ce2ffb. Pruebas en copias (`git archive`), ya borradas; el worktree quedó limpio.

## Criterios de aceptación, verificados por el revisor (ejecutados)

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| 1 | JWKS con la forma de Keycloak: el token firmado con la llave de firma verifica y la caché queda válida | `uv run pytest contracts -q -p no:cacheprovider -k "jwks"` y `--collect-only` | pasa: 16 passed; el filtro selecciona las 7 pruebas nuevas. Rojo: en main con las pruebas nuevas, 5 fallan con `DependencyUnavailable`/`PyJWKError` |
| 2 | El `kid` de la llave `enc` da 401; sin llave de firma legible el refresco falla (503); un algoritmo no aceptado se rechaza | `-k "jwks or authn"` | pasa: 36 passed. **Ver F-01** |
| 3 | Barrido | `grep -rn -E 'PyJWK\|PyJWKSet\|PyJWKClient\|jwks' --include='*.py'` | pasa: los únicos lectores con PyJWT son `jwks_cache.py` y `oidc.py:607` |
| 4 | `make -C contracts check` y consumidores | en una copia con `npm ci` | `check` rc 0 (ruff, mypy, lint-imports, 561 passed, cobertura 97,85 %, bench, openapi y TypeScript). Unitarias: decision-registry 291, governance 320, scoring-explainability 141, case-management 345, bias-monitoring 259, product-metrics 348, model-serving 132, system-verification 922. console/bff: 226 passed y 1 failed (`test_flows_f10_to_f14…`, que ya falla en main) |

## Sondas de seguridad (ejecutadas, la misma en main y en el PR)
- **Nada que antes se rechazara se acepta ahora.** Token firmado con la llave de firma: aceptado. Token con el `kid` de la llave `enc` (firmado con la privada `enc` o con la `sig`): 401. RS512, PS256, `alg: none` y HS256 con el PEM público: 401.
- Las llaves sin `use` se cargan (correcto: en RFC 7517 `use` es opcional).
- Más estricto que antes (aceptable, AMARILLO A-4): `use: enc` con `alg: RS256` verificaba en main y ahora se ignora; `use: null` y `use: "SIG"` se rechazan.
- `use: sig` con `alg: RSA-OAEP`: se salta, `key_skipped` +1, y las demás cargan.
- `kid` duplicado entre una `enc` y una `sig` (en cualquier orden): gana la `sig`. Una `sig` ilegible no tapa a una buena con el mismo `kid`.
- `keys` ausente, entero, o el documento es una lista: 503. `keys` como dict o cadena, o un elemento que no es objeto: `AttributeError` escapa del manejador, igual que en main (preexistente; candidata).
- **Transiciones:** un JWKS bueno seguido de uno sin llave de firma conserva las llaves en caché hasta el TTL. En main, `keys: []` reemplazaba la caché por una vacía (401 a todo hasta 600 s): el cambio quita una forma de vaciar la caché con una sola respuesta.
- **Arranque con `keys: []`:** ahora 503 (antes 401), con reintento tras los 30 s del freno existente. Correcto: una dependencia que no está lista es un 503.
- `authn.py` no cambia: `ALLOWED_ALGORITHMS = ("RS256","ES256")`.

## Hallazgos
### F-01 · NARANJA · `contracts/tests/unit/test_jwks_cache.py`, `test_authn.py`, `system-verification/tests/unit/test_oidc_flow.py` · El filtro `use != sig` no está fijado por ninguna prueba
Borrando `or item.get("use","sig") != "sig"` de `jwks_cache.py:27`: 36 passed. Borrando `and jwk.get("use","sig") == "sig"` de `oidc.py:605`: 21 passed. Las pruebas pasan solo porque la llave `enc` de prueba es `RSA-OAEP`, que PyJWT no sabe leer. Falta el caso de una llave `use: enc` con un `alg` **legible** (RS256) cuya privada firma el token, esperando 401; main acepta ese token.

### F-02 · NARANJA · `jwks_cache.py:32` · El conteo de `key_skipped` no se prueba
Sustituyendo el incremento por `pass`: 36 passed.

### A-1 · AMARILLO · `oidc.py:606-609` · `_key_for` informa una llave ilegible como «desconocida» y no refresca
### A-2 · AMARILLO · `jwks_cache.py:32` · Un evento por llave en un contador por refresco; dos documentos de diseño (`logical-components.md:40`, `nfr-design-patterns.md:87`) quedan con `ok|error|throttled`. Ningún panel, alerta ni prueba enumera los valores.
### A-3 · AMARILLO · Sin comprobación contra el Keycloak real en las pruebas de integración
### A-4 · AMARILLO · `jwks_cache.py:27` · Comportamiento más estricto no declarado en la bitácora

## Imágenes a reconstruir (leyendo cada Dockerfile)
- **Verifican tokens con `JwksCache` (8):** `decision-registry`, `governance`, `scoring-explainability/scoring`, `scoring-explainability/explainability`, `case-management`, `case-management/core_banking_mock`, `bias-monitoring`, `console/bff`.
- **Empaquetan `vectra_common` sin verificar tokens (5):** `model-serving/predictor`, `model-serving/explainer`, `governance/validation_job`, `product-metrics`, `identity-edge/jobs`.
- **`system-verification`:** no lleva `vectra_common`, pero sí su `oidc.py` arreglado; corre en la estación del operador.
- **No hace falta:** `console/spa` (por este cambio), `identity-edge/keycloak`, `platform/*`.

## Tareas candidatas
- Un JWKS con `keys` que no es lista, o con elementos que no son objetos, hace escapar un `AttributeError` en vez de dar 503 (preexistente).
- `console/bff/tests/unit/test_chart.py::test_flows_f10_to_f14…` falla en main.
- `key_ops` se ignora al cargar llaves (preexistente).
- `jwks_cache.py` está en `do_not_mutate` de `contracts/tools/mutation.py`: la puerta de mutación de la CI no lo mide.

```
VEREDICTO: NO-VERDE
NARANJA|contracts/tests/unit/test_jwks_cache.py + system-verification/tests/unit/test_oidc_flow.py|el filtro use!=sig no está fijado: borrarlo deja 36/36 y 21/21 en verde
NARANJA|vectra_common/jwks_cache.py:32|el conteo de key_skipped no tiene prueba que lo lea
INFORME: revisiones/U00-T05/ronda-1.md
```
