from __future__ import annotations
import shutil
import subprocess
import time
from pathlib import Path
from typing import Iterable, Optional

def which_container_runtime() -> tuple[list[str], list[str]]:
    # returns (compose_cmd, container_cmd)
    if shutil.which("podman-compose"):
        return (["podman-compose"], ["podman"])
    if shutil.which("podman"):
        return (["podman", "compose"], ["podman"])
    if shutil.which("docker"):
        return (["docker", "compose"], ["docker"])
    raise RuntimeError("podman or docker not found on PATH")

def sh(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, check=check)

def compose_up(compose_file: Path, *extra: str) -> None:
    comp, _ = which_container_runtime()
    args = [*comp, "-f", str(compose_file), "up", "-d", *extra]
    print(" ".join(args))
    subprocess.run(args, check=True)

def compose_down(compose_file: Path, remove_orphans: bool = True) -> None:
    comp, _ = which_container_runtime()
    args = [*comp, "-f", str(compose_file), "down"]
    if remove_orphans:
        args.append("--remove-orphans")
    print(" ".join(args))
    subprocess.run(args, check=True)

def container_logs(name: str, follow: bool = True) -> None:
    _, ctr = which_container_runtime()
    args = [*ctr, "logs"]
    if follow:
        args.append("-f")
    args.append(name)
    subprocess.run(args)

def ensure_network(name: str) -> None:
    _, ctr = which_container_runtime()
    subprocess.run([*ctr, "network", "inspect", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if subprocess.call([*ctr, "network", "inspect", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        subprocess.run([*ctr, "network", "create", name], check=True)

def container_exists(name: str) -> bool:
    _, ctr = which_container_runtime()
    out = subprocess.run([*ctr, "ps", "-a", "--format", "{{.Names}}"], capture_output=True, text=True, check=True).stdout
    return any(line.strip() == name for line in out.splitlines())

def http_up(url: str, tries: int = 60, timeout: float = 2.0) -> bool:
    import requests
    for _ in range(tries):
        try:
            r = requests.get(url, timeout=timeout)
            if r.ok:
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False

def write_if_missing(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content)
    return path

def ensure_vm_if_podman() -> None:
    # start podman machine on mac or windows if needed
    if not shutil.which("podman"):
        return
    try:
        state = subprocess.check_output("podman machine inspect --format '{{.State}}'", shell=True).decode().strip()
        if state != "running":
            sh("podman machine start")
    except subprocess.CalledProcessError:
        pass
