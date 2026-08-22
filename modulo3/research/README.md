# Investigación — módulo 3

Esta carpeta muestra **cómo se trabaja la investigación en este curso**, no solo su
resultado. Léela en este orden:

| Archivo | Qué es | Cómo se lee |
|---|---|---|
| `deep-research-ai-k8s-cncf.md` | Reporte de deep research generado con IA sobre agentes de IA operando Kubernetes | **Insumo crudo. No es una fuente.** Ninguna de sus cifras vale hasta pasar por la auditoría |
| `deep-research-ai-k8s-cncf.AUDIT.md` | Auditoría afirmación por afirmación contra fuentes primarias | **Esto sí es la fuente.** Solo lo marcado CONFIRMADO puede citarse |

---

## La regla

> **Un reporte de investigación con IA es un insumo de verificación, nunca el resultado
> de ella.** Resumirlo fielmente no es verificarlo.

Fluidez y URLs reales **no** son evidencia. Un reporte puede citar fuentes auténticas y
aun así leerlas mal: atribuir una cifra al estudio equivocado, invertir la dirección de
un resultado, omitir que no había significancia estadística, o inventar el nombre de una
empresa.

Todo eso pasó en el reporte que está en esta carpeta. Está documentado en la auditoría
con nombre y apellido, a propósito: **el rastro de las correcciones enseña más que un
reporte limpio.**

---

## El resultado, en números

De las afirmaciones verificadas contra fuente primaria:

- **Estado de proyectos en la CNCF:** 4 de 12 con error. El peor: *Backstage listado como
  Graduated* cuando está en Incubating.
- **Financiación de empresas:** 3 de 4 correctas. Un nombre de empresa **inventado**.
- **Cifras de Gartner:** 5 de 7 correctas — pero **todas citadas a una página de análisis
  bursátil de IBM** en vez de a Gartner. Dato bueno, citación inaceptable.
- **Estadísticas de dolor operativo:** solo **4 de 10** sobrevivieron.

## Los cinco errores que más se repiten

1. **Autocitación.** El modelo citó como fuente verificada el propio archivo de contexto
   que se le entregó. Cifras de un caso de estudio de otro dominio terminaron etiquetadas
   como hallazgos verificados sobre Kubernetes.
2. **Cifra inexistente.** Un "38% de equipos" atribuido a DORA que **no aparece en ningún
   informe de DORA**, y un "41% de commits" que no está en el PDF de Faros AI.
3. **Fuente de tercera mano.** Cifras de analistas citadas a un blog comercial o a un
   agregador bursátil en vez de a la nota de prensa original.
4. **Año equivocado.** Un multiplicador real de DORA (6.570x) tomado del informe de 2021
   y presentado como actual; el informe vigente da 2.293x.
5. **Dirección invertida.** Una predicción de ahorro de costos que el propio analista
   revirtió después, presentada como hecho consolidado.

## El hallazgo que hay que leer dos veces

El error más instructivo no fue una cifra falsa, sino una cifra **cambiada por otra más
cómoda**.

El reporte afirmó que "el 38% de los equipos que usan IA aumentaron su frecuencia de
despliegue". Esa cifra no existe. Lo que DORA sí publica es que la adopción de IA se
asocia con una **reducción del 7,2% en estabilidad**.

Es decir: el dato real era **incómodo** para la narrativa, y en el camino se convirtió en
un porcentaje inventado que suena a validación. Ese es el patrón más peligroso de todos,
porque el resultado se lee como investigación seria y apunta en la dirección contraria a
la evidencia.

---

## Qué se espera de ti

Cuando entregues tu propia investigación (validación y crítica):

- Documenta **de dónde salió cada cifra**, con enlace y fecha.
- Cuando no encuentres evidencia pública sólida, **dilo**. Un honesto "no hay datos
  públicos verificables sobre esto" vale más que una cifra plausible inventada.
- Si detectas que tu propia investigación se equivocó, **registra la corrección** en vez
  de borrarla.

En la sustentación voy a preguntar por el origen de las cifras. Las que no tengan fuente
se caen solas.
