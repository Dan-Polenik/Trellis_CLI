import os
import subprocess
import time
import json
from pathlib import Path

import typer
import requests

app = typer.Typer(help="trellis: local pulsar sandbox CLI (podman-based)")

# defaults (override via env)
PULSAR_NAME = os.getenv("PULSAR_NAME", "pulsar")
PM_NAME = os.getenv("PM_NAME", "pulsar-manager")
PROM_NAME = os.getenv("PROM_NAME", "prom")
GRAF_NAME = os.getenv("GRAF_NAME", "graf")
NET_NAME = os.getenv("NET_NAME", "pulsar-net")

PULSAR_BIN_PORT = int(os.getenv("PULSAR_BIN_PORT", "6650"))
PULSAR_HTTP_PORT = int(os.getenv("PULSAR_HTTP_PORT", "8080"))
PM_UI_PORT = int(os.getenv("PM_UI_PORT", "9527"))
PM_API_PORT = int(os.getenv("PM_API_PORT", "7750"))
PROM_PORT = int(os.getenv("PROM_PORT", "9090"))
GRAF_PORT = int(os.getenv("GRAF_PORT", "3000"))

PULSAR_CLUSTER_LABEL = os.getenv("PULSAR_CLUSTER_LABEL", "standalone")

DATA_DIR = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "trellis"
PROM_DIR = DATA_DIR / "prom"
PROM_CFG = PROM_DIR / "prometheus.yml"

