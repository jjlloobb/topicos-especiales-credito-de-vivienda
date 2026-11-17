# Guía del operador: Paso 18 de U12 en kind (verificación consolidada)

Paso 18 del plan de U12 (`aidlc-docs/construction/plans/system-verification-code-generation-plan.md`): instalar lo que falte, comprobar que todo funciona junto y correr las cuatro demos en kind, con evidencia. Lo ejecuta **un operador** después de un PR aprobado (AUTONOMIA-01): ningún agente aplica nada al clúster, y esta guía tampoco lo hace por ti.

**Para quién es.** Para una persona que no escribió el código y parte de una **máquina limpia** con el repositorio clonado y, quizá, un kind a medio instalar. No necesita nada de la máquina donde se escribió esta guía. Esta guía solo se ha ejecutado **en parte** en kind: lo medido está en `platform/runbooks/install.md` («Vault reiniciado», «Lo medido el 2026-11-15 al desplegar U2 en kind» y «Tras reiniciar la máquina», cada hecho con su fecha) y en F1 (los digests reales de `vectra-risk-gitops/values/kind`, 2026-11-16); de F2 en adelante, salvo U2, nada de esto se ha ejecutado aún de punta a punta. La prueba de «mundo cerrado» (`tests/unit/test_kind_guide.py`) demuestra que la guía no nombra nada que no exista en el repositorio, **no** que funcione. Si un paso falla, la tabla de síntomas dice a qué unidad apunta.

**Cómo está escrita.**
- Todos los comandos corren desde `vectra-risk/` (la carpeta del repositorio que contiene `system-verification/`), con el contexto `kind-vectra`.
- Todo comando propio de la guía es de **solo lectura**: `kubectl get`, `logs`, `auth can-i` y `port-forward`, `curl` a un `port-forward`, `free`, `docker stats` y la CLI de U12. Lo único que escribe va en un bloque marcado **orden del operador** (se reconoce porque el bloque dice `bash operador`) y es de una lista cerrada: sincronizar una Application de Argo CD, retirar el eco de U2, publicar la imagen de U12, y, solo en F11, reiniciar `case-worker` y borrar el pod de Keycloak. Las demás escrituras (publicar imágenes de otras unidades, políticas, modelos) las hacen los documentos dueños que la guía enlaza. Las órdenes de `git` de «El clon de promoción» (F0, paso 11: clonar y `git pull --ff-only`) solo escriben en ese clon, no en el clúster, y no amplían la lista.
- No repite lo que ya está escrito: remite por ruta y sección a cada documento dueño y dice **qué parte** de él entra (tabla de abajo). Si un documento dueño está mal, es un hallazgo de su unidad.
- Cada fase termina con una **puerta**: lo que debe verse para seguir y a qué unidad apunta cada síntoma si no se ve. Cada espera dice cuánto dura y qué se mira mientras tanto; ninguna espera es fija sin una condición observable.
- La evidencia de cada fase va en su plantilla de `aidlc-docs/construction/system-verification/evidence/kind/` (comando, salida sin secretos, esperado frente a obtenido). Lo que se pega en una plantilla nunca lleva un token, una cookie, una contraseña ni una semilla.
- **Anota la duración real de cada fase** (plantilla 12): las estimaciones de abajo son sin medir.

## Quién hace qué

| Quién | Qué hace | Con qué |
|---|---|---|
| **Codificador** (U12-T06, sin clúster) | Esta guía, el inventario único de lo que solo se ve en kind, los guiones de lectura de `system-verification/docs/kind/`, el humo (`humo.py`), las plantillas y el cierre | Dobles, Testcontainers y Docker local. Ningún kubeconfig |
| **Operador** (tú, en kind) | Publica imágenes y fija digests por PR; sincroniza por waves; arranca política y modelo; corre el humo, las 8 secciones y las cuatro demos; devuelve el clúster a su estado; abre el **PR de verificación** | Esta guía, los guiones, la imagen de U12 y el kubeconfig de administrador de kind |
| **Revisor** (agente, sin clúster) | Lee la evidencia del PR de verificación: coteja esperado y obtenido, comprueba los hashes del manifiesto y asigna cada fallo a una unidad. No ejecuta nada contra kind | Solo lectura |
| **Personas de `CODEOWNERS`** | Aprueban y fusionan el PR de verificación (`.github/CODEOWNERS`, línea 9: `vectra-risk/system-verification/evidence/`). Hoy son dos personas, no los equipos `calidad` y `cumplimiento` que nombra el plan | GitHub |

**Cómo vuelve la evidencia al loop.** En un PR, el **PR de verificación**, desde una rama `verificacion/<fecha>-<commit>`:
1. `system-verification/evidence/<fecha>-<commit>/` con `manifest.json`, `verification-report.md` y lo que escribió cada sección. Lo escribe la herramienta; nadie lo edita a mano.
2. Las plantillas `00` a `12` llenas, con «Estado: completa» o «fallida».
3. `aidlc-docs/construction/system-verification/evidence/cierre-demo.md`: el resultado de cada entrada K del inventario.
4. El plan de U12: el Paso 18 pasa a `[x]`.

Un `falla` no impide fusionar la evidencia: la evidencia dice la verdad. Cada `falla` abre una tarea en la unidad dueña; solo un fallo que rompe una de las cuatro demos obliga a repetir esa demo.

## Riesgos que pueden impedir una demo

| Id | Riesgo | Demo | Señal | Plan B |
|---|---|---|---|---|
| **R-1** | **U3 tarda o da 504 al cron de U9.** U03-T07 está aparcada y `main` no pone tope por solicitud (`DECISIONES-LOOP.md`, línea 94). La forma que usa U9 midió 0,14 a 0,21 s; la consulta sin versión, hasta 9,6 s. Sin respuesta no hay `freeze` | **D2** | El log del Job de bias trae 504 o `agregador_atrasado`; no hay `freeze` tras dos corridas (30 min) | (1) Correr D2 con la máquina sin otra carga: nada de `decisions`, de construir imágenes ni de navegadores de más. (2) Esperar la corrida siguiente (15 min): `rt2` se retoma. (3) Si el **primer ensayo** da 504, se para y se avisa: reactivar U03-T07 es decisión del usuario. Tras tres corridas sin `freeze`: D2 queda `no ejecutado` con la causa y se hace el rollback |
| **R-2** | **`ImagePullBackOff`:** una imagen sin publicar o un digest de los values que no es el que se publicó (`vectra-risk-gitops/values/kind` ya no trae ningún digest de ejemplo) | Todas | `arranque.sh` | F1 completa antes de sincronizar. Un solo PR de digests con `generate.py` regenerado. Si un pod sigue así, su digest no coincide con el publicado: compáralo con `docker inspect` |
| **R-3** | **El realm viejo** en el kind: ningún login funciona | Todas | «Unexpected error when handling authentication request»; o el login termina en una pantalla de perfil | Resincronizar `keycloak` (`identity-edge/docs/realm-importacion.md`, línea 28). No hace falta borrar el realm. Después, `humo login`. El aviso de la política de contraseñas y la segunda credencial OTP son esperados (K-27) |
| **R-4** | **Memoria:** 13,8 GiB de requests en una máquina de 14 GiB, más la estación (la imagen de U12 con Chromium, el navegador del presentador, Docker). En D2 conviven el modelo activo, el proxy y el de staging | Todas; sobre todo D2 | `free -m` con menos de 1,5 GiB disponibles; un pod `OOMKilled`; el escritorio lento | Cerrar todo lo demás. No construir imágenes durante las demos. Retirar los `InferenceService` de staging en cuanto `rt2-setup` y `rt3` terminen. Si no alcanza: parar, medir con `memoria.sh` y decidir; no se bajan requests sin un PR |
| **R-5** | **Los tres arreglos de autenticación solo se han probado contra un Keycloak local:** el emisor público que valida cada servicio (U02-T21), la `aud` de la aserción de servicio (U00-T04) y el realm (U02-T22). Nunca en kind con el realm real, PostgreSQL, Infinispan y el gateway | Todas | 401 en toda la API (emisor); `invalid_client: Invalid token audience` en los logs y ningún caso sale de `en_evaluacion` (`aud`); login roto (realm) | No hay atajo: es un defecto de U0 o de U2 y va por tarea y PR. Por eso F3 y F4 van **pronto** (jornada 1): queda un día para corregir antes de las demos. Una investigación de solo lectura concluyó que las audiencias cuadran en las 20 llamadas (el token de usuario lleva seis audiencias fijas; cada cliente de servicio pide el scope que añade la del destino), pero solo dos casos están medidos: F4 comprueba que un servicio real acepta un token real |
| **R-6** | **La serie de Linkerd:** nadie ha visto en un clúster el target `linkerd-proxy` de `vectra-mock` ni las etiquetas reales de `inbound_http_authz_deny_total` (según el código del proxy trae `route_name`; la prueba de U1 declara otras). El `Server` del 4191 puede bloquear el raspado o las sondas | **D3** | `up{namespace="vectra-mock"}` en 0 o ausente; los pods de `vectra-mock` sin `Ready`; `CoreWriteAttempt` no dispara aunque el Job recibió 403 | K-21 se comprueba en F2, un día antes. Si la serie existe con otras etiquetas, se anota el conjunto real y es una tarea corta de U1 o de U8. En la demo, el 403 del log del Job y el contador en 0 siguen siendo ciertos; el oráculo marcará `falla` y el informe lo dirá |
| **R-7** | **La bóveda de kind guarda todo en memoria.** Un reinicio de su pod en los dos días borra lo sembrado y las claves nuevas no coinciden | Todas | Todos los `ExternalSecret` fallan a la vez; los logins dejan de servir tras horas; `humo` o `prepare` no leen credenciales | «Después de reiniciar la máquina» (más abajo) es el único sitio: vuelve a sembrar (`seed-vault.sh` y `seed-vault.sh identity`: desde U01-T16 **recuperan de los `Secret` antes de generar** y su informe dice qué generaron) y **pon al día solo lo que el informe diga generado** (MinIO, Grafana, PostgreSQL; Keycloak, Valkey y `envoy-ratelimit` sin medir; Tempo y Loki solo si los reactivaste: kind ya no los instala). «Vault reiniciado» de `platform/runbooks/install.md` es el procedimiento. K-05 lo mira al empezar cada jornada: `arranque.sh vault` compara siempre el arranque del contenedor de la bóveda con la última sincronización de los `ExternalSecret` y falla si no se resembró después (haya reiniciado o se haya recreado el pod); solo avisa, y sale 0, si se reinició y sí se resembró. Las credenciales de los usuarios «-2» deben existir de nuevo (K-33) |
| **R-8** | **Calendario de D4:** `decisions` lanzada tarde, `product-metrics` arrancado antes que el registro, o lectura de `u11` fuera del día D + 1 UTC (desde las 00:00 UTC de D + 2 el «ayer» ya no tiene decisiones y D4 no pasa: F9) | **D4** | `decisions` se niega (hora); dashboard vacío; `/readyz` de `product-metrics` en 503 | Empezar la jornada 2 antes de las 12:00 de Colombia (17:00 UTC). `product-metrics` se sincroniza el último (K-18). Leer D4 antes de las 00:00 UTC de D + 2 (las 19:00 de Colombia de D + 1). Si el dashboard está vacío dentro de ese día, esperar la siguiente pasada (15 min) antes de darlo por fallo |

Los más probables: **R-5** (tres cambios sin probar juntos en un clúster), **R-2** y **R-4** (seguros si no se atienden) y **R-1** (medido bajo carga).

## Si algo falla: a qué unidad apunta cada síntoma

Un fallo en kind aparece en U12 y cuesta más ubicar su unidad (costo aceptado de la enmienda §8, `aidlc-docs/construction/plans/demo-recorte-funcional.md`, línea 429). Esta tabla es el primer paso.

| Síntoma | Causa más probable | Unidad | Fuente |
|---|---|---|---|
| Pod en `ImagePullBackOff` | Falta publicar la imagen, o su digest en los values no es el que se publicó (los values de kind ya no traen ninguno de ejemplo) | La del pod | `CANDIDATAS.md`, línea 701; `identity-edge/docs/paso-16-kind.md`, línea 15 |
| Contenedor que **sale con código 0 y sin mensaje** (`reason: Completed`, reinicios sin error): un servicio que falla al arrancar por una variable o la llave que falta no dice nada | Falta una variable (por ejemplo `VECTRA_ASSERTION_AUDIENCE`) o la llave `private_key_jwt` no está montada. Defecto conocido de U0 | U0 (`run_service`); mira el `ExternalSecret` de esa unidad | `revisiones/U08-T05/ronda-1.md`, línea 66; `CANDIDATAS.md`, líneas 616 y 624 |
| Pod en `CreateContainerConfigError` | El `ExternalSecret` no está `SecretSynced`: ruta sin sembrar en la bóveda | U1 o U2 (siembra) | `identity-edge/docs/paso-16-kind.md`, §5, «Importación del realm» |
| Todos los `ExternalSecret` fallan de golpe («could not get secret data from provider»), o los logins dejan de servir tras horas; `arranque.sh vault` marca el pod de la bóveda que se reinició (`restartCount` mayor que 0) y no se resembró después (si ya la resembraste, solo avisa y sale 0) | La bóveda se reinició (también al reiniciar la máquina, con cualquier código de salida): en kind guarda todo en memoria. Ver «Después de reiniciar la máquina» | U1 | `platform/runbooks/install.md`, «Vault reiniciado» |
| Pods con malla en `Unknown` o `ContainerCreating`; `linkerd-cni` con `too many open files` (cientos de reinicios) | El límite de inotify volvió a 128 (solo si se aplicó con un `sysctl` suelto: el runbook lo deja persistente en `/etc/sysctl.d/`), y los pods con malla creados antes del plugin de CNI no se recuperan solos (`linkerd-network-validator`). Ver «Después de reiniciar la máquina» | U1 | `platform/runbooks/install.md`, «Antes de instalar: memoria y Docker» y «Vault reiniciado» |
| Un servicio que lee MinIO da 403 o «The request signature we calculated does not match» después de volver a sembrar la bóveda (el 2026-11-14 fueron Tempo en `CrashLoopBackOff` y Loki con 403, de cuando estaban instalados; hoy kind no los trae) | MinIO conserva las claves viejas de sus usuarios: el Job del chart solo crea un usuario si no existe. Ver «Después de reiniciar la máquina» | U1 (el runbook solo reinicia MinIO y resincroniza `minio`) | `platform/runbooks/install.md`, «Vault reiniciado» |
| Grafana `OOMKilled` al arrancar, o 401 con la clave de `admin` del Secret | 250 MiB en reposo con un límite de 256 MiB; y la base de Grafana conserva la clave vieja de `admin`. Ver «Después de reiniciar la máquina» | U1 | `platform/runbooks/install.md`, «Vault reiniciado» |
| Todo login da «Unexpected error when handling authentication request» | El kind tiene el realm viejo | U2: resincronizar | `identity-edge/docs/realm-importacion.md`, líneas 10 y 28 |
| El login termina en una pantalla de perfil | `VERIFY_PROFILE` activa: realm viejo | U2 | `identity-edge/docs/realm-importacion.md`, línea 11 |
| `login_rejected` al repetir un comando de `humo` o de la CLI con el mismo usuario | Reuso del código TOTP dentro de su ventana de 30 s (cuenta para el bloqueo por fuerza bruta) | El operador: espera 30 s entre comandos | `humo.py`, cabecera |
| Toda la API da 401 con un token válido | El servicio valida otro emisor (`iss`) | El servicio que responde 401 (`humo flujo --delivery /verification/reference-model/.out` nombra el destino) | `CANDIDATAS.md`, líneas 692 y 702 |
| Ningún caso sale de `en_evaluacion`; logs con `invalid_client: Invalid token audience` | La `aud` de la aserción de servicio | U0 y el chart del servicio | `identity-edge/docs/emisor-de-tokens.md`, línea 81 |
| Todos los casos salen `revision_requerida` | La vigencia de `reference-policy.json` no cubre la fecha | U5 y U4 | `aidlc-docs/construction/plans/demo-recorte-funcional.md`, línea 388 |
| Casos en fail-closed con `serving_config_unavailable` | No hay política activa o governance no responde | U4 | `aidlc-docs/construction/plans/demo-recorte-funcional.md`, líneas 43 a 47 |
| `case-service` no conecta con la base | `verify-full`: el certificado no cubre `case-db-rw.vectra-data.svc.cluster.local` | U8 y U1 | `aidlc-docs/construction/case-management/evidence/cierre-demo.md`, línea 74 |
| `product-metrics` con `/readyz` en 503 y dashboard vacío | Arrancó antes que el registro: reintenta a los 15 min | U11 (esperar hasta 30 min) | `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md`, línea 54 |
| Los últimos casos de `decisions` quedan sin decidir | La bandeja se listó antes de que llegaran a `listo`; o siguen en `en_sincronizacion` (el worker los reintenta) al vencer `--settle-timeout`: la salida y el manifiesto los cuentan por separado (`undecided_after_wait` y `syncing_after_wait`) | U12; los `en_sincronizacion`, U8 | `CANDIDATAS.md`, línea 676 |
| Un servicio de U0 no deja pasar ninguna petición con un token válido y registra `DependencyUnavailable` al refrescar el JWKS (Keycloak sí responde) | El JWKS del realm trae una llave de cifrado (`use: enc`, RSA-OAEP) y la caché de JWKS de una imagen anterior a U00-T05 no la salta: la imagen se construyó sin ese arreglo | U0 (rehacer la imagen en F1 con el commit que lo trae) | `bitacoras/U00-T05.md` |
| La primera petición al gateway tras ≈ 90 s sin tráfico falla con un error de TLS; el `linkerd-proxy` del gateway registra `Connection denied server.name=deny tls=None(PortSkipped)` | El contenedor `envoy` no declara el 10443 como `containerPort` y, tras ≈ 90 s sin tráfico, el proxy de Linkerd deja de admitirlo (U02-T25 lo declara en `envoyDeployment.patch`) | U2 (`gateway` sincronizado con el parche) | `identity-edge/docs/adr-envoy-gateway.md`, «U02-T25» |
| Pods nuevos de un nodo en `ContainerCreating` con `plugin type="calico" failed (add)` y `connection is unauthorized: Unauthorized` | Las credenciales del plugin de Calico (`calico-kubeconfig`) dejaron de refrescarse en ese nodo; recrear el pod `calico-node` del nodo lo arregló (orden del operador fuera de la lista cerrada: está en el runbook) | U1 | `platform/runbooks/install.md`, «Lo medido el 2026-11-15 al desplegar U2 en kind» |
| El primer `sync keycloak` termina en `Failed` («statefulsets.apps "keycloak" not found») y no corre `keycloak-config-cli` | El HPA se evalúa antes de que exista el StatefulSet; el segundo sync termina bien e importa el realm. Procedimiento propuesto, no medido: sincronizar `gateway` antes y repetir `keycloak` | U2 | `platform/runbooks/install.md`, «Lo medido el 2026-11-15 al desplegar U2 en kind» |
| Un pod nuevo se queda en `Init:1/2` y su `linkerd-proxy` registra `invalid peer certificate: certificate expired` (tras suspender la máquina) | El certificado del plano de control de Linkerd vive 24 h y venció durante la suspensión; reiniciar los pods de `linkerd` (la identidad primero) es una orden del operador fuera de la lista cerrada: está en el runbook | U1 | `platform/runbooks/install.md`, «Tras reiniciar la máquina», párrafo «Tras suspender la máquina» |
| `https://vectra.localtest.me` no conecta desde la estación (nada responde en `127.0.0.1:443`) | El nombre resuelve a `127.0.0.1` y ahí no escucha el gateway: responde en la dirección del `LoadBalancer`, y Docker puede reasignarla al reiniciar. F0 y F5 corren `platform/kind/gateway-address.sh` | U1 | `platform/runbooks/install.md`, «Lo medido el 2026-11-15 al desplegar U2 en kind», hecho 4 |
| `decisions` termina en `no ejecutado` con `decisions_lectura_agotada`: el BFF respondió 429, 502, 503, 504 o no respondió durante todo el tope de la lectura (300 s) | Un fallo transitorio que no cedió; la sección queda `interrumpida` con lo enviado ya en el manifiesto (`decisions.sent`, `decisions.accepted`) | U10 o U2 según el estado; **repetirla envía otros 2 000 casos** (F6) | `system-verification/src/vectra_verification/retry.py` |
| 429 durante `decisions` | Límite del gateway: 30/s para el simulador, 20/s por usuario en `/api/console` | U2; bajar el ritmo | `identity-edge/gateway/routes.yaml`, líneas 87 a 97 |
| No hay `freeze` tras dos corridas de bias; el log del Job de bias trae 504 o `agregador_atrasado` | U3 tarda con la máquina cargada, o el agregador va atrasado | U3 (R-1) | `DECISIONES-LOOP.md`, línea 94; `CANDIDATAS.md`, línea 254 |
| `CoreWriteAttempt` no dispara aunque el Job recibió 403 | La serie del proxy no existe: target `linkerd-proxy` caído o etiquetas distintas | U1 (R-6) | `aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md`, línea 28; `CANDIDATAS.md`, línea 719 |
| Los pods de `vectra-mock` no quedan `Ready` | El `Server` del 4191 bloquea las sondas `/live` y `/ready` | U1 (U01-T09) | `aidlc-docs/construction/case-management/evidence/cierre-demo.md`, línea 69 |
| Un pod `OOMKilled`, o el escritorio se congela | Memoria (R-4) | La del pod; parar y medir | `DECISIONES-LOOP.md`, línea 78 |

