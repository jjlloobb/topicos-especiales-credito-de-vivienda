# Los tres agentes del loop

**Módulo 6 · Trabajo de proyecto final**

> Tres contratos listos para copiar. El orquestador despacha, el codificador implementa, el
> revisor juzga, y **un humano fusiona**.

| Archivo | Papel | Modelo | Herramientas |
|---|---|---|---|
| [`orquestador.md`](./orquestador.md) | Despacha, arbitra, entrega | `fable` | la sesión principal |
| [`revisor.md`](./revisor.md) | Juzga. Corre los comandos él mismo | `opus` | `Bash, Read, Grep, Glob` |
| [`codificador.md`](./codificador.md) | Implementa una tarea en su worktree | `sonnet` | `Bash, Read, Edit, Write, Grep, Glob` |
| [`plantilla-tarea.md`](./plantilla-tarea.md) | El contrato de entrada del codificador | — | — |

---

## Por qué el revisor es más capaz que el codificador

Es la decisión de diseño que más sorprende, porque la intuición dice lo contrario: poner el
mejor modelo a escribir. Dos razones, y la segunda es la de fondo.

**La económica.** Revisar es una tarea **pesada en entrada y ligera en salida**: el revisor lee
la especificación y el diff, corre comandos, y emite un veredicto de veinte líneas. Generar
código es lo contrario: **ligero en entrada y pesado en salida**. El precio de un modelo se paga
sobre todo por lo que produce, así que poner el modelo caro a revisar cuesta mucho menos de lo
que parece, y poner el modelo caro a generar cuesta mucho más.

**La que de verdad manda.** Un error del codificador lo atrapa el revisor. **Un error del
revisor se va a producción.** El juicio es el punto donde equivocarse es más caro, así que ahí
va la capacidad. Y el orquestador está por encima porque su error es el más caro de todos:
despachar trabajo mal especificado multiplica el desperdicio por cada codificador de la ola.

**Regla práctica:** si tienes que recortar presupuesto, recorta en el codificador y deja el
revisor donde está. Un codificador barato con un revisor exigente converge, aunque cueste
rondas. Un codificador caro con un revisor complaciente produce código que nadie verificó.

---

## Instalación en Claude Code

Los dos subagentes van en `.claude/agents/` de tu proyecto:

```bash
cd ~/mi-producto
mkdir -p .claude/agents
cp /ruta/a/topicos-especiales/modulo6/agentes/codificador.md .claude/agents/
cp /ruta/a/topicos-especiales/modulo6/agentes/revisor.md     .claude/agents/
```

El orquestador es **la sesión principal**, no un subagente. Ponle el modelo más capaz con
`/model` y dale su contrato al abrir la sesión:

```text
Lee modulo6/agentes/orquestador.md y actúa según ese contrato. Mi archivo de unidades y tareas
está en unidades-y-tareas.md.
```

Comprueba que los dos subagentes quedaron registrados preguntándole a la sesión qué subagentes
tiene disponibles. Si no los ve, revisa que los archivos estén en `.claude/agents/` y que el
frontmatter tenga `name` y `description`, que son los dos campos obligatorios.

### Lo que hace cada campo del frontmatter

| Campo | Qué hace |
|---|---|
| `name` | **Obligatorio.** El identificador con el que se despacha |
| `description` | **Obligatorio.** Lo que decide si se delega automáticamente |
| `tools` | Lista blanca. **Si se omite, el subagente hereda todas las herramientas** |
| `model` | `sonnet`, `opus`, `haiku` o `fable`; o un identificador completo como `claude-opus-5`; o `inherit` |
| `isolation` | Con el valor `worktree`, el subagente corre en un worktree temporal de git |

Dos de esos campos están puestos a propósito:

**El revisor no tiene `Write` ni `Edit`.** No es una recomendación de que no edite: es que **no
puede**. La restricción vive en la herramienta, no en su buena voluntad. Tampoco tiene `Agent`,
así que no puede despachar más agentes; para dejar a un subagente en solo lectura se omite
`Agent` de su lista o se añade a `disallowedTools`.

**El codificador sí tiene escritura, pero acotada por worktree.** Puedes dejar que Claude Code
le dé uno automáticamente añadiendo `isolation: worktree` a su frontmatter, que crea una copia
aislada del repositorio y la limpia sola si el subagente no cambió nada. O puedes crearlos tú a
mano, que es lo que explica la guía del módulo y lo que funciona en cualquier herramienta.

---

## Si no usas Claude Code

Los tres contratos son Markdown, así que el diseño es portable. Lo que cambia es **cómo se
despacha**, no el contrato.

| Lo que necesitas | En Claude Code | En cualquier otra herramienta |
|---|---|---|
| Tres papeles con modelos distintos | tres definiciones con su campo `model` | **tres sesiones separadas**, una por papel, cada una con su modelo y con su contrato pegado al abrir |
| Aislamiento del codificador | `isolation: worktree` o worktrees a mano | worktrees de git a mano, que es estándar |
| Paso de contexto | rutas en el despacho | rutas en el mensaje; los archivos están en el disco de todas formas |
| Persistir el informe de la ronda | el orquestador lo escribe | tú copias el informe del revisor al archivo de la ronda |

La versión manual es más lenta y más incómoda, pero **enseña lo mismo y no se rompe**: los
papeles siguen sellados porque cada sesión solo tiene su contrato, el revisor sigue sin poder
editar porque está en otra sesión sin tu repositorio abierto para escritura, y el humano sigue
fusionando.

Lo que **no** debes hacer es simular los tres papeles en una sola conversación. Un modelo que
escribe el código y luego se pone el sombrero de revisor no está revisando: está justificando.

---

## Verificado el 10 de septiembre de 2026

Los campos del frontmatter, los valores válidos de `model` (incluido `fable`), el
comportamiento de `tools` cuando se omite, cómo dejar a un subagente sin capacidad de despachar
otros, y el campo `isolation: worktree`, se comprobaron contra la documentación oficial de
Claude Code: <https://code.claude.com/docs/en/sub-agents>

Los nombres de modelo cambian. Antes de afirmar que un valor es válido, **míralo en esa página**,
no en esta.

---

_Creado con ❤️ por Luis Felipe Ariza Vesga._
