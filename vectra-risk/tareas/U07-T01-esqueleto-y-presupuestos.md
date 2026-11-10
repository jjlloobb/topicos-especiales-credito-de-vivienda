# U07-T01 — Esqueleto y presupuestos de `scoring-explainability`

**Unidad:** U7 `scoring-explainability`
**Historias que implementa:** ninguna directamente. Fija la estructura, los contratos de import y los presupuestos de tiempo que usan US-103, US-104, US-105, US-109, US-111 y US-113 en las tareas siguientes.
**Depende de:** U0 y U1 en `main` (`vectra_contracts`, `vectra_common.deps`, `vectra_common.deadline`, `vectra_common.ops_server`). No depende de U3, U4, U5 ni U6 en esta tarea.
**Se despacha** ya: no espera a ninguna tarea de U7. Puede correr en paralelo con tareas de otras unidades (RL-5).
**Rama:** `tarea/U07-T01`, desde `origin/main`.

Bloque A del plan de U7 (`aidlc-docs/construction/plans/scoring-explainability-code-generation-plan.md`), tarea «A (1–2)» de `demo-recorte-funcional.md` §8. La enmienda rige donde difiera del alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 1 Esqueleto | **E** | Completo | Enmienda §3 U7 (Pasos 1–5) |
| 2 Presupuestos como constantes | **E** | Completo | Enmienda §3 U7 (Pasos 1–5) |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda.

---

## Alcance

**Dentro:** los Pasos 1 y 2 del plan, con su texto y su aceptación, sin recortes. Léelos allí. Precisiones:

### Paso 1 — Esqueleto (E)

- `scoring-explainability/` con la estructura de destino de §1 del plan: `scoring/src/scoring/`, `explainability/src/explainability/` (con `templates/`), `chart/`, `policies/conftest/`, `observability/`, y `tests/{unit,property,integration,doubles,fixtures,load}/`. Los módulos de §1 se crean vacíos o con su firma; su lógica es de U07-T02 y U07-T03.
- `pyproject.toml` con **dos miembros del workspace** (scoring y explainability), que dependen de `vectra_contracts` y `vectra_common`. Agrégalos al `pyproject.toml` raíz y regenera `uv.lock`.
- `scoring-explainability/.importlinter` con los cuatro contratos del plan:
  - `factuality` no importa `narrative` (BR-U7-11);
  - ningún módulo importa `httpx` fuera de `vectra_common.deps` (P-U0-07);
  - ninguno importa librerías de circuit breaking (NFR-U7-43) ni clientes de LLM (NFR-U7-32);
  - ningún módulo contiene la URL ni un cliente del core bancario (BR-U7-02).
- El cuarto no se expresa con import-linter: lo cubre `tests/unit/test_no_core_client.py`, que recorre las fuentes de U7 y falla si aparece un host o nombre del core. La lista sale de `platform/network/forbidden.yaml` (X01: `core-banking-mock`) y de `flows.yaml`; no la copies a mano.
- `scoring-explainability/Makefile` con `check` (lint, mypy estricto, import-linter y pruebas), con el formato de `governance/Makefile` y `governance/.importlinter`.
- Diseño: BR-U7-02, 11; NFR-U7-30, 32, 43; P-U7-07.

### Paso 2 — Presupuestos como constantes (E)

- `scoring/config.py` y `explainability/config.py`, con constantes tipadas. Todos los valores del plan:
  - presupuesto previo al registro: 700 ms;
  - timeouts por llamada de NFR-U7-10: `serving-config` 500 ms, `:predict` 300 ms, explainability 800 ms, `:explain` 500 ms, diccionario 500 ms, registro 2,5 s;
  - append: 2 intentos de 2,5 s, con jitter de 0 a 100 ms;
  - `fail_closed`: 250 ms;
  - tope propio de explainability: 700 ms, más 50 ms de margen;
  - tamaños de pool de P-U7-04: `:predict` 20, explainability 20, registro 10, `serving-config` 5; en explainability, `:explain` 20, diccionario 5, registro 5;
  - umbrales del circuit breaker de NFR-U7-11 (≥ 50 % en 20 llamadas dentro de 30 s; semiabierto a los 10 s), escritos como `BreakerConfig` de `vectra_common.deps`;
  - caché de `serving-config` ≤ 5 s y LRU del diccionario de 4 versiones.
- Ningún presupuesto se lee de variables de entorno (INF-U7-04).
- Diseño: INF-U7-04; P-U7-01, 02, 04, 05; NFR-U7-10, 11.

### Plan

Marca `[x]` los Pasos 1 y 2 con `(U07-T01)`.

**Fuera** (rechazar aunque se vea roto o tentador):

