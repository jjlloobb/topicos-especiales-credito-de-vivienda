# U02-T23 — Keycloak con una réplica mínima solo en kind

**Unidad:** U2 — `identity-edge`
**Historias que implementa:** ninguna nueva; recorte de memoria de kind para la máquina de la demo (decisión del usuario del 2026-11-14).
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> En kind, el HPA de Keycloak pasa a `minReplicas: 1` (hoy 2, en `identity-edge/keycloak/values/common.yaml:38`), para ahorrar ≈ 1,02 GiB y 0,6 CPU pedidos: con dos réplicas, el pico de la demo D2 no deja margen en una máquina de 15 GiB. Staging y prod siguen con mínimo 2.
>
> La política Rego de U2 lo impide hoy: `identity-edge/keycloak/policy/keycloak.rego` exige `minReplicas == 2` (reglas `hpa_problem`, líneas ≈ 128-131, y `expected_hpa_spec`) y fija las réplicas del StatefulSet, sin distinguir entorno; `identity-edge/tests/unit/test_keycloak_deploy.py` (mutaciones «minimo 1» y «1 replica») espera que falle. Decisión del usuario, opción (a): **la política se vuelve sensible al entorno**: mínimo 1 **solo** en kind, 2 en staging y prod, sin relajar nada más. La política debe reconocer kind por algo que no se pueda poner por descuido en staging o prod (el codificador de U01-T11 sugirió evaluar por directorio de entorno con `--combine`, o reconocer el StatefulSet de kind, que es el que lleva el administrador de arranque): elige el mecanismo, justifícalo y pruébalo.

**Antes de cambiar nada, comprueba y, si algo choca, PARA y devuélvelo como pregunta:**

- Qué más depende de 2 réplicas en kind: el PDB (`minAvailable`), la caché distribuida (JGroups), `topologySpreadConstraints`, las pruebas e2e e integración de U2, las alertas (`identity-rules`) que disparen con menos de 2 réplicas, y la política de Kyverno `require-hpa-bounds` (U01-T11 comprobó que solo mira `Deployment`; confírmalo).
- Si `spec.replicas` del StatefulSet debe cambiar también en kind y qué exige la política ahí.

**Fuera:**

- `platform/` (incluidos `BUDGET_GIB` y `test_kind_profile.py`: los ajusta el orquestador después, porque U01-T11 los está cambiando en otra rama).
- Cualquier otro recurso o límite de Keycloak, el gateway, Valkey, el realm.
- Staging y prod: su render no cambia ni un byte.
- Relajar la política para todos los entornos (opción descartada).

---

## Archivos de contexto

- `identity-edge/keycloak/values/` (`common.yaml`, `kind.yaml`, staging, prod), `identity-edge/keycloak/rendered/`, `identity-edge/keycloak/policy/keycloak.rego`
- `identity-edge/tests/unit/test_keycloak_deploy.py`, `identity-edge/Makefile` (`render-keycloak`, `policy-keycloak`, `policy-keycloak-u1`, `check-keycloak-rendered`)
- `identity-edge/rules/` o donde vivan las alertas de identidad, `platform/policies/kyverno/require-hpa-bounds.yaml` (solo lectura)
- `aidlc-docs/construction/identity-edge/` (el diseño: por qué 2 réplicas), `DECISIONES-LOOP.md` §7, §9 y §10 (excepciones de kind anteriores), `CANDIDATAS.md`

---

## Criterios de aceptación

- [ ] **CA-1** — El render de kind trae `minReplicas: 1`; los de staging y prod no cambian.
  ```bash
  cd vectra-risk && make -C identity-edge render-keycloak && git diff --stat origin/main -- identity-edge/keycloak/rendered && grep -n 'minReplicas' identity-edge/keycloak/rendered/*/keycloak.yaml
  ```
  Esperado: solo cambia `rendered/kind/`; kind 1, staging 2, prod 2.

- [ ] **CA-2** — La política acepta mínimo 1 en kind y lo rechaza en staging y prod; acepta 2 en staging y prod; rechaza 0 y 3 en todos.
  ```bash
  cd vectra-risk && make -C identity-edge policy-keycloak policy-keycloak-u1 && uv run pytest identity-edge/tests/unit/test_keycloak_deploy.py -q -p no:cacheprovider
  ```
  Esperado: rc 0. La mutación «minimo 1» sigue fallando en staging y prod, y hay mutaciones nuevas: mínimo 1 con el render de staging o de prod falla; mínimo 2 en kind, decide y di si se acepta; un render de staging o prod «disfrazado» de kind con la señal que elegiste no pasa por descuido (explica por qué).

- [ ] **CA-3** — Lo que dependía de 2 réplicas en kind sigue coherente (PDB, alertas, pruebas), con evidencia en la bitácora de la comprobación previa.
  ```bash
  cd vectra-risk && make -C identity-edge check-keycloak-rendered rules
  ```
  Esperado: rc 0.

- [ ] **CA-4** — `identity-edge` sigue en verde.
  ```bash
  cd vectra-risk && make -C identity-edge check
  ```
  Esperado: rc 0. Si `check` levanta contenedores, una sola vez y al final; si la máquina cargada hace fallar una prueba de integración ajena al cambio, corre aparte lo que no llegó a correr y dilo.

---

## Plan de pruebas

- Mutaciones por entorno de la política (CA-2).
- Prueba de que el render de staging y prod no cambia (CA-1).

**Rojo primero** en cada una; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`** (Keycloak aún no está instalado allí). La máquina tiene poca memoria y hay otros agentes trabajando.
- `CANDIDATAS.md:88,167`: `charts.sh` no baja el chart `keycloakx`; si `make render-keycloak` lo necesita y no está, cópialo del árbol principal (`platform/.charts`, no versionado) o bájalo con la versión fijada por el repositorio, y dilo. No descargues imágenes de contenedor.
- Es una excepción anotada a «kind igual a staging», como las de memoria de U8, U10 y U11: la anota el orquestador en `DECISIONES-LOOP.md`; tú no lo toques.
- Scratchpad compartido: prefijo `u02t23-`. Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
