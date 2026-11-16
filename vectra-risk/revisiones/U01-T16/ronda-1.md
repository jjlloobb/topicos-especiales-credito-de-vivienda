# Ronda 1 — U01-T16

VEREDICTO: NO-VERDE

Hay tres NARANJA y ningún ROJO. Los siete criterios pasan con mis propias corridas. La recuperación es correcta para todo lo que hoy es copia literal. Lo que falla es lo que se le promete al orquestador para la corrida real: en vez de 3 rutas generadas salen 6. Además, `gateway-address.sh` usa un mismo código de salida para dos casos distintos.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Recuperar antes de generar | `pytest platform/kind/tests -k "recover or recupera"` (con `--collect-only` selecciona 18 de 92, todas de `test_vault_from_cluster.py`) | pasa, 18 |
| 2 | Informe sin secretos | `-k "report or informe"` (selecciona 5 de 92: las 3 `test_report_*` y 2 `*_reported`) | pasa, 5 |
| 3 | Namespaces de `identity/` | `-k namespaces` (selecciona 3 de 92) | pasa, 3 |
| 4 | Solo lectura y `shellcheck` | `shellcheck` 0.11.0 (ya está instalado en `~/.local/bin`) sobre los dos guiones: rc 0. El `! grep …`: rc 0. `bash -n`: rc 0 | pasa |
| 5 | Runbook | El grep encuentra las líneas 64, 67 y 199. Los guiones como los corre `make`: `test_runbooks.py` da 56 alertas, `--operational` da 4, `test_links.py` da 647 archivos sin enlaces rotos | pasa (el pytest del criterio da rc 5, defecto del criterio, no del codificador) |
| 6 | pytest de `platform` como la CI | `.tools` movido fuera del árbol y PATH sin `.tools`, con `.charts` presente: 1002 passed en 303,81 s, 0 omitidas, rc 0. Después `test_kind_guide.py` y `test_kind_inventory.py`: 95 passed. `.tools` devuelto | pasa |
| 7 | `make -C platform check` | Una sola vez: rc 0, 7 min 7 s | pasa |
| — | `test_traceability.py --all` | rc 0 en la rama y rc 0 en `main` (`ed0e496`, que difiere de la base solo en 3 archivos de tareas) | sin fallos nuevos |

**Mutaciones sobre copias de `vault_paths.py`, todas detectadas:**
- `find` devuelve None: 13 pruebas fallan, entre ellas la primera de CA-1.
- Sin detección de conflicto: falla la prueba del conflicto.
- Sin comprobar que `jwks` y privada casan: falla la prueba del par.
- Toda plantilla tratada como literal: fallan 3.

## Hallazgos

### F-01 · NARANJA · `bitacoras/U01-T16.md` («Qué debe ver»), `install.md` paso 3 («Hoy: …»), `test_vault_from_cluster.py::identity_cluster` · La lista de lo que se genera está incompleta: son 6 rutas, no 3
`identity_cluster` inventa un `Secret` `*-client` en `vectra-app` para **cada** cliente con cuenta de servicio. En el repositorio, `git grep clientId` sobre los `values` de los charts solo declara estos: bias-monitoring-service/job, case-service, case-worker, governance-service, model-validation-job, product-metrics, scoring-service y explainability-service, además de keycloak-config-cli y keycloak-reader en identity-edge.

`channel`, `channel-simulator` y `verification-reader` no tienen ningún `ExternalSecret` con `private-key`. Su privada solo vivía en la bóveda y en el directorio e2e, que está en `/run/user/1000`, un tmpfs que hoy no existe.

Simulé el caso con solo los `*-client` que declaran los charts. El informe real sale así:
`identity/clients/channel|channel-simulator|verification-reader: … generadas 2 (jwks, private-key)` y el cierre «Se generaron valores nuevos en **6** ruta(s)».

La bitácora le dice al orquestador «Se generaron valores nuevos en 3 ruta(s)», y `install.md` enumera como «Hoy» solo Valkey, `grafana` y break-glass.

