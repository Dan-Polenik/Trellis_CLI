from __future__ import annotations
from pathlib import Path
import json
import typer
from trellis_cli.utils import compose_up, compose_down, write, ensure_network
app = typer.Typer(help="Scala kernel and Jupyter notebook control")

COMPOSE_NOTEBOOK_FILE = Path.home() / ".trellis" / "compose.notebook.yml"

COMPOSE_NOTEBOOK_TEXT = """
version: '3.8'
services:
  notebook:
    image: docker.io/almondsh/almond:latest
    container_name: trellis-almond-notebook
    command: [
      "jupyter", "lab",
      "--ip=0.0.0.0",
      "--port=8888",
      "--no-browser",
      "--allow-root",
      "--LabApp.token=",
      "--LabApp.password="
    ]
    ports:
      - "8888:8888"
    volumes:
      - ./notebooks:/home/jovyan/work:Z


"""
DEFAULT_NOTEBOOK_PATH = Path("notebooks/trellis-starter.ipynb")

def ensure_compose() -> Path:
    notebooks_path = Path("notebooks").resolve()
    notebooks_path.mkdir(parents=True, exist_ok=True)
    text = COMPOSE_NOTEBOOK_TEXT.format(notebooks_host=str(notebooks_path))
    return write(COMPOSE_NOTEBOOK_FILE, text)

def ensure_default_notebook() -> Path:
    DEFAULT_NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DEFAULT_NOTEBOOK_PATH.exists():
        return DEFAULT_NOTEBOOK_PATH
    
    nb = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# Trellis starter\n",
                    "Flink at `jobmanager:8081`. Pulsar at `localhost:8080` from host. Inside network use `host.containers.internal:8080` on mac or `localhost` on linux."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "import $ivy.`org.apache.beam:beam-runners-flink-1:2.57.0`\n",
                    "import $ivy.`com.spotify::scio-core:0.14.9`\n",
                    "println(\"Scala kernel up. You can now add your Beam args with FlinkRunner.\")\n",
                    "val flinkArgs = Array(\"--runner=FlinkRunner\", \"--flinkMaster=jobmanager:8081\")"
                ]
            },
            {
                "cell_type": "code", 
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "import $ivy.`com.softwaremill.sttp.client3::core:3.9.6`\n",
                    "import sttp.client3._\n",
                    "val pulsarUrl = sys.props.getOrElse(\"pulsar.http\", \"http://host.containers.internal:8080\")\n",
                    "val backend = HttpURLConnectionBackend()\n",
                    "val r = basicRequest.get(uri\"$pulsarUrl/admin/v2/brokers/health\").send(backend)\n",
                    "println(s\"Pulsar HTTP health status: ${r.code}\")"
                ]
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Scala",
                "language": "scala", 
                "name": "scala"
            },
            "language_info": {
                "codemirror_mode": "text/x-scala",
                "file_extension": ".sc",
                "mimetype": "text/x-scala",
                "name": "scala",
                "nbconvert_exporter": "script",
                "version": "2.13.12"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }
    
    DEFAULT_NOTEBOOK_PATH.write_text(json.dumps(nb, indent=2))
    return DEFAULT_NOTEBOOK_PATH
@app.command("up")
def up():
    ensure_default_notebook()
    compose_up(ensure_compose())
    typer.echo("Notebook http://localhost:8888  Scala kernel container will be running")

@app.command("down")
def down():
    compose_down(ensure_compose())
    typer.echo("Notebook stack stopped")
