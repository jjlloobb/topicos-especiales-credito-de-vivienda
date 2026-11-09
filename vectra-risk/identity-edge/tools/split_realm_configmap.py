"""Separa del render de kind el ConfigMap del realm (U02-T19, arreglo del CI KSV-0109, decision del usuario, PR 85).

Lee el render de `helm template` por la entrada estandar y escribe dos archivos: el render sin el ConfigMap `keycloak-config-cli-realm`
(`keycloak.yaml`) y ese ConfigMap solo (`config-cli-realm.yaml`). El segundo lo omite Trivy (`skip-files`, falso positivo KSV-0109 de las
claves `revokeRefreshToken` y `client_credentials.use_refresh_token`; decision T1); `keycloak.yaml` se sigue escaneando entero.

Uso: helm template … | python split_realm_configmap.py <keycloak.yaml> <config-cli-realm.yaml>
"""

import sys
from pathlib import Path

NAME = "name: keycloak-config-cli-realm"


def split(text: str) -> tuple[str, str]:
    """(resto, ConfigMap del realm). Los documentos se separan por las lineas `---`; el orden y el texto del resto no cambian."""
    chunks = text.split("\n---\n")
    realm = [c for c in chunks if "kind: ConfigMap" in c and NAME in c]
    if len(realm) != 1:
        raise SystemExit(f"se esperaba exactamente un ConfigMap {NAME}, hay {len(realm)}")
    rest = "\n---\n".join(c for c in chunks if c is not realm[0])
    document = realm[0].strip("\n")
    return rest, f"---\n{document}\n"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write(__doc__ or "")
        return 2
    rest, realm = split(sys.stdin.read())
    Path(argv[1]).write_text(rest, encoding="utf-8")
    Path(argv[2]).write_text(realm, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
