"""`promotion-tool` (Paso 12 de U4; BR-U4-08 y 09; NFR-U4-20 y 21): la CLI de la estacion del ingeniero.

Genera PR de un solo commit firmado sobre `vectra-risk-gitops/values/<env>/model-serving.yaml` y llama a `mark_active`. Nunca
sincroniza ni aplica nada en el cluster (AUTONOMIA-01): la evidencia `kubectl diff` es de solo lectura y la corre el comando
que el ingeniero pasa.
"""
