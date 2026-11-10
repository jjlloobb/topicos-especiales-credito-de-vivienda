#!/usr/bin/env bash
# Imprime el cuerpo JSON de `POST /v1/models/{id}/freeze` (`FreezeContext`, contrato F27) para el escenario 7. En produccion lo arma el
# `bias-monitoring-job`; en kind, con U9 ausente, lo arma este script con los mismos modelos de `vectra_contracts`.
#
#   freeze-cuerpo.sh <model_version_id>
set -euo pipefail

if [ "${1:-}" = "--dry-run" ]; then echo "dry-run: FreezeContext de ejemplo (vectra_contracts) para la version dada"; exit 0; fi
modelo="${1:?uso: freeze-cuerpo.sh <model_version_id>}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
exec uv run --project "$root" python -c '
import sys
from datetime import date, datetime, timezone
from vectra_contracts.models.monitoring import AffectedVolume, DisparityResult, FreezeContext

modelo = sys.argv[1]
despues = DisparityResult(population="modelo", model_version_id=modelo, window_from=date(2026, 11, 1), window_to=date(2026, 11, 8), attributes=[])
print(FreezeContext(
    model_version_id=modelo, computed_at=datetime.now(timezone.utc), threshold_pp="5.0000", n_min=30, window_days=30, schedule="daily",
    stale_after_s=86400, library_version="kind-demo", window_start=date(2026, 10, 10), before="sin_datos", after=despues, last_7_days="sin_datos",
    trigger_attribute="sexo", implicated=[], affected_volume=AffectedVolume(total=10, favorable=5), truncated=False,
).model_dump_json())
' "$modelo"
