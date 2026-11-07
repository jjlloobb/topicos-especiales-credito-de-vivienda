#!/usr/bin/env bash
# Instala helm, kyverno, conftest, promtool, actionlint, hadolint, kubeconform, egctl y k6 en platform/.tools/bin, comprobando el SHA-256 publicado.
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
fetch "https://github.com/hadolint/hadolint/releases/download/$HADOLINT_VERSION" hadolint-linux-x86_64 checksums.sha256
install -m 0755 "$work/hadolint-linux-x86_64" "$bin/hadolint"
fetch "https://github.com/yannh/kubeconform/releases/download/$KUBECONFORM_VERSION" kubeconform-linux-amd64.tar.gz CHECKSUMS
tar -xzf "$work/kubeconform-linux-amd64.tar.gz" -C "$bin" kubeconform
# egctl: el release no publica un archivo de checksums, asi que el sha256 del tarball esta fijado en tools.env (U02-T10, W7).
curl -fsSL -o "$work/egctl.tar.gz" "https://github.com/envoyproxy/gateway/releases/download/$EGCTL_VERSION/egctl_${EGCTL_VERSION}_linux_amd64.tar.gz"
echo "$EGCTL_SHA256  $work/egctl.tar.gz" | sha256sum -c -
mkdir "$work/egctl" && tar -xzf "$work/egctl.tar.gz" -C "$work/egctl"
install -m 0755 "$(find "$work/egctl" -type f -name egctl | head -n 1)" "$bin/egctl"
# k6 (U02-T15, J2): el tarball se comprueba contra el sha256 fijado en tools.env y contra k6-<version>-checksums.txt del release.
k6_tar="k6-${K6_VERSION}-linux-amd64.tar.gz"
fetch "https://github.com/grafana/k6/releases/download/$K6_VERSION" "$k6_tar" "k6-${K6_VERSION}-checksums.txt"
echo "$K6_SHA256  $work/$k6_tar" | sha256sum -c -
tar -xzf "$work/$k6_tar" -C "$bin" --strip-components=1 "k6-${K6_VERSION}-linux-amd64/k6"
