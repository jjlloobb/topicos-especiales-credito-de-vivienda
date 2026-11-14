# Resumen del código — U12 `system-verification`, Pasos 12, 13 (U12-T04), 15 y 17 (U12-T05)

Código en `vectra-risk/system-verification/src/vectra_verification/`: `cli` (14 subcomandos más `all`), `live` (el mundo real de la CLI), `store` (el único escritor), `manifest`, `scenarios/u11`, `scenarios/demos`, `scenarios/resume` y, en `scenarios/rt2`, el modo `PresenterReactivation`.
Guiones, `verify` y PR preparados en `system-verification/demos/`. Contratos de import-linter nuevos: `store` solo lo importa `cli`; `cli` es el único que une `scenarios`, `driver` y `store`.

## Uso

`vectra-verification <sección> [opciones]` (también `python -m vectra_verification.cli`); `--dir` es el directorio de la verificación (`manifest.json`, evidencias, informe, parche); `--issuer`, `--gateway-host` y `--ca-file` (o `VERIFICATION_ISSUER`, `VERIFICATION_GATEWAY_HOST`
y `VERIFICATION_CA_FILE`) fijan el entorno; `--redo` repite una sección terminada; `all --from <sección>` corre en orden desde ahí. `--help` no hace nada: ni red, ni bóveda, ni archivos, ni importa `playwright` ni `pyarrow`.

| Sección | Qué hace | Opciones propias | Evidencias que escribe |
|---|---|---|---|
| `prepare` | `runId` (`AAAAMMDD-HHMM` de `started_at`), manifiesto inicial y parche de `values/kind/case-management.yaml`; **ninguna solicitud** | `--commit`, `--operator` (obligatorias), `--values-file`, `--patch-root`, `--delivery` (la entrega de U5; queda en el manifiesto, `paths.delivery`) | — (`manifest.json`, `case-management-runid.patch`) |
| `decisions` | `normal` + espera a `listo` + conductor + `SIM-NORMAL` | `--volume`, `--rate`, `--seed`, `--settle-timeout`, `--delivery` (por omisión, la del manifiesto) | `SIM-NORMAL` |
| `rt5` | el Job `rt5-demo-<runId>` y la alerta | `--after-job-minutes` | `RT-5`, `rt-5` |
| `rt3` | RT-3 (a, c, d y F22) y la escalada; tras la escalada sondea `FailClosedPersistente` hasta 5 min (cada 30 s). Con `--closing`: solo el cierre de D1 (un caso de sonda nuevo llega a `listo` tras revertir F22); su resultado va **aparte** (`closing_rt3` en el manifiesto) y el registro de `rt3` no se toca | `--packages-dir`, `--rt3b-dir`, `--seed`, `--probes`, `--no-wait-for-escalation`, `--deployed-a`, `--deployed-d`, `--operator-timeout`, `--closing`, `--delivery` | `RT-3`, `journey-7-3` |
| `rt2-setup` | registra, valida y aprueba la versión del proxy | `--proxy-root`, `--versions`, `--seed`, `--validation-timeout`, `--delivery` | — (no es un elemento del informe) |
| `rt2` | RT-2, latencia y reactivación; al final **espera el cierre** de D2 (`rollback-pr` y `mark-active` del modelo de referencia; lo dice al operador) y lo registra aparte (`closing_rt2`) | `--proxy-root`, `--versions`, `--seed`, `--reference-dir`, `--reactivation {tool,presenter}`, `--operator-timeout`, `--reactivation-timeout`, `--bias-timeout`, `--volume`, `--delivery` | `RT-2`, `RT2-LATENCY`, `journey-7-4` |
| `u11` | las cuatro series de los paneles y `ProductMetricsStale`, el día D + 1 | — | `dashboard` |
| `report` | `verification-report.md`, en cualquier momento | `--story-map` | — |
| `network`, `rt1`, `rt4`, `load`, `pii`, `resilience` | **diferidas por la demo**: ninguna solicitud, línea en el manifiesto con la cita de la enmienda, código 2 | — | — |

Los archivos de las evidencias de demo llevan el prefijo `demo-` (`demo-rt-5.json`, `demo-journey-7-3.json`, `demo-journey-7-4.json`, `demo-dashboard.json`): `rt-5` y `RT-5` solo se distinguen por mayúsculas.

**Rutas de datos (ninguna va escrita en el código).** `--delivery` (la entrega de U5, con `datasets/test.parquet`) llega por opción o por el manifiesto (`prepare --delivery`); `--packages-dir` (`<entrega>/adversarial/rt3`), `--proxy-root` (`<entrega>/proxy`) y `--reference-dir` (`<entrega>/package`) por omisión cuelgan de ella. Sin ninguna, la sección se niega
(`ruta_faltante`, código 3) o, si es la entrega, sale `no ejecutado` (`u5_delivery_missing`). La demo puede correr en otra máquina y desde una imagen sin un clon en una ruta fija. `all` cierra el backend (navegador y `port-forward`) de cada sección antes de abrir el de la siguiente, y la ventana TOTP de cada usuario se comparte entre ellos (una por proceso).