Consecuencia: `keycloak-realm-clients-jwks` cambia para esos tres clientes, pero Keycloak conserva los `jwks` viejos hasta que `keycloak-config-cli` reimporte el realm. Hasta entonces fallan `channel-simulator` (F07) y `verification-reader`, es decir, la verificación de U12. El informe lo dice en tiempo de ejecución y el paso 8 trae el camino genérico («sincroniza keycloak»). Pero la expectativa documentada es falsa y la prueba oculta el caso.

### F-02 · NARANJA · `platform/kind/vault_paths.py` (`LITERAL_TEMPLATE`) · Una plantilla con espacios o salto de línea alrededor se toma por copia literal y escribe un valor distinto
La expresión es `^\s*\{\{\s*\.(\w+)\s*\}\}\s*$`. ESO conserva el texto que rodea a `{{ }}`, así que ese contorno acaba dentro del valor recuperado. Demostrado con un clúster falso:
- con la plantilla `"{{ .pw }}\n"` (un `|` de YAML), `find` devuelve `'VAULTVALUE\n'`;
- con `"  {{ .pw }}"`, devuelve `'  VAULTVALUE'`.

Ese valor iría a la bóveda y de ahí a todos los consumidores literales. Hoy no se dispara: las dos únicas plantillas literales, `exporter-password` y `sentinel-lookup-password`, van entre comillas simples y sin espacios. Es justo el caso «escribir un valor que no es el que había». Además, ninguna prueba lo cubre.

### F-03 · NARANJA · `gateway-address.sh` y `seed-vault.sh` (`identity`) · Los códigos de salida no cumplen lo que el runbook promete
- **`gateway-address.sh`, error de `kubectl` → rc 1.** Si `kubectl` falla (Service inexistente, API caída), `set -e` sale con el código de `kubectl`, que es 1. Demostrado con un `kubectl` falso que devuelve NotFound: rc=1. El runbook (paso 3 de «Tras reiniciar la máquina») lee rc 1 como «edita `/etc/hosts`».
- **`gateway-address.sh`, códigos que las pruebas no fijan.** Las pruebas solo miran `!= 0`. Dos mutaciones sobreviven con 8 de 8 en verde: intercambiar 3↔4 y cambiar 1→5.
- **`seed-vault.sh identity`, fallo silencioso.** `mapfile -t namespaces < <(… identity-namespaces …)` ignora el fallo del proceso sustituido. Comprobado con bash: queda la traza en stderr, 0 namespaces y rc 0, así que el refresco no ocurre y el guion dice que terminó bien.

Sin hallazgo en `gateway-address.sh`: es de solo lectura, el `curl` va sin credenciales (la mutación con `-H Authorization` la detecta una prueba) y la mutación «nunca no responde» también se detecta.

### F-04 · AMARILLO · Valkey, residuo conforme a la especificación (pregunta 2)
Confirmado en `identity-edge/charts/valkey/rendered/kind/valkey.yaml:764-787` y `ratelimit/external-secret.yaml:19`:
- `ratelimit`, `replication`, `sentinel` y `sentinel-peer` solo viven dentro de `users.acl`, `valkey-secret.conf`, `sentinel-*.conf` y `REDIS_AUTH: "ratelimit:{{…}}"`;
- `exporter` y `sentinel-ratelimit` sí son literales y se recuperan.

Valkey carga el `aclfile` y el `include` al arrancar (líneas 84-85). Los Sentinel componen su configuración con `cat` al arrancar (163-166). `envoy-ratelimit` lee las variables por `secretKeyRef`.

Qué pasa tras la siembra:
- Nada se rompe de inmediato.
- Cualquier reinicio parcial (OOM, desalojo) deja dos lados: una réplica con `masterauth` nuevo frente a la ACL vieja de la primaria, o `ratelimit` con la clave nueva frente a la ACL vieja. Eso da WRONGPASS en `ratelimit`, y `/auth/**` es fail-closed (`routes.yaml:47`, `failure_mode_deny`), así que el login responde 503.
- El arreglo es reiniciar Valkey, los Sentinel y `envoy-ratelimit` **juntos y enseguida**. El paso 8 lo dice como «no medido», metido en «Identidad (Keycloak)».