- La lógica de `policy`, `narrative`, `factuality` y `applicant` (U07-T02; `applicant` está en D).
- Clientes, `orchestrator`, endpoints y `create_app` (U07-T03).
- Chart, Dockerfiles, Application y cierre (U07-T04).
- Workflows de CI propios (T4).
- Cambios en U0 o U1. Si falta algo allí (por ejemplo, que `BreakerConfig` no acepte los cuatro parámetros de NFR-U7-11), **detente y repórtalo**.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/scoring-explainability-code-generation-plan.md`: §1, Pasos 1 y 2.
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` §3 U7 y §8; `demo-kind-alcance.md` §2 y §6.
- `aidlc-docs/construction/scoring-explainability/`: `functional-design/business-rules.md` (BR-U7-02, 11), `nfr-requirements/nfr-requirements.md` (NFR-U7-10, 11, 30, 32, 43), `nfr-design/nfr-design-patterns.md` (P-U7-01, 02, 04, 05, 07) e `infrastructure-design/infrastructure-design.md` (INF-U7-04).
- `contracts/python/vectra_common/src/vectra_common/deps.py` (`BreakerConfig`, `DependencyClient`) y `deadline.py`.
- `governance/Makefile`, `governance/.importlinter` y `governance/pyproject.toml` (formato de referencia).
- `platform/network/forbidden.yaml` (X01, X02) y `platform/network/flows.yaml`.

---

## Criterios de aceptación

Desde `vectra-risk/`. Ninguno toca el clúster.

- [ ] **CA-1** — Paso 1: aceptación del plan.
  ```bash
  uv sync --frozen && uv run lint-imports --config scoring-explainability/.importlinter && make -C scoring-explainability check
  ```
  Esperado: código 0. Cada uno de los tres contratos de import-linter falla con una mutación (rojo primero en la bitácora).

- [ ] **CA-2** — Paso 1: sin cliente del core.
  ```bash
  uv run pytest scoring-explainability/tests/unit/test_no_core_client.py -v
  ```
  Esperado: código 0. La prueba lee los nombres de X01 de `platform/network/forbidden.yaml` y falla si un archivo de `scoring-explainability/` (fuentes, plantillas o chart) contiene uno.

- [ ] **CA-3** — Paso 2: aceptación del plan.
  ```bash
  uv run pytest scoring-explainability/tests/unit/test_config.py -v
  ```
  Esperado: código 0. Pasan, como mínimo:
  - `700 + 250 + 50 ≤ 1000 ms`;
  - `20 s > 0,7 + 2 × 2,5 + 0,1 s`;
  - ningún presupuesto se lee de variables de entorno (la prueba busca `os.environ` y `getenv` en los dos `config.py`);
  - cada valor de NFR-U7-10, P-U7-04 y NFR-U7-11 tiene su constante con el valor del diseño.

- [ ] **CA-4** — `check` de la unidad y de U1 (RL-4).
  ```bash
  make -C scoring-explainability check && make -C platform check
  ```
  Esperado: código 0 en los dos. Si `make -C platform check` falla en `check-tools` porque `platform/.tools` no existe en el worktree, regístralo y usa las herramientas del checkout principal tras comparar la versión con `tools.env`.

- [ ] **CA-5** — Estado del plan.
  ```bash
  git diff origin/main -- aidlc-docs/construction/plans/scoring-explainability-code-generation-plan.md | grep -E "^\+- \[.\] \*\*Paso [12] "
  ```
  Esperado: Pasos 1 y 2 en `[x] (U07-T01)`. Ningún otro cambio en el texto del plan.

---

## Plan de pruebas

**Rojo primero**, con cada par falla-pasa en `bitacoras/U07-T01.md`:
- `factuality` importa `narrative` → `lint-imports` falla;
- un módulo importa `httpx` directamente → falla;
- un módulo importa `pybreaker` (o un cliente de LLM, como `openai`) → falla;
- una cadena `core-banking-mock` en un módulo → `test_no_core_client.py` falla;
- un presupuesto leído con `os.environ` → `test_config.py` falla;
- `fail_closed` a 400 ms → la suma pasa de 1000 ms y falla.

---

## Notas

- Archivos nuevos: todo `scoring-explainability/`. Se modifican en su sitio: el `pyproject.toml` raíz, `uv.lock`, el plan y `CANDIDATAS.md`.
- **Otros codificadores en paralelo:** el `pyproject.toml` raíz y `uv.lock` los pueden tocar otras tareas. Si `origin/main` avanza, integra y regenera `uv.lock`. No toques directorios de otras unidades.
- Los nombres de paquete (`scoring`, `explainability`) son los del plan. Si chocan con otro paquete del workspace, **detente y repórtalo** antes de renombrar.
- **Bitácora:** `bitacoras/U07-T01.md`.
