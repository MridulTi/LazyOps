from registry.discover import *
from registry.paths import PROJECT_ROOT, venv_python
import os
import subprocess
import typer
from typing import *


def register(app: typer.Typer):

    @app.command("run", help="run workflows")
    def run_workflow(workflow_name: str, extra_args: List[str] = typer.Argument(None)):
        workflow_path = PROJECT_ROOT / "workflows" / workflow_name / "workflow.yaml"
        workflow = read_workflow(workflow_path)
        entrypoint = workflow_path.parent / workflow["entrypoint"]
        inputs = list(extra_args or [])

        env = os.environ.copy()
        env.setdefault("LAZYOPS_ROOT", str(PROJECT_ROOT))
        env.setdefault("WORKFLOW_ID", workflow.get("id", workflow_name))
        env.setdefault("WORKFLOW_ROOT", str(workflow_path.parent))
        env.setdefault("WORKFLOW_RUNTIME", workflow["runtime"])
        env.setdefault("WORKFLOW_VERSION", workflow.get("version", "1.0.0"))

        if workflow["runtime"] == "bash":
            cmd = ["bash", str(entrypoint)] + inputs
        elif workflow["runtime"] == "python":
            cmd = [venv_python(), str(entrypoint)] + inputs
        elif workflow["runtime"] == "node":
            cmd = ["node", str(entrypoint)] + inputs
        else:
            raise ValueError("Unsupported runtime")

        subprocess.run(cmd, check=True, env=env, cwd=workflow_path.parent)