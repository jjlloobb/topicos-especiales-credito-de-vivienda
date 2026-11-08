# Arbitraje de la ronda 1 — U05-T01

Orquestador, 2026-11-08. Informe: `revisiones/U05-T01/ronda-1.md` (NO-VERDE por un ROJO).

## Regla

RL-2 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6: máximo 2 rondas, y solo un ROJO bloquea. NARANJA y AMARILLO van a `CANDIDATAS.md`, salvo que rompan una de las demos. Como la ronda 2 se abre de todos modos por el ROJO, entran también los arreglos baratos que corrigen un incumplimiento del diseño en el código que esta misma tarea escribió.

## Decisiones

- **F-01 (ROJO) — entra.** La prueba usa literales: `"999"` para CC y `"SYN"` para los demás tipos, más el patrón completo (`^999\d{7}$` o el que corresponda a la longitud elegida, y `^SYN[A-Za-z0-9]+$`). **Rojo primero:** con las constantes del módulo cambiadas a `"10"` y `"AB"`, la prueba falla.
- **F-02 (NARANJA) — entra en parte.**
  - El comentario de `generate.py` deja de afirmar que el bloque `999` «no se asigna a personas». Queda como «convención sintética del proyecto, `[VERIFICAR]` contra la numeración real de la Registraduría».
  - La candidata de `CANDIDATAS.md` sobre `document_number` se amplía con el impacto en U12: `LOGS-NO-PII` (BR-U12-12) busca `SYN-` y no vería `document_number`, `email` ni `full_name`.
  - El email usa `SYN-` en mayúsculas, si U0 lo admite, para que lleve el mismo marcador que buscará U12. Si U0 no lo admite, se deja como está y se anota.
  - No se cambia el diseño en esta tarea.
- **F-03 (NARANJA) — entra.** BR-U5-01 dice que el generador solo usa `generator.yaml`. Los literales de l.144–309 pasan a `marginals` (o a la sección que corresponda de domain-entities §1): antigüedad (media y tope), margen VIS, estrato de `no_informado`, días por año de la fecha de nacimiento si es un parámetro y no una constante física, rangos de dirección y número de brokers. El valor de la vivienda no VIS con ingreso bajo (≥ 204 M COP) se deja como está y va a candidatas, porque cambiarlo cambia la distribución.
  - El determinismo de CA-3 tiene que seguir: misma semilla, mismos SHA-256. Si los SHA cambian solo porque cambió la configuración por defecto, está bien. Regístralo en la bitácora.
- **F-04, F-05, F-06 (AMARILLO) — a `CANDIDATAS.md`.** No se corrigen.

## Aceptación de la ronda 2

Los CA-1 a CA-5 de la tarea, con el rojo de F-01 en la bitácora y una prueba que falla si un literal de F-03 vuelve al código: por ejemplo, cambiar la antigüedad en `generator.yaml` cambia la salida.
