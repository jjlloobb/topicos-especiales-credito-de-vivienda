import subprocess
import sys

NS = "vectra-app"
VERB = sys.argv[1]
subprocess.run(["kubectl", "-n", NS, VERB, "pod", "x"], check=True)
