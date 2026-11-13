import subprocess

subprocess.run(["kubectl", "--context", "kind-vectra", "-n", "vectra-app", "get", "pods"], check=True)
