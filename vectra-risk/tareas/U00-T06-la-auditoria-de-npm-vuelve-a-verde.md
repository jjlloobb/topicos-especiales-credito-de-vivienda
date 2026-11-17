# U00-T06 — La auditoría de dependencias de npm vuelve a verde

**Unidad:** U0 — `contracts` (dueña del `package.json` y del `package-lock.json` de la raíz y del workflow que corre la auditoría)
**Historias que implementa:** ninguna nueva; desbloquea la CI de todos los PR.
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> El 2026-11-17 el check `checks` (`.github/workflows/contracts.yml`, paso «Auditoria de dependencias», `npm audit --audit-level=high`) empezó a fallar en el PR #203, que no toca ningún archivo de npm. La causa es un aviso nuevo:
>
> ```
> picomatch  *
> Severity: high
> picomatch vulnerable to ReDoS through single-branch repeated extglobs - https://github.com/advisories/GHSA-fc5q-39xc-vjpf
> fix available via `npm audit fix --force`
> …
> 11 high severity vulnerabilities
> ```
>
> Las once son `picomatch` (en el lockfile, 4.0.7) y lo que cuelga de él: `fdir`, `tinyglobby`, `vite`, `vitest`, `@vitest/coverage-v8`, `@vitejs/plugin-react`, `size-limit`, `@size-limit/file`, `@typescript-eslint/typescript-estree` y `@typescript-eslint/parser`. Son herramientas de desarrollo y de construcción de los dos workspaces (`contracts/ts` y `console/spa`). El rango afectado que imprime la auditoría es `*`, y el arreglo que propone es `--force`, es decir, cambios de versión mayor. El mismo rojo saldrá en cada PR hasta que se arregle. No está comprobado en `main`: la última corrida allí es anterior al aviso.
>
> Lo que se quiere: que `npm audit --audit-level=high` vuelva a terminar en 0 **sin apagar la auditoría y sin esconder un riesgo real**.
>
> 1. **Diagnóstico primero, escrito en la bitácora.** Con `npm audit --json`: el rango afectado exacto, si existe una versión de `picomatch` corregida y cuál, por qué caminos entra `picomatch` en el árbol, y si alguno de esos caminos llega a código que se ejecuta en producción (la SPA servida, el BFF) o solo a herramientas de desarrollo y de CI. Di si la entrada que dispara el ReDoS (un patrón glob) puede venir de un usuario en algún uso del repositorio.
> 2. **El arreglo, por este orden de preferencia:**
>    - (a) **Si hay una versión corregida de `picomatch` compatible:** fíjala con `overrides` en el `package.json` de la raíz (ya hay uno para `minimatch`: el mismo patrón) y regenera el `package-lock.json`. Versiones exactas, sin `^` ni `~`.
>    - (b) **Si el arreglo exige subir versiones de las herramientas** (`vite`, `vitest`, `size-limit`…): súbelas a versiones exactas y arregla lo que rompan. No aceptes una **bajada** de versión mayor de `npm audit fix --force` sin justificarla.
>    - (c) **Si no existe versión corregida:** no hay arreglo posible hoy. Entonces, y solo entonces, una excepción **acotada a ese aviso** (`GHSA-fc5q-39xc-vjpf`), con fecha de caducidad y motivo escritos junto a ella, de modo que cualquier otro aviso alto siga poniendo el check en rojo y que la excepción caduque sola. `npm audit` no tiene lista de excepciones: si hace falta, un guion pequeño del repositorio que lea `npm audit --json`, con su prueba (un aviso distinto → rojo; el exceptuado y vigente → verde; el exceptuado y caducado → rojo). Di en tu informe por qué (a) y (b) no eran posibles.
> 3. **Nada se rompe.** Los dos workspaces siguen pasando sus comprobaciones, el tamaño del bundle de la SPA sigue dentro de su límite y `uv`/`pip-audit` no cambian.

**Fuera:**

