# Ronda 1 — U01-T03

VEREDICTO: NO-VERDE

Worktree `wt-U01-T03`, rama `tarea/U01-T03`, sha `676458d`, base `f44ba83`. Nada se ejecutó contra un clúster. El efecto real (que los targets dejen de dar 504) sigue sin comprobar.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | NetworkPolicy de ingress y egress de F130 en los 3 entornos, con esos puertos y sin 4143 | `uv run pytest platform/network/tests -q -k f130` | pasa: `3 passed, 85 deselected in 1.68s`, una prueba por entorno (`--collect-only`: kind, staging, prod). La prueba es débil, ver F-01 |
| 1b | Lectura de vuelta de `generated/` con un script propio | `yaml.safe_load_all` sobre `generated/{kind,staging,prod}/vectra-observability.yaml` | pasa: en los 3 entornos, ingress y egress prometheus↔alertmanager [8080], prometheus↔operator [8080], prometheus↔grafana [3000]; sin 4143 |
| 2 | Lo generado coincide y el inventario está al día | `uv run python platform/network/generate.py --check && uv run pytest platform/network/tests -q` | pasa: gen rc=0, `88 passed in 41.46s`, pytest rc=0 |

Sobre el tiempo: 1.68 s y 41 s, sin omisiones (`-rs` no lista ninguna). La suite es pura, sin estado externo: construye desde `flows.yaml`, y `--check` ata el resultado a `generated/`.

## Hallazgos

### F-01 · NARANJA · `platform/network/tests/test_flows.py:427-433` · La prueba de F130 no ata puerto, destino ni origen
La prueba solo compara las listas ordenadas de puertos (`[[3000],[8080],[8080]]`). No mira a quién selecciona cada política, de modo que **tres mutaciones incorrectas pasan los dos criterios**. Cada una se aplicó en una copia temporal, regenerando `generated/` y confirmando la mutación al leer `flows.yaml`:

| Mutación de F130 en `flows.yaml` | `-k f130` | `generate.py --check` | Suite completa |
|---|---|---|---|
| M1, puertos cruzados: grafana y operator 8080, alertmanager 3000 | 3 passed | rc=0 | 88 passed |
| M2, origen `loki` en vez de `prometheus` | 3 passed | rc=0 | 88 passed |
| M3, destinos `loki, tempo` en vez de `alertmanager, prometheus-operator` | 3 passed | rc=0 | 88 passed |

Las tres dejarían los targets en 504 con todo en verde. El criterio CA-1 se cumple hoy solo porque lo comprobé leyendo `generated/` (fila 1b), no porque la prueba lo garantice.

La prueba tampoco comprueba `MeshTLSAuthentication` ni `AuthorizationPolicy` de F130. El vecindario del namespace funciona con `deny` por defecto, así que sin ellas Linkerd rechazaría el tráfico.

Sí detecta otras mutaciones:
- Sin F130: 3 failed.
- Grafana en 3100: 3 failed.
- 4143 añadido: 3 failed.
- F130 solo en kind: 2 failed, 1 passed.

Corrección esperada: afirmar por entorno, para cada destino, el par (selector del destino, selector del origen, puerto) en ingress y egress, y la identidad `prometheus` en la autorización de cada `Server`. Después, repetir M1, M2 y M3.

### F-02 · AMARILLO · `bitacoras/U01-T03.md:24` · Regeneró con `generate.py` en vez de `make -C platform generate`
Las notas de la tarea piden regenerar solo con `make -C platform generate`, y la bitácora declara `generate.py`. No tiene efecto: corrí el `make` en una copia y `git status` quedó vacío, así que el resultado es idéntico byte a byte, incluidos quotas y gitops. Para ese `make` añadí `--frozen --offline` a sus `uv run`, solo en la copia.

