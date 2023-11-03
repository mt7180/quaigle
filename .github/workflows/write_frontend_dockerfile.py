import sys
import re


def rewrite_frontend_dockerfile(new_backend_ip):
    new_backend_url = f"http://{new_backend_ip}:8000"
    file_changed = "false"
    with open("Dockerfile", "r") as file:
        docker_file = file.read()
    match = re.search(r"ENV (\w+)", docker_file)
    if match:
        old_backend_url = match.group(1)
        docker_file.replace(old_backend_url, new_backend_url, 1)
        with open("Dockerfile", "w") as file:
            file.write(docker_file)
            file_changed = "true"
    # set step output in gh actions
    print(f"::set-output name=file_changed::{file_changed}")


if __name__ == "__main__":
    new_backend_ip = sys.argv[1]
    rewrite_frontend_dockerfile(new_backend_ip)