Mi juicio: no es ROJO, porque el punto 1 de la tarea prescribe exactamente esto («solo se recupera lo que es copia literal; lo demás se informa») y está informado. Pero no es opcional: conviene sacarlo como paso propio del runbook. El arbitraje es del orquestador.

### F-05 · AMARILLO · Detalles menores
- `identity/break-glass` siempre se genera, así que el cierre del informe de `identity` nunca puede decir «nada que realinear», aunque nadie lea esa ruta. El runbook usa esa frase como condición para saltarse los pasos 4 a 8.
- `ClusterSecrets.secret` hace `.decode()` sin capturar el error. Un `Secret` con bytes que no son UTF-8 aborta toda la siembra con un `UnicodeDecodeError` que cita un byte del valor (`can't decode byte 0xff`). Hoy ninguno lo es.
- El paso 3 de «Vault reiniciado» perdió una frase medida el 2026-11-14 («Devolvieron los `ExternalSecret` a sincronizados, con claves nuevas»). El resto de lo medido el 14, 15 y 16 sigue ahí: «2026-11-14» aparece 6 veces en la base y 7 en la rama.

### Comprobado sin hallazgo
- **Las cifras de `install.md` coinciden con `test_kind_profile.py`.** `BUDGET_GIB` es 13,8; `CPU_BUDGET`, 10,7; el pico es 13,7344 con una réplica de Keycloak y 14,7539 con dos. `cluster.yaml` tiene tres nodos.
- **Secretos.** No hay valores en el diff, en los commits, en la bitácora ni en los mensajes de `RecoveryConflict`. Las lecturas del clúster son solo `get`. Los dos guiones se niegan con rc 2 fuera de un contexto `kind-*`.
- **Plataforma.** Todos los `ExternalSecret` son literales (salvo `alertmanager-config`, cuyo `url` es fijo). Los conflictos entre namespaces (`vectra-data` frente a `vectra-app`) se detectan. Los `fixed_value` ganan siempre. `TOKEN_PENDING` solo se usa si no hay un token que recuperar.
- **Par de llaves.** El `jwks` nunca se recupera literal, porque en `keycloak-realm-clients-jwks` pasa por `toJson`. Siempre se deriva de la privada recuperada. Si un `jwks` literal aparece y no casa, `client_pair` falla.
- **Alcance.** Ningún archivo fuera de alcance. `CANDIDATAS.md` solo crece al final.

## Tareas candidatas (defectos reales fuera de alcance)
- Recuperar los pares de `channel`, `channel-simulator` y `verification-reader`, o persistir el directorio e2e fuera de tmpfs. Hoy se regeneran tras cada reinicio y obligan a reimportar el realm.
- Invertir las plantillas reversibles (`toJson`, `ratelimit:{{…}}`, `users.acl`). El codificador ya la anotó.

## Rutas de transcripciones largas
- Ninguna. Las copias del scratchpad se borraron. El worktree quedó limpio (`git status --short` vacío) y `platform/.tools` volvió a su enlace original.

```
VEREDICTO: NO-VERDE
NARANJA|bitacoras/U01-T16.md, install.md paso 3, test_vault_from_cluster.py::identity_cluster|Se generan 6 rutas, no 3 (channel, channel-simulator, verification-reader sin Secret *-client)
NARANJA|platform/kind/vault_paths.py LITERAL_TEMPLATE|Plantilla con espacios o salto de línea alrededor se recupera como literal y escribe otro valor
NARANJA|platform/kind/gateway-address.sh, seed-vault.sh identity|Error de kubectl sale con rc 1 (el de «edita /etc/hosts»); códigos sin fijar en las pruebas; fallo de identity-namespaces silencioso con rc 0
AMARILLO|edge/valkey|Residuo conforme a la especificación: reinicio coordinado de Valkey, Sentinel y ratelimit obligatorio, no medido
AMARILLO|vault_paths.py Report / ClusterSecrets.secret / install.md|break-glass impide «nada que realinear»; decode sin capturar; frase medida del 11-14 eliminada
INFORME: revisiones/U01-T16/ronda-1.md
```
