# vectra-risk-gitops

Manifiestos de Argo CD por entorno (P-U1-12). Ninguna `Application` tiene `syncPolicy.automated`: el único cambio al clúster es un sync manual aprobado (NFR-U1-43).
# Las waves 3 y 6 (Keycloak, gateway, InferenceServices) las agregan U2 y U6.

Vive dentro del monorepo. Una `Application` nueva es una entrada de `components.yaml`; los valores de una unidad van en `values/<env>/<componente>.yaml`, que `generate.py` agrega solo y no borra.
