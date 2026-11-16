# Cierre de U12 con alcance acotado a la demo (U12-T06)

**Estado: guía lista, pendiente del operador.** U12 queda cerrada **para kind** (`demo-recorte-funcional.md` §3 U12 y §8), no para staging ni prod. U12-T01 a U12-T05 dejaron la herramienta, los escenarios, la CLI, los guiones de las cuatro demos y la imagen; U12-T06 deja la **guía del operador** (`system-verification/docs/paso-18-kind.md`), el inventario único de lo que solo se ve en kind, los guiones de lectura, el humo, las plantillas de evidencia y las pruebas sin clúster que atan todo eso al repositorio. **Ningún agente tocó el clúster** (AUTONOMIA-01): la verificación en kind (Paso 18) la corre un operador y entra en el **PR de verificación**, que revisan las personas de `CODEOWNERS` (`.github/CODEOWNERS`, línea 9). El Paso 18 sigue en `[ ]` hasta ese PR; el Paso 19 (cierre) está en `[x]`.

## Comprobado

Lo del codificador, sin clúster, desde `vectra-risk/` (la salida de cada comando está en `bitacoras/U12-T06.md`):

| Criterio | Punto | Comando | Resultado |
|---|---|---|---|
| CA-1 | La guía tiene las doce fases F0 a F11 en orden, cada una con prerrequisitos, pasos con comando, plantilla, duración y puerta; y en la primera página «Quién hace qué», R-1 a R-8, la tabla de síntomas y «Cómo dejar el clúster como estaba» | `grep -nE "^## F(0\|1\|2\|3\|4\|5\|6\|7\|8\|9\|10\|11) " system-verification/docs/paso-18-kind.md`; `uv run pytest system-verification/tests/unit/test_kind_guide.py -k structure` | 12 encabezados; 5 pasan |
| CA-2 | Mundo cerrado sobre la guía: Applications, namespaces, secciones y opciones de la CLI, guiones, PR preparados, rutas, líneas citadas, selectores, series, alertas, usuarios, rutas de la consola; el orden de F2 y `decisions` antes de `rt2` | `uv run pytest system-verification/tests/unit/test_kind_guide.py -k closed_world` | pasan; 6 rojos con mutaciones reales en la bitácora |
| CA-3 | Verbos de `kubectl`: `scan_tree` alcanza `docs/`; los bloques `bash operador` solo admiten la lista cerrada de P-4 | `uv run pytest system-verification/tests/unit/test_kubectl_verbs.py` | 134 pasan; `grep` de `docs/kind/` sin órdenes de escritura (`rc=0`) |
| CA-4 | Inventario K-01 a K-66: fuentes dentro de su archivo, comprobación real, plantilla y demo; cada fila de «Pendiente en U12» de los seis cierres, cada fila con destino U12 de `cierre-acotado.md` y cada línea de «Se atienden aquí» es fuente de alguna entrada; cada entrada en la guía, en una plantilla y en la tabla de abajo | `uv run pytest system-verification/tests/unit/test_kind_inventory.py` | 10 pasan |
| CA-5 | Cinco guiones de lectura: `shellcheck`; cada uno contra un `kubectl`, un `free` y un `docker` ejecutables de mentira (los cuatro verbos, `port-forward` a un pod, ImagePullBackOff, salida 0 con reinicios y `ExternalSecret` sin sincronizar dan 1, un `port-forward` caído da 2 sin reintento, ninguna espera fija, nunca un valor de la bóveda, `Ki`/`Mi`/`Gi`) | `uvx --from shellcheck-py shellcheck system-verification/docs/kind/*.sh`; `uv run pytest system-verification/tests/unit/test_kind_scripts.py` | rc 0; 39 pasan |
| CA-6 | Humo contra el Keycloak de Testcontainers y los dobles del gateway y del BFF: claims de los cinco usuarios y ningún token, `iss` distinto del público como fallo, estado de cada llamada, plazo con reloj inyectado, un 401 nombra su destino, un `securitypolicyviolation` provocado, `guard` sin solicitudes, nada en disco | `uv run pytest system-verification/tests/integration/test_kind_smoke.py` | 20 pasan |
| CA-7 | Trece plantillas (`00` a `12`) en «Estado: pendiente del operador», sin salida inventada | `ls aidlc-docs/construction/system-verification/evidence/kind/`; `grep -L "Estado: pendiente del operador" …/*.md`; `uv run pytest …/test_kind_inventory.py -k templates` | 13 archivos; el `grep -L` no lista ninguno; pasan |
| CA-8 | Coherencia: la orden `docker run` (la función `vv` del README de U12-T05: banderas, variables, montajes y perfil seccomp; y la función corrida con un `docker` de mentira), las 8 secciones en el orden de la CLI, ninguna sección diferida ni `k6` ni las Applications diferidas, los `verify` como los definió U12-T04, los tiempos de los guiones | `uv run pytest system-verification/tests/unit/test_kind_guide.py -k coherence`; `uv run pytest system-verification/tests/unit/test_demos_closed_world.py` | pasan tras integrar U12-T05 y la ronda 2 de U12-T04; la guía ya no lleva marcas «POR CONFIRMAR»; `humo` con `--entrypoint python` comprobado contra la imagen real (`--help`, sin red) |
| CA-9 | Paso 19: `make -C system-verification check` | `uptime; time make -C system-verification check; echo "rc=$?"; uptime; docker ps -a …` | rc=0 en **28 min 16 s** (`uptime` al empezar: carga 2,49; al terminar, 3,82; había otros codificadores y un revisor corriendo); primera pasada **1034 pasan** en 19 min 11 s con cobertura de ramas **94,33 %** (umbral 85 %), segunda pasada **827 pasan** en 8 min 55 s con 100 % en `report` y `sampler`; `ruff`, `mypy` (36 archivos), `Contracts: 11 kept, 0 broken`, `shellcheck` y `links` (589 archivos) dentro de `check`; contenedores restantes: ninguno (`restantes=1`) |
| CA-10 | Trazabilidad | `uv run python platform/tests/test_traceability.py --unit system-verification --all` | `system-verification: 22 identificadores con trazabilidad`, rc 0, con la lista «Diferido por la demo» de U12-T05 (medido tras integrar) |
| CA-11 | Plan: Paso 19 `[x] (U12-T06, acotado a la demo)`; Paso 18 `[ ]` con «guía lista, pendiente del operador»; el diff toca solo esas dos casillas | `grep` de las dos líneas; `git diff f3873bd..HEAD -- …plan.md \| grep -cE "^[-+]- \["` | 4 |
| CA-12 | Enlaces y frases prohibidas | `uv run python platform/tests/test_links.py`; `uv run python contracts/tools/forbidden_phrases.py system-verification/docs/paso-18-kind.md` | `589 archivos Markdown sin enlaces rotos`; rc 0 |
| CA-13 | Lock y alcance del diff | `uv lock --check`; `git diff --name-only f3873bd..HEAD \| grep -vE "<lista de la tarea>"`; `ls system-verification/evidence` | `Resolved 127 packages`; `fuera=1`; `evidence/` solo con `.gitkeep`; `src/`, `demos/` y `README.md` sin cambios |

