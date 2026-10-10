# Plan de NFR Requirements — U12 `system-verification`

**Alcance:** requisitos no funcionales y stack de las herramientas de verificación de U12
(simulador, conductor de decisiones, escenarios RT y X, carga, demos e informe), sobre el
Functional Design aprobado (BR-U12-01..13, PBT-U12-01..04). U12 no tiene NFR Design
(`aidlc-state.md`: SKIP); lo que haga falta de diseño se fija aquí y en el Infrastructure Design.

**Ya decidido** (no se pregunta):
- U12 no corre en producción; RT, X, carga y demos corren en kind, por el operador, tras un PR aprobado; humo en staging (BR-U12-10).
- Simulador con el cliente `channel-simulator` (≤ 30 req/s); conductor con `analista-1` y `analista-2` por el BFF (BR-U12-02, 03).
- Los cambios al clúster de RT-2 y RT-3 son PRs preparados; U12 solo lee el clúster (BR-U12-09).
- Informe generado desde las evidencias, con el mapa historia → evidencias (BR-U12-11, 13).
- Criticidad: Low en runtime, alta como puerta de calidad.

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Desde dónde corren las herramientas (Tech Stack / Security; AUTONOMIA-01)

A) **Desde un contenedor del operador, fuera del clúster**:
   - simulador, conductor, escenarios, carga e informe corren en una imagen `system-verification` que el operador ejecuta en su estación (o en el runner de kind), contra el gateway (`/api/intake/**`, `/api/console/**`) y las APIs de lectura, como un canal y unos usuarios reales;
   - así U12 no agrega Jobs ni identidades dentro del clúster, y nada de U12 se despliega con Argo CD;
   - lo que sí corre dentro es ajeno a U12: el Job de RT-5 de U8 y la suite de conectividad de U1;
   - para la carga, si la estación no alcanza 20 req/s + 200 usuarios, k6 corre en un segundo contenedor en la misma red de kind.

   (Recomendado)

B) Jobs dentro del clúster en una Application `system-verification` (solo kind y staging), lanzados por PR con un `runId`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: las lecturas del registro (entradas `freeze` y de umbral para la latencia de RT-2, entradas de los escenarios) y las consultas a Prometheus y Loki necesitan una identidad. El NFR la define: o un cliente de solo lectura de U2 solo en kind y staging (con su caso en `realm-lint`, cambio a U2), o los usuarios sintéticos existentes con sus scopes de lectura. Se decide en el Infrastructure Design y se registra como cambio a U2 si hace falta un cliente nuevo.
## Question 2 — Barreras contra el entorno equivocado (Security)

A) **La herramienta se niega a correr fuera de kind y staging**:
   - al arrancar, comprueba que el `issuer` del token sea el del realm `vectra` de kind o de staging (lista explícita de URLs) y que el host del gateway esté en una lista de entornos permitidos; si no, termina con error antes de enviar nada;
   - en staging solo se permiten los escenarios de humo (BR-U12-10): RT, carga y demos se niegan;
   - el cliente `channel-simulator` y los usuarios sintéticos no existen en producción (`realm-lint`), así que la barrera es doble.

   (Recomendado)

B) Solo la barrera del realm

X) Other (please describe after [Answer]: tag below)

[Answer]: A
## Question 3 — Credenciales de la herramienta (Security; SECURITY-12)

A) **Solo en memoria, nunca en las evidencias**:
   - la llave de `channel-simulator` y las contraseñas y semillas TOTP de `analista-1` y `analista-2` se leen al arrancar desde el Vault de kind (o la bóveda de staging) con la sesión del operador, y viven solo en memoria;
   - el código TOTP se calcula en el proceso (`pyotp`);
   - toda salida que va a una evidencia pasa por un filtro que quita `Authorization`, tokens, cookies y semillas; una prueba falla si un archivo de evidencia contiene un JWT o una semilla.

   (Recomendado)

B) Variables de entorno en un archivo `.env` del operador

X) Other (please describe after [Answer]: tag below)

[Answer]: A
## Question 4 — Reproducibilidad (Maintainability)

A) **Todo fijado y registrado en la evidencia**:
   - semillas de muestreo y de la mezcla de decisiones; `generator_version` y `seed` de U5; versión de la imagen de U12 por digest;
   - cada evidencia registra esos valores, el commit y el digest de cada imagen desplegada (leídos del clúster);
   - con los mismos valores, la muestra y la mezcla son idénticas (PBT-U12-01, 03).

   (Recomendado)

