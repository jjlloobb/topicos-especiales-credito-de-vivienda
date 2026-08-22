# Auditoría del reporte `deep-research-oci-lxc-lxd.md`

**Qué es este archivo.** El reporte de deep research que lo acompaña es un **insumo**,
no un resultado. Este documento verifica sus afirmaciones contra fuentes primarias
(vía `WebFetch` directo a cada URL citada, y un `WebSearch` de contraste para la fecha
más reciente) antes de que cualquiera de ellas entre a la sección "Para profundizar" de
`laboratorio-virtualizacion-contenedores.md`.

**Regla que aplica aquí:** ningún dato de este reporte se cita en el laboratorio sin
aparecer abajo con veredicto SOPORTADO. Un reporte fluido con URLs reales no es
evidencia: los reportes citan fuentes auténticas y aun así las leen mal, o citan la URL
equivocada para una afirmación correcta.

**Veredicto general:** este reporte es sustancialmente más sólido que el precedente de
este módulo (`deep-research-ai-k8s-cncf.md`, que tuvo autocitación y cifras con
transferencia de dominio inventada — ver su propio `.AUDIT.md`). En particular, la
pregunta más delicada que se le hizo — la posible bifurcación de LXD por un cambio de
licencia de Canonical — resultó ser **real, bien documentada y correctamente
investigada**, incluida la instrucción explícita de no suavizarla si era incómoda. Aun
así, aparecieron: una afirmación fabricada presentada como política oficial, varias URLs
de cita rotas o equivocadas para afirmaciones que sí son correctas, y dos casos de
paráfrasis vendida como cita textual.

---

## Hallazgo crítico — Sección 4, cadencia de reconstrucción "cada 3-4 semanas": FABRICADO

**Severidad: alta. No usar esta cifra en ninguna forma.**

El reporte afirma (sección 4, "Política Oficial de Reconstrucción"):

> "Las imágenes base de distribuciones Linux... se reconstruyen y sincronizan con los
> repositorios de seguridad de las distribuciones en una cadencia habitual de
> aproximadamente tres a cuatro semanas (frecuencia mensual)"

citando como única fuente `github.com/docker-library/official-images/issues/14813`.

**Verificación directa de ese issue:** es un *feature request* titulado "Release
schedule for Debian security upgrades" que se **queja** de que las imágenes llevan
"several weeks out of date" — da como ejemplo `node:slim` con 17 días de antigüedad como
un problema, no como una política cumplida. El issue **no contiene ninguna cadencia
declarada, ningún proceso de emergencia para CVEs críticos, ni ningún mecanismo de
reconstrucción en cascada**. El reporte convirtió un hilo de queja de un usuario en una
supuesta política oficial de Docker. Es el mismo patrón de falla que el reporte anterior
de este módulo (afirmación plausible, cita real, lectura equivocada de la fuente).

**Veredicto: NO USAR.** Si se quiere hablar de cadencia de parches de Docker Official
Images en el laboratorio, hace falta una fuente que la declare explícitamente (no se
encontró una en esta auditoría) — o decir honestamente que no hay una política pública
verificable de intervalo fijo.

---

## Hallazgo — Sección 5, ejemplos de herramientas "de superficie de ataque" atribuidos a NIST SP 800-190: PARAFRASEADO, no citado

**Severidad: media.**