**Límite de la prueba de mundo cerrado.** `tests/unit/test_kind_guide.py` demuestra que la guía **no nombra nada que no exista** en el repositorio (Applications, namespaces, secciones y opciones de la CLI, guiones, PR preparados, rutas, líneas citadas, selectores, series, alertas, usuarios y rutas de la consola) y que respeta el orden de F2 y el de las secciones. **No demuestra que la guía funcione en kind.** Eso lo dice la evidencia del operador.

## Pendiente del operador

Cada entrada del inventario (`system-verification/docs/kind/inventario.yaml`, K-01 a K-66) con su plantilla en `aidlc-docs/construction/system-verification/evidence/kind/`, en el orden en que el operador las comprueba. «Estado» cambia a `comprobada` o `falla` en el PR de verificación, no antes. La última columna es la fila del cierre de otra unidad (sección «Pendiente en U12», o `cierre-acotado.md`) que esa entrada responde, con la abreviatura del inventario (`C-U1` platform-foundation, `C-U3` decision-registry, `C-U4` governance, `C-U6` model-serving, `C-U7` scoring-explainability, `C-U8` case-management, `C-U9` bias-monitoring, `C-U10` console, `C-U11` product-metrics) y la línea.

| Id | Qué | Plantilla | Estado | Fila del cierre de origen que responde |
|---|---|---|---|---|
| K-01 | Memoria del host: al menos 8 GiB disponibles antes de instalar (14 GiB de RAM es el minimo; los requests del perfil de kind suman 13,8 GiB) | `00-prerrequisitos.md` | pendiente del operador | C-U6:34 |
| K-02 | U12-T03, T04 y T05, U02-T22 y U00-T04 en main; la reparacion del realm retirada de tests/doubles/keycloak_tc.py | `00-prerrequisitos.md` | pendiente del operador | — |
| K-03 | Paquetes de U5 generados (base, proxy/run-1, adversarial/rt3) y la vigencia de reference-policy.json cubre los dos dias de la corrida | `00-prerrequisitos.md` | pendiente del operador | — |
| K-04 | Calendario: decisions se lanza antes de 22:18 UTC; el dia D + 1 no es dia 1 del mes; D4 solo pasa durante el dia D + 1 UTC (hasta las 00:00 UTC de D + 2); F5 a F10 caben en 3 dias (retencion de Prometheus) | `00-prerrequisitos.md` | pendiente del operador | — |
| K-05 | La boveda de kind esta sembrada y no se ha reiniciado desde la siembra (guarda todo en memoria) | `00-prerrequisitos.md` | pendiente del operador | — |
| K-06 | Imagenes de U3 a U11 publicadas en kind-registry y digests reales en los values de kind, por PR (un digest que no es el publicado da ImagePullBackOff; ya no queda ninguno de ejemplo) | `01-imagenes.md` | pendiente del operador | C-U7:41, C-U8:72, C-U9:39, C-U10:70, C-U11:50 |
| K-07 | Governance, scoring, explainability y casos construidas del mismo commit, con sus digests en un solo PR | `01-imagenes.md` | pendiente del operador | C-U7:42, C-U8:72 |
| K-08 | Imagenes de U2 (Keycloak, identity-jobs, config-cli, Envoy, Valkey) publicadas, si U2 no esta instalado | `01-imagenes.md` | pendiente del operador | — |
| K-09 | Imagen de U12 publicada y corrida por digest; su memoria en el host frente a --memory 1g | `01-imagenes.md` | pendiente del operador | — |
| K-10 | U2 arranca: Envoy con la raiz de solo lectura, las sondas de Valkey contestan, el Job keycloak-config-cli termina | `02-sync-y-arranque.md` | pendiente del operador | — |
| K-11 | decision-registry: Application Synced y Healthy; /readyz responde 200 | `02-sync-y-arranque.md` | pendiente del operador | C-U3:71, C-U3:72 |
| K-12 | ESO materializa las llaves de cada unidad (scoring, explainability, case-service, case-worker, las dos de bias, product-metrics) y existen los cuatro pg-role-case-* | `02-sync-y-arranque.md` | pendiente del operador | C-U7:44, C-U8:73, C-U9:40, C-U11:51 |
| K-13 | Ningun contenedor sale con codigo 0 y sin mensaje (falta una variable o la llave private_key_jwt) | `02-sync-y-arranque.md` | pendiente del operador | — |
| K-14 | U8: el hook de migracion corre antes de que los Deployment queden Ready; sslmode=verify-full conecta de verdad con case-db | `02-sync-y-arranque.md` | pendiente del operador | C-U8:74 |
| K-15 | U7 arranca con la raiz de solo lectura y sin emptyDir; los hosts <isvc>-predictor.vectra-serving y -explainer resuelven desde vectra-app | `02-sync-y-arranque.md` | pendiente del operador | C-U7:43, C-U7:45 |
| K-16 | vectra-internal-ca existe en vectra-app y el JWKS responde por https | `02-sync-y-arranque.md` | pendiente del operador | C-U10:72 |
| K-17 | El eco de U2 y la ServiceAccount temporal console-bff de U4 no existen antes del sync de U10 | `02-sync-y-arranque.md` | pendiente del operador | C-U10:71 |
| K-18 | product-metrics arranca despues del registro; si no, 503 hasta 30 min y dashboard vacio | `02-sync-y-arranque.md` | pendiente del operador | C-U11:54 |
| K-19 | Prometheus carga las PrometheusRule de U8 y U11 y raspa los ServiceMonitor de U8 (tres), del BFF y de U11; Grafana descubre el ConfigMap del dashboard en Vectra / Producto | `02-sync-y-arranque.md` | pendiente del operador | C-U8:75, C-U10:73, C-U11:52 |
| K-20 | Selectores y puertos de partida: Prometheus (app.kubernetes.io/name=prometheus, 9090) y el registro (decision-registry-service, 8080) | `02-sync-y-arranque.md` | pendiente del operador | — |
| K-21 | Proxy de Linkerd en vectra-mock: el target linkerd-proxy en up == 1 (no 403) y los pods Ready con el Server del 4191 (las sondas /live y /ready pasan) | `02-sync-y-arranque.md` | pendiente del operador | C-U1:28, C-U8:69 |
| K-22 | Politica activa y modelo de referencia activo: serving-config trae policy_version_id y la version | `02-sync-y-arranque.md` | pendiente del operador | C-U4:27, C-U4:28 |
| K-23 | Con 256 MiB por pod bastan el predictor y el explicador del modelo de referencia (sin OOMKilled) | `02-sync-y-arranque.md` | pendiente del operador | C-U6:34 |
| K-24 | Paquetes proxy y RT-3 (a, b, c y d) en el model-store, para D1 y D2 | `02-sync-y-arranque.md` | pendiente del operador | — |
| K-25 | Watchdog recibido, no solo disparado | `02-sync-y-arranque.md` | pendiente del operador | C-U1:27 |
| K-26 | Flujos negados (suite X01 a X10, casos bloqueados de INF-U10-04, X04): no se comprueban porque network y el Paso 9 estan diferidos; los permitidos se ven por el flujo base y las demos | `02-sync-y-arranque.md` | pendiente del operador | C-U1:23, C-U1:25, C-U8:70, C-U9:36, C-U10:68, C-U11:49 |
| K-27 | Si el kind tiene el realm viejo: tras resincronizar U2 quedan 26 de 26 ejecuciones enlazadas; config-cli avisa que no reaplica contrasenas y anade una segunda credencial OTP con la misma semilla | `03-identidad-y-acceso.md` | pendiente del operador | — |
| K-28 | Bloqueos por fuerza bruta: el login fallido por el error interno del realm viejo no cuenta (numFailures 0); si cuentan las contrasenas mal tecleadas (60 s al quinto fallo, permanente al 20) | `03-identidad-y-acceso.md` | pendiente del operador | — |
| K-29 | Login por rol por el gateway real, con el emisor publico: analista-1, analista-2, ingeniero-1, cro-1 y cumplimiento-1; cada token con acr = mfa, amr, aud con console-bff y su rol | `03-identidad-y-acceso.md` | pendiente del operador | C-U10:65 |
| K-30 | El iss de los tokens del navegador es el que valida el BFF y cada destino (F10 a F14): 200 en bandeja, detalle, modelos y congelamientos, ningun 401 | `03-identidad-y-acceso.md` | pendiente del operador | C-U10:69 |
| K-31 | La aud de la asercion de servicio la acepta el Keycloak del cluster (nunca medido en kind con el realm real) | `03-identidad-y-acceso.md` | pendiente del operador | — |
| K-32 | Camino a la boveda desde la estacion (no lo da K16): lectura de las 5 credenciales y las 2 llaves; el token root de kind no rompe el filtro de evidencias | `03-identidad-y-acceso.md` | pendiente del operador | — |
| K-33 | Credenciales de los usuarios -2 (analista-2 o cro-2 en D1; cumplimiento-2 en D2) en la boveda, y sus semillas TOTP en el telefono del presentador | `03-identidad-y-acceso.md` | pendiente del operador | — |
| K-34 | K16 de verdad: lo que cada verify lee lo permite el grupo vectra-verification-operators; que pasa en vectra-staging y vectra-mock (K16 no da nada) | `03-identidad-y-acceso.md` | pendiente del operador | — |
| K-35 | Consola en el navegador por el gateway real: redireccion, /callback, recarga con prompt=none; cero securitypolicyviolation con la CSP real; la cookie vectra-spa-route llega a los pods | `03-identidad-y-acceso.md` | pendiente del operador | C-U10:65, C-U10:66, C-U10:73 |
| K-36 | CASE_ALLOW_TEST_SCENARIOS activo en kind (la cabecera de escenario de U12 se acepta) | `03-identidad-y-acceso.md` | pendiente del operador | — |
| K-37 | Limites del gateway con el volumen real: 30/s para el simulador, 20/s por usuario en /api/console, 600/min en auth-login y auth-token (cero 429) | `03-identidad-y-acceso.md` | pendiente del operador | — |
| K-38 | Humo de punta a punta: una solicitud por el gateway llega a listo con registry_entry_id; la explicacion por el BFF; una decision de analista-1; el append con ack | `04-flujo-base.md` | pendiente del operador | C-U7:40, C-U3:73 |
| K-39 | prepare fija runId y started_at; con el PR de runId fusionado, make -C case-management policy-chart sigue en verde sobre main | `05-prepare-y-d3.md` | pendiente del operador | — |
| K-40 | El Job rt5-demo-<runId> termina despues de started_at; su log trae el 403 del proxy y el valor real de l5d-proxy-error | `05-prepare-y-d3.md` | pendiente del operador | C-U8:68 |
| K-41 | La serie inbound_http_authz_deny_total existe con sus etiquetas reales (namespace vectra-mock, route_name core-mock-catch-all; la prueba de U1 declara otras) | `05-prepare-y-d3.md` | pendiente del operador | C-U1:28, C-U8:69 |
| K-42 | CoreWriteAttempt llega a firing y cuanto dura (no tiene for:; la expresion mira 5 min) | `05-prepare-y-d3.md` | pendiente del operador | — |
| K-43 | vectra_core_write_attempts_total en 0 desde el arranque | `05-prepare-y-d3.md` | pendiente del operador | C-U8:68 |
| K-44 | 2 000 casos: accepted = sent; cada uno en listo o en un fail-closed documentado; los ultimos no quedan en not_ready sin decidir | `06-decisions-d4.md` | pendiente del operador | — |
| K-45 | Las constantes de la estimacion de guard (1 s por caso, 300 s) frente al tiempo real; el ritmo real frente a 10/s | `06-decisions-d4.md` | pendiente del operador | — |
| K-46 | registry-aggregator con atraso 0 y POST /v1/monitoring/daily:query con resultado mayor que 0 tras los 2 000 casos | `06-decisions-d4.md` | pendiente del operador | C-U3:74, C-U3:75 |
| K-47 | Memoria real con 2 000 decisiones frente a los 128 MiB de request de kind: case-service, case-worker, el BFF y product-metrics | `06-decisions-d4.md` | pendiente del operador | C-U8:76, C-U10:74, C-U11:53 |
| K-48 | RT3-a, c y d: 422 de U4 y serving-config sin cambio. RT3-b y 'a y d desplegados' se informan y pueden quedar no ejecutado | `07-d1-rt3.md` | pendiente del operador | — |
| K-49 | Con el PR de F22 fusionado y network sincronizada con prune, desaparecen los cinco recursos de F22; con la reversion, vuelven | `07-d1-rt3.md` | pendiente del operador | — |
| K-50 | Que last_cause da F22 apagado (timeout o explainer_unavailable); el caso pasa de en_sincronizacion a no_disponible entre 12,4 y 19,3 min; cero recommendation | `07-d1-rt3.md` | pendiente del operador | — |
| K-51 | vectra_cases_failclosed_persistent raspado y FailClosedPersistente en firing unos minutos despues del primer caso en no_disponible (la herramienta la sondea hasta 5 min tras la escalada) | `07-d1-rt3.md` | pendiente del operador | C-U8:75 |
| K-52 | La reversion devuelve el flujo a listo; cuantos casos no_disponible quedan y si la alerta sigue activa durante D2 y D4 | `07-d1-rt3.md` | pendiente del operador | — |
| K-53 | rt2-setup: el proxy queda aprobado, con initial_disparity no vacia, tras el PR proxy-staging | `08-d2-rt2.md` | pendiente del operador | — |
| K-54 | Promocion con trafico: 0 version_mismatch; el activo nunca baja de 2 replicas; los requests de memoria durante la promocion caben | `08-d2-rt2.md` | pendiente del operador | C-U7:38, C-U6:32 |
| K-55 | Las celdas de RT-2: rt2 se niega solo por una celda alcanzable corta; las inalcanzables se informan | `08-d2-rt2.md` | pendiente del operador | — |
| K-56 | U3 no responde 504 al cron de U9 con la maquina cargada; las metricas de bias llegan por el Pushgateway | `08-d2-rt2.md` | pendiente del operador | — |
| K-57 | El proxy congela con una corrida real del CronJob; rt2_latency a 1 800 s o menos (una medicion); el paquete completo (FreezeContext, data_sources, initial_disparity) | `08-d2-rt2.md` | pendiente del operador | C-U9:37 |
| K-58 | FailClosed(model_frozen) en 6 s o menos tras el freeze; los casos nuevos quedan modelo_congelado | `08-d2-rt2.md` | pendiente del operador | C-U7:39, C-U4:32 |
| K-59 | Duracion y pico de memoria de una corrida de bias, bajo los 256 MiB del limite | `08-d2-rt2.md` | pendiente del operador | C-U9:38 |
| K-60 | Los dos modos de reactivacion: el de la herramienta con cumplimiento-1, y --reactivation presenter con cumplimiento-2 en la consola (ventana emergente, /stepup-callback, acr = mfa, ResolveFrozenDialog) | `08-d2-rt2.md` | pendiente del operador | C-U10:67 |
| K-61 | Tras reactivar no se recongela; el barrido de U8 devuelve los modelo_congelado; el rollback deja el modelo de referencia activo; la duracion real frente a mas de 75 min | `08-d2-rt2.md` | pendiente del operador | — |
| K-62 | North Star, sostenida, tasa de consulta y ProductMetricsStale con datos reales, dentro del dia D + 1 UTC (la herramienta espera hasta las 02:40 UTC; desde las 00:00 UTC de D + 2 el ayer no tiene decisiones) | `09-d4-u11-y-grafana.md` | pendiente del operador | C-U11:47, C-U11:48 |
| K-63 | Grafana por port-forward con grafana-admin; el dashboard Producto carga con sus cuatro paneles. Los permisos por carpeta y rol no se ensenan | `09-d4-u11-y-grafana.md` | pendiente del operador | C-U11:48 |
| K-64 | El informe lista cada RT, demo e historia; salen no ejecutado US-106, 109, 603, 305, 604, 608, 609 y 610, RT3-b y 'a y d desplegados'; ninguno sale pasa sin evidencia | `10-informe-y-estado-final.md` | pendiente del operador | — |
| K-65 | El cluster queda como estaba: modelo de referencia activo, ninguna version congelado, sin InferenceService de staging, F22 encendido | `10-informe-y-estado-final.md` | pendiente del operador | — |
| K-66 | (a) El login de la herramienta con Keycloak caido a mitad: se cuelga o termina con error. (b) El apagado del worker con trabajo en vuelo (34 s frente a 40 s de gracia). (c) PBT-U8-07 abreviado contra el registro real | `11-opcionales.md` | pendiente del operador | C-U8:77, C-U8:71 |

