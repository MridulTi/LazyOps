from __future__ import annotations

import os
import shutil
import subprocess

import typer

from registry.discover import read_workflow
from registry.fetch import FetchError, fetch_plugin_dir
from registry.packs import pack_installed
from registry.paths import PROJECT_ROOT, venv_python
from registry.source import SourceError, get_source


def run_target(pack: str, plugin: str, extra_args: list[str]) -> None:
    if not pack_installed(pack):
        typer.secho(
            f"Pack not installed: {pack}. Run: lazyops pack add {pack}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        source = get_source()
    except SourceError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    tmp_root = None
    workflow_dir = None
    delete_tmp = True
    try:
        workflow_dir, tmp_root, delete_tmp = fetch_plugin_dir(
            url=source["url"],
            ref=source["ref"],
            path_prefix=source.get("path_prefix", "plugins"),
            pack=pack,
            plugin=plugin,
        )

        workflow_path = workflow_dir / "workflow.yaml"
        workflow = read_workflow(workflow_path)
        entrypoint = workflow_dir / workflow["entrypoint"]
        inputs = list(extra_args or [])

        env = os.environ.copy()
        env.setdefault("LAZYOPS_ROOT", str(PROJECT_ROOT))
        env.setdefault("WORKFLOW_ID", workflow.get("id", plugin))
        env.setdefault("WORKFLOW_ROOT", str(workflow_dir))
        env.setdefault("WORKFLOW_RUNTIME", workflow["runtime"])
        env.setdefault("WORKFLOW_VERSION", workflow.get("version", "1.0.0"))
        env.setdefault("WORKFLOW_PACK", pack)
        env.setdefault("WORKFLOW_PLUGIN", plugin)
        env.setdefault("WORKFLOW_SOURCE_REF", source["ref"])

        if workflow["runtime"] == "bash":
            cmd = ["bash", str(entrypoint)] + inputs
        elif workflow["runtime"] == "python":
            cmd = [venv_python(), str(entrypoint)] + inputs
        elif workflow["runtime"] == "node":
            cmd = ["node", str(entrypoint)] + inputs
        else:
            typer.secho(
                f"Unsupported runtime: {workflow['runtime']}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)

        subprocess.run(cmd, check=True, env=env, cwd=workflow_dir)

    except FetchError as exc:
        typer.secho(f"Failed to fetch workflow: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    finally:
        if delete_tmp and tmp_root is not None:
            shutil.rmtree(tmp_root, ignore_errors=True)
