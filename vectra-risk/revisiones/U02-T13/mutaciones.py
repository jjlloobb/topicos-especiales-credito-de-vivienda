"""Mutaciones de las reglas de U2 (U02-T13, ronda 3, F-03 de la ronda 2).

Uso: python mutaciones.py <carpeta rules/> <promtool> > mutaciones-ronda-3.txt

Copia la carpeta de reglas con sus pruebas de promtool, aplica una mutacion a `identity-edge-rules.yaml` y corre `promtool test rules`.
`DETECTADA` = promtool falla con la regla rota (bien); `SOBREVIVE` = promtool pasa con la regla rota (falta un caso). Sale con 1 si sobrevive alguna.
Equivalente (no se incluye): quitar el `> 0` de N en la rama 2, porque un contador no es negativo y `0 > 0` nunca se cumple.
Incluye las 30 de la ronda 1 (con la rama de B11), las 13 del revisor en la ronda 2 sobre la condicion `up`, y las nuevas de B11 y de KeycloakMetricsDown.
"""

import pathlib
import shutil
import subprocess
import sys
import tempfile

src = pathlib.Path(sys.argv[1]).resolve()
promtool = str(pathlib.Path(sys.argv[2]).resolve())
orig = (src / "identity-edge-rules.yaml").read_text()
X = 'keycloak_user_events_total{event="login",client_id="security-admin-console",error=""}'
UPC = ' and on(namespace, pod) (up{job="keycloak"} offset 5m == 1)'
SEG2 = f" or (({X} > 0 unless {X} offset 5m) > (last_over_time({X}[1h] offset 5m) or {X} * 0))"
SEG3 = f" or (({X} > 0 unless {X} offset 5m){UPC})"
M = [
 ("KeycloakDown sin for", "    for: 1m\n    labels:\n      severity: SEV1\n    annotations:\n      summary: KeycloakDown", "    labels:\n      severity: SEV1\n    annotations:\n      summary: KeycloakDown"),
 ("KeycloakDown == 0 -> < 2", 'statefulset="keycloak"} == 0', 'statefulset="keycloak"} < 2'),
 ("RateLimit sin for", "    for: 2m\n", "    for: 0m\n"),
 ("RateLimit for 4m", "    for: 2m\n", "    for: 4m\n"),
 ("RateLimit sin rama redis", ' or (redis_up{job="valkey"} == 0)', ''),
 ("RateLimit valkey sin sum", 'sum(kube_statefulset_status_replicas_available{namespace="vectra-edge",statefulset=~"valkey-.+"}) == 0', 'kube_statefulset_status_replicas_available{namespace="vectra-edge",statefulset=~"valkey-.+"} == 0'),
 ("AuthDenied > 25", "* 60) > 20", "* 60) > 25"),
 ("AuthDenied > 15", "* 60) > 20", "* 60) > 15"),
 ("AuthDenied sin error!=", 'event="login",error!=""', 'event="login"'),
 ("AuthDenied for 0", "    for: 5m\n    labels:\n      severity: SEV2\n    annotations:\n      summary: AuthDeniedBurst", "    labels:\n      severity: SEV2\n    annotations:\n      summary: AuthDeniedBurst"),
 ("BreakGlass sin error=", ',error=""', ''),
 ("BG sin rama 2 (serie nueva > ultimo valor)", SEG2, ''),
 ("BG sin rama 3 (up a 1 hace 5m)", SEG3, ''),
 ("BG rama 2: sin last_over_time (solo X * 0)", f"(last_over_time({X}[1h] offset 5m) or {X} * 0)", f"({X} * 0)"),
 ("BG rama 2: sin el 'or X * 0' (serie nueva no cuenta)", f" or {X} * 0)", ")"),
 ("BG rama 2: ventana 30m", "[1h] offset 5m", "[30m] offset 5m"),
 ("BG rama 2: ventana 2h", "[1h] offset 5m", "[2h] offset 5m"),
 ("BG rama 2: sin offset 5m en last_over_time", "[1h] offset 5m", "[1h]"),
 ("BG rama 2: > en vez de >=... (>= )", f"> (last_over_time", ">= (last_over_time"),
 ("BG rama 2: X * 0 -> X * 1", f"{X} * 0)", f"{X} * 1)"),
 ("BG rama 2: max_over_time", "last_over_time(", "max_over_time("),
 ("BG rama 3: N sin '> 0'", f"(({X} > 0 unless {X} offset 5m){UPC}", f"(({X} unless {X} offset 5m){UPC}"),
 ("BG rama 2: unless offset 1m", f"unless {X} offset 5m) > (", f"unless {X} offset 1m) > ("),
 ("BG rama 2: and en vez de unless", f"{X} > 0 unless {X} offset 5m) > (", f"{X} > 0 and {X} offset 5m) > ("),
 ("BG up: sin condicion up", UPC, ''),
 ("BG up: sin offset", 'up{job="keycloak"} offset 5m == 1', 'up{job="keycloak"} == 1'),
 ("BG up: >= 0", 'offset 5m == 1)', 'offset 5m >= 0)'),
 ("BG up: == 0", 'offset 5m == 1)', 'offset 5m == 0)'),
 ("BG up: on(namespace)", 'and on(namespace, pod)', 'and on(namespace)'),
 ("BG up: on(pod)", 'and on(namespace, pod)', 'and on(pod)'),
 ("BG up: on()", 'and on(namespace, pod)', 'and on()'),
 ("BG up: otro job", 'up{job="keycloak"}', 'up{job="keycloak-x"}'),
 ("BG up: sin job", 'up{job="keycloak"}', 'up'),
 ("BG up: offset 1m", 'up{job="keycloak"} offset 5m', 'up{job="keycloak"} offset 1m'),
 ("BG up: offset 10m", 'up{job="keycloak"} offset 5m', 'up{job="keycloak"} offset 10m'),
 ("BG up: or en vez de and", ') and on(namespace, pod) (up', ') or on(namespace, pod) (up'),
 ("BG up: unless X offset 1m (rama 3)", f"unless {X} offset 5m){UPC}", f"unless {X} offset 1m){UPC}"),
 ("BG increase [1m]", 'error=""}[5m])', 'error=""}[1m])'),
 ("BG increase [10m]", 'error=""}[5m])', 'error=""}[10m])'),
 ("BG sin rama increase", f"(increase({X}[5m]) > 0) or ", ''),
 ("BG increase > 1", f"increase({X}[5m]) > 0)", f"increase({X}[5m]) > 1)"),
 ("BreakGlass realm vectra", 'client_id="security-admin-console",error=""}[5m]', 'client_id="security-admin-console",error="",realm="vectra"}[5m]'),
 ("BreakGlass sin client", f'increase({X}[5m])', 'increase(keycloak_user_events_total{event="login",error=""}[5m])'),
 ("BreakGlass event client_login", f'increase({X}[5m])', f'increase({X.replace("login", "client_login", 1)}[5m])'),
 ("BreakGlass con for 5m", "      severity: SEV1\n    annotations:\n      summary: BreakGlassLogin", "      severity: SEV1\n    annotations:\n      summary: BreakGlassLogin\n    for: 5m"),
 ("KeycloakMetricsDown sin absent", ' or absent(up{job="keycloak"})', ''),
 ("KeycloakMetricsDown sin == 0", '(up{job="keycloak"} == 0) or', '(up{job="keycloak"} == 1) or'),
 ("KeycloakMetricsDown == 0 -> < 1 (igual)", '(up{job="keycloak"} == 0) or', '(up{job="keycloak"} > 0) or'),
 ("KeycloakMetricsDown sin job", 'up{job="keycloak"} == 0) or', 'up == 0) or'),
 ("KeycloakMetricsDown absent otro job", 'absent(up{job="keycloak"})', 'absent(up{job="keycloak-x"})'),
 ("KeycloakMetricsDown sin for", "    for: 5m\n    labels:\n      severity: SEV2\n    annotations:\n      summary: KeycloakMetricsDown", "    labels:\n      severity: SEV2\n    annotations:\n      summary: KeycloakMetricsDown"),
 ("KeycloakMetricsDown for 1m", "    for: 5m\n    labels:\n      severity: SEV2\n    annotations:\n      summary: KeycloakMetricsDown", "    for: 1m\n    labels:\n      severity: SEV2\n    annotations:\n      summary: KeycloakMetricsDown"),
 ("KeycloakMetricsDown for 10m", "    for: 5m\n    labels:\n      severity: SEV2\n    annotations:\n      summary: KeycloakMetricsDown", "    for: 10m\n    labels:\n      severity: SEV2\n    annotations:\n      summary: KeycloakMetricsDown"),
 ("KeycloakMetricsDown SEV1", "      severity: SEV2\n    annotations:\n      summary: KeycloakMetricsDown", "      severity: SEV1\n    annotations:\n      summary: KeycloakMetricsDown"),
 ("RealmDrift >= 0", 'vectra_realm_drift{job="realm-drift"} > 0', 'vectra_realm_drift{job="realm-drift"} >= 0'),
 ("RoleConflict [5m]", "vectra_role_conflict_total[15m]", "vectra_role_conflict_total[5m]"),
 ("RoleConflict for 0", "    for: 5m\n    labels:\n      severity: SEV2\n    annotations:\n      summary: RoleConflict", "    labels:\n      severity: SEV2\n    annotations:\n      summary: RoleConflict"),
 ("Ldap [15m]", "vectra_ldap_connection_failures_total[5m]", "vectra_ldap_connection_failures_total[15m]"),
 ("Ldap for 0", "    for: 5m\n    labels:\n      severity: SEV2\n    annotations:\n      summary: LdapUnavailable", "    labels:\n      severity: SEV2\n    annotations:\n      summary: LdapUnavailable"),
 ("Gateway > 20", ")) > 5'", ")) > 20'"),
 ("Gateway > 0", ")) > 5'", ")) > 0'"),
 ("Gateway for 5m", "    for: 15m\n", "    for: 5m\n"),
 ("SigningAge > 79d", "> 6912000", "> 6825600"),
 ("SigningAge > 81d", "> 6912000", "> 6998400"),
 ("SigningAge for 0", "    for: 1h\n", ""),
 ("RealmDriftStale 25h", "> 93600", "> 90000"),
 ("RealmDriftStale 27h", "> 93600", "> 97200"),
 ("SigningStale 2h", "> 10800", "> 7200"),
 ("SigningStale 4h", "> 10800", "> 14400"),
 ("severity KeycloakDown SEV2", "      severity: SEV1\n    annotations:\n      summary: KeycloakDown", "      severity: SEV2\n    annotations:\n      summary: KeycloakDown"),
]
survivors = 0
# Sin mutar, las pruebas deben pasar: si no, todas las mutaciones saldrian "DETECTADAS" sin significar nada.
base = subprocess.run([promtool, "test", "rules", *sorted(str(p) for p in (src / "tests").glob("*.yaml"))], capture_output=True, text=True, cwd=src / "tests")
print(f"{'PASA' if base.returncode == 0 else 'FALLA'} | sin mutar (linea base)", flush=True)
if base.returncode:
    sys.exit(2)
for name, old, new in M:
    assert orig.count(old) >= 1, f"la mutacion no aplica: {name}"
    with tempfile.TemporaryDirectory() as d:
        work = pathlib.Path(d) / "rules"
        shutil.copytree(src, work)
        (work / "identity-edge-rules.yaml").write_text(orig.replace(old, new, 1))
        tests = sorted(str(p) for p in (work / "tests").glob("*.yaml"))
        r = subprocess.run([promtool, "test", "rules", *tests], capture_output=True, text=True, cwd=work / "tests")
    survivors += r.returncode == 0
    print(f"{'DETECTADA' if r.returncode else 'SOBREVIVE'} | {name}", flush=True)
print(f"{len(M)} mutaciones, {survivors} sobreviven")
sys.exit(1 if survivors else 0)
