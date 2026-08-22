# Cómo correr esta investigación en Gemini (Deep Research)

1. Abre Gemini (web UI, modo **Deep Research**).
2. Copia y pega el contenido completo de `01-prompt.md` como el prompt inicial.
3. Adjunta como archivo de contexto (o pega su contenido si Gemini no acepta adjuntos):
   - `02-context-alcance-curso.md` — el temario del curso, para que la investigación
     entienda para qué se usa esto.
   - Si Gemini limita a un solo adjunto, usa `CONTEXT-ALL.md` (todo concatenado).
4. Deja correr el Deep Research completo (puede tardar varios minutos).
5. Cuando termine, **descarga o copia el reporte completo en Markdown**.
6. Guárdalo en el repo en esta ruta exacta:

   ```
   /home/lfarizav/topicos-especiales/modulo3/research/deep-research-oci-lxc-lxd.md
   ```

7. Avísame en la siguiente sesión de Claude Code ("ya guardé el research de Gemini
   sobre OCI/LXC/LXD en modulo3/research/") y yo lo audito claim por claim contra las
   fuentes citadas antes de usarlo para enriquecer la sección "Para profundizar" de
   `laboratorio-virtualizacion-contenedores.md`.

No uses este reporte directamente en el laboratorio sin que yo lo audite primero — los
reportes de deep research a veces citan fuentes reales pero las interpretan mal (mismo
patrón ya documentado en `deep-research-ai-k8s-cncf.AUDIT.md` de este mismo módulo).

## Por qué este bundle es más angosto que el de PVB/PRD

El laboratorio ya está escrito y **cada comando que aparece en él fue corrido de
verdad en una máquina real** — namespaces, cgroups, kernels, tamaños de imagen y
vulnerabilidades con Trivy no son afirmaciones de este research, son observaciones
directas. Lo que este research SÍ necesita resolver es lo que un comando de terminal no
puede contestar: gobernanza de OCI, historia y relación exacta de LXD con Canonical
(incluida la pregunta delicada de si hubo un fork de la comunidad), y el programa de
imágenes oficiales de Docker Hub. Es angosto a propósito.
