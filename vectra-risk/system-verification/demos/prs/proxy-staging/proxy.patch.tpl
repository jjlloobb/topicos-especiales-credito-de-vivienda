--- a/vectra-risk/vectra-risk-gitops/values/kind/model-serving.yaml
+++ b/vectra-risk/vectra-risk-gitops/values/kind/model-serving.yaml
@@ -1,7 +1,8 @@
 # Values de model-serving en kind (U6). Los edita `promotion-tool` por PR y solo la clave `inferenceServices`: contrato en
 # model-serving/docs/values.md, esquema en model-serving/chart/values.schema.json. U06-T02 no declara ningun InferenceService.
 # El digest real de las imagenes (`images.predictor.digest` y `images.explainer.digest`) lo fija el operador en el Paso 11 de U6.
-inferenceServices: []
+inferenceServices:
+  - { modelVersionId: @@M2@@, storageUri: "s3://model-store/@@M2@@/", profile: staging }
 # Presupuesto de memoria de kind (DECISIONES-LOOP.md §7, opcion c, decision del usuario 2026-11-09, U06-T03): 256 Mi por pod en lugar de los
 # 512 Mi de INF-U6-01, solo aqui. Replicas, HPA y PDB no cambian (require-hpa-bounds; el activo nunca baja de 2). Staging y prod siguen en
 # chart/values.yaml (test_kind_profile.py lo comprueba). Los limits tampoco cambian: el modelo de referencia usa menos de 256 Mi, y el
