# trellis_cli/flink.py
from pathlib import Path
import typer
from trellis_cli.utils import ensure_network, write, compose_up, compose_down, container_logs

app = typer.Typer(help="Local Apache Flink control")

COMPOSE_FLINK_FILE = Path.home() / ".trellis" / "compose.flink.yml"
COMPOSE_FLINK_TEXT = """\
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
    networks: [trellis-net]
  taskmanager:
    image: apache/flink:1.18.1-java11
    container_name: trellis-flink-tm
    command: taskmanager
    depends_on: [jobmanager]
    environment:
      - |
        FLINK_PROPERTIES=
        jobmanager.rpc.address: jobmanager
        taskmanager.numberOfTaskSlots: 2
    networks: [trellis-net]
"""

def ensure_compose() -> Path:
    ensure_network("trellis-net")
    return write(COMPOSE_FLINK_FILE, COMPOSE_FLINK_TEXT)
@app.command("up")
def up():
    compose_up(ensure_compose())
    typer.echo("Flink UI http://localhost:8081")

@app.command("down")
def down():
    compose_down(ensure_compose())
    typer.echo("Flink stopped")

@app.command("logs")
def logs(service: str = typer.Argument(..., help="jm or tm"), follow: bool = True):
    name = {"jm": "trellis-flink-jm", "tm": "trellis-flink-tm"}.get(service)
    if not name:
        typer.echo("choose jm or tm")
        raise typer.Exit(1)
    container_logs(name, follow=follow)