B) Sin fijar las semillas

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: la evidencia también registra el tamaño de la partición `test` de U5 y si hubo solicitudes repetidas entre escenarios; si el muestreo estratificado no alcanza 30 casos en alguna celda, la sección `rt2` se niega a correr y lo informa (cierra la nota pendiente del FD sobre la población de `test`).
## Question 5 — Integridad de las evidencias (Security / Maintainability)

A) **Versionadas en el PR, con un manifiesto de hashes**:
   - las evidencias se guardan en `system-verification/evidence/<fecha>-<commit>/`, con un `manifest.json` que lista cada archivo con su SHA-256;
   - el generador del informe verifica el manifiesto antes de leer; un archivo con un hash distinto o ausente → el elemento sale `no ejecutado`;
   - las evidencias van en el PR de verificación; no contienen datos del solicitante (BR-U12-12 y el filtro de Q3).

   (Recomendado)

B) Evidencias sin manifiesto

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: el manifiesto detecta alteraciones accidentales y archivos faltantes, pero quien edite una evidencia y el manifiesto a la vez no queda detectado; esa protección la da la revisión del PR de verificación (CODEOWNERS). El informe lo dice.
## Question 6 — Duración y ejecución por partes (Performance / Usability)

A) **Presupuesto y secciones**:
   - una verificación completa dura del orden de 6 a 8 h (RT-2 son 5 corridas de ~30 min con reactivación; la carga, ~1 h con la línea base) más el día siguiente para U11;
   - la herramienta corre por **sección** (`network`, `decisions`, `rt1`, `rt4`, `rt5`, `rt3`, `rt2`, `load`, `pii`, `u11`, `report`), en el orden de business-logic-model §2.1, y puede retomarse desde una sección; cada sección escribe su evidencia al terminar;
   - el informe puede generarse en cualquier momento: lo no corrido sale `no ejecutado`.

   (Recomendado)

B) Una sola corrida de principio a fin

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: (1) la estimación de 6 a 8 h no incluye la espera de los PR y syncs del operador (RT-3 con 4 paquetes, RT-2 y sus reversiones); el presupuesto la lista aparte. (2) La sección `decisions` debe empezar y terminar dentro de un solo día UTC, para que la verificación de U11 del día siguiente vea las 2 000 decisiones completas (cierra la nota pendiente del FD).
## Question 7 — Stack (Tech Stack)

A) **Python y k6**:
   - Python 3.12 con `httpx` (cliente propio, no `vectra_common.deps`, porque U12 es un cliente externo), `pytest` para los escenarios y sus oráculos, `pyotp`, `vectra_contracts` para los tipos y la validación de las respuestas;
   - k6 para la carga, reutilizando los scripts de U7, U8 y U10;
   - `kubectl` **solo** para lectura (`get`, `auth can-i`); una prueba sobre el código rechaza cualquier llamada de escritura (`apply`, `create`, `delete`, `patch`, `scale`);
   - consultas a Prometheus y Loki por sus APIs de lectura.

   (Recomendado)

B) Todo en k6 (JavaScript)

X) Other (please describe after [Answer]: tag below)

[Answer]: A
## Question 8 — Calidad del propio código de U12 (Maintainability; PBT)

A) **Proporcional a su papel de puerta**:
   - cobertura de ramas 100 % en `report` y `sampler` (deciden qué pasa y qué se muestra), ≥ 85 % en el resto;
   - PBT-U12-01..04 con perfiles `ci` y `nightly`; `mutmut` en `report`;
   - los oráculos de cada RT probados contra respuestas de ejemplo correctas e incorrectas (que una falla se detecte).

   (Recomendado)

B) Solo pruebas de ejemplo

X) Other (please describe after [Answer]: tag below)

[Answer]: A
## Question 9 — Trazabilidad de una corrida en el sistema (Reliability)

A) **Etiquetada de punta a punta**: cada solicitud del simulador y del conductor lleva la cabecera de escenario de U8 y un `traceparent` con un prefijo de corrida; la evidencia guarda los `correlation_id` y las consultas de Prometheus y Loki usadas, para que un revisor pueda repetir la lectura. Ninguna etiqueta lleva datos del solicitante. (Recomendado)

B) Sin etiquetas propias

X) Other (please describe after [Answer]: tag below)

[Answer]: A
---

## Parte B — Plan de trabajo

- [x] Leer y validar las respuestas; preguntas de aclaración si alguna es ambigua
- [x] `nfr-requirements.md` (NFR-U12-xx)
- [x] `tech-stack-decisions.md`
- [x] Cambios a otras unidades registrados
- [x] Tabla de cumplimiento de extensiones
- [x] Registrar en `audit.md` y actualizar `aidlc-state.md`
