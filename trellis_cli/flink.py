from pathlib import Path
import subprocess
import shutil
import typer
import urllib.request
app = typer.Typer(help="Local Apache Flink cluster and Beam Job Server")

COMPOSE_TEXT = """\
version: "3.8"
services:
  jobmanager:
    image: apache/flink:1.18.1-java11
    container_name: trellis-flink-jm
    command: jobmanager
    ports:
      - "8081:8081"
    environment:
      - |
        FLINK_PROPERTIES=
        jobmanager.rpc.address: jobmanager
        rest.port: 8081
        taskmanager.numberOfTaskSlots: 2

  taskmanager:
    image: apache/flink:1.18.1-java11
    container_name: trellis-flink-tm
    depends_on: [jobmanager]
    command: taskmanager
    environment:
      - |
        FLINK_PROPERTIES=
        jobmanager.rpc.address: jobmanager
        taskmanager.numberOfTaskSlots: 2

  beam_job_server:
    image: apache/beam_flink1.18_job_server:2.57.0
    container_name: trellis-beam-flink-js
    depends_on: [jobmanager, taskmanager]
    ports:
      - "8099:8099"  # job service
      - "8098:8098"  # artifact
      - "8097:8097"  # expansion
    command: >
      --flink-master=jobmanager:8081
      --job_port=8099
      --artifact_port=8098
      --expansion_port=8097
"""

USER_DIR = Path.home() / ".trellis" / "flink"
COMPOSE_FILE = USER_DIR / "docker-compose.yml"

BEAM_JAR_DIR = USER_DIR / "jars"

KAFKA_XLANG_JARS = [
    ("beam-sdks-java-io-expansion-service-2.66.0.jar",
     "https://repo1.maven.org/maven2/org/apache/beam/beam-sdks-java-io-expansion-service/2.66.0/beam-sdks-java-io-expansion-service-2.66.0.jar")
]
def ensure_beam_jars():
    BEAM_JAR_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in KAFKA_XLANG_JARS:
        path = BEAM_JAR_DIR / name
        if not path.exists():
            print(f"📥 Downloading {name} from {url}")
            urllib.request.urlretrieve(url, path)
            print(f"✅ Saved to {path}")
        else:
            print(f"✔ JAR already exists: {path}")
def ensure_compose_file() -> Path:
    USER_DIR.mkdir(parents=True, exist_ok=True)
    if not COMPOSE_FILE.exists():
        COMPOSE_FILE.write_text(COMPOSE_TEXT)
    return COMPOSE_FILE
def run_compose(*args: str) -> None:
    compose_yaml = str(ensure_compose_file())
    if shutil.which("podman-compose"):
        subprocess.run(["podman-compose", "-f", compose_yaml, *args], check=True)
    else:
        subprocess.run(["podman", "compose", "-f", compose_yaml, *args], check=True)
def compose_text(with_kafka_xlang: bool, with_external_go: bool) -> str:
    # Base services
    base = f"""
version: "3.8"

networks:
  trellis-net:
    name: trellis-net

services:
  jobmanager:
    image: apache/flink:1.18.1-java11
    container_name: trellis-flink-jm
    command: jobmanager
    ports:
      - "8081:8081"
    environment:
      - |
        FLINK_PROPERTIES=
        jobmanager.rpc.address: jobmanager
        rest.port: 8081
        taskmanager.numberOfTaskSlots: 2
    networks:
      - trellis-net

  taskmanager:
    image: apache/flink:1.18.1-java11
    container_name: trellis-flink-tm
    command: taskmanager
    depends_on:
      - jobmanager
    environment:
      - |
        FLINK_PROPERTIES=
        jobmanager.rpc.address: jobmanager
        taskmanager.numberOfTaskSlots: 2
    networks:
      - trellis-net

"""
    return base

@app.command("up")
def up(
    with_kafka_xlang: bool = typer.Option(True, help="Mount Beam IO Expansion JARs for cross-language IO"),
    with_external_go: bool = typer.Option(False, help="Run a dedicated external Go SDK harness on port 50000"),
):
    if with_kafka_xlang:
        ensure_beam_jars()

    # write compose with requested services
    COMPOSE_FILE.write_text(compose_text(with_kafka_xlang, with_external_go))
    run_compose("up", "-d")

    # friendly output
    typer.echo("Flink UI:            http://localhost:8081")
    typer.echo("Beam Job Server:     localhost:8099")
    typer.echo("Expansion Service:   localhost:8097")
    typer.echo(f"Jar Dir:  {str(BEAM_JAR_DIR)}")
    if with_kafka_xlang:
        typer.echo(f"JARs mounted from:   {BEAM_JAR_DIR}")
    if with_external_go:
        typer.echo("Go Harness (ext):    localhost:50000")




@app.command("down")
def down() -> None:
    run_compose("down", "-v")
    typer.echo("Flink cluster stopped")

@app.command("logs")
def logs(
    service: str = typer.Argument(..., help="Service to view logs: jm | tm | js"),
    follow: bool = typer.Option(True, "--no-follow", help="Follow logs in real time")
) -> None:
    """
    Stream logs from a service:
      jm = JobManager
      tm = TaskManager
      js = Beam Job Server
    """
    service_map = {
        "jm": "trellis-flink-jm",
        "tm": "trellis-flink-tm",
        "js": "trellis-beam-flink-js",
    }
    if service not in service_map:
        typer.secho(f"Invalid service '{service}'. Choose jm | tm | js", fg=typer.colors.RED)
        raise typer.Exit(1)
    cmd = ["podman", "logs"]
    if follow:
        cmd.append("-f")
    cmd.append(service_map[service])
    subprocess.run(cmd)

@app.command("print-go-flags")
def print_go_flags(
    loopback: bool = typer.Option(False, help="Run Go DoFns in-process")
) -> None:
    """
    Print flags for running a Go Apache Beam pipeline against the local Flink Job Server.
    """
    if loopback:
        flags = "--runner=PortableRunner --job_endpoint=localhost:8099 --environment_type=LOOPBACK"
    else:
        flags = (
            "--runner=PortableRunner --job_endpoint=localhost:8099 "
            "--environment_type=DOCKER --environment_config=apache/beam_go_sdk:2.57.0"
        )
    typer.echo(flags)

@app.command("run-sum")
def run_sum(
    kafka_bootstrap: str = typer.Option("localhost:9092", help="Kafka bootstrap"),
    topic: str = typer.Option("orders", help="Topic to consume"),
    key_by: str = typer.Option("global", help="Keying: global or kafka"),
    loopback: bool = typer.Option(True, "--docker", help="Use LOOPBACK by default; pass --docker for containerized Go SDK"),
    src: str = typer.Option("examples/go/stream_sum_avg", help="Path to the Go example"),
):
    """
    Run the streaming sum+avg example against the local Flink Job Server.
    """
    base = [
        "go", "run", ".",
        "--runner=PortableRunner",
        "--job_endpoint=localhost:8099",
        "--expansion_addr=localhost:8097",
        f"--kafka_bootstrap={kafka_bootstrap}",
        f"--kafka_topic={topic}",
        f"--key_by={key_by}",
    ]
    if loopback:
        base += ["--environment_type=LOOPBACK"]
    else:
        base += ["--environment_type=DOCKER", "--environment_config=apache/beam_go_sdk:2.57.0"]

    subprocess.run(base, cwd=src, check=True)