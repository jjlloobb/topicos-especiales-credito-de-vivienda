#!/usr/bin/env bash
# Califica el ESTADO FINAL del clúster, no los comandos que usaste.
# Salida: líneas [PASA]/[FALLA] por comprobación, puntaje y código de salida
# 0 si aprobaste (66 o más de 100), 1 si no.
set -uo pipefail

command -v kubectl >/dev/null || { echo "ERROR: falta kubectl"; exit 2; }
command -v docker  >/dev/null || { echo "ERROR: falta docker";  exit 2; }
command -v curl    >/dev/null || { echo "ERROR: falta curl";    exit 2; }
kubectl get nodes >/dev/null 2>&1 || { echo "ERROR: kubectl no alcanza el clúster"; exit 2; }

ESPERA=20            # segundos que debe seguir ausente el Pod estático
GRACIA=30            # segundos máximos para que el kubelet retire el Pod tras borrar el manifiesto
P1=30; P2=40; P3=30  # puntos por problema; todo o nada
APRUEBA=66
OK=0; TOTAL=0; PROB_OK=1

# chequeo "descripción" comando...  -> imprime PASA/FALLA y marca el problema
chequeo() {
  local desc=$1; shift
  if "$@" >/dev/null 2>&1; then echo "  [PASA]  $desc"; else echo "  [FALLA] $desc"; PROB_OK=0; fi
}
cierra() {  # $1 = puntos del problema
  TOTAL=$((TOTAL+$1))
  if [ "$PROB_OK" = 1 ]; then OK=$((OK+$1)); echo "  => $1/$1 puntos"; else echo "  => 0/$1 puntos"; fi
  PROB_OK=1
}

# ---------- instantánea inicial (antes de la espera) ----------
NODOS=$(kubectl get nodes -o jsonpath='{.items[*].metadata.name}')
manifiesto_en_nodos() {
  local n
  for n in $NODOS; do
    docker exec "$n" test -e /etc/kubernetes/manifests/vigia.yaml 2>/dev/null && return 0
  done
  return 1
}
pod_vigia() { kubectl -n examen1 get pods -o name 2>/dev/null | grep -qE '^pod/vigia'; }
sin_pod_vigia() { ! pod_vigia; }
sin_manifiesto() { ! manifiesto_en_nodos; }
reinicios() {  # suma de restartCount de los pods vivos de reporte
  kubectl -n examen2 get pods -l app=reporte -o json 2>/dev/null |
    python3 -c '
import json,sys
d=json.load(sys.stdin)
t=0
for p in d["items"]:
    if p["metadata"].get("deletionTimestamp"): continue
    for c in p["status"].get("containerStatuses",[]): t+=c["restartCount"]
print(t)' 2>/dev/null
}
A_REI=$(reinicios)

# ---------- Problema 1 ----------
echo "Problema 1: Pod estático (${P1} puntos)"
espera_ausente() {  # el Pod debe desaparecer (hasta GRACIA s) y seguir ausente ESPERA s más
  local t=0
  while pod_vigia; do
    [ "$t" -ge "$GRACIA" ] && return 1
    sleep 2; t=$((t+2))
  done
  sleep "$ESPERA"
  sin_pod_vigia
}
chequeo "La causa raíz del Pod ya no existe en ningún nodo" sin_manifiesto
chequeo "El Pod vigia desaparece y sigue ausente ${ESPERA} s después" espera_ausente
cierra $P1

# ---------- Problema 2 ----------
echo "Problema 2: Memoria (${P2} puntos)"
dep() { kubectl -n examen2 get deploy reporte -o jsonpath="$1" 2>/dev/null; }
# memoria -> MiB (soporta Ki, Mi, Gi, K, M, G; sin sufijo = bytes)
a_mib() {
  python3 - "$1" <<'PY'
import sys,re
v=sys.argv[1]
m=re.fullmatch(r"([0-9.]+)([A-Za-z]*)",v) if v else None
if not m: print(0); sys.exit()
f={"":1,"Ki":1024,"Mi":1024**2,"Gi":1024**3,"K":1e3,"k":1e3,"M":1e6,"G":1e9}.get(m.group(2))
print(0 if f is None else int(float(m.group(1))*f/1024/1024))
PY
}
LIM_MIB=$(a_mib "$(dep '{.spec.template.spec.containers[0].resources.limits.memory}')")
MB=$(dep '{.spec.template.spec.containers[0].env[?(@.name=="MB")].value}')
listo() { [ "$(dep '{.status.readyReplicas}')" = 1 ]; }
# Al menos un Pod vivo de reporte, y todos Running y Ready (si no, las comprobaciones
# de estabilidad no pueden pasar: un Pod en crash backoff no reinicia "durante la espera").
pods_sanos() {
  kubectl -n examen2 get pods -l app=reporte -o json 2>/dev/null |
    python3 -c '
import json,sys
d=json.load(sys.stdin)
v=[p for p in d["items"] if not p["metadata"].get("deletionTimestamp")]
ok=len(v)>=1 and all(p["status"].get("phase")=="Running" and
  any(c["type"]=="Ready" and c["status"]=="True" for c in p["status"].get("conditions",[])) for p in v)
sys.exit(0 if ok else 1)' 2>/dev/null
}
sin_oom() {
  pods_sanos || return 1
  ! kubectl -n examen2 get pods -l app=reporte -o jsonpath='{range .items[*]}{.status.containerStatuses[*].lastState.terminated.reason}{"\n"}{end}' 2>/dev/null | grep -q OOMKilled
}
estable() { local ahora; pods_sanos || return 1; ahora=$(reinicios); [ -n "$A_REI" ] && [ "$A_REI" = "$ahora" ]; }
chequeo "El Deployment reporte tiene 1 réplica Ready" listo
chequeo "La carga no cambió: sigue reservando 150 MB (no vale bajar MB)" test "$MB" = 150
chequeo "Los recursos del contenedor alcanzan para la carga (memoria >= 160 MiB)" test "$LIM_MIB" -ge 160
chequeo "La memoria pedida es razonable (<= 1024 MiB, no vale pedir medio nodo)" test "$LIM_MIB" -le 1024
chequeo "Ningún Pod vivo de reporte reinició durante la espera" estable
chequeo "Ningún Pod vivo de reporte tiene terminaciones forzosas en su historial" sin_oom
cierra $P2

# ---------- Problema 3 ----------
echo "Problema 3: Red (${P3} puntos)"
IP=$(kubectl get nodes -o jsonpath='{.items[-1:].status.addresses[?(@.type=="InternalIP")].address}')
http() {
  local i code
  for i in 1 2 3; do
    code=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "http://${IP}:30080/" 2>/dev/null)
    [ "$code" = 200 ] && return 0
    sleep 2
  done
  return 1
}
sin_politica() { ! kubectl -n examen3 get networkpolicy default-deny-all >/dev/null 2>&1; }
web_listo() { [ "$(kubectl -n examen3 get deploy web -o jsonpath='{.status.readyReplicas}' 2>/dev/null)" = 1 ]; }
svc_ok() { [ "$(kubectl -n examen3 get svc web -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null)" = 30080 ]; }
chequeo "La causa raíz del bloqueo ya no existe" sin_politica
chequeo "El Deployment web sigue con 1 réplica Ready" web_listo
chequeo "El Service web sigue siendo NodePort 30080" svc_ok
chequeo "GET http://${IP}:30080/ desde el host responde 200" http
cierra $P3

echo
echo "Resultado: ${OK}/${TOTAL} puntos (se aprueba con ${APRUEBA})"
[ "$OK" -ge "$APRUEBA" ]