## Cómo dejar el clúster como estaba

BR-U12-10: «RT-2 y RT-3 devuelven el entorno a su estado inicial al terminar: revierten por PR lo desplegado y vuelven al modelo de referencia con un rollback». La guía lo pide en F7 y F8 y lo comprueba en F10 con `estado-final.sh`:

1. **F22 encendido:** el PR de reversión fusionado y `network` sincronizada con prune; los cinco recursos de F22 otra vez presentes; un caso nuevo llega a `listo`.
2. **Modelo de referencia `activo`** y el proxy `inactivo`; ninguna versión `congelado`. `estado-final.sh` recibe el `model_version_id` del modelo de referencia (`--referencia`) y falla si el modelo activo es otro (con el proxy `activo` ya no sale 0).
3. **`InferenceService` de staging retirados** (el PR de retiro de `proxy-staging` y de `rt3-staging`, que arma `entrada.py --retirar`: `git apply -R` del parche de alta ya no aplica cuando `promotion-tool` reescribió el bloque).
4. Lo que **queda** y se anota: el `runId` en `vectra-risk-gitops/values/kind/case-management.yaml`; los casos `no_disponible` de D1 y la alerta `FailClosedPersistente` (no hay reintento: P-16 de la enmienda sigue pendiente); los 2 000 casos decididos; la segunda credencial OTP de cada usuario si se reimportó el realm; el Job `rt5-demo-<runId>`.

## Después de reiniciar la máquina

