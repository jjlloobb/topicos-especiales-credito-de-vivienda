#!/usr/bin/env bash
# Imprime en stdout un access token del realm `vectra` de kind. Nada mas: ni lo exporta, ni lo escribe en un archivo, ni lo pone en un argumento.
# Se usa en una tuberia (`token.sh cro-2 | llamar.sh ...`), justo antes de la llamada: `accessTokenLifespan` es de 300 s y el step-up de MFA, de 15 min.
#
#   token.sh <usuario>                      persona sintetica con MFA (cro-2, cro-1, ingeniero-1, cumplimiento-1...)
#   token.sh --servicio <cliente> [scope]   cliente de servicio con private_key_jwt (scoring-service, bias-monitoring-job...)
#   token.sh --dry-run ...                  dice que haria y sale; no toca la red
#
# Credenciales: las del operador, ya en el entorno de su shell por `source "$VECTRA_E2E_KEYS_DIR/env"` (platform/kind/seed-vault.sh identity):
# SYNTH_<USUARIO>_{PASSWORD,TOTP_SEED}, VECTRA_E2E_BASE_URL, VECTRA_E2E_CA_BUNDLE y VECTRA_E2E_CLIENT_KEYS_DIR. Nada va en este archivo.
set -euo pipefail

dry=0
if [ "${1:-}" = "--dry-run" ]; then dry=1; shift; fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export PYTHONPATH="$root/identity-edge/tests/e2e${PYTHONPATH:+:$PYTHONPATH}"

if [ "${1:-}" = "--servicio" ]; then
  cliente="${2:?uso: token.sh --servicio <cliente> [scope]}"
  scope="${3:-}"
  if [ "$dry" = 1 ]; then echo "dry-run: token de servicio de $cliente (scope: ${scope:-ninguno}) con e2e_support.service_token"; exit 0; fi
  exec uv run --project "$root" python -c '
import sys
from e2e_support import gateway_client, service_token
print(service_token(gateway_client(), sys.argv[1], sys.argv[2] or None))
' "$cliente" "$scope"
fi

usuario="${1:?uso: token.sh <usuario> | --servicio <cliente> [scope]}"
if [ "$dry" = 1 ]; then echo "dry-run: token de $usuario con e2e_support.user_access_token (login con MFA)"; exit 0; fi
exec uv run --project "$root" python -c '
import sys
from e2e_support import user_access_token
print(user_access_token(None, sys.argv[1]))
' "$usuario"