- Quitar el paso de auditoría, bajarle el nivel (`--audit-level=critical`), o ponerle `continue-on-error`.
- `--omit=dev` como arreglo: las herramientas de construcción son parte de la cadena de suministro de la imagen de la SPA.
- Cambios de comportamiento en `contracts/ts` o en `console/spa` que no exija la subida de versiones.
- Las dependencias de Python.
- Cualquier orden contra el clúster.

---

## Archivos de contexto

- `.github/workflows/contracts.yml` (paso «Auditoria de dependencias», y los pasos de `npm` anteriores), `.github/workflows/supply-chain.yml`
- `vectra-risk/package.json` (`workspaces`, `overrides`), `vectra-risk/package-lock.json`
- `vectra-risk/contracts/ts/package.json`, `vectra-risk/console/spa/package.json`, `vectra-risk/console/spa/vite.config.ts`, `vectra-risk/console/Makefile`, `vectra-risk/contracts/Makefile`
- `vectra-risk/tareas/` y `vectra-risk/bitacoras/` de U10 (por qué están fijadas las versiones de `vite`, `vitest` y `size-limit`)

---

## Criterios de aceptación

- [ ] **CA-1** — La auditoría termina en 0 con el lockfile del repositorio.
  ```bash
  cd vectra-risk && npm ci && npm audit --audit-level=high
  ```
  Esperado: rc 0 (o, en el caso (c), rc 0 del guion que la sustituye en el workflow, y `npm audit` muestra solo el aviso exceptuado). Pega la salida.

- [ ] **CA-2** — El workflow corre exactamente la orden que pasa, y el lockfile es coherente.
  ```bash
  cd vectra-risk && grep -n -A4 'Auditoria de dependencias' ../.github/workflows/contracts.yml && npm ci --dry-run >/dev/null && git diff --exit-code package-lock.json
  ```
  Esperado: el paso sigue con `--audit-level=high` (o llama al guion del caso (c)); `npm ci` no modifica el lockfile.

- [ ] **CA-3** — `contracts/ts` sigue en verde.
  ```bash
  cd vectra-risk && npm run -w contracts/ts typecheck && npm run -w contracts/ts lint && npm run -w contracts/ts test
  ```
  Esperado: rc 0 en los tres.

- [ ] **CA-4** — `console/spa` sigue en verde, incluido el tamaño del bundle.
  ```bash
  cd vectra-risk && make -C console lint-spa test-spa build-spa
  ```
  Esperado: rc 0 en los tres (lint y typecheck, vitest con cobertura, build y `size-limit`). `e2e-spa` (navegadores) queda fuera salvo que la subida toque Playwright; si la tocas, córrelo y dilo.

- [ ] **CA-5** — Solo en el caso (c): la excepción es de un solo aviso y caduca.
  ```bash
  cd vectra-risk && uv run pytest contracts/tests -q -p no:cacheprovider -k "npm_audit"
  ```
  Esperado: pasa, con los tres casos del punto 2 (c). En los casos (a) y (b), di «no aplica».

- [ ] **CA-6** — La unidad sigue en verde.
  ```bash
  cd vectra-risk && make -C contracts check
  ```
  Esperado: rc 0. Una sola vez, al final.

---

## Plan de pruebas

CA-1 es la prueba: rojo antes (pega la salida de `npm audit` sobre la base), verde después.

---

## Notas

- **Nada contra el clúster `kind-vectra`, ni lecturas.** Corre todo con `KUBECONFIG=/nonexistent` y con un `PATH` sin `/snap/bin`.
- `npm audit` y `npm ci` hablan con el registro público de npm: es lo mismo que hace la CI. No envíes nada más a ningún servicio externo.
- Versiones exactas en `package.json`, como todo el repositorio. El `package-lock.json` va en el commit.
- Si la subida cambia el `Dockerfile` de la SPA o la imagen, dilo: el digest de kind habría que reconstruirlo y eso lo hace el orquestador.
- La máquina tiene poca memoria y un clúster de kind completo corriendo: una sola corrida pesada a la vez.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u00t06-`, y borra tus copias al terminar. `node_modules` no va en el commit.
- `CANDIDATAS.md`: solo añadir al final. Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
