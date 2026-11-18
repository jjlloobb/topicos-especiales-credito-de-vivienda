# U01-T19 — Las sondas de los operadores en kind aguantan una racha de CPU lenta

**Unidad:** U1 — `platform` (solo kind)
**Historias que implementa:** ninguna nueva; corrige lo medido en `kind-vectra` el 2026-11-17.
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> Medido por el orquestador el 2026-11-17 en `kind-vectra` (portátil de 4 núcleos y 8 hilos, 15 GB, tres nodos de kind):
>
> - En calma el clúster entero consume menos de un núcleo. A rachas (16 inicios entre las 13:05 y las 20:32), el mismo trabajo consume de 4 a 5 veces más CPU en **todos** los contenedores a la vez (kube-apiserver, etcd, Calico, Postgres, kubelet), con las mismas sondas por segundo y las mismas operaciones de kubelet. La causa de las rachas es de la máquina y no está cerrada (la mejor pista: coinciden con la batería cargando); **no es objeto de esta tarea**.
> - Durante una racha las sondas fallan **por plazo agotado**, no por error. En una hora: miles de eventos `Unhealthy … timeout` repartidos por todo el clúster.
> - Los contenedores cuya sonda de **vida** falla se reinician, y cada arranque gasta más CPU. Reinicios acumulados en 16 días: `argo-cd-argocd-repo-server` 100, `argo-cd-argocd-server` 95, `cloudnative-pg` (operador) 105, `kserve-controller-manager` 77, `trust-manager` 58, `cert-manager` 47, `metrics-server` 43, `calico-kube-controllers` 36, `kyverno-admission-controller` 36. Todos terminan con rc 0 (reinicio por sonda).
> - **Ninguna sonda del repositorio fija `timeoutSeconds`**: 68 de las 170 sondas del clúster (sin contar las del proxy de Linkerd) corren con el valor por defecto, 1 segundo, y casi todas con `failureThreshold: 3` y `periodSeconds: 10`: 30 segundos de lentitud bastan para un reinicio.
>
> Lo que se quiere, **solo en los values de kind** de los operadores de plataforma (`platform/operators/*-kind.yaml`):
>
> 1. **Las sondas de vida y de disponibilidad de los operadores que se reiniciaron tienen margen.** Para Argo CD (`repo-server`, `server`, `application-controller`), CloudNativePG (operador), Kyverno (los cuatro controladores), `metrics-server`, cert-manager (`controller`, `webhook`, `cainjector`) y `trust-manager`: `timeoutSeconds` de 5 o más en las dos sondas, y en la de vida un margen total (`periodSeconds × failureThreshold`) de al menos 120 segundos. Usa las claves que cada chart ofrezca; **comprueba cada clave con `helm template`**, no la supongas.
> 2. **Lo que el chart no permita, dilo.** Si un chart no expone la sonda (o un operador se instala sin chart: Calico, KServe), no lo parchees a mano: déjalo escrito en la bitácora y en `CANDIDATAS.md`, con el nombre del componente y lo que haría falta.
> 3. **Una prueba que lo fije.** En `platform/tests`, sobre el `helm template` de cada operador con sus values de kind: toda sonda de vida de los contenedores de la lista tiene `timeoutSeconds >= 5` y `periodSeconds × failureThreshold >= 120`. Debe fallar con los values de `main` (rojo primero) y debe fallar si alguien quita una de las claves.
> 4. **Producción no cambia.** Los values sin sufijo `-kind` rinden idéntico antes y después.

**Fuera:**

- La causa de las rachas (energía, temperatura, cargador): es de la máquina.
- Las sondas de los charts de la aplicación y de `identity-edge` (`case-service`, `case-worker`, los `sentinel` de Valkey con límite de 100m y sonda `exec` de 1 s, Keycloak…): son de otras unidades. Anótalas en `CANDIDATAS.md` si no están.
- Las sondas del proxy de Linkerd y del plano de control de Linkerd.
- Límites y peticiones de CPU.
- Cualquier orden contra el clúster: la sincronización la hace el orquestador con aprobación del usuario.

---

## Archivos de contexto

- `platform/operators/argo-cd-kind.yaml`, `cloudnative-pg-kind.yaml`, `kyverno-kind.yaml`, `metrics-server-kind.yaml`, `cert-manager-kind.yaml` y sus pares sin `-kind`
- `platform/Makefile` (`charts`), `platform/.charts/` (charts descargados), `platform/tests/test_upstream_charts.py` (cómo se rinden los charts en las pruebas)
- `platform/docs/` (el runbook de kind: dónde se cuenta qué hacer si los operadores se reinician)

---

## Criterios de aceptación

- [ ] **CA-1** — Las sondas de los operadores de la lista tienen margen en kind, y una prueba lo fija.
  ```bash
  cd vectra-risk && uv run pytest platform/tests -q -p no:cacheprovider -k "probe_margin"
  ```
  Esperado: pasa. **Rojo primero, pegado en la bitácora:** con los values de `main` falla nombrando cada contenedor. Mutación que debe fallar: quitar el `timeoutSeconds` de un operador. Comprueba con `--collect-only` qué selecciona el filtro.

- [ ] **CA-2** — Producción rinde idéntico.
  Rinde con `helm template` cada operador tocado con sus values **sin** `-kind`, en la base y en tu rama, y compara. Esperado: sin diferencias. Pega la orden y el resultado.

- [ ] **CA-3** — En la bitácora, una tabla por contenedor: sonda, valores antes y después, y la clave del chart usada; y la lista de lo que el chart no deja tocar.

- [ ] **CA-4** — El pytest completo de `platform` pasa como lo corre la CI y sin clúster.
  ```bash
  cd vectra-risk && NOKUBE="$(echo "$PATH" | tr ':' '\n' | grep -v -E '^/snap/bin$' | paste -sd:)" && PATH="$NOKUBE" KUBECONFIG=/nonexistent uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider -q && KUBECONFIG=/nonexistent make -C platform check
  ```
  Esperado: pasan. (Con `platform/.tools` movido FUERA del árbol para el pytest y devuelto antes de `make check`; `make check` una sola vez, al final.)

---

## Plan de pruebas

La de CA-1. **Rojo primero**; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`, ni lecturas.** Corre TODO con `KUBECONFIG=/nonexistent` y con un `PATH` sin `kubectl` real. No uses `~/.kube/config` ni `~/.kube/kind-vectra-readonly`.
- Lo que no puedes medir sin clúster dilo como «no medido». Deja en la bitácora las órdenes exactas para el orquestador: qué Applications sincronizar y qué mirar después (`kubectl get pod … -o jsonpath` de la sonda de cada operador).
- Cambiar una sonda cambia la plantilla del pod: al sincronizar, cada operador tocado **se reinicia una vez**. Dilo en la bitácora, con el orden prudente (Argo CD el último).
- `platform/.tools`: enlázalo a `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools`; `platform/.charts`: cópialo de `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u01-t13/vectra-risk/platform/.charts`. No van en el commit.
- La máquina se satura cuando se corren pruebas con el clúster arriba: una sola corrida pesada a la vez.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u01t19-`, y borra tus copias al terminar.
- `CANDIDATAS.md`: solo añadir al final. Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