def sh(*args: str, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(" ".join(args), shell=True, check=check)

def http_up(url: str, tries: int = 60, timeout: float = 2.0) -> bool:
    for _ in range(tries):
        try:
            r = requests.get(url, timeout=timeout)
            if r.ok:
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False

def ensure_podman_vm():
    # mac/windows podman uses a VM; if present, make sure it's running
    try:
        out = subprocess.check_output("podman machine inspect --format '{{.State}}'", shell=True).decode().strip()
        if out != "running":
            typer.echo("starting podman machine…")
            sh("podman machine start")
    except subprocess.CalledProcessError:
        # linux or older setups—ignore
        pass

def ensure_prom_cfg():
    PROM_DIR.mkdir(parents=True, exist_ok=True)
    if not PROM_CFG.exists():
        PROM_CFG.write_text(f"""global:
  scrape_interval: 15s
  external_labels:
    cluster: {PULSAR_CLUSTER_LABEL}
scrape_configs:
  - job_name: broker
    metrics_path: /metrics
    static_configs:
      - targets: [ "host.containers.internal:{PULSAR_HTTP_PORT}" ]
""")

@app.command()
def start():
    """start pulsar, pulsar-manager, prometheus, grafana (pulsar dashboards)"""
    ensure_podman_vm()
    ensure_prom_cfg()

    # network
    sh(f"podman network inspect {NET_NAME} >/dev/null 2>&1 || podman network create {NET_NAME}", check=False)

    # pulsar (standalone)
    sh(f"podman rm -f {PULSAR_NAME} >/dev/null 2>&1 || true", check=False)
    sh(
        f"podman run -d --name {PULSAR_NAME} --network {NET_NAME} "
        f"-p {PULSAR_BIN_PORT}:6650 -p {PULSAR_HTTP_PORT}:8080 "
        f"-e PULSAR_STANDALONE_USE_ZOOKEEPER=1 "
        f"-e PULSAR_PREFIX_exposeTopicLevelMetricsInPrometheus=true "
        f"-e PULSAR_PREFIX_exposeManagedLedgerMetricsInPrometheus=true "
        f"-e PULSAR_PREFIX_exposeBookkeeperClientStatsInPrometheus=true "
        f"-e PULSAR_PREFIX_exposeProducerAndConsumerMetricsInPrometheus=true "
        f"docker.io/apachepulsar/pulsar:latest "
        f"bash -lc \"bin/apply-config-from-env.py conf/standalone.conf && bin/pulsar standalone\""
    )
    ok = http_up(f"http://localhost:{PULSAR_HTTP_PORT}/admin/v2/brokers/health", tries=60)
    typer.echo("pulsar http: " + ("up" if ok else "not up yet (continuing)"))

    # pulsar manager
    sh(f"podman rm -f {PM_NAME} >/dev/null 2>&1 || true", check=False)
    sh(
        f"podman run -d --name {PM_NAME} --network {NET_NAME} "
        f"-p {PM_UI_PORT}:9527 -p {PM_API_PORT}:7750 "
        f"-e SPRING_CONFIGURATION_FILE=/pulsar-manager/pulsar-manager/application.properties "
        f"docker.io/apachepulsar/pulsar-manager:latest"
    )
    http_up(f"http://localhost:{PM_API_PORT}/actuator/health", tries=60)

    # prometheus
    sh(f"podman rm -f {PROM_NAME} >/dev/null 2>&1 || true", check=False)
    sh(
        f"podman run -d --name {PROM_NAME} --network {NET_NAME} "
        f"-p {PROM_PORT}:9090 "
        f"-v \"{PROM_CFG}\":/etc/prometheus/prometheus.yml:ro "
        f"docker.io/prom/prometheus:latest"
    )

    # grafana (streamnative dashboards)
    sh(f"podman rm -f {GRAF_NAME} >/dev/null 2>&1 || true", check=False)
    sh(
        f"podman run -d --name {GRAF_NAME} --network {NET_NAME} "
        f"-p {GRAF_PORT}:3000 "
        f"-e PULSAR_PROMETHEUS_URL=\"http://host.containers.internal:{PROM_PORT}\" "
        f"-e PULSAR_CLUSTER=\"{PULSAR_CLUSTER_LABEL}\" "
        f"docker.io/streamnative/apache-pulsar-grafana-dashboard:latest"
    )

    typer.echo(f"urls:\n"
               f"  pulsar admin api:   http://localhost:{PULSAR_HTTP_PORT}\n"
               f"  pulsar manager ui:  http://localhost:{PM_UI_PORT}\n"
               f"  prometheus:         http://localhost:{PROM_PORT}\n"
               f"  grafana:            http://localhost:{GRAF_PORT} (admin / happypulsaring)")

@app.command("down")
def down_cmd():
    """stop and remove all containers"""
    sh(f"podman rm -f {GRAF_NAME} {PROM_NAME} {PM_NAME} {PULSAR_NAME} 2>/dev/null || true", check=False)
    typer.echo("stack stopped.")

@app.command("status")
def status():
    """show running containers and ports"""
    sh("podman ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'")

@app.command("logs")
def logs(name: str = typer.Argument(..., help="container name (pulsar|pulsar-manager|prom|graf)")):
    """follow container logs"""
    sh(f"podman logs -f {name}", check=False)

@app.command("init-space")
def init_space(
    tenant: str = "test-pulsar-dev",
    namespace: str = "ingress",
    topic: str = "nums",
    partitions: int = 3,
):
    """create a default tenant/namespace/topic and run a smoke publish (logs → init-publish-logs.log)"""
    # check pulsar up
    if not http_up(f"http://localhost:{PULSAR_HTTP_PORT}/admin/v2/brokers/health", tries=5):
        typer.echo("pulsar not reachable on http://localhost:8080 — start it first (trellis start)")
        raise typer.Exit(1)

    # discover cluster name
    cp = subprocess.run(
        f"podman exec -it {PULSAR_NAME} bin/pulsar-admin clusters list",
        shell=True, check=True, capture_output=True, text=True
    )
    clusters = cp.stdout.replace('[', '').replace(']', '').replace('"', '').replace('\r', '').strip()
    cluster = clusters.split()[0] if clusters else "standalone"

    # tenant
    subprocess.run(
        f"podman exec -it {PULSAR_NAME} bin/pulsar-admin tenants list | tr -d '\\r' | grep -qx {tenant} || "
        f"podman exec -it {PULSAR_NAME} bin/pulsar-admin tenants create {tenant} --allowed-clusters {cluster}",
        shell=True, check=True
    )
    subprocess.run(
        f"podman exec -it {PULSAR_NAME} bin/pulsar-admin tenants update {tenant} --allowed-clusters {cluster}",
        shell=True, check=True
    )

    # namespace
    subprocess.run(
        f"podman exec -it {PULSAR_NAME} bin/pulsar-admin namespaces list {tenant} | tr -d '\\r' | grep -qx {tenant}/{namespace} || "
        f"podman exec -it {PULSAR_NAME} bin/pulsar-admin namespaces create {tenant}/{namespace}",
        shell=True, check=True
    )

    # defaults + topic
    subprocess.run(
        f"podman exec -it {PULSAR_NAME} bin/pulsar-admin namespaces set-schema-compatibility-strategy {tenant}/{namespace} --compatibility BACKWARD",
        shell=True, check=True
    )
    subprocess.run(
        f"podman exec -it {PULSAR_NAME} bin/pulsar-admin namespaces set-retention {tenant}/{namespace} --time 1d --size -1",
        shell=True, check=True
    )
    subprocess.run(
        f"podman exec -it {PULSAR_NAME} bin/pulsar-admin topics list-partitioned-topics {tenant}/{namespace} | tr -d '\\r' | grep -qx persistent://{tenant}/{namespace}/{topic} || "
        f"podman exec -it {PULSAR_NAME} bin/pulsar-admin topics create-partitioned-topic persistent://{tenant}/{namespace}/{topic} -p {partitions}",
        shell=True, check=True
    )
    subprocess.run(
        f"podman exec -it {PULSAR_NAME} bin/pulsar-admin topics set-deduplication persistent://{tenant}/{namespace}/{topic} --enable",
        shell=True, check=True
    )

    # smoke publish -> log file
    log_file = Path("init-publish-logs.log")
    cmd = (
        f"podman exec -it {PULSAR_NAME} bin/pulsar-client produce persistent://{tenant}/{namespace}/{topic} -m '5' -n 1 && "
        f"podman exec -it {PULSAR_NAME} bin/pulsar-client produce persistent://{tenant}/{namespace}/{topic} -m '2.75' -n 1 && "
        f"podman exec -it {PULSAR_NAME} bin/pulsar-client produce persistent://{tenant}/{namespace}/{topic} -m '-1' -n 1"
    )
    rc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    log_file.write_text(rc.stdout + rc.stderr)
    if rc.returncode == 0:
        typer.echo("✅ publish test passed (see init-publish-logs.log)")
    else:
        typer.echo("❌ publish test failed (see init-publish-logs.log)")
        raise typer.Exit(rc.returncode)

if __name__ == "__main__":
    app()
