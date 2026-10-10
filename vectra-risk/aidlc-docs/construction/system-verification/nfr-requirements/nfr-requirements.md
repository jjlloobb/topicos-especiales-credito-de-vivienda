# Requisitos no funcionales — U12 `system-verification`

Decisiones del plan (`system-verification-nfr-requirements-plan.md`, Q1–Q9 = A, con las notas
del usuario). U12 no tiene NFR Design (SKIP en `aidlc-state.md`): los mecanismos se fijan aquí y
en el Infrastructure Design.

Los IDs `NFR-U12-xx` se referencian en el Infrastructure Design y en el plan de tareas.

---

## 1. Ejecución y seguridad (Q1, Q2, Q3)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U12-01 | **Fuera del clúster**: simulador, conductor, escenarios, carga e informe corren en una imagen `system-verification` que el operador ejecuta en su estación o en el runner de kind, contra el gateway y las APIs de lectura. U12 no despliega nada con Argo CD ni agrega Jobs. Lo que corre dentro es ajeno a U12: el Job de RT-5 de U8 y la suite de conectividad de U1. k6 corre **siempre** en su propio contenedor (`grafana/k6` por digest, 2 CPU y 2 GiB), que el operador lanza con la sección `load` en la red de kind; la imagen `system-verification` no lo incluye (antes, «si la estación no alcanza»; pendientes consolidados, 2026-10-10) | Prueba de que la imagen no contiene manifiestos de Kubernetes y de que el código no crea recursos |
| NFR-U12-02 | **Identidad de lectura** (nota de Q1): las lecturas del registro (latencia de RT-2, entradas de los escenarios) y de Prometheus y Loki necesitan una identidad propia, de solo lectura y solo en kind y staging. Se define en el Infrastructure Design, con su caso en `realm-lint` si es un cliente nuevo de U2 | Infrastructure Design de U12 |
| NFR-U12-03 | **Barrera de entorno**: al arrancar, la herramienta comprueba que el `issuer` del token sea el del realm de kind o de staging (lista explícita) y que el host del gateway esté en la lista de entornos permitidos; si no, termina con error antes de enviar nada. En staging solo se permiten los escenarios de humo | Prueba con un `issuer` y un host de producción simulados → sale con error y cero solicitudes enviadas; en staging, la sección `rt2` → se niega |
| NFR-U12-04 | **Credenciales solo en memoria**: la llave de `channel-simulator` y las contraseñas y semillas TOTP de `analista-1` y `analista-2` se leen al arrancar desde el Vault de kind (o la bóveda de staging) con la sesión del operador, en las mismas rutas donde ESO las lee para el realm (U2); la herramienta no usa ESO ni crea Secrets (revisión del NFR Requirements de U12, 2026-10-10); el TOTP se calcula en el proceso (`pyotp`) | Prueba de que no se escribe ningún archivo con credenciales |
| NFR-U12-05 | **Filtro de evidencias**: toda salida que va a una evidencia pasa por un filtro que quita `Authorization`, tokens, cookies y semillas | Prueba: un archivo de evidencia con un JWT o una semilla → la generación falla |

## 2. Reproducibilidad (Q4)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U12-10 | Semillas fijas de muestreo y de la mezcla; `generator_version` y `seed` de U5; imagen de U12 por digest. Cada evidencia registra esos valores, el commit y el digest de cada imagen desplegada (leídos del clúster) | PBT-U12-01, 03 (misma semilla → misma muestra y misma mezcla) |
| NFR-U12-11 | La evidencia registra también el tamaño de la partición `test` de U5 y si hubo solicitudes repetidas entre escenarios. Si el muestreo estratificado no alcanza 30 casos en alguna celda, la sección `rt2` **se niega a correr** y lo informa (nota de Q4) | Prueba con una población de fixture con una celda chica → `rt2` se niega |

## 3. Integridad de las evidencias (Q5)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U12-20 | Evidencias en `system-verification/evidence/<fecha>-<commit>/` con un `manifest.json` que lista cada archivo con su SHA-256; el generador verifica el manifiesto antes de leer, y un archivo con hash distinto o ausente deja el elemento en `no ejecutado` | Prueba: un byte cambiado en una evidencia → su elemento sale `no ejecutado` |
| NFR-U12-21 | **Límite del manifiesto** (nota de Q5): detecta alteraciones accidentales y archivos faltantes, pero no a quien edite la evidencia y el manifiesto a la vez. Esa protección la da la revisión del PR de verificación, con `CODEOWNERS` del directorio de evidencias. El informe lo dice en su encabezado | Prueba del encabezado del informe; `CODEOWNERS` con la línea de `system-verification/evidence/` |