## Códigos de salida

`0` la sección terminó y todo lo suyo es `pasa`; `1` algún `falla`; `2` `no ejecutado` (faltó un prerrequisito, o es una sección diferida); `3` la herramienta se negó (barrera, uso incorrecto, `prepare` ausente o repetido, un archivo que el filtro de evidencias no deja escribir).
`falla` y `no ejecutado` nunca comparten código ni texto. Una sección `no ejecutado` queda `interrumpida` en el manifiesto y se retoma al volver a correrla; una terminada no se repite sin `--redo`; `rt2` guarda `state-rt2.json` al terminar **cada fase** (y si una excepción o un Ctrl-C la corta) y retoma en la fase que paró, sin reenviar el lote.

## Barreras (antes de la primera solicitud)

`guard.check_environment` (emisor y host), `guard.check_section` y `guard.check_decisions` (barrera horaria de las 23:00 UTC; ≤ 100 en staging). En staging solo `prepare` (sin parche), `decisions`, `u11` y `report`. El `Backend` (bóveda, login, `kubectl`) se crea **después**.
`prepare` corre sin `VAULT_ADDR` ni kubeconfig. Todo lo que se escribe pasa por `store.Store` (filtro de evidencias, temporal y renombrado; si el filtro falla, no queda archivo; un archivo de más de 50 MB se sustituye por un resumen con el hash del original).

## Modo de reactivación de D2

`--reactivation tool` (por omisión): step-up de `cumplimiento-1` y `resolve_frozen(…, "rt2")`. `--reactivation presenter`: `PresenterReactivation` espera (reloj inyectado, `--reactivation-timeout`) la entrada `frozen_resolution` con `action = reactivar` que el presentador crea en la consola con `cumplimiento-2`
(el MFA lo impone el BFF) **desde el `recorded_at` del congelamiento actual** (una reactivación de un ensayo anterior no cuenta); `investigar` es `falla`; vencido el plazo, `no ejecutado` retomable. La verificación posterior (`verify_reactivation`, «no se recongela», barrido) es la misma. La opción solo existe en `rt2`. Para no iniciar sesión con ningún usuario de cumplimiento,
las lecturas de modelos de `rt2` pasaron de `cumplimiento-1` a `cro-1` (rol permitido en `/modelos`).

## Tiempos y lo que sale `no ejecutado`

| Demo | Tiempo real |
|---|---|
| D1 | 12,4 a 19,3 min hasta `no_disponible`; unos minutos más hasta `FailClosedPersistente` en `firing` (se sondea hasta 5 min); el cierre ≤ 15 min |
| D2 | más de 75 min con 1 versión (≈ 30 min más por las 2 corridas de bias de `no_recongela`) |
| D3 | segundos el Job; la alerta `CoreWriteAttempt` se ve ≈ 5 min |
| D4 | día D antes de las 22:18 UTC (barrera de las 23:00); día D + 1 tras las 02:30 UTC |

`no ejecutado` por la demo: `RT-1`, `RT-4`, `X01` a `X10`, `LOGS-NO-PII`, `LOAD`, `RESTORE-DRILL`, `READINESS`, `CASE-SIZE`, y las historias US-106, 109, 305, 603, 604, 608, 609 y 610; el informe da el motivo de cada una. `RT3-b` y los dos «desplegado» de RT-3 no bajan el resultado.

## Qué hacen los guiones de D1 y D2 de verdad

- **D1:** al revertir F22 vuelven los cinco recursos y un caso de sonda **nuevo** llega a `listo` (`closing_rt3`); `FailClosedPersistente` **sigue en `firing`**: los casos de la sonda están en `no_disponible` y solo el reintento del CRO los saca, que no existe de punta a punta (la ruta del BFF existe; la vista de fallos de la consola está diferida). No afecta a D2, D3 ni D4.
- **D2:** sigue la secuencia de `promotion-tool` (`governance/docs/paso-20-kind.md`, 5.4 y 6): `create-promotion-pr`, `mark-active` y `post-activation-pr` de la versión del proxy; en el cierre, `rollback-pr`, sync, pods `Ready` y `mark-active` del modelo de referencia, mientras `rt2` espera. `journey-7-4.sh 4` comprueba `closing_rt2 = pasa` (el modelo de referencia `activo` en governance) además del `InferenceService` `Ready`.
- Los PR de `proxy-staging` y `rt3-staging` **no son plantillas**: se arman con `demos/prs/entrada.py` sobre los values tal como estén (con la referencia ya promovida, un parche fijo no aplicaba).

