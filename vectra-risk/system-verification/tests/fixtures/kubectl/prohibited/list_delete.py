import subprocess

subprocess.run(["kubectl", "-n", "vectra-app", "delete", "pod", "x"], check=True)
