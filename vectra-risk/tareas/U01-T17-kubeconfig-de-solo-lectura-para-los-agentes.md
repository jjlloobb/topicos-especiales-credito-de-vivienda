# U01-T17 — Un kubeconfig de solo lectura para los agentes del loop

**Unidad:** U1 — `platform` (solo kind)
**Historias que implementa:** ninguna nueva; cierra la causa de fondo de dos incidentes del 2026-11-16 en `kind-vectra`.
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> En la máquina de desarrollo, el `kubectl` de cualquier proceso usa `~/.kube/config`, cuyo contexto `kind-vectra` es de administrador. La regla «los agentes no tocan el clúster» es solo una instrucción en los despachos, y el 2026-11-16 falló dos veces:
>
> - **Lecturas (PR #195).** Dos pruebas de `platform/kind/tests/test_identity_seed.py` ejecutaban `kubectl --context kind-vectra get …` de verdad y leían los `Secret` del clúster, con sus valores, en cada corrida del codificador y del revisor. Se vio solo porque la CI, sin clúster, falló.
> - **Un borrado (15:01:27 UTC).** Una prueba nueva de `system-verification/tests/unit/test_kind_guide.py` pasó a `bash`, con el `PATH` real, la guía de kind casi entera. Corrió `kubectl --context kind-vectra delete -f identity-edge/tests/e2e/echo/manifests.yaml` y borró el Deployment, el Service, la ServiceAccount y el PDB de `console-spa`, `console-bff`, `case-service` y `governance-service`. Nadie lo notó en 12 horas.
>
> Lo que se quiere: que un proceso lanzado por un codificador o un revisor **no pueda escribir en el clúster ni leer un `Secret`, aunque lo intente**, y que eso no dependa de recordar una variable en cada orden.
>
> 1. **Una identidad de solo lectura, declarada en Git y solo en kind.** Una `ServiceAccount` con su token y el RBAC mínimo:
>    - puede `get`, `list` y `watch` lo que hace falta para diagnosticar: los recursos del núcleo y de `apps`, `batch`, `autoscaling`, `policy` y `networking.k8s.io`, los nodos y namespaces, `pods/log`, las métricas (`metrics.k8s.io`) y los recursos propios que el proyecto usa (Applications de Argo CD, `ExternalSecret` y `SecretStore`, clústeres de CloudNativePG, políticas de Kyverno, recursos de Gateway API y de Envoy Gateway, `InferenceService` de KServe, `Server` y `AuthorizationPolicy` de Linkerd, los monitores y reglas de Prometheus). Saca la lista de lo que leen los guiones de solo lectura del repositorio (`system-verification/docs/kind/*.sh`, `platform/kind/gateway-address.sh`) y de los CRD que instala `vectra-risk-gitops/components.yaml`; no la inventes;
>    - **no** puede leer `secrets`, ni `pods/exec`, `pods/portforward`, `pods/attach`, ni ningún verbo de escritura (`create`, `update`, `patch`, `delete`, `deletecollection`), ni `impersonate`, ni `escalate`/`bind`;
>    - **sin comodines** en `verbs`, `resources` ni `apiGroups`: la política `disallow-rbac-wildcards` (`platform/policies/kyverno/`) está en `Enforce` y no se relaja ni se le añade una excepción. Si reutilizas el `ClusterRole` integrado `view`, comprueba qué agrega y qué no (no cubre los CRD ni lo que es de ámbito de clúster) y dilo.
>    Llega al clúster como una Application solo de kind, igual que `external-secrets-rbac-kind` (`vectra-risk-gitops/components.yaml`, línea 17, y `generate.py`): decide el namespace (uno que ya exista y cuyas políticas y cuotas admitan una `ServiceAccount` sin pods) y la wave, y di por qué.
> 2. **Un guion del operador, `platform/kind/readonly-kubeconfig.sh`**, con dos órdenes:
>    - `write [ruta]`: lee el token y la CA y escribe un kubeconfig (0600, **fuera del repositorio**; por omisión `~/.kube/kind-vectra-readonly`) con **un solo contexto, llamado `kind-vectra`**, atado a esa identidad. El nombre importa: los guiones y las pruebas del repositorio llevan `--context kind-vectra` escrito; con este archivo en `KUBECONFIG`, esa misma orden resuelve a la identidad de solo lectura en vez de fallar o de escapar al de administrador. No imprime el token. Usa el kubeconfig de administrador solo para leer ese token (di con qué orden) y se niega fuera de un contexto `kind-*`.
>    - `check [ruta]`: de solo lectura. Con el kubeconfig generado, corre una tabla de `kubectl auth can-i` y sale 0 solo si **todas** las filas dan lo esperado: sí a `get pods`, `list deployments`, `get pods/log`, `list applications.argoproj.io`, `list externalsecrets.external-secrets.io`, `get nodes`; no a `get secrets`, `delete deployments`, `create pods`, `patch deployments`, `create pods/exec`, `create pods/portforward`, `delete -f` de cualquier cosa, `impersonate users`, en `vectra-app`, `vectra-edge`, `vectra-data` y a nivel de clúster. Imprime la tabla. Es la lectura de vuelta que el orquestador correrá en el clúster.
> 3. **`argocd` y `docker`.** La CLI de `argocd` guarda una sesión de administrador en la máquina y `docker` puede entrar a los nodos de kind: el kubeconfig no los cubre. Investiga y documenta, sin cambiar la configuración de nadie: qué variable o archivo hace que un proceso use otra configuración de `argocd` (vacía) y qué deja a `docker` sin llegar al demonio (`DOCKER_HOST`), y qué pruebas del repositorio necesitan Docker de verdad (Testcontainers) y no podrían correr así. Deja la recomendación escrita; decidirlo es del usuario.
> 4. **Cómo se usa**, en `platform/kind/registry.md` o en un documento nuevo junto a él, y en `loop/README.md` (una sección corta): el operador corre `write` una vez (y otra tras recrear el clúster); los agentes corren con `KUBECONFIG` apuntando a ese archivo; la sesión del orquestador usa el de administrador solo en las órdenes que el usuario aprueba, nombrándolo de forma explícita. Di qué pasa tras reiniciar la máquina (¿el token sigue valiendo?) y tras recrear el clúster.
> 5. **Qué NO resuelve**, escrito sin adornos: un proceso que fije él mismo `KUBECONFIG=~/.kube/config` o `--kubeconfig`; `docker exec` en un nodo; la sesión de `argocd`. La identidad de solo lectura reduce el daño de un error, no impide un acto deliberado.

**Fuera:**

- **`.claude/settings.json` y `.claude/agents/*.md`.** Fijar `KUBECONFIG` en el entorno de los agentes cambia la configuración de permisos del usuario: no lo edites. Deja en tu informe el cambio exacto que propones (clave, valor y a quién afecta, incluida la sesión del orquestador) para que el usuario lo decida.
- Relajar `disallow-rbac-wildcards` u otra política, o añadirles excepciones.
- Staging y prod: esta identidad no existe allí. Comprueba que `generate.py` no la emite para esos entornos.
- Las pruebas de otras unidades que lanzan `kubectl` o `bash` con el `PATH` real (candidatas; U12-T09 arregla las suyas).
- Cualquier orden contra el clúster.

---

## Archivos de contexto

- `vectra-risk-gitops/components.yaml` (línea 17), `vectra-risk-gitops/generate.py`, `vectra-risk-gitops/apps/kind/external-secrets-rbac-kind.yaml`, `platform/secrets/eso-rbac-secrets-read-kind.yaml` (el patrón de un RBAC solo de kind)
- `platform/policies/kyverno/disallow-rbac-wildcards.yaml`, `require-criticality-label.yaml`, `fixtures/`, `kyverno-test.yaml`; `platform/policies/rego/` (reglas de RBAC, si las hay); `platform/namespaces/` (etiquetas y cuotas)
- `platform/kind/gateway-address.sh`, `platform/kind/seed-vault.sh`, `platform/kind/tests/` (`conftest.py` con la salvaguarda de `kubectl`, `test_gateway_address.py`: el patrón de un guion probado con `kubectl` falso), `platform/kind/registry.md`, `platform/kind/cluster.yaml`
- `system-verification/docs/kind/*.sh` y `lib.sh` (qué leen los guiones de solo lectura)
- `platform/tests/test_waves.py`, `test_platform.py`, `test_ci.py` (lo que ata las Applications, las waves y los verbos de `kubectl`), `platform/Makefile`
- `loop/README.md`, `loop/orquestador.md` (regla dura 5), `DECISIONES-LOOP.md` §11
- `revisiones/U01-T16/` (`ci-respuesta.md`) y `revisiones/U12-T09/` (lo ocurrido)

---

## Criterios de aceptación

- [ ] **CA-1** — El RBAC no tiene comodines, no da ningún verbo de escritura ni acceso a `secrets`, y pasa las políticas de la plataforma.
  ```bash
  cd vectra-risk && uv run pytest platform -q -p no:cacheprovider --rootdir=platform --import-mode=importlib -k "readonly" && make -C platform check-tools
  ```
  Esperado: pasa, con pruebas nuevas sobre el manifiesto real (no sobre una copia): cada regla lista solo `get`, `list`, `watch`; `secrets`, `pods/exec`, `pods/portforward` y `pods/attach` no aparecen; ningún `*`. Mutaciones que deben fallar: añadir `delete` a una regla, añadir `secrets`, poner `*` en `resources`. En `check-tools`, un caso de `kyverno test` para el `ClusterRole` nuevo con `disallow-rbac-wildcards` en `pass`. Comprueba con `--collect-only` que el filtro selecciona tus pruebas.

- [ ] **CA-2** — La Application existe solo en kind y `generate.py` está al día.
  ```bash
  cd vectra-risk && uv run python vectra-risk-gitops/generate.py --check && ls vectra-risk-gitops/apps/kind | grep -c readonly && ! ls vectra-risk-gitops/apps/staging vectra-risk-gitops/apps/prod | grep readonly && uv run python platform/tests/test_waves.py
  ```
  Esperado: rc 0 y 1 archivo en `apps/kind`. Ajusta el nombre del filtro al que elijas y dilo.

- [ ] **CA-3** — `readonly-kubeconfig.sh write` escribe un kubeconfig 0600 con un único contexto `kind-vectra`, fuera del repositorio, sin imprimir el token; `check` sale 0 solo si toda la tabla da lo esperado.
  ```bash
  cd vectra-risk && uv run pytest platform/kind/tests -q -p no:cacheprovider -k "readonly_kubeconfig" && shellcheck platform/kind/readonly-kubeconfig.sh
  ```
  Esperado: pasa, con `kubectl` falso (el patrón de `test_gateway_address.py`). Casos: escritura correcta y permisos; se niega con una ruta dentro del repositorio; se niega fuera de `kind-*`; el token no aparece en stdout ni stderr; `check` con un falso que responde bien sale 0; con una sola fila mal (por ejemplo `can-i delete deployments` = `yes`, o `can-i get pods` = `no`) sale distinto de 0 y nombra la fila. Mutación: quitar una fila de «no» de la tabla hace fallar una prueba que fija la tabla mínima. `shellcheck` está en `~/.local/bin`.

- [ ] **CA-4** — `check` es de solo lectura y ningún guion nuevo escribe en el clúster.
  ```bash
  cd vectra-risk && ! grep -n -E 'kubectl[^|#]*\b(apply|delete|patch|annotate|create|edit|replace|scale|rollout|exec)\b' platform/kind/readonly-kubeconfig.sh
  ```
  Esperado: rc 0. Si `write` necesita una orden que este filtro rechaza (por ejemplo crear un token), dila, justifícala y ajusta el filtro en tu informe; la preferencia es leer un token que ya exista.

- [ ] **CA-5** — La documentación dice cómo se usa y qué no resuelve.
  ```bash
  cd vectra-risk && grep -n -c 'readonly-kubeconfig.sh' platform/kind/registry.md loop/README.md && uv run python platform/tests/test_links.py && uv run python platform/tests/test_runbooks.py
  ```
  Esperado: al menos 1 en cada archivo (o en el documento nuevo que enlacen: dilo); enlaces y runbooks en rc 0.

- [ ] **CA-6** — El pytest completo de `platform` pasa como lo corre la CI y sin clúster, y `platform` sigue en verde.
  ```bash
  cd vectra-risk && NOKUBE="$(echo "$PATH" | tr ':' '\n' | grep -v -E '^/snap/bin$' | paste -sd:)" && PATH="$NOKUBE" KUBECONFIG=/nonexistent uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider -q && KUBECONFIG=/nonexistent make -C platform check
  ```
  Esperado: pasan. (Con `platform/.tools` movido FUERA del árbol para el pytest y devuelto antes de `make check`; `make check` una sola vez, al final.)

---

## Plan de pruebas

Las de CA-1 a CA-3. **Rojo primero**; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`, ni lecturas.** Corre TODO con `KUBECONFIG=/nonexistent` y con un `PATH` sin `kubectl` real (está en `/snap/bin`; compruébalo con `which`). Tus pruebas usan un `kubectl` falso. La salvaguarda `autouse` de `platform/kind/tests/conftest.py` debe seguir en pie.
- Ninguna prueba ejecuta con `bash` o `subprocess` texto sacado de un documento. Las pruebas de tus guiones los lanzan con un `PATH` que contiene solo el directorio de falsos y los binarios inofensivos que hagan falta, y con `env` construido desde cero (sin `os.environ`).
- Ningún token ni valor secreto en pruebas, bitácora ni salidas: usa valores de mentira.
- Lo que no puedes medir sin clúster (que el token de la `ServiceAccount` exista como esperas, que `auth can-i` responda así con los CRD reales) dilo como «no medido»: el orquestador corre `write` y `check` en el clúster, con aprobación del usuario, cuando la tarea esté fusionada. Deja en la bitácora las órdenes exactas y qué debe ver.
- `platform/.tools`: enlázalo a `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools`; `platform/.charts`: cópialo de `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u01-t13/vectra-risk/platform/.charts`. No van en el commit.
- La máquina tiene poca memoria y un clúster de kind completo corriendo: una sola corrida pesada a la vez.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u01t17-`, y borra tus copias al terminar.
- En paralelo corre U12-T09 (`system-verification/`): no toques esos archivos.
- `CANDIDATAS.md`: solo añadir al final. Pocos commits grandes (uno por bloque terminado). No hagas push, no fusiones, no muevas el estado de la tarea.