El reporte afirma que NIST SP 800-190 identifica específicamente `bash`/`sh`, `apt`/
`yum`, compiladores y herramientas de depuración de red como ejemplos de utilidades que
expanden la superficie de ataque. Verificación directa del PDF oficial
(csrc.nist.gov/pubs/sp/800/190/final): las secciones 3.5.1–3.5.2 y 4.1.2 sí discuten
minimización de superficie de ataque y recomiendan imágenes base minimalistas (cita
textual: *"selection of base layers from minimalistic technologies like Alpine
Linux... to reduce attack surface"*), pero **el documento nunca enumera esas
herramientas específicas**. La recomendación general (usar imágenes mínimas) es real y
está correctamente atribuida; los ejemplos concretos no están en el documento y no deben
presentarse como cita de NIST.

**Veredicto: usar solo la afirmación general** ("NIST SP 800-190 recomienda imágenes
base minimalistas para reducir superficie de ataque"), sin los ejemplos de herramientas
específicas.

---

## Hallazgo — Sección 1, conteo de miembros fundadores de OCI: 20 vs 21

**Severidad: baja.**

El reporte dice "veinte organizaciones". La página oficial citada
(opencontainers.org/posts/announcements/2015-06-20-...) lista **21** organizaciones —
los 20 nombres que el reporte enumera son todos reales y están bien escritos (ningún
nombre inventado), pero falta uno respecto del total real de la página.

**Veredicto: si se cita la cifra, decir "más de 20" o verificar el conteo exacto de
nuevo antes de publicar un número preciso** — no repetir "veinte" como si fuera exacto.

---

## Hallazgo — URLs de cita rotas o equivocadas (afirmación correcta, cita mal apuntada)

**Severidad: baja-media — no invalida el dato, pero las URLs no deben copiarse tal cual
al laboratorio.**

| Afirmación (correcta) | URL citada por el reporte | Problema |
|---|---|---|
| runtime-spec/image-spec v1.0, julio 2017 | `.../2017-07-17-oci-releases-v1-0-of-container-standards/` | 404 — URL real: `.../2017-07-17-open-container-initiative-oci-releases-v1-0-of-container-standards/` |
| distribution-spec v1.0, mayo 2021 | `.../2021-05-04-oci-distribution-specification-v1-0/` | 404 — URL real: `.../2021-05-04-oci-dist-spec-v1/` |
| Docker Hub bloqueó acceso de LXD a su servidor de imágenes desde inicios de 2024 | `linuxcontainers.org/lxd/` | Esa página no dice esto — la fuente real es el hilo `discuss.linuxcontainers.org/t/important-notice-for-lxd-users-image-server/18479` (16 dic 2023, por stgraber): acceso restringido desde el 1 ene 2024, corte completo el 1 may 2024. El dato es correcto, la cita apunta al lugar equivocado. |
| Programa "Docker Official Images", namespace `library/` | `docs.docker.com/docker-hub/image-library/trusted-content/` | Esa página no detalla el mecanismo; la fuente que sí lo hace es el README de `github.com/docker-library/official-images/` |

**Veredicto: dato correcto en los cuatro casos — corregir la URL antes de usarla en el
laboratorio.**

---

## Hallazgo — Sección 2, atribución de LXC a Daniel Lezcano y Serge Hallyn en IBM: sin soporte en las fuentes citadas

**Severidad: media.**

El reporte cita `linuxcontainers.org/lxc/news/` y `linuxcontainers.org/incus/
announcement/` para sostener que LXC (2008) fue liderado por Lezcano y Hallyn, entonces
en IBM. Verificación directa: ninguna de las dos páginas menciona a Lezcano, a Hallyn
como fundador de LXC, ni a IBM. La página de LXC news no cubre historia de origen; la de
Incus solo menciona a Hallyn como mantenedor inicial de Incus en 2023, sin relación con
LXC en 2008. El año 2008 sí aparece confirmado en un post de Medium (fuente débil, no
oficial, pero coincide con la fecha comúnmente citada).

**Veredicto: la fecha 2008 se puede usar (con una fuente mejor si se consigue); la
atribución específica a Lezcano/Hallyn/IBM queda SIN VERIFICAR — no presentarla como
hecho confirmado en el laboratorio.**

---

## Confirmado sin reservas — lo que SÍ se puede usar

### La bifurcación LXD → Incus (sección 3 completa)

Esta era la pregunta más delicada del prompt — se le pidió explícitamente a Gemini que
no suavizara una historia de gobernanza incómoda si la encontraba. La verificación
directa confirma que **todo el relato es real y está bien sourceado**:

- **4 de julio de 2023:** Canonical retira LXD de la infraestructura de
  linuxcontainers.org hacia sus propios dominios — confirmado textualmente en
  `linuxcontainers.org/lxd/`: *"Canonical, the creator and main contributor of the LXD
  project has decided that after over 8 years... the project would now be better served
  directly under Canonical's own set of projects"*, firmado por Brauner, Hallyn y
  Graber. Coincide con la salida de Graber de su rol en Canonical ese mismo mes
  (corroborado con su propio blog, "Time to move on", 10 jul 2023).
- **Diciembre de 2023, relicenciamiento a AGPLv3 + CLA obligatorio:** confirmado en el
  hilo `discuss.linuxcontainers.org/t/lxd-has-been-re-licensed-and-is-now-under-a-
  cla/18454` (13 dic 2023, por stgraber), cita textual: *"the Canonical team has decided
  to change the LXD license from Apache2 to AGPLv3 as well as require all new
  contributions to sign the Canonical CLA."* **Matiz para el laboratorio:** esta es la
  cuenta del equipo de Linux Containers sobre la decisión de Canonical, no un anuncio
  oficial firmado por Canonical mismo — hay que atribuirlo así, no como "Canonical
  anunció".
- **Incus como fork:** confirmado en `linuxcontainers.org/incus/announcement/` (7 ago
  2023): *"a fork of LXD created by Aleksa Sarai... shortly after Canonical's decision
  to take LXD away from Linux Containers"*, con Brauner, Hallyn, Graber y Andersen como
  mantenedores iniciales junto a Sarai — es decir, el equipo histórico completo de LXD
  migró a Incus. Incus 0.1 confirmado el 7 de octubre de 2023
  (`linuxcontainers.org/incus/news/2023_10_07_06_10.html`). Licencia Apache 2.0 con DCO
  (sin CLA) confirmada en el `CONTRIBUTING.md` de `github.com/lxc/incus`.

### Gobernanza de OCI (sección 1)

- Fecha de fundación (22 de junio de 2015, DockerCon San Francisco) y hospedaje bajo The
  Linux Foundation: confirmado textualmente en la página oficial de anuncio.
- División Trademark Board / Technical Oversight Board (TOB) / Technical Developer
  Community (TDC): confirmada en `github.com/opencontainers/tob/blob/main/CHARTER.md`.
- Roster actual del TOB (8 miembros con nombres, afiliaciones y fechas de término):
  confirmado nombre por nombre y fecha por fecha contra `github.com/opencontainers/tob`
  en vivo — incluida la distinción correcta que el reporte ya hace entre los cuatro
  miembros con término 2026-2028 y los cuatro con término 2025-2027.

### LXC — tabla de versiones LTS (sección 2)

Confirmadas las tres fechas y ventanas de soporte contra `linuxcontainers.org/lxc/
news/` en vivo, incluida LXC 7.0 LTS (30 abr 2026, soporte hasta junio 2031) —
contrastada además con una búsqueda web independiente. Ningún dato inventado aquí.

### Docker Official Images — criterios de revisión (sección 4, sin la cadencia)

Confirmados contra el README de `github.com/docker-library/official-images/`: FOSS
únicamente, compromiso de mantenimiento upstream, fijación de versiones, prohibición de
`FROM` sobre imágenes no oficiales (salvo `scratch` o imágenes oficiales), y `bashbrew`
como herramienta de construcción multi-arquitectura — todo verbatim.

### NIST SP 800-190 — metadatos (sección 5)

Fecha (septiembre 2017) y autores (Murugiah Souppaya, John Morello, Karen Scarfone)
confirmados exactos contra el PDF oficial en csrc.nist.gov.

### "System container" vs "application container" (sección 6)

Las dos citas textuales atribuidas a `linuxcontainers.org/incus/docs/main/explanation/
instances/` son **coincidencia palabra por palabra** con la página en vivo, verificado
oración por oración. La página `containers_and_vms/` también usa la misma terminología.
Un detalle menor: la tabla comparativa de mapeo de UID/GID (root remapeado por defecto
en LXC/Incus vs no remapeado en Docker) es técnicamente correcta pero no está discutida
en la página citada para ese punto específico — es un hecho bien establecido, solo con
una cita mal apuntada.

### Sección 5, tabla de cifras de vendors (Sysdig, Snyk, Chainguard)

El reporte ya las etiqueta correctamente **[VENDOR CLAIM]** en su propio texto — no se
re-verificaron los números exactos de cada reporte de vendor (eso requeriría acceder a
los reportes originales de pago/gated de cada empresa), pero la etiqueta que el reporte
les puso es la correcta y ya cumple la regla de evidencia del curso: no se presentan
como hechos verificados.

---

## Resumen para uso en el laboratorio

**Usar sin reservas:** toda la sección 3 (LXD → Incus), la gobernanza de OCI y su
roster del TOB, la tabla de versiones LTS de LXC, los criterios de revisión de Docker
Official Images (sin la cifra de cadencia), los metadatos de NIST SP 800-190, y las dos
citas textuales de terminología de Incus.

**No usar:** la cadencia "3-4 semanas" de reconstrucción de Docker Official Images
(fabricada), los ejemplos específicos de herramientas atribuidos a NIST (parafraseados,
no citados), y la cifra exacta "20 miembros fundadores" de OCI (es 21).

**Corregir antes de citar:** las cuatro URLs señaladas arriba con su URL correcta.