**Conteo:** 66 entradas (una puede sostener varias demos): flujo base 29 · D1 10 · D2 16 · D3 9 · D4 9 · ninguna 3.

**Lo que el inventario deja fuera a propósito** (está en «Pendiente» de algún cierre, pero el recorte lo difiere o es de otra guía): los ítems 3 a 8 del Paso 16 de U2 (`testssl.sh`, Valkey en 0, borrar el pod de Keycloak, el controlador en 0, la rotación de la llave, el 503 del eco) y los escenarios 4 y 7 de U4 y 1 a 3 de U6 que no sean el arranque (P-2 de U12-T06); `LOGS-NO-PII`, `CASE-SIZE`, la carga y la resiliencia (diferidos); `break-glass`, la `aud` por scope y el OIDC de Grafana (`CANDIDATAS.md`, líneas 40, 47 y 48).

## Diferido por la demo

Lista que acepta `platform/tests/test_traceability.py --unit system-verification --all` (`DECISIONES-LOOP.md` §6; `demo-recorte-funcional.md` §2, regla 4). Cada fila lleva el identificador, el paso del plan que lo implementaría y la cita del recorte. Un identificador de esta lista no puede tener código ni prueba: la herramienta falla si ya lo tiene.

| Identificador | Paso del plan | Cita del recorte | Qué falta |
|---|---|---|---|
| INF-U12-05 | Paso 11 (carga, US-609) | Enmienda `demo-recorte-funcional.md` §3 U12, fila «8b · 9 · 11: D»; `demo-kind-alcance.md` §3 U12 | La sección `load`, la estimación de capacidad para la carga y su contenedor de carga con límites: ninguna demo la usa |