## 4. Duración y ejecución por secciones (Q6)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U12-30 | **Secciones** `prepare` (primera, antes del PR de los Jobs de prueba; se niega si ya existe un manifiesto de esa verificación; pendientes posteriores al cierre, 2026-10-10), `network`, `decisions`, `rt1`, `rt4`, `rt5`, `rt3`, `rt2`, `load`, `pii`, `u11` y `report`, en el orden de business-logic-model §2.1; la herramienta puede retomarse desde una sección y cada sección escribe su evidencia al terminar. El informe puede generarse en cualquier momento | Prueba de retoma: interrumpir en `rt3` y retomar → las secciones anteriores no se repiten |
| NFR-U12-31 | **Presupuesto**: 6 a 8 h de ejecución (RT-2: 5 corridas de ~30 min con reactivación; carga ~1 h con la línea base) más el día siguiente para `u11`. **Aparte**, las esperas de los PRs y syncs del operador (RT-3 con 4 paquetes y sus reversiones; RT-2 y su vuelta al modelo de referencia), que no se cuentan en ese presupuesto (nota 1 de Q6) | Medición en la primera verificación completa, registrada en el informe |
| NFR-U12-32 | La sección `decisions` empieza y termina dentro de un solo día UTC; si no puede terminar antes de las 23:00 UTC, no empieza. Así la verificación de U11 del día siguiente ve las 2 000 decisiones completas (nota 2 de Q6) | Prueba con reloj simulado a las 22:30 UTC → `decisions` se niega a empezar |

## 5. Calidad del código de U12 (Q8)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U12-40 | Cobertura de ramas 100 % en `report` y `sampler`, ≥ 85 % en el resto; `mutmut` en `report` | `pytest-cov`, `mutmut` |
| NFR-U12-41 | PBT-U12-01..04 con perfiles `ci` y `nightly` y la semilla impresa | CI |
| NFR-U12-42 | Cada oráculo de RT y de X probado contra respuestas de ejemplo correctas **e incorrectas**: una respuesta incorrecta debe dar `falla` | Pruebas de oráculos con fixtures |
| NFR-U12-43 | `kubectl` solo con `get`, `auth can-i`, `logs` y `port-forward` (los dos últimos agregados en el Infrastructure Design de U12, 2026-10-10, INF-U12-02, 03); una prueba sobre el código rechaza cualquier invocación de `exec`, `apply`, `create`, `delete`, `patch`, `scale`, `edit` o `rollout` | Prueba estática sobre el código y los guiones |

## 6. Trazabilidad (Q9)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U12-50 | Cada solicitud del simulador y del conductor lleva la cabecera de escenario de U8 y un `traceparent` con un prefijo de corrida; la evidencia guarda los `correlation_id` y las consultas de Prometheus y Loki usadas, para que un revisor repita la lectura; ninguna etiqueta lleva datos del solicitante | Prueba: las solicitudes de una corrida llevan el prefijo y la cabecera; la evidencia incluye las consultas |

## 7. Cumplimiento de extensiones (NFR Requirements U12)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | NFR-U12-01, 43 (sin cambios al clúster desde U12) |
| AUTONOMIA-02 | Cumple | NFR-U12-20, 42 (evidencias verificables; oráculos probados) |
| SECURITY-03 | Cumple | NFR-U12-05, 50 |
| SECURITY-12 | Cumple | NFR-U12-04, 05 |
| SECURITY-11 | Cumple | NFR-U12-03 (barrera de entorno) |
| PBT-02..10 | Cumple | NFR-U12-40..42 |

## 8. Pendientes para el Infrastructure Design

- La identidad de lectura de NFR-U12-02: un cliente nuevo de solo lectura en U2 (kind y staging) o los usuarios sintéticos con sus scopes, y su acceso a Prometheus y Loki.
- La imagen `system-verification` y el contenedor de k6 en la red de kind.
- `CODEOWNERS` del directorio de evidencias (NFR-U12-21).
- **X04 y X06 chocan con «fuera del clúster y solo lectura»** (revisión del NFR Requirements de U12, 2026-10-10): X04 exige llamar a governance **con la identidad de `bias-monitoring-job`**, y X06 exige un `UPDATE` con `registry_app` en `registry-db`. Ninguna de las dos se puede hacer desde fuera del clúster con solo `get` y `auth can-i` (NFR-U12-43). El Infrastructure Design decide el mecanismo: un Job de demostración de la unidad dueña (U4 o U9 para X04, U3 para X06) que intenta la acción y deja su resultado, y que U12 solo **lee**, como el Job de RT-5 de U8; o permitir `kubectl exec` en NFR-U12-43 con su justificación.
- **Camino de acceso a lo interno** (revisión del NFR Requirements de U12, 2026-10-10): el gateway solo expone `/api/intake/**` y `/api/console/**`; el registro, Prometheus y Loki son internos. NFR-U12-02 define la identidad de lectura, pero no por dónde se llega. El Infrastructure Design decide entre `kubectl port-forward` (lectura, solo kind y staging) o una ruta publicada, y su efecto en X09 (único ingress) y en las `AuthorizationPolicy`.
