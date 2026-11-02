F-03: Corregido en 3e810b1: OPERATOR_PORTS[alertmanager] incluye 8080 (reloader-web, comprobado con helm template del Service de alertmanager); `make -C platform charts` + `uv run pytest platform -q` da 597 passed (antes 1 failed, 596 passed).
F-04: No es un defecto propio de F130: la misma laxitud aplica a cualquier flujo con otro id, y endurecerla es una prueba genérica de inventario, fuera del alcance de esta tarea; tarea candidata: prueba que ate cada flujo a sus destinos declarados.
F-05: Corregido en 3e810b1: la prueba compara la lista completa de requiredAuthenticationRefs; con una segunda ref inyectada en el generador, -k f130 pasa a 3 failed.
F-06: Corregido en 3e810b1: F130_TARGETS ahora es {target: puerto} y la etiqueta se deriva de la clave.