Lo diferido sin identificador propio (no lo mira la herramienta; cada uno con su destino):

| Qué | Paso del plan | Cita del recorte | Destino |
|---|---|---|---|
| Escaneo, SBOM y firma de la imagen | Paso 15 | Enmienda §3 U12, fila «14 · 15: N/A · E\*»; T1 (firma Cosign, SBOM y attestations) | Después de la demo; la imagen se construye y se publica en `kind-registry` sin ellos |
| Workflow de CI de la unidad | Paso 16 | Enmienda §3 U12, fila «16: D»; T4 | Después de la demo |
| Las secciones `network`, `rt1`, `rt4`, `load`, `pii` y `resilience` | Pasos 7, 8b, 9 y 11 | Enmienda §3 U12, filas «7: D» y «8b · 9 · 11: D», y fila «13» | Responden `no ejecutado` (código 2) y el informe da el motivo de cada historia que dependía de ellas |
| `LOGS-NO-PII` y `CASE-SIZE` | Paso 10 | Enmienda §3 U12, fila «10» (P-18) | Ninguna demo los usa |
| Pruebas de mutación (`mutmut`) | Paso 4 | Enmienda §3 U12, fila «4»; T3 | Después de la demo |
| Prueba de `CODEOWNERS` con `branch-protection-check` | Paso 13 | Enmienda §3 U12, fila «13» | Depende de U4 Paso 14 |
| Las Applications `bias-monitoring` y `decision-registry-rebuild` en el parche de `prepare` | Paso 13 | Enmienda §3 U12, fila «13» | El parche solo toca `case-management` |

## Quién ejecutó

- **Codificador (U12-T06, sin clúster):** la guía, los guiones, el humo, las plantillas, las pruebas y este cierre.
- **Operador (pendiente):** la verificación en kind y el PR de verificación (`verificacion/<fecha>-<commit>`).
- **Revisor (pendiente, solo lectura):** la lectura de la evidencia del PR de verificación.