## Redacción de los guiones

Los guiones de `demos/` y el README no escriben órdenes de `kubectl` ni de Argo CD: dicen «sincroniza la Application `network` en Argo CD, con prune». Las rutas de la SPA van como `ruta /x`; las alertas, `alerta X`; las Applications, `Application x`; los dashboards, `dashboard X` con `uid` y `carpeta`; los
paneles, `panel X`; las órdenes, `vectra-verification <sección> --opción`; los `verify`, `nombre.sh N`. Una prueba (`test_demos_closed_world.py`) recorre `demos/` y comprueba que cada nombre existe en el repositorio y que **el orden** de los pasos es posible (`prepare` antes que `rt5`; el PR de `runId` antes que `rt5`; `rt2-setup` antes que `rt2`; `create-promotion-pr`, `mark-active`, `post-activation-pr`, `rt2`, `rollback-pr`; el cierre de `rt3` después de revertir F22). En las listas de Python, `-n <namespace>` va después del verbo.

## BR → prueba

Las trece reglas de negocio de U12 (`functional-design/business-rules.md`). Las diferidas por la demo dicen «diferida» con su cita; ninguna tiene código ni prueba (la lista «Diferido por la demo» de `evidence/cierre-demo.md` es la de los identificadores de infraestructura).

| Regla | Prueba |
|---|---|
| BR-U12-01 (qué envía el simulador) | `tests/unit/test_u5_reader.py`, `tests/property/test_sampler.py`, `tests/integration/test_simulator.py`, `tests/integration/test_decisions_volume.py` |
| BR-U12-02 (cómo envía) | `tests/integration/test_simulator.py`, `tests/unit/test_oracles_measurements.py` (`SIM-NORMAL`) |
| BR-U12-03 (`decision-driver` y login) | `tests/integration/test_driver.py`, `tests/unit/test_oidc_flow.py`, `tests/integration/test_oidc_headless.py`, `tests/unit/test_oidc_form_errors.py`, `tests/image/test_image.py` (`-k tls`: la CA en los dos caminos, dentro de la imagen) |
| BR-U12-04 (un escenario por RT, con oráculo) | `tests/unit/test_oracles_rt2_rt3_rt5.py`, `tests/integration/test_rt5_promql.py`, `tests/integration/test_rt3_real_chain.py`, `tests/integration/test_rt2_cells_real_u5.py`; `tests/image/test_image.py` (`rt5` dentro de la imagen, contra dobles) |
| BR-U12-05 (red de U1 más comportamiento) | **diferida** (sección `network`): enmienda `demo-recorte-funcional.md` §3 U12, fila «13» (la sección `pii` y `network` salen) y §2 |
| BR-U12-06 (volúmenes de demostración) | `tests/unit/test_rt2_cells.py`, `tests/property/test_sampler.py`, `tests/integration/test_decisions_volume.py`, `tests/unit/test_u11.py` |
| BR-U12-07 (latencia de detección de RT-2) | `tests/property/test_rt2_latency.py`, `tests/unit/test_oracles_rt2_rt3_rt5.py` |
| BR-U12-08 (perfil combinado) | **diferida** (sección `load`, Paso 11): enmienda §3 U12, fila «8b · 9 · 11: D» |
| BR-U12-08b (sección `resilience`) | **diferida** (Paso 8b): enmienda §3 U12, fila «8b · 9 · 11: D» |
| BR-U12-09 (guiones y `verify` sin órdenes de escritura) | `tests/unit/test_kubectl_verbs.py` (F-06 ampliado; recorre también `README.md` y `Dockerfile`), `tests/unit/test_demos_closed_world.py` (`-k k16`, los `verify` contra el doble de `kubectl` y `-k readme`), `tests/unit/test_prepared_prs.py` |
| BR-U12-10 (dónde corre: barreras de la CLI) | `tests/integration/test_cli.py` (`-k "guard or help or exit"`), `tests/unit/test_guard.py` |
| BR-U12-11 (resultado de tres valores, informe) | `tests/integration/test_cli.py` (`-k "report or demo_evidence"`), `tests/unit/test_u11.py`, `tests/unit/test_scenario_outcome.py` |
| BR-U12-12 (logs sin datos del solicitante) | **diferida** (`LOGS-NO-PII`, Paso 10): enmienda §3 U12, fila «10» (P-18) |
| BR-U12-13 (historias, informe, `u11`) | `tests/integration/test_cli.py`, `tests/unit/test_manifest.py`, `tests/unit/test_u11.py`, `tests/unit/test_story_map.py`, `tests/property/test_report.py` |

