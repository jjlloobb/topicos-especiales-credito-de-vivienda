#!/usr/bin/env bash
# Imprime el cuerpo JSON de `POST /v1/models` (`ModelRegistration`) para un paquete de U5 ya subido al model-store, con la convencion de rutas
# `s3://model-store/<model_version_id>/<archivo>` (la que lee `S3PackageStore`, F47). Los SHA-256 salen del manifiesto del paquete local y de
# los bytes de `manifest.json`: governance los vuelve a calcular sobre lo que lee del model-store (BR-U4-06).
#
#   registro-cuerpo.sh <directorio-del-paquete>      p. ej. reference-model/.out/package
set -euo pipefail

if [ "${1:-}" = "--dry-run" ]; then echo "dry-run: ModelRegistration de un paquete de U5 (artifact_format xgboost_json)"; exit 0; fi
paquete="${1:?uso: registro-cuerpo.sh <directorio-del-paquete>}"
exec python3 -c '
import hashlib, json, sys
from pathlib import Path

paquete = Path(sys.argv[1])
manifiesto = paquete / "manifest.json"
datos = json.loads(manifiesto.read_text(encoding="utf-8"))
mv = datos["model_version_id"]
sha = {f["name"]: f["sha256"] for f in datos["files"]}
base = f"s3://model-store/{mv}/"
print(json.dumps({
    "artifact_uri": base + "predictor.json", "artifact_format": "xgboost_json", "artifact_sha256": sha["predictor.json"],
    "explainer_uri": base + "explainer.json", "explainer_sha256": sha["explainer.json"],
    "manifest_uri": base + "manifest.json", "manifest_sha256": hashlib.sha256(manifiesto.read_bytes()).hexdigest(),
}))
' "$paquete"
