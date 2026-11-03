# Ronda 1 — U02-T08

VEREDICTO: NO-VERDE

Revisé el sha `6742fc8` sobre la base `b9577ff`. El hash de la tarea coincide (`7ae6a12…`). Todo lo corrí en una copia: `git archive 6742fc8` más `platform/.tools`, `platform/.charts` y `.github`, en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/copia`. Al terminar, el worktree del codificador sigue limpio (`git status` vacío).

Los 7 criterios pasan con mis propias corridas. El veredicto es NO-VERDE por dos motivos: un falso positivo que hará saltar `RealmDrift` siempre contra un Keycloak real, y dos vías para esconder cambios.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Aceptación del Paso 6 | `uv run pytest …test_realm_diff.py -q && HYPOTHESIS_PROFILE=ci uv run pytest …test_realm_normalize.py -q` | pasa: 118 passed (6,2 s) y 5 passed (21,9 s; las propiedades tardan entre 2,7 y 8,7 s cada una, no se saltaron) |
| 2 | Reglas de la proyección | `uv run pytest identity-edge/tests/unit/test_realm_diff.py -q` | pasa: 118 passed |
| 3 | Jobs contra Keycloak y Pushgateway falsos | `uv run pytest identity-edge/tests/unit/test_identity_jobs.py -q -rs` | pasa: 125 passed, ninguna omitida |
| 4 | Render y políticas | `make -C identity-edge render-jobs policy-jobs && uv run pytest …test_identity_jobs.py -q -k render` | pasa: conftest 555/555 y 5/5 ×3; pytest 98 passed. Volví a renderizar y sale idéntico a `rendered/` (`diff -r` vacío) |
| 5 | `keycloak-reader` con tres roles | `uv run python identity-edge/tools/realm_lint.py identity-edge/keycloak/realm/realm.*.yaml && uv run pytest …test_realm_lint.py …test_realm_files.py -q` | pasa: 629 passed |
| 6 | Dockerfile y políticas de U1 | `platform/.tools/bin/hadolint identity-edge/jobs/Dockerfile && make -C identity-edge policy-jobs-u1` | pasa: Kyverno `pass: 16, fail: 0` en los 3 entornos; conftest de U1 35/35 y 3/3 por entorno |
| 7 | Regresión | `uv sync --frozen --offline && make -C identity-edge check && make -C platform check-tools` | pasa: `check` termina en 0 con 1411 passed; `check-tools` da `pass: 239, fail: 0` |

En CA-7 agregué `--offline` porque no hay red. La primera vez `check-tools` falló en mi copia porque le faltaba `.github/workflows`. Era un defecto de mi copia, no del diff: al copiar `.github` del mismo sha terminó en 0.

## Hallazgos
### F-01 · NARANJA · identity-edge/tools/realm_diff.py:83-123 y jobs/keycloak_admin.py:156-170 · Un valor por defecto de Keycloak cuenta como deriva
Keycloak crea el client scope `offline_access` con un scope mapping a nivel de realm hacia el rol `offline_access` (`DefaultClientScopes`). `_scope_mappings` lee los scope mappings de todos los client scopes, también los que Keycloak trae solo. Pero `BUILT_IN_NAMES` no tiene entrada para `("scopeMappings",)`, y Git declara `scopeMappings` en los tres realms.

Sonda: `scopeMappings += {clientScope: offline_access, roles: [offline_access]}` sobre `realm.prod.yaml` da `1 ['scopeMappings[offline_access]']`. Con Keycloak real, `vectra_realm_drift` valdrá al menos 1 cada día en los tres entornos y `RealmDrift` (SEV2) estará siempre disparada. Eso contradice INF-U2-09 («Lo que Keycloak agrega por defecto no cuenta») y la primera regla de CA-2.

El Keycloak falso (`strategies/fake_keycloak.py`) no trae este valor por defecto, por eso las pruebas pasan. Hay que barrer los demás niveles anidados que también arrastran entidades propias de Keycloak: `scopeMappings` y `clientScopeMappings` de los built-in.

### F-02 · NARANJA · realm_diff.py:244 · Una clave repetida del lado de Keycloak se pierde sin contar
`kc_by_key = {_key_of(path, e): e for e in kc}`: si dos entidades de Keycloak comparten clave, solo queda una. Sondas:
- una ejecución extra con `priority: 20` en `vectra-level-pwd`, puesta delante de la legítima, da **0**;
- una segunda credencial `otp` (`userLabel: atacante`) en un usuario de staging da **0**.

Las claves que el diseño fija (`clientId`, `name`, `alias`, `username`) Keycloak las mantiene únicas. Las que eligió el codificador no tienen esa garantía. `priority` («única en un flujo», dice el comentario de la línea 24) se puede repetir por el Admin API, y `type` de una credencial también. Lo correcto es que una clave duplicada en Keycloak cuente como diferencia (o que el job falle). Barrer `priority`, `type`, `name` de mappers y la clave `client`/`clientScope`.

### F-03 · NARANJA · realm_diff.py:205-207 y keycloak_admin.py:130 · El flag `builtIn` lo pone el lado auditado
Los flujos «propios de Keycloak» se reconocen por `builtIn is True`, que viene de la misma respuesta que se audita. Sonda: un flujo nuevo `puerta-trasera` con `builtIn: true` da **0**. Además el lector ni siquiera pide sus ejecuciones.

Las otras clases usan listas exactas de nombres, como pide la nota de la tarea. Los flujos deberían usar una lista exacta de alias de 26.8.1 (`browser`, `direct grant`, `registration`, `reset credentials`, `clients`, `first broker login`, `docker auth`, …). Un flujo con `builtIn: true` y un alias fuera de esa lista debería contar.

### F-04 · NARANJA · jobs/signing_key_age.py:25,74 · Literal `RS256` como respaldo, sin prueba
Si el realm no trae `defaultSignatureAlgorithm`, el job supone `RS256`. Ese valor elige la llave y sale como etiqueta `algorithm`. El diseño no fija ese respaldo, y ninguna prueba ejercita el camino (`grep KEYCLOAK_DEFAULT_ALGORITHM` en las pruebas no da nada). Lo coherente con el resto del job, que falla en vez de adivinar, es fallar sin empujar.

### F-05 · AMARILLO · keycloak_admin.py:32 · Lista de roles duplicada
`KEYCLOAK_USER_ROLES` repite `BUILT_IN_NAMES[("roles","realm")]`, con `default-roles-vectra` escrito a mano dos veces. Mejor una sola fuente.

### F-06 · AMARILLO · bitacoras/U02-T08.md:85 · La bitácora promete más de lo que trae
Dice «salidas completas… sha de la rama al final», pero solo trae resúmenes y ningún sha. Mis corridas reproducen exactamente los mismos recuentos (118/5/125/555/98/629/16/1411/239), así que no hay evidencia falsa.

### F-07 · AMARILLO · Plan de pruebas · El rojo primero se cumplió solo en parte
Los jobs, el chart y los values se escribieron antes que las pruebas. El codificador lo declara con honestidad y simula el rojo apartando los módulos. Es la causa de F-01: el Keycloak falso se construyó con las mismas suposiciones que el código.

### Juicio sobre las decisiones declaradas
- **Listas de entidades de Keycloak:** el principio cabe en el diseño («lo que Keycloak agrega por defecto no cuenta»), pero las listas están incompletas (F-01) y los flujos se saltan la regla de usar listas (F-03).
- **`UNREADABLE_FIELDS`:** aceptable. Un `temporary` cambiado se ve igual, como `UPDATE_PASSWORD` en `requiredActions`.
- **Claves anidadas:** el diseño no las fija. La elección es razonable, pero sin control de duplicados (F-02).
- **Empate de prioridad de llaves → falla:** conservador y declarado. Aceptado.
- **Plazos de los CronJobs:** van en `values.yaml` y están declarados. Aceptados. `backoffLimit: 0` está fijo en la plantilla.
- **`check-jobs-rendered`:** sigue el mismo patrón que `check-keycloak-rendered` y cumple la intención de CA-7. Aceptado.
- **Alcance:** el diff solo toca `identity-edge/`, `CANDIDATAS.md` y la bitácora. No hay desborde.

## Tareas candidatas (defectos reales fuera de alcance, de diseño; para el orquestador)
- **Break-glass en prod:** Git fija `requiredActions: [CONFIGURE_TOTP]` y una sola credencial `password`. Tras el primer login, que es el previsto, la sonda da deriva 2 para siempre (`credentials[otp]`, `requiredActions`). Git declara un estado que Keycloak cambia legítimamente.
- **Campos con `$(env:…)`:** el campo entero se excluye, como dice el diseño. Por ejemplo, se puede añadir `https://atacante.example/*` a `redirectUris` de `vectra-console` en staging y la sonda da 0.
- **Entidades built-in:** se ignoran enteras, no se comparan con su valor por defecto. Por ejemplo, `admin-cli` reconfigurado con cuenta de servicio da 0, y su cuenta de servicio no se lee porque los usuarios no se listan.
- **Secciones que Git no declara:** `identityProviders`, tipos de componente (por ejemplo, un `KeyProvider` intruso en prod, o cualquier componente en kind y staging) y políticas de cliente no se leen. Una entidad añadida ahí no cuenta.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/logs/ca1.txt (ca3, ca4, ca5, ca6, ca7, ca7b en la misma carpeta)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/logs/sondas.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/sondas/sonda.py

```
VEREDICTO: NO-VERDE
NARANJA|identity-edge/tools/realm_diff.py:83-123|Un valor por defecto de Keycloak (scope mapping de offline_access) cuenta como deriva
NARANJA|identity-edge/tools/realm_diff.py:244|Una clave repetida del lado de Keycloak se pierde sin contar (priority, type)
NARANJA|identity-edge/tools/realm_diff.py:205-207|El flag builtIn lo pone el lado auditado
NARANJA|identity-edge/jobs/signing_key_age.py:25|Literal RS256 como respaldo, sin prueba
INFORME: revisiones/U02-T08/ronda-1.md
```

VEREDICTO: NO-VERDE