| Otros identificadores | Prueba |
|---|---|
| NFR-U12-05 (filtro de todo lo que se escribe, también un HAR dentro de una cadena JSON y con coste acotado) | `tests/unit/test_store.py`, `tests/unit/test_evidence_filter.py` (`-k "fn4 or f07"`) |
| Armado del mundo real sin clúster | `tests/unit/test_live.py` |
| NFR-U12-31 (tiempo medido) | `tests/integration/test_cli.py` (`-k report`), `tests/unit/test_manifest.py` |
| INF-U12-01 (la imagen y cómo se corre) | `tests/image/test_image.py` (`make -C system-verification test-image`), `tests/unit/test_demos_closed_world.py` (`-k readme`) |
| INF-U12-04 (CLI y manifiesto) | `tests/integration/test_cli.py`, `tests/unit/test_manifest.py` |
| INF-U12-05 (capacidad para la carga) | **diferida** (Paso 11): ver `evidence/cierre-demo.md`, «Diferido por la demo» |

## La imagen (U12-T05, Paso 15; INF-U12-01)

`system-verification/Dockerfile` (contexto: la raíz de `vectra-risk/`; `make -C system-verification image`), etiqueta local `localhost:5001/vectra/system-verification:dev`. El README de la unidad es la guía del operador (la orden `docker run`, los montajes, la red); aquí lo que el código necesita saber:

- **Contenido:** Python 3.12 por digest, `vectra_verification` (editable sobre `/opt/system-verification`, junto a `report/story-map.yaml`, `demos/` y `seccomp/`) y `vectra_contracts`; sin `vectra_common`; Playwright 1.64.0 con el Chromium headless shell de la revisión 1248 (el binario que `launch(headless=True)` usa; no sirve `chrome://sandbox`, por eso la prueba del sandbox mira los procesos en `/proc`); `kubectl` v1.37.0; sin Argo CD, `helm`, `k6`, `git`, `curl` ni manifiestos. Cada descarga con versión y SHA-256 en el `Dockerfile` (`image/apt.lock`, `image/requirements.txt` con hashes y los `ARG` de `kubectl` y Chromium).
- **Usuario y archivos:** `USER 65532:65532`, funciona con cualquier uid sin root: `HOME=/tmp` (tmpfs), navegadores en `/opt/ms-playwright` (legibles por todos), directorio de evidencias montado en `/verification/evidence`.
- **Sandbox:** `VERIFICATION_CHROMIUM_SANDBOX=1` hace que `HeadlessForm` lance Chromium con `chromium_sandbox=True` (Playwright agrega `--no-sandbox` si no se lo piden); con `--security-opt seccomp=chrome.json`. Sin el perfil, `browser_launch_error`.
- **CA:** Node por `NODE_EXTRA_CA_CERTS` (lo pone `HeadlessForm` desde `ca_file`) y Chromium por la huella SPKI; un certificado que la CA no firma o de otro nombre falla en la huella con `tls_pin_error`.

Defectos que la imagen reveló en `src/` (U12-T04), corregidos con su rojo en `bitacoras/U12-T05.md`: (1) Playwright lanzaba Chromium con `--no-sandbox` (`clients/oidc.py`); (2) sin el montaje de evidencias, `prepare` terminaba en una traza `OSError` (`store.py`: `store_unwritable`, código 3); (3) `rt5` y `u11` pedían la entrega de U5 sin necesitarla (`cli.RecordingSimulator` arma el simulador al usarlo); (4) un certificado no firmado por la CA salía de `_form_driver` como `ssl.SSLCertVerificationError` y no como `OidcError` (`tls_pin_error`).

## Lo que U12-T05 y U12-T06 necesitan

- **U12-T05 (hecho: la imagen y el README):** `vectra-verification` es lo que la imagen arranca; `--help` y `prepare` no hacen solicitudes. La imagen necesita `report/story-map.yaml` (opción `--story-map`), `python3` y `sh` (los `verify`), y los values de kind si `prepare` corre dentro (`--values-file`). `--ca-file` expone la CA de U12-T02.
  La tabla de arriba es la fuente del README.
- **U12-T06:** `cumplimiento-2` (contraseña y semilla) en la bóveda de kind y en el teléfono del presentador; `analista-2` o `cro-2` igual; `grafana-admin`; el PR de `runId` fusionado deja `make -C case-management policy-chart` en verde; el modo `presenter` ensayado de verdad; los cinco recursos de F22 desaparecen con el sync con prune y vuelven con la reversión;
  RT3-b da 409 con los paquetes del modelo de referencia (se genera desde `proxy/run-5`); `CoreWriteAttempt` dura ≈ 5 min en `firing` y no se ensaya dos veces sin reiniciar el proxy de Linkerd de `vectra-mock`; `FailClosedPersistente` no distingue un ensayo anterior.
