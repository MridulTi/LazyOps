from registry.discover import *
import typer,subprocess
from typing import *


def register(app:typer.Typer):
    
    @app.command("run",help="run workflows")
    def run_workflow(workflow_name:str,extra_args: List[str] = typer.Argument(None)):
        workflow_path = Path(__file__).parent.parent / "workflows" / workflow_name / "workflow.yaml"
        workflow = read_workflow(workflow_path)
        entrypoint = workflow_path.parent / workflow["entrypoint"]
        inputs = list(extra_args or [])

        if workflow["runtime"] == "bash":
            cmd = ["bash", str(entrypoint)] + inputs
        elif workflow["runtime"] == "python":
            cmd = ["python", str(entrypoint)] + inputs
        elif workflow["runtime"] == "node":
            cmd = ["node", str(entrypoint)] + inputs
        else:
            raise ValueError("Unsupported runtime")

        subprocess.run(cmd, check=True)