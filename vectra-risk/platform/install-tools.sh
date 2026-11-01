#!/usr/bin/env bash
# Instala helm, kyverno, conftest, promtool y actionlint en platform/.tools/bin, comprobando el SHA-256 publicado.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$here/tools.env"
bin="$here/.tools/bin"; mkdir -p "$bin"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
fetch() { # url-base archivo checksums
  curl -fsSL -o "$work/$2" "$1/$2"
  curl -fsSL -o "$work/$3" "$1/$3"
  (cd "$work" && grep " \*\?$2\$" "$3" | sha256sum -c -)
}
fetch "https://get.helm.sh" "helm-${HELM_VERSION}-linux-amd64.tar.gz" "helm-${HELM_VERSION}-linux-amd64.tar.gz.sha256sum"
tar -xzf "$work/helm-${HELM_VERSION}-linux-amd64.tar.gz" -C "$bin" --strip-components=1 linux-amd64/helm
fetch "https://github.com/kyverno/kyverno/releases/download/$KYVERNO_VERSION" "kyverno-cli_${KYVERNO_VERSION}_linux_x86_64.tar.gz" checksums.txt
tar -xzf "$work/kyverno-cli_${KYVERNO_VERSION}_linux_x86_64.tar.gz" -C "$bin" kyverno
fetch "https://github.com/open-policy-agent/conftest/releases/download/$CONFTEST_VERSION" "conftest_${CONFTEST_VERSION#v}_Linux_x86_64.tar.gz" checksums.txt
tar -xzf "$work/conftest_${CONFTEST_VERSION#v}_Linux_x86_64.tar.gz" -C "$bin" conftest
fetch "https://github.com/prometheus/prometheus/releases/download/$PROMETHEUS_VERSION" "prometheus-${PROMETHEUS_VERSION#v}.linux-amd64.tar.gz" sha256sums.txt
tar -xzf "$work/prometheus-${PROMETHEUS_VERSION#v}.linux-amd64.tar.gz" -C "$bin" --strip-components=1 "prometheus-${PROMETHEUS_VERSION#v}.linux-amd64/promtool"
fetch "https://github.com/rhysd/actionlint/releases/download/$ACTIONLINT_VERSION" "actionlint_${ACTIONLINT_VERSION#v}_linux_amd64.tar.gz" "actionlint_${ACTIONLINT_VERSION#v}_checksums.txt"
tar -xzf "$work/actionlint_${ACTIONLINT_VERSION#v}_linux_amd64.tar.gz" -C "$bin" actionlint
