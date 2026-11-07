# vectra-risk-gitops

Manifiestos de Argo CD por entorno (P-U1-12). Ninguna `Application` tiene `syncPolicy.automated`: el único cambio al clúster es un sync manual aprobado (NFR-U1-43).
U2 agregó Valkey (wave 2), Keycloak, el gateway y el rate limit (wave 3), y las reglas, los monitores y los Jobs de identidad (wave 4). Sus manifiestos son los directorios renderizados de `identity-edge/`. La wave 6 (InferenceServices) la agrega U6.

Vive dentro del monorepo. Una `Application` nueva es una entrada de `components.yaml`; los valores de una unidad van en `values/<env>/<componente>.yaml`, que `generate.py` agrega solo y no borra.
