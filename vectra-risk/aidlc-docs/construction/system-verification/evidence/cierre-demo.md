# Cierre de la demo: U12 `system-verification` (en curso; lo completa U12-T06)

Este archivo lo abrió U12-T05 con **solo** la sección «Diferido por la demo», que necesita la trazabilidad del Paso 17. U12-T06 (Pasos 18 y 19) agrega el resto: la verificación en kind, los tiempos medidos, el presupuesto de memoria y el cierre.

## Diferido por la demo

Lista que acepta `platform/tests/test_traceability.py --unit system-verification --all` (`DECISIONES-LOOP.md` §6; `demo-recorte-funcional.md` §2, regla 4). Cada fila lleva el identificador, el paso del plan que lo implementaría y la cita del recorte. Un identificador de esta lista no puede tener código ni prueba: la herramienta falla si ya lo tiene.

| Identificador | Paso del plan | Cita del recorte | Qué falta |
|---|---|---|---|
| INF-U12-05 | Paso 11 (carga, US-609) | Enmienda `demo-recorte-funcional.md` §3 U12, fila «8b · 9 · 11: D»; `demo-kind-alcance.md` §3 U12 | La sección `load`, la estimación de capacidad para la carga y su contenedor de carga con límites: ninguna demo la usa |

Lo diferido sin identificador propio (no lo mira la herramienta; cada uno con su destino):

| Qué | Paso del plan | Cita del recorte | Destino |
|---|---|---|---|
| Escaneo, SBOM y firma de la imagen | Paso 15 | Enmienda §3 U12, fila «14 · 15: N/A · E\*»; T1 (firma Cosign, SBOM y attestations) | Después de la demo; la imagen se construye y se publica en `kind-registry` sin ellos |
| Workflow de CI de la unidad | Paso 16 | Enmienda §3 U12, fila «16: D»; T4 | Después de la demo |
| Las secciones `network`, `rt1`, `rt4`, `load`, `pii` y `resilience` | Pasos 7, 8b, 9 y 11 | Enmienda §3 U12, filas «7: D» y «8b · 9 · 11: D», y fila «13» | Responden `no ejecutado` (código 2) y el informe da el motivo de cada historia que dependía de ellas |
| `LOGS-NO-PII` y `CASE-SIZE` | Paso 10 | Enmienda §3 U12, fila «10» (P-18) | Ninguna demo los usa |
| Pruebas de mutación (`mutmut`) | Paso 4 | Enmienda §3 U12, fila «4»; T3 | Después de la demo |
| Prueba de `CODEOWNERS` con `branch-protection-check` | Paso 13 | Enmienda §3 U12, fila «13» | Depende de U4 Paso 14 |
| Las Applications `bias-monitoring` y `decision-registry-rebuild` en el parche de `prepare` | Paso 13 | Enmienda §3 U12, fila «13» | El parche solo toca `case-management` |
