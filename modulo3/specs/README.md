# specs/

Esta carpeta es el **output** del pipeline de co-creación. Está vacía hasta que ejecutes
los prompts de [`../prompts-para-especificacion.md`](../prompts-para-especificacion.md).

| Archivo | Origen | Cuándo |
|---|---|---|
| `prd.md` | Prompt 1 — PRD | **Sábado 15 de agosto de 2026**, junto con el PVB |
| `arquitectura.md` | Prompt 2 — Arquitectura técnica | Cuando tengas Kubernetes y CKA encima |
| `backlog.md` | Prompt 3 — Backlog de ingeniería | Antes de empezar a construir en serio |

---

## Tu tarea

Producir `specs/prd.md`:

1. **Reemplaza los archivos de `../docs/`** por los de tu propio producto. Los que están
   ahí son el caso de referencia (Timonel).
2. **Revisa la evidencia de tus docs** antes de empezar: cada cifra con fuente, tus
   proyecciones marcadas **[INTERNO]**, lo no verificado marcado **[VERIFICAR]**.
3. **Abre una conversación nueva** con tu LLM y pega el **Prompt 1**.
4. **Adjunta todos** los archivos de `../docs/`.
5. **Co-crea segmento por segmento.** No avances sin aprobar el anterior.
6. **Consolida el PRD final aquí**, como `specs/prd.md`.

---

## Qué hace bueno a un PRD en este curso

- **Toda cifra tiene fuente**, y las proyecciones internas están marcadas como tales.
- **El conflicto entre la validación y la crítica quedó resuelto explícitamente**, no
  disuelto a favor del optimismo.
- **El alcance del MVP es construible** en lo que queda del semestre y desplegable en
  Kubernetes en el módulo 8.
- **Si hay un agente que actúa sobre infraestructura, su límite de autonomía es
  verificable** — no una promesa, algo que se comprueba con un comando.
- **Los riesgos incluyen los que van en contra del producto**, no solo los cómodos.

> **No borres este archivo.** Explica qué va en esta carpeta a quien clone el repositorio.
