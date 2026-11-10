#!/usr/bin/env bash
# Comprobaciones de pods del escenario 3 del Paso 11 de U6. Solo lee (`kubectl get`, `kubectl exec ... cat`).
# Uso: check-pods.sh init-order POD NS      el proxy de Linkerd va antes que el storage initializer (descarga con mTLS, F46)
#      check-pods.sh initializer POD NS     el pod tiene storage-initializer (se prueba en el predictor y en el explicador)
#      check-pods.sh manifest POD NS ID     /mnt/models/manifest.json trae model_version_id = ID (riesgo MODEL_DIR)
#      check-pods.sh propagation DEPLOY NS ESTADO   la metadata del Deployment trae vectra.io/serving-state=ESTADO (inactivo) y hpa-exempt=true
# KUBECTL cambia el ejecutable. Codigo de salida: 0 si la comprobacion pasa.
set -euo pipefail

kubectl_bin="${KUBECTL:-kubectl}"
[ $# -ge 3 ] || { echo "uso: check-pods.sh init-order|initializer|manifest|propagation ..." >&2; exit 64; }
mode="$1" target="$2" namespace="$3"
case "$mode" in
  init-order)
    names=$("$kubectl_bin" get pod "$target" -n "$namespace" -o 'jsonpath={.spec.initContainers[*].name}')
    echo "initContainers: $names"
    read -r -a ordered <<< "$names"
    proxy=-1 storage=-1 i=0
    for n in "${ordered[@]}"; do
      case "$n" in linkerd-proxy) proxy=$i ;; storage-initializer) storage=$i ;; *) ;; esac
      i=$((i + 1))
    done
    [ "$proxy" -ge 0 ] && [ "$storage" -ge 0 ] && [ "$proxy" -lt "$storage" ] || { echo "FALLA: linkerd-proxy no precede a storage-initializer" >&2; exit 1; }
    echo "OK: linkerd-proxy (posicion $proxy) antes de storage-initializer (posicion $storage)"
    ;;
  initializer)
    names=$("$kubectl_bin" get pod "$target" -n "$namespace" -o 'jsonpath={.spec.initContainers[*].name}')
    case " $names " in *" storage-initializer "*) echo "OK: $target tiene storage-initializer" ;; *) echo "FALLA: $target no tiene storage-initializer ($names)" >&2; exit 1 ;; esac
    ;;
  manifest)
    expected="${4:?falta el model_version_id esperado}"
    found=$("$kubectl_bin" exec "$target" -n "$namespace" -c kserve-container -- python -c "import json; print(json.load(open('/mnt/models/manifest.json'))['model_version_id'])")
    [ "$found" = "$expected" ] || { echo "FALLA: manifest.json trae $found y se esperaba $expected" >&2; exit 1; }
    echo "OK: /mnt/models/manifest.json de $target trae $found"
    ;;
  propagation)
    state="${4:?falta el estado esperado}"
    labels=$("$kubectl_bin" get deployment "$target" -n "$namespace" -o 'jsonpath={.metadata.labels.vectra\.io/serving-state}')
    exempt=$("$kubectl_bin" get deployment "$target" -n "$namespace" -o 'jsonpath={.metadata.annotations.vectra\.io/hpa-exempt}')
    echo "serving-state=$labels hpa-exempt=$exempt"
    [ "$labels" = "$state" ] && [ "$exempt" = true ] || { echo "FALLA: KServe no propago serving-state=$state y hpa-exempt=true al Deployment (metadata, lo que miran require-hpa-bounds y hpa.rego)" >&2; exit 1; }
    echo "OK: $target propaga serving-state y hpa-exempt"
    ;;
  *) echo "modo desconocido: $mode" >&2; exit 64 ;;
esac
