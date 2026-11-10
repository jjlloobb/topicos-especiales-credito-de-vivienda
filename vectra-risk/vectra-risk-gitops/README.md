# vectra-risk-gitops

Manifiestos de Argo CD por entorno (P-U1-12). Ninguna `Application` tiene `syncPolicy.automated`: el único cambio al clúster es un sync manual aprobado (NFR-U1-43).
# La wave 6 (InferenceServices) es `model-serving` (U6): sus values por entorno los edita `promotion-tool`, ver `model-serving/docs/values.md`.

Vive dentro del monorepo. Una `Application` nueva es una entrada de `components.yaml`; los valores de una unidad van en `values/<env>/<componente>.yaml`, que `generate.py` agrega solo y no borra.