Reiniciar la máquina (o apagarla entre las dos jornadas) deja el kind arrancado y **no sano**. Este es el único sitio donde la guía lo dice: la puerta de F0, el inicio de la jornada 2 (los prerrequisitos de F5), el riesgo R-7 y la tabla de síntomas remiten aquí. Todo lo que sigue se **midió** en un kind de este repositorio tras reiniciar la máquina (2026-11-14), salvo lo que dice «no está medido». Las órdenes de escritura son **del operador**; las que caben en la lista cerrada de la guía van en un bloque `bash operador`. **Las que no caben no se escriben aquí y la lista no se amplió: están en el runbook de U1, [`platform/runbooks/install.md`](../../platform/runbooks/install.md#vault-reiniciado), secciones «Vault reiniciado» y [«Tras reiniciar la máquina»](../../platform/runbooks/install.md#tras-reiniciar-la-máquina)**, y cada paso de abajo dice cuál es su paso del runbook. Orden del runbook para una máquina reiniciada: `sysctl`, los contenedores de kind y del registro, `cloud-provider-kind` (desde U01-T16 se lanza con nombre y `--restart=always` y vuelve con Docker; si se lanzó antes con `--rm`, no sobrevive al reinicio y sin él los `LoadBalancer` quedan sin dirección: «Tras reiniciar la máquina», paso 2), `platform/kind/gateway-address.sh` (el Docker reasigna las direcciones de la red `kind`: la del gateway puede haber cambiado) y luego los pasos de esta lista. Lo medido en esta sección es de 2026-11-14 y 2026-11-16; **la siembra con recuperación (U01-T16) se probó con ejecutores falsos y no se ha corrido aún en el clúster**. **Si la máquina estuvo suspendida y no reiniciada,** lee además el párrafo «Tras suspender la máquina» de [«Tras reiniciar la máquina»](../../platform/runbooks/install.md#tras-reiniciar-la-máquina) (medido el 2026-11-16): el certificado del plano de control de Linkerd vive 24 h y puede haber vencido (un pod nuevo en `Init:1/2` y `certificate expired` en su `linkerd-proxy`); reiniciar los pods de `linkerd` es una orden del operador que no cabe en la lista cerrada y no se escribe aquí.

1. **El límite de inotify, primero.** `sysctl fs.inotify.max_user_instances` valía 128 tras el reinicio (entonces no estaba en `/etc/sysctl.d/`) y `linkerd-cni` falló en los dos workers con `couldn't initialize inotify: too many open files` (más de 840 reinicios). Con 1024 (y `max_user_watches` en 1048576, persistente en `/etc/sysctl.d/`) arrancó. El valor que aplica es el del runbook, **1024**. Aplicarlo en el host es una **orden del operador** y no cabe en la lista cerrada de esta guía: su línea de `tee` y `sysctl --system` está en [`install.md`, «Antes de instalar: memoria y Docker»](../../platform/runbooks/install.md#antes-de-instalar-memoria-y-docker) y el paso 1 de [«Vault reiniciado»](../../platform/runbooks/install.md#vault-reiniciado) la remite. Después: `system-verification/docs/kind/arranque.sh linkerd-cni` en 0 (su Application puede verse `Healthy` mientras los pods fallan: mira los pods, no la Application).
2. **Los pods con malla no se recuperan solos.** Sus sandbox se crearon antes de que el plugin de Linkerd estuviera en la configuración de CNI: `linkerd-network-validator` sigue fallando («Failed to validate networking configuration») aunque `linkerd-cni` ya corra, y los pods quedan en `Unknown`. Hay que **recrearlos** (borrar el pod; el controlador lo vuelve a crear), en este orden medido: primero los del namespace `linkerd`, luego los de `vectra-data`, luego los de `vectra-observability`. Es una **orden del operador** que no cabe en la lista cerrada (solo se admite borrar el pod de Keycloak, y solo en F11): no se escribe aquí, está en el paso 2 de [«Vault reiniciado»](../../platform/runbooks/install.md#vault-reiniciado) (borrar los pods de un namespace y esperar a que vuelva a `Running`, uno por uno). Los demás namespaces con malla no están medidos: `arranque.sh` dice cuáles siguen en `Unknown` o `ContainerCreating`; lee con `system-verification/docs/kind/arranque.sh linkerd vectra-data vectra-observability` entre un namespace y el siguiente.
3. **Bóveda vacía.** Los `ExternalSecret` quedan en `False` («could not get secret data from provider»): la bóveda de kind guarda todo en memoria. `arranque.sh vault` marca el pod de la bóveda que **no se resembró después de arrancar**, con cualquier código de salida y con cualquier número de reinicios: compara siempre el arranque de su contenedor con la última sincronización de los `ExternalSecret` (el contador de reinicios no baja nunca y vuelve a 0 si el pod se recrea, así que no es la puerta). Con la bóveda resembrada, un pod con reinicios es un AVISO y el guion sale 0; sin ningún `ExternalSecret` con el que comparar, falla y lo dice. **Orden del operador**, de los documentos dueños (`platform/kind/seed-vault.sh` y `platform/kind/seed-vault.sh identity`, F0 paso 5; paso 3 de [«Vault reiniciado»](../../platform/runbooks/install.md#vault-reiniciado)): medido el 2026-11-16: los 71 `Secret` destino seguían con los valores de antes). Desde U01-T16 la siembra **recupera antes de generar**: devuelve a la bóveda lo que esos `Secret` guardan, imprime por ruta cuántas propiedades conservó, recuperó y generó (con los nombres de las generadas, nunca los valores) y cierra con «nada que realinear» o con lo que sí hay que realinear: **léelo antes de seguir**. Con todo recuperado, los pasos 4 a 6 no hacen falta; lo que genera son **claves nuevas** (seis rutas hoy, todas de `identity`; ver el paso 3 de «Vault reiniciado») que ya no coinciden con las que guardan MinIO, Grafana y Keycloak: los pasos 4 a 6 son solo para lo generado.
4. **MinIO conserva las claves viejas de sus usuarios.** El Job `minio-post-job` del chart solo crea un usuario si no existe («User already exists») y **no cambia la clave** de uno que ya existe; los usuarios viven en el volumen. La sincronización que pide `install.md` («Vault reiniciado», paso 3) terminó bien y, con Tempo y Loki instalados (así estaban el 2026-11-14; desde U01-T11 kind ya no los instala), Tempo siguió en `CrashLoopBackOff` («The request signature we calculated does not match») y Loki con 403. Con los usuarios que kind tiene hoy el síntoma es el mismo en otro cliente de MinIO (403 o la misma firma); empieza por sincronizar `minio`:
   ```bash operador
   argocd app sync minio
   ```
   No basta. Lo que lo arregló fue un Job de una sola vez que corre el script `add-user` del chart forzando `mc admin user add` para cada uno de los 10 usuarios de MinIO de kind (los de `platform/data/minio/values-kind.yaml`; entonces eran 12, con los de Loki y Tempo), con `priorityClassName: vectra-normal` (Kyverno lo exige) y, si Tempo estaba instalado, reinicia los pods de Tempo: todo ello es una **orden del operador** que **no cabe en la lista cerrada** (crear un Job y reiniciar pods de Tempo no están entre las escrituras admitidas), así que la guía no la escribe: el procedimiento (leer el script `add-user` del ConfigMap `minio`, crear el Job con la imagen `mc` del chart y `priorityClassName: vectra-normal`, forzar `mc admin user add`) y el reinicio de Tempo (solo si lo reactivaste) están en los pasos 4 y 5 de [«Vault reiniciado»](../../platform/runbooks/install.md#vault-reiniciado), que dice además que el Job no está versionado como manifiesto. Quién y cómo retira o reactiva Loki, Tempo y Alloy en kind está en [`install.md`](../../platform/runbooks/install.md) (la nota «Qué instala kind»). Comprueba: `system-verification/docs/kind/arranque.sh vectra-data vectra-observability` en 0.
5. **Grafana.** El contenedor `grafana` usa 250 MiB en reposo con un límite de 256 MiB: `OOMKilled` al arrancar con la máquina cargada, y otra vez al ejecutar `grafana cli admin reset-admin-password` dentro del contenedor. La clave de `admin` del Secret dio 401 (la base conserva la vieja). Se subió el límite a 512 MiB a mano (una **deriva** respecto a Git: es de U1, por PR), se restableció la clave, se corrió `seed-vault.sh grafana-token` y se sincronizó `grafana-config`:
   ```bash operador
   argocd app sync grafana-config
   ```
   Subir el límite y restablecer la clave son **órdenes del operador** que no caben en la lista cerrada: no se escriben aquí, están en el paso 6 de [«Vault reiniciado»](../../platform/runbooks/install.md#vault-reiniciado) (`grafana cli admin reset-admin-password`; el límite ya está en 512 MiB en el runbook); `seed-vault.sh grafana-token` es del documento dueño (`install.md`, paso 9).
6. **Keycloak: no está medido.** En esa medición Keycloak no estaba instalado (se desplegó el 2026-11-15: lo medido desde entonces está en «Lo medido el 2026-11-15 al desplegar U2 en kind» de `install.md` y no cubre una resiembra). Con la siembra de U01-T16 (`platform/kind/vault_paths.py`, `plan_identity`), `seed-vault.sh identity` recupera de los `Secret` las contraseñas, las semillas TOTP y las llaves privadas de cliente, y **solo genera** lo que no puede: los pares de `channel`, `channel-simulator` y `verification-reader`, el `jwks` de `grafana` y las claves de `edge/valkey` (y `identity/break-glass`, que nadie lee). Keycloak conserva los `jwks` viejos hasta reimportar el realm: hasta entonces fallan `channel-simulator` y `verification-reader`, es decir, la verificación de U12. Si el informe generó algo de las rutas de `identity`, hay que resincronizar `keycloak` (el hook `keycloak-config-cli`), y puede no bastar: `config-cli` no reaplica las contraseñas de usuarios que ya existen (K-27). Nada de esto está medido (el runbook lo dice igual en el paso 8 de [«Vault reiniciado»](../../platform/runbooks/install.md#vault-reiniciado)); si el informe generó `edge/valkey`, el runbook pide reiniciar **juntos y enseguida** Valkey, los Sentinel y `envoy-ratelimit` (su paso siguiente: sin eso el `ratelimit` da `WRONGPASS` y `/auth/**` falla cerrado: el login responde 503; no medido); PostgreSQL tampoco (paso 7 del runbook: sus roles reciben contraseñas nuevas y puede hacer falta reiniciar los pods que las leen). Si después `humo login` falla, es de U2:
   ```bash operador
   argocd app sync keycloak
   ```
7. **Al terminar:** `platform/kind/gateway-address.sh` en 0, `system-verification/docs/kind/arranque.sh vault vectra-identity vectra-data vectra-observability vectra-edge vectra-serving vectra-app vectra-mock` en 0 (la puerta de F0), `identidad.sh` en 0 y, en la jornada 2, `humo login`. Si algo de la lista de arriba sigue fallando, anótalo en la plantilla 00 y no sigas.

**Lo que la lista cerrada no admite, y no se amplió:** borrar los pods de `linkerd`, `vectra-data` y `vectra-observability` (paso 2); crear el Job que reescribe las claves de MinIO y reiniciar los pods de Tempo (paso 4; solo si lo reactivaste: kind ya no lo instala); subir el límite de Grafana y restablecer la clave de `admin` (paso 5); aplicar el límite de inotify en el host (paso 1). Son órdenes del operador y están en [`platform/runbooks/install.md`](../../platform/runbooks/install.md), «Vault reiniciado» y «Tras reiniciar la máquina».

## Fases, orden y tiempos

Las Applications de U3 a U11 están todas en la **wave 5** y `model-serving` en la 6 (`vectra-risk-gitops/components.yaml`: las entradas con `wave: 5` y la de `model-serving`, con `wave: 6`). Sin auto-sync las waves no ordenan nada (`platform/runbooks/install.md`, §7 «Sincronizar en orden»): el orden dentro de la wave 5 lo fija esta guía.

| Fase | Qué | Tiempo estimado |
|---|---|---|
| **F0** Prerrequisitos | Máquina, herramientas, kind arriba, bóveda sembrada, paquetes de U5, calendario | 30 min, más la instalación de la plataforma si parte de cero |
| **F1** Imágenes y digests | Construir **del mismo commit** las imágenes de U3, U4, U6, U7, U8, U9, U10 y U11, publicarlas y fijar los digests en **un solo PR**; publicar la de U12 | 60 a 90 min |
| **F2** Sync y arranque | U2 si falta, `decision-registry`, `governance`, política, `model-serving`, modelo de referencia, `scoring-explainability`, `case-management`, `bias-monitoring`, retirar el eco, `console-bff` y `console-spa`, `product-metrics` | 2 a 3 h |
| **F3** Identidad y acceso | Realm, login por rol, K16, bóveda, consola en el navegador | 40 min |
| **F4** Flujo base | Una solicitud hasta `listo` y una decisión; **puerta de las cuatro demos** | 15 min |
| **F5** `prepare` y D3 | `prepare`, PR de `runId`, sync de `case-management`, la alerta en vivo | 20 min |
| **F6** `decisions` (D4, día D) | 2 000 casos y el conductor; `rt5` al terminar | ≈ 45 min |
| **F7** D1 (`rt3`) | RT3-a, c y d; PR de F22 apagado; esperar; PR de reversión | ≈ 50 min (12,4 a 19,3 de espera, la alerta unos minutos después, 2 PR) |
| **F8** D2 (`rt2-setup`, `rt2`) | PR `proxy-staging`; promoción; lote; `freeze`; 3 corridas de bias; reactivación; 1 corrida más; rollback; retirar staging | ≈ 3 h (más de 75 min de esperas, más 6 PR) |
| **F9** D4 (día D + 1 UTC) | `u11`; Grafana por `port-forward`; el dashboard «Producto» | 15 min, tras la espera |
| **F10** Informe y estado final | `report`; `estado-final.sh`; PR de verificación | 30 min |
| **F11** Opcionales | Sondas que no sostienen ninguna demo | 30 min |

**Orden de las demos: D3, D4 (día D), D1, D2, D4 (día D + 1).** Razones:
1. Es el orden de las secciones de la CLI (`prepare`, `decisions`, `rt5`, `rt3`, `rt2-setup`, `rt2`, `u11`, `report`). La guía no pide correr secciones fuera de orden.
2. `decisions` va antes de RT-2 y con el modelo sin congelar. Es además la única con hora límite: no empieza si no termina antes de las 23:00 UTC.
3. D3 dura segundos, no toca el modelo y su estímulo ya ocurrió en F5. Va primero para no perder la ventana de 5 min de la alerta.
4. D1 apaga F22 para todas las versiones. Si se cruza con `decisions` o con el lote de D2, arruina las dos. Va entre ambas, con su reversión comprobada.
5. D2 va la última del día D: es la más larga, depende de dos crons (bias cada 15 min, minutos 2, 17, 32 y 47; agregador cada 5) y deja el modelo congelado mientras dura.
6. D4 se cierra sola: el día D + 1 UTC empieza a las 19:00 de Colombia del día D, así que el dashboard se lee la misma noche; y **termina** a las 19:00 de Colombia del día D + 1 (00:00 UTC de D + 2): después el «ayer» ya no tiene decisiones y D4 no pasa (F9).

**Calendario.** Dos jornadas. Jornada 1 (F0 a F4): 5 a 7 h. Jornada 2 (F5 a F10): ≈ 5 h 30 min seguidos, empezando **antes de las 12:00 de Colombia (17:00 UTC)**, más, para F9, el día D + 1 UTC (de las 19:00 de Colombia del día D a las 19:00 de Colombia del día D + 1; la espera prudente hasta las 21:40 de Colombia, ver F9). Las esperas de aprobación de los ≈ 10 PR van aparte. En total, de 11 a 13 h de trabajo del operador.
- `decisions` se lanza antes de ≈ 22:18 UTC (la herramienta se niega si no puede terminar antes de las 23:00 UTC).
- El día D + 1 UTC no puede ser el día 1 del mes (falta el acumulado del mes).
- **D2 conviene terminarla antes de las 00:00 UTC (19:00 de Colombia).** Comprobado en `bias-monitoring` (`bias-monitoring/src/vectra_bias/window.py`, función `window_start`): tras una reactivación, la ventana de la versión empieza el **día UTC siguiente** a la reactivación. Antes de la medianoche, todo su rango cae antes del inicio y el Job de bias devuelve `sin_datos`; después, ya no hay datos nuevos de esa versión. Las dos vías dan «no se recongela», pero solo la primera está medida: cruzar las 00:00 UTC cambia el porqué sin que nadie lo haya probado. **La misma versión del proxy no se recongela el mismo día UTC de su reactivación** (la ventana empieza el día siguiente): el ensayo «en el otro modo» de F8 va **otro día UTC** (con un lote nuevo ese día; que alcance para congelar no está medido) o **con otro paquete** (otra corrida `run-N` de `reference-model/.out/proxy`, con otro `model_version_id`).
- **D4 solo pasa durante el día D + 1 UTC:** `u11` lee `period="day"`, el «ayer» de `product-metrics` (`product-metrics/src/vectra_product/compute.py`, `compute`): el día D + 1 UTC es el de las decisiones del día D; desde las 00:00 UTC de D + 2 es el día D + 1, sin decisiones, y la razón se omite («ausente, no 0»). **Lee D4 antes de las 00:00 UTC de D + 2 (las 19:00 de Colombia de D + 1).**
- Entre F5 y F10 no pueden pasar más de **3 días**: es la retención de Prometheus en kind (`platform/observability/values/kube-prometheus-stack-kind.yaml`, línea 5). Con más, el oráculo de RT-5 da `no ejecutado`.

## Documentos dueños a los que la guía remite

| Para | Documento | Qué parte entra |
|---|---|---|
| Herramientas, clúster, Argo CD, `sync`, bóveda, «Vault reiniciado» | [`platform/runbooks/install.md`](../../platform/runbooks/install.md) | «Antes de instalar», §1 a §10 y «Vault reiniciado» |
| U2: imágenes, secretos, sync y realm | [`identity-edge/docs/paso-16-kind.md`](../../identity-edge/docs/paso-16-kind.md) | §3, §4 y §5 (sin «Backend de eco» ni los ítems de §6) |
| Realm viejo y desbloqueo | [`identity-edge/docs/realm-importacion.md`](../../identity-edge/docs/realm-importacion.md) | «Qué hace el operador», con las dos correcciones de F3 |
| U3: imagen | [`decision-registry/docs/imagen-kind.md`](../../decision-registry/docs/imagen-kind.md) | «Publicar» |
| U4: imágenes, sync, política y modelo de referencia | [`governance/docs/paso-20-kind.md`](../../governance/docs/paso-20-kind.md) y [`governance/runbooks/kind-politica-de-referencia.md`](../../governance/runbooks/kind-politica-de-referencia.md) | §1 a §5 (sin los escenarios 4 y 7) |
| U6: imágenes y paquetes del model-store | [`model-serving/docs/paso-11-kind.md`](../../model-serving/docs/paso-11-kind.md) | §0 a §2 (paquetes: líneas 42 a 58) |
| U7, U8, U9, U11: imágenes y digests | [`scoring-explainability/docs/imagenes.md`](../../scoring-explainability/docs/imagenes.md), [`case-management/docs/imagenes.md`](../../case-management/docs/imagenes.md), [`bias-monitoring/docs/imagenes.md`](../../bias-monitoring/docs/imagenes.md), [`product-metrics/docs/imagenes.md`](../../product-metrics/docs/imagenes.md) | Enteros |
| U10: imágenes | [`console/README.md`](../../console/README.md) | «Imágenes» |
| U12: imagen, orden `docker run` (la función `vv`), prerrequisitos y lectura del informe | `system-verification/README.md` | «La imagen», «Cómo correrla: la orden `docker run`» y «Cómo correr cada sección» (la orden se muestra en F0, paso 9) |
| Las cuatro demos y sus PR preparados | [`system-verification/demos/journey-7-3.md`](../demos/journey-7-3.md), `journey-7-4.md`, `rt-5.md`, `dashboard.md`, [`demos/verify/`](../demos/verify) y [`demos/prs/`](../demos/prs) | Cada demo, en su fase |

## F0 Prerrequisitos y máquina limpia

Entradas: K-01 a K-05. Plantilla: `00-prerrequisitos.md`. Duración: 30 min, más la instalación de la plataforma si parte de cero. Puerta al final.

**Prerrequisitos de la máquina.**
- **Memoria: 14 GiB es el mínimo y 16 GiB lo recomendable.** Los requests del perfil de kind suman 13,8 GiB (`platform/tests/test_kind_profile.py`, `BUDGET_GIB`) y la estación suma encima la imagen de U12 con Chromium, el navegador del presentador y Docker. Con menos de 14 GiB, o con menos de 8 GiB disponibles al empezar, pasa una de tres cosas: pods que no se programan o mueren por `OOMKilled`, una instalación que se detiene a mitad de una wave, o el escritorio que se congela. Si pasa, para: bajar requests es una decisión del usuario, no del operador.
- **Docker Engine nativo** (`docker-ce`, no Docker Desktop salvo en una máquina grande ni el Docker de snap): las razones y los comandos están en `platform/runbooks/install.md`, «Antes de instalar: memoria y Docker». Allí mismo: el límite de inotify (`fs.inotify.max_user_instances`; `install.md` pide **1024** y `fs.inotify.max_user_watches` en 1048576, de forma persistente en `/etc/sysctl.d/`; en la medición 128 falló y 1024 funcionó: compruébalo con `sysctl fs.inotify.max_user_instances`. Persistente sobrevive a un reinicio de la máquina; **un `sysctl` suelto no**: tras un reinicio compruébalo otra vez, ver «Después de reiniciar la máquina»), las credenciales de Docker y comprobar que no hay otro clúster `kind`.
- **Herramientas, con versiones.**

| Herramienta | Versión | De dónde sale |
|---|---|---|
| kind | v0.33.0 | `platform/runbooks/install.md`, «Diagnóstico» |
| `kubectl` | de la versión del clúster, `kindest/node:v1.37.0` (`platform/kind/cluster.yaml`, línea 18); sirve la 1.36 a la 1.38 | su orden de versión del cliente (`platform/runbooks/install.md`, «Diagnóstico») |
| `helm` | v4.3.0 | `platform/tools.env` (`HELM_VERSION`); la instala `platform/install-tools.sh` |
| `conftest`, `kyverno`, `promtool`, `kubeconform`, `egctl`, `hadolint`, `actionlint` | las de `platform/tools.env` | `bash platform/install-tools.sh` las deja en `platform/.tools/bin`, con su SHA-256 comprobado |
| CLI de Argo CD | de la misma versión menor que el servidor del chart `argo-cd` 10.11.6 (`vectra-risk-gitops/components.yaml`, línea 26) | su orden de versión del cliente (`platform/runbooks/install.md`, «Diagnóstico») |
| `uv`, `python3`, `git`, `curl`, `openssl`, `gh` | recientes; `python3` 3.12 o superior | `gh` autenticado y commits firmados para los PR de `promotion-tool` (`governance/docs/paso-20-kind.md`, §1) |

  Las demos de U12 **no** usan `k6`: no lo instales para esto.

**Pasos.**

1. **Clona** el repositorio y entra a `vectra-risk/`. Todo lo demás corre desde ahí.
2. **Comprueba las herramientas** (solo lectura; la versión de `kubectl` y la del CLI de Argo CD las comprueba el «Diagnóstico» de `install.md`):
   ```bash
   kind version
   docker version --format '{{.Server.Version}}'
   free -m
   ```
3. **Descarga herramientas y charts** una vez: `bash platform/install-tools.sh` y `bash platform/charts.sh` (`platform/runbooks/install.md`, «Diagnóstico»).
4. **¿Hay un clúster `vectra`?** `kind get clusters`. Si no existe, o está a medio instalar, sigue `platform/runbooks/install.md` **de §1 a §10 completa** (llave de etcd, clúster, Calico, registro local y LoadBalancer, imágenes propias, Argo CD, sincronización en orden, secretos de Vault, token de Grafana, otros). Dos cosas fáciles de olvidar: el segundo terminal de §4 (`cloud-provider-kind`) **se queda corriendo** durante las dos jornadas, o el gateway pierde su dirección; y §10 emite el certificado del operador (K16) y exporta la CA interna que usa U12. El diagnóstico del paso 6 te dice qué parte de U1 ya está sana.
5. **Siembra la bóveda** si no lo está: `platform/kind/seed-vault.sh` (rutas de U1; §8 de `install.md`) y, para U2, `platform/kind/seed-vault.sh identity` (`identity-edge/docs/paso-16-kind.md`, §4). La segunda escribe las contraseñas y las semillas TOTP de **todos** los usuarios sintéticos, incluidos los «-2» del presentador (`analista-2`, `cro-2`, `cumplimiento-2`), en `identity/synthetic-users`.
6. **Diagnóstico inicial: salta lo que ya esté sano.** Con un kind que ya tiene parte instalada, este diagnóstico decide qué de F1 a F3 se hace:
   ```bash
   system-verification/docs/kind/memoria.sh antes
   system-verification/docs/kind/arranque.sh vault vectra-identity vectra-edge vectra-data vectra-observability vectra-serving vectra-app vectra-mock
   system-verification/docs/kind/observabilidad.sh targets
   ```
   `vectra.localtest.me` resuelve a `127.0.0.1`, y en `127.0.0.1:443` no escucha nada (`platform/kind/cluster.yaml` mapea ese puerto al nodo de control): el gateway responde en la dirección del `LoadBalancer` que le asigna `cloud-provider-kind`, y Docker puede reasignarla al reiniciar. Comprueba que la máquina llega al gateway (solo lectura; lo entrega U01-T16 y sale 0 si el nombre resuelve a esa dirección y responde; si no, dice qué línea de `/etc/hosts` falta):
   ```bash
   platform/kind/gateway-address.sh
   ```
   Esa línea de `/etc/hosts` es una **orden del operador** que no cabe en la lista cerrada y no se escribe aquí (está en `platform/runbooks/install.md`): la necesitan el navegador del presentador y `promotion-tool`; la herramienta de la imagen la recibe por `--add-host` en `vv` (paso 9). El Service se llama `api-gateway` en `vectra-edge` (`platform/operators/envoy-gateway.yaml` despliega el data plane con `type: GatewayNamespace`, que nombra el Service como el Gateway; lo mismo que lee `gateway-address.sh`): `kubectl --context kind-vectra get svc api-gateway -n vectra-edge` da la dirección en `EXTERNAL-IP`.

   Lee su salida así: pods de una unidad sin imagen (`ImagePullBackOff`) se hacen en F1; `ExternalSecret` sin sincronizar, en la siembra del paso 5; una Application fuera de `Healthy`, en F2. `arranque.sh` lee siempre también el namespace `linkerd-cni` aunque no lo pidas (su Application puede verse `Healthy` mientras sus pods fallan) y marca el pod de la bóveda que se reinició. Si la máquina se reinició desde la última vez, el diagnóstico sale con hallazgos a propósito: sigue «Después de reiniciar la máquina» antes de seguir. **Una unidad completa (imágenes, secretos, sync, realm, política, modelo de referencia, paquetes) que el diagnóstico muestra sana no se repite.** `arranque.sh` informa y sale con 1 cuando hay hallazgos; con 2 si no pudo leer.
7. **Paquetes de U5.** `make -C reference-model release` genera, en `reference-model/.out/`, el paquete base, `reference-model/.out/proxy/run-1`, `reference-model/.out/adversarial/rt3` y `reference-policy.json` (procedimiento: `reference-model/docs/release.md`). Comprueba que `reference-model/.out` existe y que la vigencia normativa de `reference-policy.json` cubre los dos días de la corrida (`aidlc-docs/construction/plans/demo-recorte-funcional.md`, línea 388); si no, todos los casos saldrán `revision_requerida`. Si la demo corre en otra máquina, copia allí `reference-model/.out` (ver los avisos del paso 9).
8. **La bóveda desde la estación** (la CLI de U12 y `humo` la leen; K16 no da este camino). En una terminal que se queda abierta:
   ```bash
   kubectl --context kind-vectra port-forward -n vault --address=127.0.0.1 pod/vault-0 8200:8200
   ```
   En la terminal de trabajo: `export VAULT_ADDR=http://127.0.0.1:8200` y `export VAULT_TOKEN=root` (el token de desarrollo de kind está escrito en `platform/operators/vault-kind.yaml`; en kind no es un secreto). Si el `port-forward` cae, la herramienta da un error claro: vuélvelo a abrir.
9. **La imagen de U12 y la orden `docker run`.** La herramienta se ejecuta **desde la imagen** (`system-verification/README.md`, «Cómo correrla: la orden `docker run`»), no desde el árbol de trabajo: la imagen lleva la herramienta, los guiones y los `verify` de las demos, `kubectl`, `python3` y el Chromium sin interfaz del login. La orden es **la función `vv` del README**, mostrada aquí una sola vez con las rutas de este repositorio; solo se agrega `--name` (para que `memoria.sh` encuentre el contenedor) y la lista `VV_EXTRA` (para `humo`). Si el README cambia, vale el README: `tests/unit/test_kind_guide.py` falla cuando una opción o un montaje del README falta aquí. Los montajes son `--mount type=bind`: si falta un archivo, Docker se niega en vez de crear un directorio de root.
   ```bash
   export VERIFICATION_IMAGE="${VERIFICATION_IMAGE:-localhost:5001/vectra/system-verification:dev}"   # en F1 la cambias por el digest
   export VERIF_HOME="${VERIF_HOME:-$HOME/.vectra-verification}"; mkdir -p "$VERIF_HOME"; chmod 700 "$VERIF_HOME"
   kind get kubeconfig --name vectra > "$VERIF_HOME/kubeconfig"
   kubectl --context kind-vectra get secret -n cert-manager vectra-internal-ca -o jsonpath='{.data.ca\.crt}' | base64 -d > "$VERIF_HOME/vectra-ca.pem"
   # `EVID` se calcula UNA vez por verificación y se guarda; cada terminal nueva lo lee (recalcularlo con la fecha y el commit apunta a otro directorio tras las 00:00 UTC o tras un `git pull`).
   [ -s "$VERIF_HOME/evid" ] || printf '%s\n' "$VERIF_HOME/evidence/$(date -u +%Y%m%d)-$(git rev-parse --short HEAD)" > "$VERIF_HOME/evid"
   export EVID="$(cat "$VERIF_HOME/evid")"
   mkdir -p "$EVID" && chmod 755 "$EVID"      # fuera del repositorio: `promotion-tool` exige el árbol limpio (paso 11). F10 lo copia al PR de verificación
   export VERIFICATION_DIR="$EVID"             # los `verify` de las demos leen el manifiesto de aquí
   export GATEWAY_ADDRESS="$(kubectl --context "${KUBE_CONTEXT:-kind-vectra}" get svc api-gateway -n vectra-edge -o 'jsonpath={.status.loadBalancer.ingress[0].ip}')"   # la dirección del gateway (paso 6)
   vv() {
     docker run --rm --name "vectra-verification-$$-$RANDOM" --read-only --tmpfs /tmp --network host \
       --user "$(id -u):$(id -g)" --memory 1g \
       --add-host "vectra.localtest.me:${GATEWAY_ADDRESS:?lee la dirección del gateway: platform/kind/gateway-address.sh}" \
       --security-opt seccomp=system-verification/seccomp/chrome.json \
       --mount type=bind,source="$VERIF_HOME/kubeconfig",target=/kube/config,readonly -e KUBECONFIG=/kube/config \
       --mount type=bind,source="$VERIF_HOME/vectra-ca.pem",target=/certs/ca.pem,readonly -e VERIFICATION_CA_FILE=/certs/ca.pem \
       --mount type=bind,source="$EVID",target=/verification/evidence \
       --mount type=bind,source="$PWD/vectra-risk-gitops/values/kind/case-management.yaml",target=/values/case-management.yaml,readonly \
       --mount type=bind,source="$PWD/reference-model/.out",target=/verification/reference-model/.out,readonly \
       -e VAULT_ADDR -e VAULT_TOKEN -e KUBE_CONTEXT \
       "${VV_EXTRA[@]}" "$VERIFICATION_IMAGE" "$@"
   }
   vectra-verification() { vv "$@"; }   # el nombre con que la guía llama a la herramienta
   humo() { local VV_EXTRA=(--mount type=bind,source="$PWD/system-verification/docs/kind/humo.py",target=/humo.py,readonly --entrypoint python); vv /humo.py "$@"; }
   ```
   **`EVID` es un directorio fuera del repositorio** (`$VERIF_HOME/evidence/<fecha>-<commit>`), guardado en `$VERIF_HOME/evid` la primera vez. En **cada terminal nueva**, repite este bloque: con `$VERIF_HOME/evid` presente, `EVID` lee el de la primera vez (no se recalcula) y `GATEWAY_ADDRESS` se vuelve a leer del Service del gateway; tras un reinicio de la máquina, relee la dirección antes de cualquier `vv` (`vv` se niega a arrancar sin ella: con `--network host` y sin `--add-host`, `vectra.localtest.me` sería `127.0.0.1` y nada responde). **No está medido** que Docker aplique `--add-host` con `--network host`: si la herramienta no llega al gateway, la línea de `/etc/hosts` del paso 6 es la otra vía, y lo dices en la plantilla 00.

   Con estas tres funciones, cada `vectra-verification <sección>` y cada `humo <subcomando>` de la guía corre dentro de la imagen (el punto de entrada de la imagen es `vectra-verification`; `humo` lo cambia por `python`, que la imagen trae con sus dependencias). `VERIFICATION_IMAGE` es la imagen **por digest** (la publicas en F1). El token de la bóveda va como variable (`-e VAULT_TOKEN`; `-e KUBE_CONTEXT` solo importa si tu contexto no es `kind-vectra`), nunca como archivo ni en la línea de órdenes; la herramienta solo acepta `127.0.0.1`, `localhost` y `vault.vault.svc` como bóveda (paso 8). **Si la orden se niega a arrancar Chromium** (el sandbox necesita espacios de nombres de usuario sin privilegios y el perfil `seccomp`), el login y `humo consola` terminan con `browser_launch_error` (código 2); la herramienta nunca desactiva el sandbox.

   **Avisos de la herramienta y de la imagen** (de `system-verification/README.md` y de `CANDIDATAS.md`; la demo los respeta):
   - **Solo Linux con Docker Engine, no Docker Desktop (tampoco en Linux).** `--network host` comparte la red del host: con Docker Desktop (macOS, Windows o Linux) comparte la de la máquina virtual y ni el gateway de kind ni los `port-forward` llegan. No está probado: corre la demo en Linux con Docker Engine (o en una máquina virtual Linux con Docker y kind). `make`, `python3` y `git` hacen falta en la máquina (`make image`, la huella de las fuentes y `--commit` de `prepare`).
   - **El contexto de `kubectl` es `kind-vectra`** (el que crea kind para un clúster llamado `vectra`): la herramienta y los `verify` lo leen del kubeconfig. Con otro nombre, exporta `KUBE_CONTEXT=<contexto>` antes de `vv` y de los `verify` (y cambia `--context kind-vectra` de las órdenes de la guía). Un contexto que no existe da código 2, no una traza.
   - **Cómo leer el código de salida** (README, «Códigos de salida»). Para las secciones: `0` todo `pasa`; `1` algo `falla` (un incumplimiento del sistema, anótalo); `2` `no ejecutado`: un prerrequisito o la **infraestructura** falló (Chromium que no arranca, la bóveda que no responde, un `port-forward` caído, un contexto inexistente) y lo dice con un código estable y sin traza (`decisions_sesion_oidc_no_disponible`, `u11_kubectl_no_responde`): **no es un fallo del sistema**; arregla el entorno y repite la sección (queda `interrumpida`); `3` la herramienta se negó (barrera, uso, `prepare` ausente, directorio sin escritura). Para los `verify` de `demos/verify/`: `0` lo esperado, `1` no es lo esperado, `2` no se pudo leer (por ejemplo, `rt-5.sh 1` con otro contexto o sin conexión; solo un `NotFound` es «no existe», 1).
   - **La entrega de U5** (`reference-model/.out`, paso 7) se genera con el repositorio. Si la demo corre en otra máquina, **cópiala allí** antes de empezar: se monta de solo lectura en `/verification/reference-model/.out`. `prepare`, `rt5`, `u11` y `report` no la necesitan; `decisions`, `rt3`, `rt2-setup` y `rt2` sí. Sin `--delivery` en `prepare` ni en la sección, la sección termina con código 3 y `ruta_faltante`.
   - **`--memory 1g` no está medido con 2 000 decisiones.** Lo mides tú en F6 (`memoria.sh durante` y `docker stats`, K-09): si el contenedor sale `OOMKilled` (código 137), anótalo en la plantilla y sube `--memory` en `vv` antes de volver a correr la sección.
   - **El perfil `seccomp`** (`system-verification/seccomp/chrome.json`) sale de `/usr/share/containers/seccomp.json` (`containers-common`) **recortado** (sin `keyctl`, `mount` y su familia, `pivot_root`, `syslog`, `reboot` y otras; lo que no está en la lista da EPERM), no es el de Playwright ni se afirma que sea idéntico al de Docker. Está probado solo en Ubuntu 26.04, kernel 7.0, Docker Engine 29.9.2 con AppArmor; **no** en otros kernels, Docker rootless, SELinux ni Docker Desktop. Si el perfil no deja arrancar el sandbox, el login termina con `browser_launch_error` (2) y la herramienta nunca desactiva el sandbox. Se pasa la ruta del repositorio (`--security-opt seccomp=system-verification/seccomp/chrome.json`), así que se corre desde `vectra-risk/`.
   - **La ventana TOTP no se comparte entre procesos.** Dos órdenes seguidas con el mismo usuario dentro de 30 s reusan el código y Keycloak rechaza la segunda; **un rechazo cuenta para el bloqueo por fuerza bruta**. Espera 30 s entre una orden y la siguiente que use los mismos usuarios (`humo login` lo recuerda al terminar).
   - **Una verificación, un directorio.** `prepare` se corre una vez por directorio de evidencias (`$EVID`); para otra verificación, un directorio nuevo: guarda el `evid` anterior (`mv "$VERIF_HOME/evid" "$VERIF_HOME/evid.<fecha>"`), haz `git pull --ff-only` en tu copia de trabajo y repite el bloque: el nombre del directorio sale de la fecha y del commit de **ese** momento. En la primera verificación ese commit (el de F0) es anterior a los digests de F1: el nombre es solo una etiqueta; el commit que se verifica es el que `prepare --commit` guarda en el manifiesto (F5).
10. **Calendario.** `date -u`. Decide las dos fechas (día D y día D + 1; el día D + 1 no es día 1 del mes) y empieza la jornada 2 antes de las 17:00 UTC.
11. **El clon de promoción** (donde se abren los PR y se corre `promotion-tool`). `promotion-tool` se niega con `working_tree_dirty` si `git status --porcelain` trae algo (`governance/promotion_tool/vectra_promotion/gitops.py`, `open_pr`), lee los values del árbol en que corre y crea la rama desde el `main` **local** (`git switch -c <rama> main`): con un árbol sucio (el directorio de evidencias, un `.patch` suelto) se niega, y con un `main` sin actualizar abre un PR sobre values viejos. Por eso **todo PR y toda orden de `promotion-tool` van en un clon limpio y aparte**, que no recibe archivos de la verificación; tu copia de trabajo (la de los pasos 1 a 10) queda para leer la guía y correr la imagen. La evidencia **no** se oculta con un `.gitignore`: tiene que acabar en el PR de verificación (F10), y por eso vive fuera de ambos árboles.
   ```bash
   export PROMO="$VERIF_HOME/promocion"      # el clon limpio: solo PR y promotion-tool
   [ -d "$PROMO/.git" ] || git clone "$(git remote get-url origin)" "$PROMO"
   git -C "$PROMO" switch main && git -C "$PROMO" pull --ff-only
   mkdir -p "$VERIF_HOME/plantillas"
   [ -d "$VERIF_HOME/plantillas/kind" ] || cp -r "$PROMO/vectra-risk/aidlc-docs/construction/system-verification/evidence/kind" "$VERIF_HOME/plantillas/kind"
   [ -f "$VERIF_HOME/plantillas/cierre-demo.md" ] || cp "$PROMO/vectra-risk/aidlc-docs/construction/system-verification/evidence/cierre-demo.md" "$VERIF_HOME/plantillas/cierre-demo.md"
   ```
   **Las plantillas `00` a `12` y la tabla de `cierre-demo.md` se llenan en esa copia, `$VERIF_HOME/plantillas`** (fuera de los dos árboles: llenarlas en el clon lo ensucia y `promotion-tool` se niega; llenarlas en tu copia de trabajo las deja sin llegar al PR y el `git pull --ff-only` se niega en cuanto `main` toca una). En F10 se copian sobre la rama del PR de verificación. Las reglas, para F1, F5, F7, F8 y F10: (1) **antes de cada orden de `promotion-tool` y antes de cada rama nueva**: `git -C "$PROMO" switch main && git -C "$PROMO" pull --ff-only` (también después de fusionar un PR: la orden siguiente lee los values de aquí); (2) los parches (`proxy.patch`, `rt3-a.patch`, `retirar.patch`, el de `prepare`) se escriben **fuera del árbol**, en `$VERIF_HOME` o en `$EVID`, y se aplican con `git -C "$PROMO" apply <parche>` en una rama nueva (`git -C "$PROMO" switch -c <rama> origin/main`) antes de abrir el PR; (3) `promotion-tool` corre desde `"$PROMO/vectra-risk"` con `--repo ..` (como en `governance/docs/paso-20-kind.md`, §5), con el usuario `ingeniero-2` (F3, paso 7). Tu copia de trabajo también necesita `git pull --ff-only` antes de F5 (`prepare` toma de ella los values y el commit).

<!-- inventario:F0 -->
| Id | Qué se mira | Cómo (solo lectura) | Demo |
|---|---|---|---|
| K-01 | Memoria del host: al menos 8 GiB disponibles antes de instalar (14 GiB de RAM es el minimo; los requests del perfil de kind suman 13,8 GiB) | `free -m`; `docker stats --no-stream`; `memoria.sh antes` | Base |
| K-02 | U12-T03, T04 y T05, U02-T22 y U00-T04 en main; la reparacion del realm retirada de tests/doubles/keycloak_tc.py | `git log --oneline origin/main`; `grep -c repair_shared_authenticator_configs system-verification/tests/doubles/keycloak_tc.py` | Base |
| K-03 | Paquetes de U5 generados (base, proxy/run-1, adversarial/rt3) y la vigencia de reference-policy.json cubre los dos dias de la corrida | `ls reference-model/.out`; a mano: la vigencia normativa de reference-policy.json cubre los dos dias de la corrida | Base |
| K-04 | Calendario: decisions se lanza antes de 22:18 UTC; el dia D + 1 no es dia 1 del mes; D4 solo pasa durante el dia D + 1 UTC (hasta las 00:00 UTC de D + 2); F5 a F10 caben en 3 dias (retencion de Prometheus) | `date -u`; `observabilidad.sh consulta prometheus_tsdb_lowest_timestamp_seconds` | D3, D4 |
| K-05 | La boveda de kind esta sembrada y no se ha reiniciado desde la siembra (guarda todo en memoria) | `kubectl --context kind-vectra get pods -n vault`; `kubectl --context kind-vectra get externalsecret -A`; `arranque.sh vault` | Base |
<!-- /inventario:F0 -->

**Puerta de F0.** Sigues solo si: hay al menos 8 GiB disponibles (`memoria.sh antes` sale 0), el clúster existe con el contexto `kind-vectra`, la bóveda está sembrada y no se ha reiniciado (si la máquina se reinició: «Después de reiniciar la máquina» hecha), `reference-model/.out` existe, y sabes qué de F1 a F3 salta el diagnóstico. Si `memoria.sh antes` sale 1: para (R-4). Si la bóveda no tiene las claves de los «-2»: U2 (`seed-vault.sh identity`).

## F1 Imágenes y digests

Entradas: K-06 a K-09. Plantilla: `01-imagenes.md`. Duración: 60 a 90 min. Puerta al final.

**Prerrequisitos.** F0 completa. El registro `kind-registry` en `127.0.0.1:5001` (§4 de `install.md`). Mide la memoria antes de construir: `system-verification/docs/kind/memoria.sh antes`.

**Por qué un solo PR.** `ServingConfig` es estricto (`additionalProperties: false`) y un consumidor con el tipo viejo falla cerrado: governance, scoring, explainability y casos se construyen **del mismo commit** y sus digests suben en **un solo PR** (`aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md`, línea 42). Anota ese commit en la plantilla.

**Pasos.** Publica, con el documento dueño de cada unidad, las imágenes que el diagnóstico de F0 mostró ausentes. Cada una termina con un digest real que va a un values de kind por PR (en una rama del clon de promoción, F0 paso 11, con `git pull --ff-only` antes de crearla); después `uv run python vectra-risk-gitops/generate.py` y `uv run python vectra-risk-gitops/generate.py --check`:

| Unidad | Imágenes | Documento dueño |
|---|---|---|
| U2 | `keycloak`, `identity-jobs`, `keycloak-config-cli`, Envoy, Valkey (si U2 no está instalado) | `identity-edge/docs/paso-16-kind.md`, §3 |
| U3 | `decision-registry` | `decision-registry/docs/imagen-kind.md`, «Publicar» |
| U4 | `governance` y `model-validation-job` | `governance/docs/paso-20-kind.md`, §2 |
| U6 | `model-predictor` y `model-explainer` | `model-serving/docs/paso-11-kind.md`, §1 |
| U7 | `scoring-service` y `explainability-service` | `scoring-explainability/docs/imagenes.md` |
| U8 | `case-service` y `case-worker` | `case-management/docs/imagenes.md` |
| U9 | `bias-monitoring` | `bias-monitoring/docs/imagenes.md` |
| U10 | `console-bff` y `console-spa` | `console/README.md`, «Imágenes» |
| U11 | `product-metrics` | `product-metrics/docs/imagenes.md` |

**La imagen de U12.** Constrúyela como dice el README de la imagen («La imagen»): `make -C system-verification image` desde `vectra-risk/` (la construcción descarga Chromium, `kubectl` y los paquetes del sistema, cada uno con su suma comprobada; sin `make`, la construcción equivalente que da el README). Comprueba que arranca con `docker run --rm --read-only localhost:5001/vectra/system-verification:dev --help`, publícala en el registro local y exporta `VERIFICATION_IMAGE` con **el digest** que imprime `docker inspect`; es el que usan `vv` y `humo`. La imagen corre en tu estación, no en el clúster: no hace falta cargarla en los nodos de kind. **Si la demo corre en otra máquina, lleva la imagen ya construida** (`docker save` en esta y `docker load` allí, o publícala en el registro de kind de la otra): `make image` en una máquina limpia puede fallar cuando Debian retire una versión fijada en `image/apt.lock`, y entonces hay que regenerar `apt.lock` (README, «La imagen»).

```bash operador
docker push localhost:5001/vectra/system-verification:dev
docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/vectra/system-verification:dev
```

Con el digest en la mano: `export VERIFICATION_IMAGE=localhost:5001/vectra/system-verification@sha256:<digest>`.

<!-- inventario:F1 -->
| Id | Qué se mira | Cómo (solo lectura) | Demo |
|---|---|---|---|
| K-06 | Imagenes de U3 a U11 publicadas en kind-registry y digests reales en los values de kind, por PR (un digest que no es el publicado da ImagePullBackOff; ya no queda ninguno de ejemplo) | `grep -rn sha256:0000 vectra-risk-gitops/values/kind`; `arranque.sh vectra-app` | Base |
| K-07 | Governance, scoring, explainability y casos construidas del mismo commit, con sus digests en un solo PR | `git log --oneline origin/main`; a mano: el commit de cada imagen en la plantilla y un solo PR de digests | Base |
| K-08 | Imagenes de U2 (Keycloak, identity-jobs, config-cli, Envoy, Valkey) publicadas, si U2 no esta instalado | `arranque.sh vectra-identity vectra-edge` | Base |
| K-09 | Imagen de U12 publicada y corrida por digest; su memoria en el host frente a --memory 1g | `docker stats --no-stream`; `memoria.sh durante` | Base |
<!-- /inventario:F1 -->

**Espera (≈ 5 a 10 min por imagen).** Mientras tanto no construyas otra cosa en paralelo: la memoria (R-4). Mira `docker stats --no-stream`.

**Puerta de F1.** Sigues solo si: no queda `sha256:0000` en `vectra-risk-gitops/values/kind` (K-06), el PR de digests de las cuatro imágenes del mismo commit está fusionado en `main` y la imagen de U12 tiene su digest. Un pod que luego quede en `ImagePullBackOff` es su unidad (R-2).

## F2 Sync y arranque de cada unidad

Entradas: K-10 a K-26. Plantilla: `02-sync-y-arranque.md`. Duración: 2 a 3 h (la validación del modelo tarda hasta 30 min). Puerta al final.

**Prerrequisitos.** F1 completa. La CLI de Argo CD con sesión (`platform/runbooks/install.md`, §6) y la función `sync` de `install.md`, §7 «Sincronizar en orden»: cópiala en tu terminal. **Argo CD sincroniza lo que hay en `main`**, no tu rama.

**El orden importa, y no es el de las waves** (todas en la 5): la política va **antes** de `console-bff` (el runbook de U4 crea y borra una `ServiceAccount` `console-bff` temporal y la del chart de U10 no debe existir aún); el eco de U2 no debe existir cuando se sincroniza U10; y `product-metrics` va **el último**: si arranca antes que el registro, el dashboard queda vacío hasta 30 min (`aidlc-docs/construction/product-metrics/evidence/cierre-demo.md`, línea 54). Después de cada sync, corre el diagnóstico del namespace y mira la puerta.

**Pasos.**

1. **U2, si falta.** `identity-edge/docs/paso-16-kind.md`, §5 (valkey, keycloak, gateway, ratelimit, identity-jobs, identity-rules, identity-monitors; **salta** «Backend de eco»). Comprueba: `system-verification/docs/kind/arranque.sh vectra-edge vectra-identity` (K-10).
2. **`decision-registry`:**
   ```bash operador
   sync decision-registry
   ```
   Comprueba: `kubectl --context kind-vectra get applications.argoproj.io decision-registry -n argocd` y que `/readyz` responde 200 (K-11).
3. **`governance`:** `sync governance` (`governance/docs/paso-20-kind.md`, §3: el Job `governance-migration` termina antes de que el servicio quede `Ready`).
   ```bash operador
   sync governance
   ```
4. **Política activa** (`governance/docs/paso-20-kind.md`, §4, y `governance/runbooks/kind-politica-de-referencia.md` de punta a punta): `cro-2` propone y `cro-1` aprueba. Va **antes** de `console-bff`. La plantilla de U4 es `aidlc-docs/construction/governance/evidence/kind/03-arranque-politica.md`.
5. **`model-serving`** y los paquetes del model-store (`model-serving/docs/paso-11-kind.md`, §0 a §2; paquetes en las líneas 42 a 58):
   ```bash operador
   sync model-serving
   ```
6. **Modelo de referencia `activo`** (`governance/docs/paso-20-kind.md`, §5: subir, registrar, validar, aprobar y promover). La validación tarda hasta 30 min. **Espera (hasta 30 min):** mira `system-verification/docs/kind/arranque.sh vectra-serving` y que el pod del modelo de referencia quede sin `OOMKilled` (K-23).
7. **`scoring-explainability`:**
   ```bash operador
   sync scoring-explainability
   ```
   Comprueba: `arranque.sh vectra-app` (raíz de solo lectura, K-15) y que los hosts `<isvc>-predictor.vectra-serving` y `<isvc>-explainer.vectra-serving` resuelven desde `vectra-app`.
8. **`case-management`:**
   ```bash operador
   sync case-management
   ```
   Comprueba: el hook de migración corre antes de que los `Deployment` queden `Ready` y `verify-full` conecta de verdad con `case-db` (K-14); ningún contenedor sale con código 0 y sin mensaje (K-13).
9. **`bias-monitoring`:**
   ```bash operador
   sync bias-monitoring
   ```
10. **Retira el eco de U2 y la `ServiceAccount` temporal `console-bff` de U4**, si el diagnóstico las muestra (K-17):
    ```bash
    kubectl --context kind-vectra get deploy,sa -n vectra-app
    kubectl --context kind-vectra get sa console-bff -n vectra-app
    ```
    Si el eco existe, retíralo; la `ServiceAccount` temporal la borra el propio runbook de U4 al terminar.
    ```bash operador
    kubectl --context kind-vectra delete -f identity-edge/tests/e2e/echo/manifests.yaml
    ```
    La segunda lectura debe dar `NotFound` **antes** del sync de U10.
11. **`console-bff` y `console-spa`:**
    ```bash operador
    sync console-bff console-spa
    ```
12. **`product-metrics`, el último:**
    ```bash operador
    sync product-metrics
    ```
    **Espera (hasta 30 min si arrancó antes que el registro; 15 min por pasada).** Mira `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=product-metrics` y `/readyz` (K-18).
13. **Observabilidad.** `system-verification/docs/kind/observabilidad.sh reglas` (las alertas `CoreWriteAttempt`, `FailClosedPersistente` y `ProductMetricsStale` cargadas) y `observabilidad.sh targets` (el target `linkerd-proxy` de `vectra-mock` en `up`, K-21). Selectores de partida: Prometheus `app.kubernetes.io/name=prometheus` (9090) y el registro `app.kubernetes.io/name=decision-registry-service` (8080) (K-20; kind no instala Loki desde U01-T11). Si K-21 falla, es R-6.
14. **Flujos negados.** La suite de conectividad X01 a X10 está diferida (la sección `network` y el Paso 9 no entran en la demo): K-26 queda `no ejecutado`. Los flujos **permitidos** se ven en F4 y en las demos.

<!-- inventario:F2 -->
| Id | Qué se mira | Cómo (solo lectura) | Demo |
|---|---|---|---|
| K-10 | U2 arranca: Envoy con la raiz de solo lectura, las sondas de Valkey contestan, el Job keycloak-config-cli termina | `arranque.sh vectra-edge vectra-identity`; `kubectl --context kind-vectra get job keycloak-config-cli -n vectra-identity` | Base |
| K-11 | decision-registry: Application Synced y Healthy; /readyz responde 200 | `kubectl --context kind-vectra get applications.argoproj.io decision-registry -n argocd`; `arranque.sh vectra-app` | Base |
| K-12 | ESO materializa las llaves de cada unidad (scoring, explainability, case-service, case-worker, las dos de bias, product-metrics) y existen los cuatro pg-role-case-* | `kubectl --context kind-vectra get externalsecret -n vectra-app`; `arranque.sh vectra-app` | Base |
| K-13 | Ningun contenedor sale con codigo 0 y sin mensaje (falta una variable o la llave private_key_jwt) | `arranque.sh vectra-app`; `kubectl --context kind-vectra logs --previous -n vectra-app` | Base |
| K-14 | U8: el hook de migracion corre antes de que los Deployment queden Ready; sslmode=verify-full conecta de verdad con case-db | `kubectl --context kind-vectra get jobs -n vectra-app`; `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=case-service` | Base |
| K-15 | U7 arranca con la raiz de solo lectura y sin emptyDir; los hosts <isvc>-predictor.vectra-serving y -explainer resuelven desde vectra-app | `arranque.sh vectra-app`; `humo flujo --delivery /verification/reference-model/.out` | Base |
| K-16 | vectra-internal-ca existe en vectra-app y el JWKS responde por https | `kubectl --context kind-vectra get configmap vectra-internal-ca -n vectra-app`; `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=console-bff` | Base |
| K-17 | El eco de U2 y la ServiceAccount temporal console-bff de U4 no existen antes del sync de U10 | `kubectl --context kind-vectra get deploy,sa -n vectra-app`; `kubectl --context kind-vectra get sa console-bff -n vectra-app` | Base |
| K-18 | product-metrics arranca despues del registro; si no, 503 hasta 30 min y dashboard vacio | `kubectl --context kind-vectra get pods -l app.kubernetes.io/name=product-metrics -n vectra-app`; `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=product-metrics` | D4 |
| K-19 | Prometheus carga las PrometheusRule de U8 y U11 y raspa los ServiceMonitor de U8 (tres), del BFF y de U11; Grafana descubre el ConfigMap del dashboard en Vectra / Producto | `observabilidad.sh reglas`; `observabilidad.sh targets` | D1, D3, D4 |
| K-20 | Selectores y puertos de partida: Prometheus (app.kubernetes.io/name=prometheus, 9090) y el registro (decision-registry-service, 8080) | `kubectl --context kind-vectra get pods -l app.kubernetes.io/name=prometheus -n vectra-observability`; `kubectl --context kind-vectra get pods -l app.kubernetes.io/name=decision-registry-service -n vectra-app` | Base |
| K-21 | Proxy de Linkerd en vectra-mock: el target linkerd-proxy en up == 1 (no 403) y los pods Ready con el Server del 4191 (las sondas /live y /ready pasan) | `observabilidad.sh consulta up{namespace="vectra-mock"}`; `kubectl --context kind-vectra get pods -n vectra-mock` | D3 |
| K-22 | Politica activa y modelo de referencia activo: serving-config trae policy_version_id y la version | `humo flujo --delivery /verification/reference-model/.out`; a mano: plantillas 03 y 04 de U4 (governance/evidence/kind) | Base |
| K-23 | Con 256 MiB por pod bastan el predictor y el explicador del modelo de referencia (sin OOMKilled) | `arranque.sh vectra-serving`; `memoria.sh antes` | Base |
| K-24 | Paquetes proxy y RT-3 (a, b, c y d) en el model-store, para D1 y D2 | a mano: la salida de mc ls de model-serving/docs/paso-11-kind.md, seccion 2, con RT3-a, RT3-c y RT3-d (rt3 exige los tres); `arranque.sh vectra-data` | D1, D2 |
| K-25 | Watchdog recibido, no solo disparado | `observabilidad.sh consulta ALERTS{alertname="Watchdog"}` | — |
| K-26 | Flujos negados (suite X01 a X10, casos bloqueados de INF-U10-04, X04): no se comprueban porque network y el Paso 9 estan diferidos; los permitidos se ven por el flujo base y las demos | `humo flujo --delivery /verification/reference-model/.out` | — |
<!-- /inventario:F2 -->

**Puerta de F2.** Sigues solo si: `arranque.sh vectra-edge vectra-identity vectra-data vectra-observability vectra-serving vectra-app vectra-mock` sale 0 (las cinco Applications `OutOfSync` de U1 se anotan: `aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md`, línea 22), todas las Applications de U2 a U11 están `Synced` y `Healthy`, y el target `linkerd-proxy` está `up`. Síntomas: `ImagePullBackOff` es la unidad del pod (R-2); `CreateContainerConfigError` es el `ExternalSecret` (U1 o U2); salida con código 0 sin mensaje, U0 y la llave; `product-metrics` con 503, esperar.

## F3 Identidad y acceso

Entradas: K-27 a K-37. Plantilla: `03-identidad-y-acceso.md`. Duración: 40 min. Puerta al final. **Va en la jornada 1:** los tres arreglos de autenticación solo se han probado contra un Keycloak local (R-5).

**Prerrequisitos.** F2 completa. Las funciones `vectra-verification` y `humo` de F0, el `port-forward` a la bóveda abierto y `VAULT_ADDR` y `VAULT_TOKEN` exportadas.

**Pasos.**

1. **¿El kind tiene el realm viejo?** Los síntomas: todo login da «Unexpected error when handling authentication request», o el login termina en una pantalla de perfil. Si es así, **resincroniza U2** (no hace falta borrar el realm; `identity-edge/docs/realm-importacion.md`, «Qué hace el operador», punto 2):
   ```bash operador
   sync keycloak
   ```
   Si el primer `sync keycloak` termina en `Failed` (el HPA no encuentra el StatefulSet y no corre el hook `keycloak-config-cli`), **repítelo**: el 2026-11-15 el segundo terminó bien e importó el realm (`platform/runbooks/install.md`, «Lo medido el 2026-11-15 al desplegar U2 en kind», hecho 3; que sincronizar `gateway` antes lo evite no está medido).
   Lo medido, que **corrige** dos líneas de ese documento (`revisiones/U02-T22/ronda-1.md`, F-01): el login fallido por el error interno del realm viejo **no** cuenta para la fuerza bruta (`numFailures` en 0), así que el desbloqueo del punto 3 es una precaución y no un paso obligado; sí cuentan las contraseñas mal tecleadas (60 s al quinto fallo, permanente al 20). Al reaplicar el realm sobre uno ya importado, `keycloak-config-cli` avisa `Password policy violation ... Password was NOT updated` (no reaplica contraseñas) y **añade una segunda credencial OTP** con la misma semilla: es esperado.
2. **Identidad, K16 y bóveda (solo lectura):**
   ```bash
   system-verification/docs/kind/identidad.sh
   ```
   Hace tres comprobaciones: K16 con el grupo `vectra-verification-operators` (lo que lee cada `verify` da `yes`; lo que K16 no da, `vectra-mock` y `vectra-staging`, da `no`), el Job `keycloak-config-cli` y sus avisos, y los **nombres** de las claves de `identity/synthetic-users` (nunca los valores), con las de `analista-2`, `cro-2` y `cumplimiento-2`. Usa `--as` y `--as-group`: es lectura, con el kubeconfig de administrador de kind.
3. **Login por rol por el gateway real** (primera ejecución de `live.py` y del login de la herramienta contra el Keycloak del clúster):
   ```bash
   humo login
   ```
   Imprime, por cada uno de los cinco usuarios (`analista-1`, `analista-2`, `ingeniero-1`, `cro-1` y `cumplimiento-1`), `iss`, `aud`, `acr`, `amr`, roles y `auth_time`; **nunca el token**. Esperado: `iss = https://vectra.localtest.me/auth/realms/vectra`, `acr = mfa`, `aud` con `console-bff` y su rol. **Espera 30 s** (la ventana del TOTP) antes de repetir un comando con los mismos usuarios (reuso del TOTP); mientras tanto, lee la salida del anterior. Si falla: `token_issuer_not_allowed` es el emisor (U2); `login_rejected` es el realm viejo o una contraseña mal (paso 1); `browser_launch_error` o el sandbox, la orden `docker run` (F0, paso 9).
4. **La consola en Chromium sin interfaz** (el sandbox siempre activo):
   ```bash
   humo consola
   ```
   Redirección completa, recarga y conteo de `securitypolicyviolation` con la CSP real del perfil `spa` y la de `/auth/**`; dice si llegó la cookie de afinidad `vectra-spa-route` (nunca su valor). Esperado: cero violaciones.
5. **A mano: la consola en el navegador del presentador.** Abre `https://vectra.localtest.me/` con `analista-1` y confirma redirección, `/callback` y recarga sin volver al formulario; mira la consola del navegador: cero errores de CSP. Instala en el teléfono del presentador las **semillas TOTP** de los usuarios «-2» que usará: `cro-2` en D1 (o `analista-2`, ver el paso 7) y `cumplimiento-2` en D2 (las escribe `seed-vault.sh identity` en el archivo `env` de `${VECTRA_E2E_KEYS_DIR:-${XDG_RUNTIME_DIR:-/tmp}/vectra-e2e-keys}`; `identity-edge/docs/paso-16-kind.md`, §4). Prueba un login manual de `cumplimiento-2`.
6. **Límites del gateway.** 30/s para el simulador, 20/s por usuario en `/api/console` y 600/min en `auth-login` y `auth-token` (`identity-edge/gateway/routes.yaml`, líneas 87 a 107). Se prueban con el volumen real en F6: cero 429.

7. **Reparto de usuarios y de pestañas.** Cada login gasta un código TOTP, y dos logins del mismo usuario dentro de la misma ventana de 30 s reusan el código: Keycloak rechaza el segundo y **ese rechazo cuenta para el bloqueo por fuerza bruta**. Por eso cada usuario tiene **un solo dueño a la vez**, con los que existen en `identity-edge/keycloak/realm/realm.kind.yaml`:

   | Quién | Usuario | Dónde |
   |---|---|---|
   | La herramienta (`vectra-verification`) y `humo` | `analista-1` (casos, `rt3`), `ingeniero-1` (`rt3`, `rt2-setup`, `rt2`, `humo modelos`), `cro-1` (aprueba), `cumplimiento-1` (`rt2` en modo `tool` y el subcomando `flujo` de `humo`) y `analista-2`, **solo** como segundo analista del conductor de `decisions` (`ANALYSTS` en `driver.py`) | La imagen |
   | `promotion-tool` y los `token.sh` de los documentos dueños que corren **mientras la herramienta corre** | `ingeniero-2` (mismo rol `ingeniero_riesgo`; `ingeniero-1` es de la herramienta) | El navegador del operador y su terminal |
   | El presentador | D1: `cro-2` (ve `ruta /casos`; `analista-2` es del conductor); D2: `cumplimiento-2` | El navegador del presentador |

   `identidad.sh` y `humo login` no comprueban `ingeniero-2` (miran siete y cinco usuarios): haz un login manual con él y su semilla TOTP (las escribe `seed-vault.sh identity` junto con las de los demás usuarios; K-33) antes de F2. **Una sola pestaña por usuario:** no abras el mismo usuario en dos pestañas ni lo uses en el navegador mientras la herramienta o `humo` lo usan; espera 30 s entre dos logins del mismo usuario. `journey-7-3.md` nombra `analista-2` para el presentador de D1: sirve igual `cro-2`, y la guía reserva `analista-2` para el conductor.

<!-- inventario:F3 -->
| Id | Qué se mira | Cómo (solo lectura) | Demo |
|---|---|---|---|
| K-27 | Si el kind tiene el realm viejo: tras resincronizar U2 quedan 26 de 26 ejecuciones enlazadas; config-cli avisa que no reaplica contrasenas y anade una segunda credencial OTP con la misma semilla | `identidad.sh`; `humo login` | Base |
| K-28 | Bloqueos por fuerza bruta: el login fallido por el error interno del realm viejo no cuenta (numFailures 0); si cuentan las contrasenas mal tecleadas (60 s al quinto fallo, permanente al 20) | `humo login` | Base |
| K-29 | Login por rol por el gateway real, con el emisor publico: analista-1, analista-2, ingeniero-1, cro-1 y cumplimiento-1; cada token con acr = mfa, amr, aud con console-bff y su rol | `humo login` | Base |
| K-30 | El iss de los tokens del navegador es el que valida el BFF y cada destino (F10 a F14): 200 en bandeja, detalle, modelos y congelamientos, ningun 401 | `humo flujo --delivery /verification/reference-model/.out` | Base |
| K-31 | La aud de la asercion de servicio la acepta el Keycloak del cluster (nunca medido en kind con el realm real) | `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=case-worker`; `humo flujo --delivery /verification/reference-model/.out` | Base |
| K-32 | Camino a la boveda desde la estacion (no lo da K16): lectura de las 5 credenciales y las 2 llaves; el token root de kind no rompe el filtro de evidencias | `humo login`; `vectra-verification prepare` | Base |
| K-33 | Credenciales de los usuarios -2 (analista-2 o cro-2 en D1; cumplimiento-2 en D2) en la boveda, y sus semillas TOTP en el telefono del presentador | `identidad.sh`; a mano: login manual de cumplimiento-2 en la consola | D1, D2 |
| K-34 | K16 de verdad: lo que cada verify lee lo permite el grupo vectra-verification-operators; que pasa en vectra-staging y vectra-mock (K16 no da nada) | `identidad.sh` | D1, D2, D3 |
| K-35 | Consola en el navegador por el gateway real: redireccion, /callback, recarga con prompt=none; cero securitypolicyviolation con la CSP real; la cookie vectra-spa-route llega a los pods | `humo consola`; a mano: la consola del navegador del presentador | Base |
| K-36 | CASE_ALLOW_TEST_SCENARIOS activo en kind (la cabecera de escenario de U12 se acepta) | `humo flujo --delivery /verification/reference-model/.out` | Base |
| K-37 | Limites del gateway con el volumen real: 30/s para el simulador, 20/s por usuario en /api/console, 600/min en auth-login y auth-token (cero 429) | `vectra-verification decisions` | D2, D4 |
<!-- /inventario:F3 -->

**Puerta de F3.** Sigues solo si: `identidad.sh` sale 0, `humo login` da los cinco usuarios bien y `humo consola` da cero violaciones. Síntomas: 401 en toda la API, el servicio que responde (emisor, U2); `invalid_client: Invalid token audience`, U0 y el chart del servicio; login roto, realm viejo (paso 1); la bóveda no lee, R-7.

## F4 Flujo base

Entradas: K-38. Plantilla: `04-flujo-base.md`. Duración: 15 min. **Es la puerta de las cuatro demos.**

**Prerrequisitos.** F3 completa. `reference-model/.out` montado en `/verification/reference-model/.out` (F0, paso 9). `CASE_ALLOW_TEST_SCENARIOS` activo en los values de kind (`allowTestScenarios: true` en `vectra-risk-gitops/values/kind/case-management.yaml`): la solicitud de `humo flujo --delivery /verification/reference-model/.out` lleva la cabecera de escenario y debe aceptarse (K-36).

**Pasos.**

1. **Una solicitud de punta a punta:**
   ```bash
   humo flujo --delivery /verification/reference-model/.out
   ```
   Envía una solicitud `normal` por el gateway, sondea hasta `listo` (plazo por omisión de 300 s), lee el detalle y la explicación por el BFF con `analista-1`, registra una decisión, lee `/api/console/models` con `ingeniero-1` y `/api/console/freezes` con `cumplimiento-1`, e informa el **estado HTTP de cada llamada**. Esperado: el caso `listo` con `registry_entry_id`; la decisión con ack; ninguna llamada con 401 ni 429.
2. **Un servicio real acepta un token real** (la pregunta de R-5): si el caso llega a `listo`, el token de usuario fue aceptado por el BFF, `case-service`, `scoring-service` y `explainability-service` (el que cada servicio valida es el emisor público), y la aserción de servicio de `case-worker` y `scoring-service` fue aceptada por Keycloak. Si no llega: `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=case-worker` busca `invalid_client` (la `aud`, K-31); un 401 en la salida de `humo flujo --delivery /verification/reference-model/.out` nombra el **destino** que rechaza (el emisor, K-30).
3. **Los modelos que hay** (para el estado final; **espera 30 s** desde que terminó la orden del paso 1: las dos usan `ingeniero-1`, el código TOTP se reusaría, Keycloak lo rechaza (`login_rejected`) y ese rechazo cuenta para el bloqueo por fuerza bruta): `humo modelos` imprime el JSON con el estado de cada versión. Guarda el de ahora en la plantilla: F10 lo compara. Anota el `model_version_id` del modelo de referencia (el `activo`): F10 se lo pasa a `estado-final.sh`.

<!-- inventario:F4 -->
| Id | Qué se mira | Cómo (solo lectura) | Demo |
|---|---|---|---|
| K-38 | Humo de punta a punta: una solicitud por el gateway llega a listo con registry_entry_id; la explicacion por el BFF; una decision de analista-1; el append con ack | `humo flujo --delivery /verification/reference-model/.out` | Base |
<!-- /inventario:F4 -->

**Puerta de F4: no se empieza ninguna demo sin esto.** Un caso `listo` con `registry_entry_id`, una decisión con ack y cero 401 y cero 429. Síntomas: el caso queda en `en_evaluacion`, `invalid_client` en `case-worker` (U0 y el chart, R-5); `serving_config_unavailable`, U4 (política); `revision_requerida` en todos, la vigencia de `reference-policy.json` (U5 y U4); un 401 con el destino nombrado, ese destino.

## F5 `prepare` y D3 (RT-5)

Entradas: K-39 a K-43. Plantilla: `05-prepare-y-d3.md`. Duración: 20 min. **Empieza la jornada 2, antes de las 12:00 de Colombia (17:00 UTC).** Demo: D3 (`system-verification/demos/rt-5.md`). Puerta al final.

**Prerrequisitos.** F4 completa; si la máquina se reinició o se apagó entre las jornadas, **primero** «Después de reiniciar la máquina» (el límite de inotify, los pods con malla, la bóveda, MinIO y Grafana); `memoria.sh antes` en 0 otra vez; todo el diagnóstico de F2 en 0. **`platform/kind/gateway-address.sh` en 0** (si no, la línea de `/etc/hosts` que dice: sin ella el navegador y `promotion-tool` no llegan al gateway) y `GATEWAY_ADDRESS` releída en cada terminal (el bloque del paso 9 de F0; `vv` se niega sin ella). **`git pull --ff-only` en tu copia de trabajo** (`prepare` toma de ella los values y el commit, y los digests de F1 ya están fusionados). La imagen de U12 por digest.

**Pasos.**

1. **`prepare`.** Fija el `runId` y el `started_at` (sin ninguna solicitud) y escribe el parche del `runId`:
   ```bash
   vectra-verification prepare --commit "$(git rev-parse --short HEAD)" --operator "<tu nombre>" \
       --values-file /values/case-management.yaml --delivery /verification/reference-model/.out
   ```
   `--commit` y `--operator` van por parámetro (la imagen no trae `git`). `--values-file` es el archivo de values de kind que `vv` montó de solo lectura en `/values/case-management.yaml` (el de `vectra-risk-gitops/values/kind/` del commit que se verifica); `prepare` escribe en `$EVID` el `manifest.json` y `case-management-runid.patch`. `--delivery` guarda en el manifiesto la ruta de la entrega **dentro del contenedor** (`paths.delivery`): `decisions`, `rt3`, `rt2-setup` y `rt2` la toman de ahí y ya no tienen una por omisión (sin ella, código 3 y `ruta_faltante`; cada una acepta también `--delivery`). El `runId` es `AAAAMMDD-HHMM` de `started_at`. `prepare` se corre **una sola vez** por `$EVID`: repetirlo se niega (código 3).
2. **El PR de `runId`.** Abre el PR `system-verification/demos/prs/rt5-run-id/` con el parche que produjo `prepare` (agrega `runId` bajo `probes:` en `vectra-risk-gitops/values/kind/case-management.yaml`; está en `$EVID`, fuera del repositorio): en el clon de promoción, `git -C "$PROMO" switch main && git -C "$PROMO" pull --ff-only`, una rama nueva (`git -C "$PROMO" switch -c <rama> origin/main`) y `git -C "$PROMO" apply "$EVID/case-management-runid.patch"`; antes, `make -C case-management policy-chart` debe seguir en verde. Fusiónalo.
   **Repetir D3 tras un fallo a medias:** un segundo `prepare` se niega mientras los values conserven el `runId` (`values_already_have_runid`, `manifest.py`), y el Job `rt5-demo-<runId>` tiene `backoffLimit: 0` y no se puede borrar con la lista cerrada. El camino, todo por PR: (1) **quita el `runId`** (`git -C "$PROMO" apply -R "$EVID/case-management-runid.patch"` en una rama nueva, PR, fusión) y sincroniza `case-management` **con prune** (el Job no lleva `ttlSecondsAfterFinished`: se poda al dejar de renderizarse); (2) **vuelve a ponerlo** (`git -C "$PROMO" apply "$EVID/case-management-runid.patch"`, PR, fusión) y sincroniza otra vez con prune: nace un Job nuevo con el mismo `runId`; (3) `vectra-verification rt5 --redo`. Para una verificación nueva (otro `$EVID`, F0 paso 9: guarda el `evid` anterior y recalcula), quita el `runId` viejo igual y corre `prepare` en el directorio nuevo. El detalle está en `system-verification/demos/prs/rt5-run-id/README.md`; el contador de Linkerd no distingue un ensayo anterior (paso 4).
3. **Sincroniza `case-management` con prune** (el Job `rt5-demo-<runId>` nace **después** de `started_at`):
   ```bash operador
   argocd app sync case-management --prune && argocd app wait case-management --health --timeout 900
   ```
4. **Mira la alerta en vivo, en ese momento.** `CoreWriteAttempt` no tiene `for:` y su expresión mira 5 min: se ve en `firing` unos 5 min y se apaga sola. **Espera (segundos para el Job, ≈ 5 min de alerta).** Mientras tanto:
   ```bash
   system-verification/demos/verify/rt-5.sh 1
   system-verification/demos/verify/rt-5.sh 2
   system-verification/demos/verify/rt-5.sh 3
   system-verification/docs/kind/observabilidad.sh consulta 'ALERTS{alertname="CoreWriteAttempt"}'
   system-verification/docs/kind/observabilidad.sh serie inbound_http_authz_deny_total
   system-verification/demos/verify/rt-5.sh 4
   system-verification/demos/verify/rt-5.sh 5
   ```
   Repite la consulta de la alerta cada 30 s durante 7 min y anota la hora en que aparece y la hora en que se apaga (K-42). Copia el conjunto **real** de etiquetas de la serie (K-41: se espera `namespace="vectra-mock"` y `route_name="core-mock-catch-all"`). No ensayes D3 dos veces sin reiniciar el proxy de Linkerd de `vectra-mock`: el contador no distingue un ensayo anterior (`CANDIDATAS.md`, línea 742).

<!-- inventario:F5 -->
| Id | Qué se mira | Cómo (solo lectura) | Demo |
|---|---|---|---|
| K-39 | prepare fija runId y started_at; con el PR de runId fusionado, make -C case-management policy-chart sigue en verde sobre main | `vectra-verification prepare`; `make -C case-management policy-chart` | D3 |
| K-40 | El Job rt5-demo-<runId> termina despues de started_at; su log trae el 403 del proxy y el valor real de l5d-proxy-error | `rt-5.sh`; `kubectl --context kind-vectra get jobs -n vectra-app` | D3 |
| K-41 | La serie inbound_http_authz_deny_total existe con sus etiquetas reales (namespace vectra-mock, route_name core-mock-catch-all; la prueba de U1 declara otras) | `observabilidad.sh serie inbound_http_authz_deny_total` | D3 |
| K-42 | CoreWriteAttempt llega a firing y cuanto dura (no tiene for:; la expresion mira 5 min) | `observabilidad.sh consulta ALERTS{alertname="CoreWriteAttempt"}`; `rt-5.sh` | D3 |
| K-43 | vectra_core_write_attempts_total en 0 desde el arranque | `vectra-verification rt5`; `rt-5.sh`; `observabilidad.sh consulta sum(vectra_core_write_attempts_total)` | D3 |
<!-- /inventario:F5 -->

**Puerta de F5.** Sigues solo si: el Job `rt5-demo-<runId>` terminó **después** de `started_at`, su log trae el 403 con el valor real de `l5d-proxy-error`, la serie existe y la alerta se vio en `firing`. La sección `rt5` y `rt-5.sh 6` van al final de F6. Síntomas: el Job no nace, el PR de `runId` o el sync (U8); sin serie, R-6 (U1); el 403 con `l5d-proxy-error: None`, lo dio la aplicación y no el proxy (U8 y U1).

## F6 `decisions` (D4, día D)

Entradas: K-44 a K-47. Plantilla: `06-decisions-d4.md`. Duración: ≈ 45 min (más la espera a `listo`, hasta 30 min). Demo: D4 (`system-verification/demos/dashboard.md`). Puerta al final.

**Prerrequisitos.** F5 completa. **Lanza antes de ≈ 22:18 UTC** (`date -u`): `decisions` estima 2 000 / 10 + 2 000 × 1 s + 300 s ≈ 42 min y se niega si no termina antes de las 23:00 UTC. **La estimación no cuenta la espera a que ningún caso siga en evaluación** (`--settle-timeout`, 1 800 s por omisión): con el sistema lento, `decisions` puede durar hasta 30 min más. Lánzala con holgura (antes de ≈ 21:45 UTC si puedes) y no empieces nada más pesado mientras corre. El modelo de referencia `activo` (sin congelar: `decisions` va antes de RT-2). Nada más corriendo en la máquina.

**Pasos.**

1. **Mide la memoria antes:** `system-verification/docs/kind/memoria.sh antes`.
2. **Lanza `decisions`** (2 000 casos `normal` y el conductor; espera a que cada caso llegue a `listo`). **Es la primera ejecución real de `live.py`** (el mundo real de la CLI: bóveda, login, `kubectl`, `port-forward`; 0 % de cobertura hasta hoy, `aidlc-docs/construction/system-verification/code/cli.md`): si falla al arrancar, antes de la primera solicitud, el error nombra qué parte (bóveda, login, lectura de Kubernetes o `port-forward`) y no se envió nada; corrige y repite sin `--redo`. `humo flujo --delivery /verification/reference-model/.out` de F4 ya ejercitó los mismos clientes de login y de API, no el armado de `live.py`.
   ```bash
   vectra-verification decisions
   system-verification/demos/verify/dashboard.sh 5
   ```
   **Lo que aguanta la herramienta** (`system-verification/src/vectra_verification/retry.py`, `simulator.py` y `system-verification/src/vectra_verification/scenarios/sim_normal.py`): al enviar, un 429, 502, 503, 504 o un fallo de transporte se reenvía hasta 3 veces con **la misma llave de idempotencia** (`case-management` devuelve el mismo caso al reenviar la misma llave con el mismo cuerpo: `intake.py`, `submit`), y `accepted = sent` si el reenvío entra; en las lecturas (la espera y la bandeja del conductor) esos mismos estados y los fallos de transporte se reintentan con espera creciente (2 s, 4 s, hasta 30 s; manda el `Retry-After` si es mayor) durante un tope de 300 s. Si el tope se agota, la sección termina en `no ejecutado` con `decisions_lectura_agotada` y queda `interrumpida`: el manifiesto ya trae `decisions.sent` y `decisions.accepted`, pero **repetirla envía otros 2 000 casos** con llaves nuevas (no retoma); decide con esas cifras antes de repetir. Los casos que el worker dejó en `en_sincronizacion` (reintento) **se esperan** como los `en_evaluacion` hasta `--settle-timeout`; los que siguen así al vencer el plazo no se deciden y la salida y el manifiesto los cuentan aparte (`undecided_after_wait` para `en_evaluacion` y `syncing_after_wait` para `en_sincronizacion`).
   `dashboard.sh 5` lee del manifiesto que `decisions` terminó y pasó (no consulta el clúster); córrelo al terminar. **Espera (≈ 45 min).** Mientras tanto, en otra terminal y sin competir por memoria: `system-verification/docs/kind/memoria.sh durante` (gate de 1,5 GiB) y `docker stats --no-stream` del contenedor de la imagen (K-09: frente a `--memory 1g`). No abras navegadores de más.
3. **Mide la memoria con 2 000 decisiones:** `system-verification/docs/kind/memoria.sh despues` (K-47: `case-service`, `case-worker`, el BFF y `product-metrics` frente a su request de 128 MiB).
4. **El agregador:** el log del último Job del agregador con atraso 0 (`kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=registry-aggregator`) y, si ya corrió una pasada de bias, `observabilidad.sh consulta vectra_bias_last_run_ok` (K-46).
5. **`rt5`, al terminar `decisions`** (lee el Job de F5 y la alerta; pasados más de 15 min del Job usa `query_range`):
   ```bash
   vectra-verification rt5
   system-verification/demos/verify/rt-5.sh 6
   ```
   Esperado: `RT-5` y `rt-5` en `pasa`; `vectra_core_write_attempts_total` en 0 (K-43; `observabilidad.sh consulta 'sum(vectra_core_write_attempts_total)'`).
6. **El modelo de referencia sigue `activo`** (espera 30 s desde el último comando con `ingeniero-1`; el mismo motivo que en F4): `humo modelos`. El cron de bias evalúa toda versión con recomendaciones de hoy o de ayer (`bias-monitoring/src/vectra_bias/window.py`, `evaluated_versions`), y el modelo de referencia las tiene: los 2 000 casos de `decisions`. Si sale `congelado`, **para**: D1 y D2 parten del modelo de referencia activo y los casos nuevos quedarían en `modelo_congelado`; es un hallazgo de U9 (el cron congeló el modelo de referencia, sin RT-2). Anótalo y avisa; reactivarlo es del usuario de `cumplimiento` en la consola (`ruta /congelamientos`) y no está ensayado para este caso.

<!-- inventario:F6 -->
| Id | Qué se mira | Cómo (solo lectura) | Demo |
|---|---|---|---|
| K-44 | 2 000 casos: accepted = sent; cada uno en listo o en un fail-closed documentado; los ultimos no quedan en not_ready sin decidir | `vectra-verification decisions` | D4 |
| K-45 | Las constantes de la estimacion de guard (1 s por caso, 300 s) frente al tiempo real; el ritmo real frente a 10/s | `vectra-verification decisions` | D4 |
| K-46 | registry-aggregator con atraso 0 y POST /v1/monitoring/daily:query con resultado mayor que 0 tras los 2 000 casos | `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=registry-aggregator`; `observabilidad.sh consulta vectra_bias_last_run_ok` | D2 |
| K-47 | Memoria real con 2 000 decisiones frente a los 128 MiB de request de kind: case-service, case-worker, el BFF y product-metrics | `memoria.sh despues` | D4 |
<!-- /inventario:F6 -->

**Puerta de F6.** Sigues solo si: `decisions` terminó con 2 000 enviados, aceptados y decididos (o el número real con su causa), **cero 429**, la memoria bajo su límite, `RT-5` y `rt-5` en `pasa` y el modelo de referencia sigue `activo`. Síntomas: 429, límite del gateway (U2; baja el ritmo con `--rate`); los últimos casos sin decidir, la bandeja (U12); `OOMKilled`, la unidad del pod (R-4); `decisions` se niega, la hora.

## F7 D1 (`rt3`)

Entradas: K-48 a K-52. Plantilla: `07-d1-rt3.md`. Duración: ≈ 50 min (12,4 a 19,3 min de espera hasta `no_disponible`, la alerta unos minutos después, dos PR). Demo: D1 (`system-verification/demos/journey-7-3.md`). Puerta al final.

**Prerrequisitos.** F6 completa. Va **después** de `decisions`: F22 apagado deja **todos** los casos en fail-closed. Antes de D2: debe estar revertido y comprobado antes del lote. Los paquetes RT3-a, c y d en el model-store (K-24). El presentador con `cro-2` (o `analista-2`, ver el reparto de F3, paso 7) en la consola, y las semillas en su teléfono (K-33).

**Pasos** (los de `journey-7-3.md`):

1. **PR de F22 apagado.** Abre el PR `system-verification/demos/prs/f22-apagado/apagar.patch` (`env_disabled` de kind con F22; en una rama del clon de promoción, con `git pull --ff-only` antes), fusiónalo y sincroniza `network` con prune (desaparecen cinco recursos de red hacia el explainer):
   ```bash operador
   argocd app sync network --prune && argocd app wait network --health --timeout 900
   ```
   Comprueba con `system-verification/demos/verify/journey-7-3.sh 1`. (Con el kubeconfig de administrador, `kubectl --context kind-vectra get networkpolicy,server,authorizationpolicy -n vectra-serving`; K16 no lee `NetworkPolicy`.)
2. **Opcional:** el paquete RT3-b, generado desde `reference-model/.out/proxy/run-5` y subido al model-store. Sin él, RT3-b sale `no ejecutado` y no baja RT-3.
3. **`rt3`:**
   ```bash
   vectra-verification rt3
   ```
   Registra RT3-a, c y d (422 de U4), envía 5 casos de sonda y espera la escalada. Los paquetes los toma de `<entrega>/adversarial/rt3` (la ruta de `--delivery` que guardó `prepare`; `--packages-dir` solo si están en otro sitio). **Espera (12,4 a 19,3 min hasta `no_disponible`; la herramienta espera hasta 25 min; `FailClosedPersistente` llega a `firing` unos minutos después del primer caso en `no_disponible`: la herramienta la sondea hasta 5 min tras la escalada).** Mientras tanto el presentador abre `ruta /casos` con `analista-2`: primero «En sincronización» y, pasados entre 12,4 y 19,3 min, «No disponible». Tú, cada minuto:
   ```bash
   system-verification/demos/verify/journey-7-3.sh 2
   system-verification/demos/verify/journey-7-3.sh 3
   system-verification/docs/kind/observabilidad.sh consulta 'vectra_cases_failclosed_persistent'
   system-verification/docs/kind/observabilidad.sh consulta 'ALERTS{alertname="FailClosedPersistente"}'
   ```
   Anota qué `last_cause` dio F22 apagado (`timeout` o `explainer_unavailable`) y el tiempo medido (K-50). `journey-7-3.sh 2` mira que el gauge de casos en fail-closed persistente suba a 1 o más y `journey-7-3.sh 3` que la alerta esté en `firing` (puede fallar hasta que pasen los minutos de espera). **Cuando `rt3` termine**, `system-verification/demos/verify/journey-7-3.sh 5` lee la evidencia que dejó (no antes: la escribe la herramienta al final).
4. **PR de reversión.** Abre el PR `system-verification/demos/prs/f22-apagado/revertir.patch`, fusiónalo y sincroniza `network` con prune:
   ```bash operador
   argocd app sync network --prune && argocd app wait network --health --timeout 900
   ```
5. **Cierre de D1:**
   ```bash
   vectra-verification rt3 --closing
   system-verification/demos/verify/journey-7-3.sh 4
   ```
   Vuelven los cinco recursos de red hacia el explainer y un caso de sonda **nuevo** recorre el flujo y llega a `listo` (K-52); el resultado del cierre queda en el manifiesto como `closing_rt3`, aparte del de `rt3`, y `journey-7-3.sh 4` lo lee de ahí (por eso va **después** de `rt3 --closing`, no antes). **`FailClosedPersistente` sigue en `firing`**: los casos de la primera sonda quedan en `no_disponible`, el reintento del CRO no existe de punta a punta (la vista está diferida) y nada los reactiva; no es un fallo de la reversión. **Cuenta** cuántos `no_disponible` quedan en la bandeja: siguen activos en D2 y D4 y no los afectan (ninguna demo lee ese gauge ni esa alerta). Después de **30 s** (ventana TOTP), `humo flujo --delivery /verification/reference-model/.out` confirma el flujo con otro caso.

<!-- inventario:F7 -->
| Id | Qué se mira | Cómo (solo lectura) | Demo |
|---|---|---|---|
| K-48 | RT3-a, c y d: 422 de U4 y serving-config sin cambio. RT3-b y 'a y d desplegados' se informan y pueden quedar no ejecutado | `vectra-verification rt3` | D1 |
| K-49 | Con el PR de F22 fusionado y network sincronizada con prune, desaparecen los cinco recursos de F22; con la reversion, vuelven | `vectra-verification rt3`; `estado-final.sh` | D1 |
| K-50 | Que last_cause da F22 apagado (timeout o explainer_unavailable); el caso pasa de en_sincronizacion a no_disponible entre 12,4 y 19,3 min; cero recommendation | `vectra-verification rt3`; `journey-7-3.sh` | D1 |
| K-51 | vectra_cases_failclosed_persistent raspado y FailClosedPersistente en firing unos minutos despues del primer caso en no_disponible (la herramienta la sondea hasta 5 min tras la escalada) | `observabilidad.sh consulta vectra_cases_failclosed_persistent`; `observabilidad.sh consulta ALERTS{alertname="FailClosedPersistente"}` | D1 |
| K-52 | La reversion devuelve el flujo a listo; cuantos casos no_disponible quedan y si la alerta sigue activa durante D2 y D4 | `humo flujo --delivery /verification/reference-model/.out`; `estado-final.sh` | D1, D2 |
<!-- /inventario:F7 -->

**Puerta de F7.** Sigues solo si: RT3-a, c y d dieron 422, con F22 apagado hubo cero `recommendation` y los casos de sonda llegaron a `no_disponible`, la alerta se vio, y **tras la reversión** `closing_rt3` está en `pasa` (`journey-7-3.sh 4` sale 0) y `humo flujo --delivery /verification/reference-model/.out` vuelve a dar `listo`; `FailClosedPersistente` sigue en `firing` y se anota. RT3-b y «a y d desplegados» pueden salir `no ejecutado` (decisión del usuario: K16 no llega a `vectra-staging`). Síntomas: los cinco recursos no vuelven, `network` no se sincronizó con prune (U1); el caso no llega a `no_disponible`, el reintento de U8; D1 no se ensaya dos veces sin esperar a que la alerta se apague.

## F8 D2 (`rt2-setup`, `rt2`)

Entradas: K-53 a K-61. Plantilla: `08-d2-rt2.md`. Duración: ≈ 3 h (más de 75 min de esperas, más 6 PR). Demo: D2 (`system-verification/demos/journey-7-4.md`). La más larga y la de más riesgo (R-1, R-4). **Termina antes de las 00:00 UTC** (ver «Calendario»). Puerta al final.

**Prerrequisitos.** F7 completa, con F22 **revertido y comprobado**. **La máquina sin otra carga** (R-1): nada de `decisions`, de construir imágenes ni de navegadores de más. **Al menos 1,5 GiB disponibles:** `system-verification/docs/kind/memoria.sh durante` sale 0 (puerta de memoria, R-4). El modelo de referencia `activo`. `reference-model/.out/proxy/run-1` existe. El presentador con `cumplimiento-2` en la consola si usa el modo `presenter`; con el modo `tool`, la herramienta usa `cumplimiento-1`. Decide el modo antes de empezar y **ensaya el otro al menos una vez**.

> **Advertencia 1: interrumpe `rt2` solo con Ctrl-C.** El defecto N-1 de la revisión de U12-T04 (el guardado por fase llegaba una fase tarde; `CANDIDATAS.md`, «U12, `scenarios/rt2.py:1008-1011`») **está corregido** (U12-T05, ronda 2): `rt2` marca la fase como hecha **antes** de guardar, así que una parada del contenedor, un `SIGKILL` o un reinicio **después** de que una fase terminó ya no la repiten al retomar (el lote tampoco, si ya había terminado de enviarse). Lo que sigue siendo cierto: una fase **en curso** no guarda nada a medias. Si se interrumpe **mientras se envía el lote** (≈ 150 s a 10 solicitudes por segundo), el lote solo se anota al terminar, y al retomar **se reenvía entero**, también con Ctrl-C. **El envío parcial no queda en la evidencia**: el manifiesto (`rows_sent`) solo trae el lote que terminó, así que los casos que ya habían llegado al sistema antes del corte serán **casos repetidos** que ninguna evidencia muestra (con un doble de pruebas: dos corridas del simulador, 150 casos recibidos y un solo lote en el manifiesto). Con **Ctrl-C** la herramienta además guarda el estado antes de salir; la parada de Docker mata a los 10 s con `SIGKILL`. Interrumpe con Ctrl-C y, si el corte cayó durante el lote, **anota la hora del corte** en la plantilla antes de volver a correr `rt2` y avisa: esa hora es lo único que dirá después que hay casos repetidos.
>
> **Advertencia 2: ten listo el cierre antes de que venza el plazo.** Al terminar sus fases, `rt2` **espera el cierre del paso 7** (`rollback-pr`, sync, pods `Ready`, `mark-active` del modelo de referencia) durante `--operator-timeout` (3 600 s por omisión) (`CANDIDATAS.md`, «U12, `cli.py:826` y `rt2._wait_closing`», N-2). Si el plazo vence, `closing_rt2` queda `no ejecutado` con `rt2` terminada y **no hay forma de retomar solo el cierre**: `rt2 --redo` empieza D2 desde cero. Antes de lanzar `rt2` deja preparados el PR de `rollback-pr` y la sesión de Argo CD; cuando `rt2` imprima que espera el cierre, el reloj corre. Si prevés tardar más, lanza `rt2` con `--operator-timeout` mayor.

**Pasos** (los de `journey-7-4.md`; la numeración de la guía no es la del guion):

1. **PR `proxy-staging`.** El parche **no es fijo**: se genera sobre los values tal como estén (`system-verification/demos/prs/proxy-staging/README.md`) con `entrada.py`, solo con la biblioteca estándar y sin escribir nada; `<M2>` es el `model_version_id` de `reference-model/.out/proxy/run-1/manifest.json`:
   ```bash
   git -C "$PROMO" switch main && git -C "$PROMO" pull --ff-only
   (cd "$PROMO/vectra-risk" && python3 system-verification/demos/prs/entrada.py --version <M2> --storage-uri "s3://model-store/<M2>/" > "$VERIF_HOME/proxy.patch")
   ```
   El parche se escribe **fuera del árbol** (`$VERIF_HOME`: un `proxy.patch` suelto en el clon lo dejaría sucio y `promotion-tool` se negaría con `working_tree_dirty`). Aplícalo con `git -C "$PROMO" apply "$VERIF_HOME/proxy.patch"` en una rama nueva, abre el PR, fusiónalo y sincroniza `model-serving`:
   ```bash operador
   sync model-serving
   ```
2. **`rt2-setup`** (`ingeniero-1` registra y valida la versión; `cro-1` la aprueba):
   ```bash
   vectra-verification rt2-setup
   system-verification/demos/verify/journey-7-4.sh 5
   ```
   **Espera (validación, hasta 30 min).** Mira `system-verification/docs/kind/memoria.sh durante` y `arranque.sh vectra-serving`. `journey-7-4.sh 5` lee del manifiesto que `rt2-setup` pasó (la versión vive en governance y K16 no la lee).
3. **Promoción de `<M2>`** (`system-verification/demos/prs/promocion/README.md`), en **este orden**: `promotion-tool create-promotion-pr <M2>`, fusión, sync de `model-serving` con prune; `promotion-tool mark-active <M2>` (governance deja a `<M1>`, el modelo de referencia, `inactivo`); `promotion-tool post-activation-pr <M1>`, fusión y sync (`<M1>` baja a 1 réplica). `post-activation-pr` solo vale **después** del `mark-active` de la versión nueva. La invocación completa está en `governance/docs/paso-20-kind.md`, §5.4 y §6 (no se copia), con `--repo "$PROMO"`, desde `"$PROMO/vectra-risk"` y como `ingeniero-2` (F3, paso 7); **antes de cada orden**, `git -C "$PROMO" switch main && git -C "$PROMO" pull --ff-only`, y también después de fusionar el PR anterior (la orden siguiente lee los values y el `main` de ese clon). Después de fusionar cada PR:
   ```bash operador
   argocd app sync model-serving --prune && argocd app wait model-serving --health --timeout 900
   ```
   Comprueba: `system-verification/demos/verify/journey-7-4.sh 1 isvc-<8 hex>` y `kubectl --context kind-vectra get inferenceservices,pods -n vectra-serving` (el activo nunca baja de 2 réplicas; K-54).
4. **`rt2`** (lote estratificado de 1 500 solicitudes a 10/s, espera del `freeze`, paquete, 3 corridas de bias, reactivación, 1 corrida más y barrido de U8):
   ```bash
   vectra-verification rt2 --reactivation presenter
   ```
   (o `--reactivation tool`; por omisión es `tool`). **Interrúmpela solo con Ctrl-C** (advertencia 1). Al terminar las fases, `rt2` imprime qué falta y **espera el cierre del paso 7** (advertencia 2). **Espera (más de 75 min).** Mira cada 15 min, mientras tanto:
   ```bash
   system-verification/demos/verify/journey-7-4.sh 2
   kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=bias-monitoring-job --tail=50
   system-verification/docs/kind/observabilidad.sh consulta 'vectra_bias_last_run_ok'
   system-verification/docs/kind/memoria.sh durante
   ```
   Si el log trae 504 o `agregador_atrasado`: es **R-1**; anota la hora y la carga de la máquina, espera la siguiente corrida y, tras tres sin `freeze`, D2 queda `no ejecutado` y se avisa (decide el usuario). Si el **primer ensayo** da 504 de U3, se para.
5. **El presentador** (`ruta /congelamientos` y `ruta /congelamientos/:freezeId`, con `cumplimiento-2`): muestra el paquete (antes, después, últimos 7 días, atributo, volumen afectado) y el texto «Modelo congelado». En modo `presenter` resuelve con «reactivar» en `ResolveFrozenDialog` (pide MFA, ventana emergente y `/stepup-callback`; `acr = mfa`). Vencido el plazo (`--reactivation-timeout`), `rt2` queda `no ejecutado` y se retoma volviendo a correrla.
6. **Tras reactivar, no se recongela.** `no_recongela` espera **siempre 2 corridas** del cron (≈ 30 min más) y, si el reloj de U3 va 0,5 s o más por delante del de U9 (no ocurre en kind), una corrida de más (`CANDIDATAS.md`, líneas 744 y 747). **Espera (≈ 30 min).** Mira cada 15 min `observabilidad.sh consulta 'vectra_bias_last_run_ok'` y el log del Job de bias.
7. **Cierre: rollback al modelo de referencia. Hazlo cuando `rt2` imprima que espera el cierre, dentro del plazo** (advertencia 2; con el proxy todavía `congelado` el `mark-active` de `<M1>` da 409 `active_version_frozen`, `governance/src/vectra_governance/model_fsm.py`: reactiva antes, en el modo elegido): `promotion-tool rollback-pr <M1>` (con `git -C "$PROMO" switch main && git -C "$PROMO" pull --ff-only` antes, como en el paso 3), fusión, sync de `model-serving` con prune:
   ```bash operador
   argocd app sync model-serving --prune && argocd app wait model-serving --health --timeout 900
   ```
   Espera a que los pods de `<M1>` estén `Ready` (`kubectl --context kind-vectra get inferenceservices,pods -n vectra-serving`) y, **después**, `promotion-tool mark-active <M1>` (governance deja a `<M2>` `inactivo`). `rt2` lo ve y termina. Entonces: `system-verification/demos/verify/journey-7-4.sh 3` y `journey-7-4.sh 4 isvc-<8 hex>`; el 4 lee `closing_rt2` del manifiesto (que governance tiene a `<M1>` `activo`), así que solo vale cuando `rt2` ya terminó.
8. **Retira staging:** el PR de retiro de `proxy-staging` (y el de `rt3-staging`, si se hizo), que arma `entrada.py --retirar` sobre los values tal como estén (`git apply -R` del parche de alta ya no aplica: `promotion-tool` reescribió el bloque `inferenceServices` en estilo de bloque):
   ```bash
   git -C "$PROMO" switch main && git -C "$PROMO" pull --ff-only
   (cd "$PROMO/vectra-risk" && python3 system-verification/demos/prs/entrada.py --version <M2> --retirar > "$VERIF_HOME/retirar-proxy.patch")
   ```
   Aplícalo en una rama nueva del clon y abre el PR. Opcional: `promotion-tool post-activation-pr <M2>` (deja a `<M2>` sin 2 réplicas de más). Fusiona y sincroniza `model-serving` con prune otra vez:
   ```bash operador
   argocd app sync model-serving --prune && argocd app wait model-serving --health --timeout 900
   ```
   Anota la **duración total** frente a «más de 75 min».

**Repetir D2 tras un fallo a medias** (la segunda pasada). Mira primero dónde quedó: `humo modelos` (guarda el JSON) y `system-verification/demos/verify/journey-7-4.sh 1 isvc-<8 hex>`. Después, según el caso:
- **`create-promotion-pr <M2>` da `already_declared`** en la segunda pasada si `<M2>` ya está en los values como `prod` o `inactive` (`governance/promotion_tool/vectra_promotion/values.py`, `promote`): **no la repitas**; sigue desde la orden que falta (`mark-active <M2>`, `post-activation-pr <M1>`...). Las ramas `promotion/<tipo>-isvc-<8 hex>-kind` tienen **nombre fijo** (`gitops.py`, `open_pr`): si un intento dejó la rama (PR cerrado o sin fusionar), la orden siguiente falla al crearla; borra la rama local vieja en el clon (`git -C "$PROMO" branch -D <rama>`) antes de repetir. Si esa rama ya se empujó, borrar la remota es una escritura en GitHub: **orden del operador** con su nombre (`git push origin --delete <rama>`, o el botón de borrar rama del PR cerrado), que no cabe en la lista cerrada ni la amplía.
- **Con el proxy `congelado` no hay rollback sin reactivar antes:** `mark-active <M1>` da 409 `active_version_frozen` (`governance/src/vectra_governance/model_fsm.py`). El orden de la segunda pasada: **reactivar `<M2>`** (el modo `tool`, el presentador o `rt2` retomada en su fase de reactivación) → `rollback-pr <M1>` → fusión → sync con prune → pods de `<M1>` `Ready` → `mark-active <M1>`.
- **`rt2`** se retoma volviendo a correrla mientras no haya terminado; `rt2 --redo` empieza D2 desde cero (otro lote de 1 500 solicitudes: casos repetidos que ninguna evidencia muestra).
- **El mismo proxy no se recongela el mismo día UTC** de su reactivación: ver «Calendario» (otro día UTC u otro paquete `run-N`).
El detalle está en `system-verification/demos/journey-7-4.md`, «Qué deja sucio y cómo se limpia».

<!-- inventario:F8 -->
| Id | Qué se mira | Cómo (solo lectura) | Demo |
|---|---|---|---|
| K-53 | rt2-setup: el proxy queda aprobado, con initial_disparity no vacia, tras el PR proxy-staging | `vectra-verification rt2-setup` | D2 |
| K-54 | Promocion con trafico: 0 version_mismatch; el activo nunca baja de 2 replicas; los requests de memoria durante la promocion caben | `arranque.sh vectra-serving`; `memoria.sh durante`; `kubectl --context kind-vectra get inferenceservices,pods -n vectra-serving` | D2 |
| K-55 | Las celdas de RT-2: rt2 se niega solo por una celda alcanzable corta; las inalcanzables se informan | `vectra-verification rt2` | D2 |
| K-56 | U3 no responde 504 al cron de U9 con la maquina cargada; las metricas de bias llegan por el Pushgateway | `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=bias-monitoring-job`; `observabilidad.sh consulta vectra_bias_last_run_ok` | D2 |
| K-57 | El proxy congela con una corrida real del CronJob; rt2_latency a 1 800 s o menos (una medicion); el paquete completo (FreezeContext, data_sources, initial_disparity) | `vectra-verification rt2` | D2 |
| K-58 | FailClosed(model_frozen) en 6 s o menos tras el freeze; los casos nuevos quedan modelo_congelado | `vectra-verification rt2`; `journey-7-4.sh` | D2 |
| K-59 | Duracion y pico de memoria de una corrida de bias, bajo los 256 MiB del limite | `kubectl --context kind-vectra get jobs -n vectra-app`; `memoria.sh durante` | D2 |
| K-60 | Los dos modos de reactivacion: el de la herramienta con cumplimiento-1, y --reactivation presenter con cumplimiento-2 en la consola (ventana emergente, /stepup-callback, acr = mfa, ResolveFrozenDialog) | `vectra-verification rt2`; a mano: la consola, con cumplimiento-2 | D2 |
| K-61 | Tras reactivar no se recongela; el barrido de U8 devuelve los modelo_congelado; el rollback deja el modelo de referencia activo; la duracion real frente a mas de 75 min | `vectra-verification rt2`; `estado-final.sh` | D2 |
<!-- /inventario:F8 -->

**Puerta de F8.** Sigues solo si: el proxy pasó `aprobado` y luego `activo`; el `freeze` trae su paquete completo y `rt2_latency` ≤ 1 800 s (una medición, DD-1); los casos nuevos quedaron en `modelo_congelado`; la reactivación se hizo en el modo elegido y el otro modo se ensayó al menos una vez; no se recongeló; el cierre se hizo dentro del plazo y `closing_rt2` quedó en `pasa` (`journey-7-4.sh 4` sale 0: el rollback dejó el modelo de referencia `activo`); cero 504 en el log del Job de bias. Síntomas: 504 o `agregador_atrasado` (U3, R-1); `OOMKilled` (R-4); `version_mismatch` en la promoción (U6 y U7); sin `freeze` tras 3 corridas, R-1.

## F9 D4 (día D + 1 UTC)

Entradas: K-62 y K-63. Plantilla: `09-d4-u11-y-grafana.md`. Duración: 15 min, tras la espera. Demo: D4. Puerta al final.

**Prerrequisitos.** F6 completa. **Dentro del día D + 1 UTC, es decir, hasta las 00:00 UTC de D + 2** (las 19:00 de Colombia de D + 1): `u11` lee las series con `period="day"`, el «ayer» de `product-metrics` (`product-metrics/src/vectra_product/compute.py`, `compute`); desde las 00:00 UTC de D + 2 el «ayer» es D + 1, sin decisiones, y su razón no se emite (`Ratio.rate`: «ausente, no 0»): D4 deja de pasar y ninguna espera lo arregla. **No antes de ≈ 02:40 UTC del día D + 1** (21:40 de Colombia del día D) es la hora de la herramienta: la pasada completa de U11 es a las 02:30 UTC más hasta 10 min de desfase, y `u11` no corre el mismo día UTC de `decisions`. Lo que dice el código sobre esa espera: el planificador publica las series tras cada lectura incremental (cada 5 min) y al cambiar el día (`product-metrics/src/vectra_product/scheduler.py`), así que las series del «ayer» pueden existir desde unos minutos después de las 00:00 UTC de D + 1 si `product-metrics` hizo su pasada completa al arrancar; **no está medido en kind**. Antes de las 02:40 UTC la herramienta trata una serie ausente como `no ejecutado` (`pass_deadline` en `system-verification/src/vectra_verification/scenarios/u11.py`), no como `falla`. **Espera (hasta ≈ 02:40 UTC):** mientras tanto, `kubectl --context kind-vectra get pods -l app.kubernetes.io/name=product-metrics -n vectra-app` y `date -u`.

**Pasos.**

1. **Grafana arriba:** `system-verification/demos/verify/dashboard.sh 1`.
2. **`u11`** (las cuatro series de los paneles y `ProductMetricsStale`; `dashboard.sh 2` comprueba que las cuatro series tengan valor y `dashboard.sh 3` que la alerta no esté en `firing`):
   ```bash
   vectra-verification u11
   system-verification/demos/verify/dashboard.sh 2
   system-verification/demos/verify/dashboard.sh 3
   ```
3. **Grafana por `port-forward` con `grafana-admin`.** La credencial sale del Secret `grafana-admin` (lo llena ESO desde `grafana/admin`; `platform/observability/grafana/external-secrets.yaml`, líneas 31 a 36):
   ```bash
   kubectl --context kind-vectra port-forward -n vectra-observability --address=127.0.0.1 pod/<pod de grafana> 13000:3000
   ```
   El pod es el de `kubectl --context kind-vectra get pods -n vectra-observability -l app.kubernetes.io/name=grafana`. Abre `http://127.0.0.1:13000` con `grafana-admin` y muestra el dashboard `Producto` (`uid` `vectra-producto-panel`, carpeta `Vectra / Producto`) con sus cuatro paneles con datos: `North Star de ayer`, `Recomendaciones sostenidas (aproximación)`, `Tasa de consulta de la explicación y piso F` y `Días bajo el piso`. Los permisos por carpeta y rol **no** se enseñan (Grafana no tiene OIDC).
4. **La evidencia:** `system-verification/demos/verify/dashboard.sh 4`.

<!-- inventario:F9 -->
| Id | Qué se mira | Cómo (solo lectura) | Demo |
|---|---|---|---|
| K-62 | North Star, sostenida, tasa de consulta y ProductMetricsStale con datos reales, dentro del dia D + 1 UTC (la herramienta espera hasta las 02:40 UTC; desde las 00:00 UTC de D + 2 el ayer no tiene decisiones) | `vectra-verification u11`; `dashboard.sh` | D4 |
| K-63 | Grafana por port-forward con grafana-admin; el dashboard Producto carga con sus cuatro paneles. Los permisos por carpeta y rol no se ensenan | `kubectl --context kind-vectra port-forward -n vectra-observability`; a mano: el navegador, en el dashboard Producto | D4 |
<!-- /inventario:F9 -->

**Puerta de F9.** Sigues solo si: `u11` dio North Star, sostenida y tasa de consulta con datos reales y el dashboard abrió con sus cuatro paneles con datos. Si el dashboard está vacío, espera la siguiente pasada (15 min) antes de darlo por fallo (R-8). Síntomas: `product-metrics` con 503, arrancó antes que el registro (U11); `ProductMetricsStale` en `firing`, la pasada no corrió (U11); `u11` se niega, el día UTC o la hora; las series vacías después de las 00:00 UTC de D + 2, la ventana se cerró (hay que repetir `decisions` otro día: D4 no tiene otra forma).

## F10 Informe y estado final

Entradas: K-64 y K-65. Plantilla: `10-informe-y-estado-final.md`. Duración: 30 min. Puerta al final.

**Prerrequisitos.** F8 completa y F9 hecha (el día D + 1 UTC). La memoria de la máquina: cierra todo lo que no uses; este es el último paso con el clúster en el estado de la demo.

**Pasos.**

1. **El informe:**
   ```bash
   vectra-verification report
   ```
   Lista cada RT, demo e historia. Salen `no ejecutado`, con su motivo: US-106, 109, 305, 603, 604, 608, 609 y 610, `RT3-b` y «a y d desplegados» (decisión del usuario), `RT-1`, `RT-4`, `X01` a `X10`, `LOGS-NO-PII`, `LOAD`, `RESTORE-DRILL`, `READINESS` y `CASE-SIZE`. Ninguno debe salir `pasa` sin evidencia. Lee `$EVID/verification-report.md` (la evidencia vive fuera del repositorio hasta el paso 4).
2. **El clúster queda como estaba** (solo lectura). El estado de los modelos sale de la API de la consola:
   ```bash
   humo modelos | system-verification/docs/kind/estado-final.sh --modelos - --referencia <M1>
   ```
   `<M1>` es el `model_version_id` del modelo de referencia (el que `humo modelos` mostró `activo` en F4; también está en `reference-model/.out/package/manifest.json`): con el proxy `activo`, `estado-final.sh` sale 1. Esperado: código 0 (modelo de referencia `activo`, ninguna versión `congelado`, sin `InferenceService` de staging, los cinco recursos de F22 presentes). Compara con el JSON que guardaste en F4. Anota lo que **queda**: los `no_disponible`, el `runId`, la alerta `FailClosedPersistente`, el Job `rt5-demo-<runId>`.
3. **Memoria del final** de la jornada: `system-verification/docs/kind/memoria.sh despues`.
4. **El PR de verificación** (desde la rama `verificacion/<fecha>-<commit>`, en el clon de promoción): `system-verification/evidence/<fecha>-<commit>/` (con `manifest.json` y `verification-report.md`), las plantillas `00` a `12` llenas, la tabla de `cierre-demo.md` con el resultado de cada K y el Paso 18 en `[x]`. La evidencia vive en `$EVID`, fuera del repositorio (F0, paso 9); aquí es donde entra al árbol:
   ```bash
   git -C "$PROMO" switch main && git -C "$PROMO" pull --ff-only
   git -C "$PROMO" switch -c "verificacion/$(basename "$EVID")"
   cp -r "$EVID" "$PROMO/vectra-risk/system-verification/evidence/"
   cp -r "$VERIF_HOME/plantillas/kind/." "$PROMO/vectra-risk/aidlc-docs/construction/system-verification/evidence/kind/"
   cp "$VERIF_HOME/plantillas/cierre-demo.md" "$PROMO/vectra-risk/aidlc-docs/construction/system-verification/evidence/cierre-demo.md"
   ```
   Las plantillas llenas (F0 paso 11) y `cierre-demo.md` se copian **sobre** las del repositorio; si `main` cambió alguna desde que las copiaste, compárala antes. Después, en esa rama, el Paso 18 pasa a `[x]` en `aidlc-docs/construction/plans/system-verification-code-generation-plan.md`.
   Lo abres tú; lo revisan las personas de `CODEOWNERS`.

<!-- inventario:F10 -->
| Id | Qué se mira | Cómo (solo lectura) | Demo |
|---|---|---|---|
| K-64 | El informe lista cada RT, demo e historia; salen no ejecutado US-106, 109, 603, 305, 604, 608, 609 y 610, RT3-b y 'a y d desplegados'; ninguno sale pasa sin evidencia | `vectra-verification report` | Base |
| K-65 | El cluster queda como estaba: modelo de referencia activo, ninguna version congelado, sin InferenceService de staging, F22 encendido | `estado-final.sh` | D1, D2 |
<!-- /inventario:F10 -->

**Puerta de F10.** Terminaste si: `estado-final.sh` salió 0, el informe lista cada RT, demo e historia y el PR de verificación está abierto. Síntomas: una versión sigue `congelado` o queda un `InferenceService` de staging, falta el rollback o el PR inverso (F8); falta un recurso de F22, la reversión de F7 no se sincronizó con prune (U1).

## F11 Opcionales

Entradas: K-66. Plantilla: `11-opcionales.md`. Duración: 30 min. **Solo después de F10 y solo si hay tiempo:** alguna sonda reinicia pods. Ninguna demo depende de ella; si no hay tiempo, quedan como candidatas.

**Pasos.**

1. **(a) El login de la herramienta con Keycloak caído a mitad.** ¿Se cuelga o termina con error? Lanza `humo login` y, mientras el login corre, borra el pod de Keycloak:
   ```bash operador
   kubectl --context kind-vectra delete pod -n vectra-identity -l app.kubernetes.io/name=keycloak
   ```
   Anota si `humo login` termina con un error claro o se queda esperando (`CANDIDATAS.md`, línea 684). Espera a que Keycloak vuelva (`arranque.sh vectra-identity`).
2. **(b) El apagado del worker con trabajo en vuelo** (≈ 34 s frente a 40 s de gracia):
   ```bash operador
   kubectl --context kind-vectra rollout restart deploy/case-worker -n vectra-app
   ```
   Mira `kubectl --context kind-vectra get pods -n vectra-app` y `logs` de `case-worker` mientras rota (`aidlc-docs/construction/case-management/evidence/cierre-demo.md`, línea 77).
3. **(c) PBT-U8-07 abreviado contra el registro real** (`aidlc-docs/construction/case-management/evidence/cierre-demo.md`, línea 71): según la guía de U8; queda como candidata si no hay tiempo.

<!-- inventario:F11 -->
| Id | Qué se mira | Cómo (solo lectura) | Demo |
|---|---|---|---|
| K-66 | (a) El login de la herramienta con Keycloak caido a mitad: se cuelga o termina con error. (b) El apagado del worker con trabajo en vuelo (34 s frente a 40 s de gracia). (c) PBT-U8-07 abreviado contra el registro real | `kubectl --context kind-vectra get pods -n vectra-app`; `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=case-worker` | — |
<!-- /inventario:F11 -->

**Puerta de F11.** Ninguna: lo que se vea se anota en la plantilla 11 y lo que falle abre una candidata, no un bloqueo.

## Al terminar

- **Duraciones y memoria** (plantilla `12-duraciones-y-memoria.md`): la duración real de cada fase frente a la estimada; `free -m` al empezar y al terminar cada jornada y en el pico de D2; la memoria del contenedor de U12 frente a `--memory 1g`; las constantes de `guard` (1 s por caso, 300 s de margen) frente a lo medido. Con eso se corrigen el README, esta guía y, si hace falta, `BUDGET_GIB`.
- **Candidatas** que esta tarea dejó para el PR de verificación: lo que falló en una unidad abre una tarea en esa unidad.
- **Lo que esta guía no demuestra.** Que funcione en kind: eso lo dice tu evidencia. La prueba de mundo cerrado solo demuestra que ningún nombre de esta guía es inventado.
