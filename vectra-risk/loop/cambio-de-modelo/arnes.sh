#!/usr/bin/env bash
# Arnés de la prueba de cambio de modelo, casos 1 a 6.
# Uso: arnes.sh <tarea> <sha-candidato>
# Corre los criterios de la tarea sobre el candidato y luego el oráculo:
# las pruebas finales del PR de la tarea, puestas sobre la implementación candidata.
set -uo pipefail
tarea=$1 sha=$2
repo=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
declare -A BASE=([T01]=737b456 [T02]=650823f [T03]=f44ba83 [T04]=650823f [T05]=f44ba83 [T06]=f44ba83)
declare -A FINAL=([T01]=0487d54 [T02]=0dce4e7 [T03]=2843b84 [T04]=2818b41 [T05]=d0e3dff [T06]=d6822a4)
ca() {
  case $tarea in
    T01) uv run pytest platform/tests/test_upstream_charts.py -q -k grafana_does_not_preinstall_plugins &&
         uv run pytest platform/tests/test_upstream_charts.py -q && uv run ruff check platform ;;
    T02) salida=$(bash platform/data/minio/tests/ilm_idempotente.sh 2>&1) && grep -q 'reglas tras 2 pasadas: 1' <<<"$salida" &&
         uv run pytest platform/tests/test_upstream_charts.py -q ;;
    T03) uv run pytest platform/network/tests -q -k f130 &&
         uv run python platform/network/generate.py --check && uv run pytest platform/network/tests -q ;;
    T04) uv run pytest platform/kind/tests -q -k grafana_token_without_external_secret &&
         uv run pytest platform/kind/tests -q -k grafana_token_stops_port_forward ;;
    T05) (cd platform/observability/rules/tests && ../../../.tools/bin/promtool test rules *.yaml) &&
         platform/.tools/bin/promtool check rules platform/observability/rules/platform-rules.yaml &&
         uv run pytest platform/tests/test_ci.py platform/tests/test_platform.py -q ;;
    T06) uv run pytest platform/observability/grafana/tests -q -k retries_on_timeout &&
         uv run pytest platform/observability/grafana/tests -q ;;
  esac
}
wt=$(mktemp -d "${TMPDIR:-/tmp}/cm-$tarea-XXXX")
git -C "$repo" worktree add -q --detach "$wt" "$sha"
ln -s "$repo/vectra-risk/platform/.tools" "$wt/vectra-risk/platform/.tools"
ln -s "$repo/vectra-risk/platform/.charts" "$wt/vectra-risk/platform/.charts"
cd "$wt/vectra-risk"
export UV_OFFLINE=1 UV_FROZEN=1
ca >/dev/null 2>&1; criterios=$?
mapfile -t pruebas < <(git diff --name-only "${BASE[$tarea]}" "${FINAL[$tarea]}" -- . | grep -E '/tests/|test_' | grep -v -E '^vectra-risk/(bitacoras|revisiones)/' | sed 's#^vectra-risk/##')
git checkout -q "${FINAL[$tarea]}" -- "${pruebas[@]}"
ca >/dev/null 2>&1; oraculo=$?
cd "$repo"
rm "$wt/vectra-risk/platform/.tools" "$wt/vectra-risk/platform/.charts"
git worktree remove --force "$wt"
echo "$tarea $sha criterios=$([ $criterios = 0 ] && echo pasa || echo falla) oraculo=$([ $oraculo = 0 ] && echo pasa || echo falla) pruebas_oraculo=${#pruebas[@]}"
