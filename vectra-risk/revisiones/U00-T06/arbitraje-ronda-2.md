# U00-T06 — Arbitraje de la ronda 2 (orquestador, 2026-11-17)

Informe: `ronda-2.md`. NO-VERDE **sin ningún ROJO**: un NARANJA (F-06) y un AMARILLO (F-07). Los criterios pasan en las corridas del revisor; F-02 a F-05 quedan cerrados y F-01 cerrado a medias.

**Decisión: no hay ronda 3 (RL-2). Se abre el PR con el veredicto NO-VERDE tal cual y F-06 y F-07 pasan a `CANDIDATAS.md` (RL-3: solo un ROJO bloquea).** Motivos:

- El revisor midió que ningún verde indebido sale de una salida que npm pueda emitir, y que el guion decide igual que `npm audit --audit-level=high` en los casos de F-06.
- El check `checks` está en rojo en todos los PR desde el aviso; el arreglo desbloquea la CI.
- Una ronda 3 exigiría autorización del usuario. Si la quiere, se hace como tarea aparte sobre `main`.

| Hallazgo | Decisión |
|---|---|
| F-06 NARANJA: una severidad permitida en el paquete tapa los avisos de su `via` | Candidata |
| F-07 AMARILLO: seis mutantes nuevos sobreviven (entre ellos `not strong`, regresión de una prueba de la ronda 1) | Candidata |