## Comprobado sin hallazgo
- **Alcance:** el diff toca solo `flows.yaml`, la prueba, `generated/`, la fila del inventario y la bitácora.
- **Efecto sobre los demás:** comparación semántica base contra HEAD de todo `generated/`. Solo cambian `vectra-observability.yaml` y `connectivity-suite.yaml` de cada entorno. Ningún documento se quita ni se altera, solo se añaden los de F130. Las 195 líneas borradas de `connectivity-suite.yaml` son ruido de serialización: `blocked` y `env` son iguales, y `allowed` solo gana 3 entradas. La autorización de los demás no cambia.
- **Puertos y etiquetas contra el chart real:** `helm template` local de kube-prometheus-stack con los valores de producción, sin red ni clúster.
  - Alertmanager: `reloader-web` 8080.
  - Grafana: contenedor en 3000, `ServiceMonitor` en `http-web` `/metrics`.
  - Operator: `http` 8080, `tls.enabled: false`, etiqueta `kube-prometheus-stack-prometheus-operator`, SA `prometheus-operator`.
- **`Server` nuevos en 8080:** el operator tiene su sonda `/healthz` en ese puerto. No hay `HTTPRoute` sobre esos `Server`, y según `generate.py:240` Linkerd solo deja de autorizar las sondas cuando hay rutas. Es una inferencia sin comprobar en clúster.
- **Afirmaciones de la bitácora, reproducidas:**
  - Hash de la tarea: `ca0a613…` coincide con `git hash-object`.
  - Rojo sin F130: `3 failed, 85 deselected`.
  - Inventario sin la fila: `1 failed, 87 passed`, en `test_every_inventory_id_is_in_flows`.
  - El orden «rojo antes de tocar `flows.yaml`» no se puede demostrar, porque todo está en un solo commit. Reproduje el fallo, no su cronología.
- **Otras comprobaciones de `check-local`:** `vectra-risk-gitops/generate.py --check` rc=0, `quotas/render.py --check` rc=0, `test_waves` rc=0, `test_links` rc=0, `ruff check platform/network` limpio.
- **`test_traceability`:** rc=1, igual en la base `f44ba83` con el mismo mensaje. Es preexistente, ver candidatas.

## Sin ejecutar
- `make check-local` completo.
- `make check-tools`, `check-integration` y `test_runbooks`.
- `pytest platform` fuera de `platform/network/tests`.

Ninguno es criterio de esta tarea.

## Tareas candidatas (defectos reales fuera de alcance)
- `platform/tests/test_traceability.py` falla ya en la base: `NFR-U1-40: solo en code/README.md, y su fila no nombra un archivo existente` (rc=1).
- El `ServiceMonitor` de Prometheus raspa `http-web` y `reloader-web`, pero `flows.yaml` no declara prometheus→prometheus en 8080 ni en 9090. Con más de una réplica, esos targets podrían fallar igual. Lo deduzco del render; no está comprobado.

## Notas sobre mi ejecución
- **Worktree:** `git status --short` da 0 líneas y HEAD sigue en `676458d`. Los fuentes están intactos.
- **Efectos fuera de los fuentes:**
  - Correr pruebas escribió cachés ignorados.
  - Mi primera tanda de mutaciones usó el `.venv` del worktree desde la copia, y `uv` reinstaló 2 paquetes en ese `.venv` (ignorado por Git). Después pasé a un venv propio.
  - Una tanda se interrumpió porque su directorio temporal `mut` desapareció a mitad de corrida. Sospecho de otro proceso que usa el mismo scratchpad, sin confirmarlo.
  - Repetí todo lo afectado en un directorio privado. Las cifras de arriba salen de esas repeticiones.
- **Repositorio principal:** leí su chart en `platform/.charts/kube-prometheus-stack` solo para renderizar. No lo modifiqué.
- **No guardé el informe:** este revisor no escribe. El orquestador guarda el texto en la ruta indicada abajo.
- **Orden del bloque final:** el contrato pone el veredicto al inicio del bloque y tú pediste terminar en él, así que dejo esa línea al final.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/tasks/b1fzmycvt.output`

NARANJA|platform/network/tests/test_flows.py:427-433|La prueba de F130 no ata puerto, destino ni origen
AMARILLO|bitacoras/U01-T03.md:24|Regeneró con generate.py en vez de make -C platform generate
INFORME: revisiones/U01-T03/ronda-1.md
VEREDICTO: NO-VERDE
