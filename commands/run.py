import os
import shutil
import subprocess

import typer
import yaml

from registry.discover import read_workflow
from registry.fetch import FetchError, fetch_pack_dir, fetch_plugin_dir, list_pack_plugins
from registry.packs import list_packs, pack_installed
from registry.paths import PROJECT_ROOT, venv_python
from registry.source import SourceError, get_source


def _parse_target(target:str)-> tuple[str,str]:
    if "/" not in target:
        raise typer.BadParameter("Use pack/plugin format, eg. aws/addpatchclasstag")

    pack,plugin = target.split("/",1)
    if not pack or not plugin:
        raise typer.BadParameter("Use pack/plugin format, e.g. aws/addpatchclasstag")
    return pack,plugin

def _run_target(pack: str, plugin: str, extra_args: list[str]) -> None:
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
    try:
        workflow_dir = fetch_plugin_dir(
            url=source["url"],
            ref=source["ref"],
            path_prefix=source.get("path_prefix", "plugins"),
            pack=pack,
            plugin=plugin,
        )
        tmp_root = workflow_dir.parent.parent

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
            typer.secho(f"Unsupported runtime: {workflow['runtime']}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)

        subprocess.run(cmd, check=True, env=env, cwd=workflow_dir)

    except FetchError as exc:
        typer.secho(f"Failed to fetch workflow: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    finally:
        if tmp_root is not None:
            shutil.rmtree(tmp_root, ignore_errors=True)


def _pick_index(prompt: str, max_index: int) -> int:
    while True:
        raw = typer.prompt(prompt)
        try:
            choice = int(raw)
        except ValueError:
            typer.secho(f"Enter a number between 1 and {max_index}", fg=typer.colors.RED)
            continue
        if 1 <= choice <= max_index:
            return choice - 1
        typer.secho(f"Enter a number between 1 and {max_index}", fg=typer.colors.RED)


def _interactive_run() -> tuple[str, str]:
    packs = list_packs()
    if not packs:
        typer.secho("No packs installed. Run: lazyops pack add aws", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    try:
        source = get_source()
    except SourceError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    typer.echo("\nInstalled packs:")
    pack_rows: list[tuple[str, list[str]]] = []
    for i, pack in enumerate(packs, start=1):
        try:
            plugins = list_pack_plugins(
                source["url"],
                source["ref"],
                source.get("path_prefix", "plugins"),
                pack,
            )
        except FetchError as exc:
            typer.secho(f"  {i}. {pack} (failed: {exc})", fg=typer.colors.YELLOW)
            plugins = []
        pack_rows.append((pack, plugins))
        typer.echo(f"  {i}. {pack} ({len(plugins)} plugins)")

    pack_idx = _pick_index(f"Select pack [1-{len(packs)}]: ", len(packs))
    pack, plugins = pack_rows[pack_idx]

    if not plugins:
        typer.secho(f"No plugins in pack {pack}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    typer.echo(f"\nPlugins in {pack}:")
    tmp_root = None
    try:
        tmp_root, pack_dir = fetch_pack_dir(
            source["url"],
            source["ref"],
            source.get("path_prefix", "plugins"),
            pack,
        )

        # plugins list order from git; enrich with local workflow.yaml names
        plugin_labels: dict[str, str] = {}
        for child in pack_dir.iterdir():
            if not child.is_dir() or child.name == "pack.yaml":
                continue
            yaml_path = child / "workflow.yaml"
            if yaml_path.is_file():
                wf = yaml.safe_load(yaml_path.read_text()) or {}
                plugin_labels[child.name] = wf.get("name", child.name)
            else:
                plugin_labels[child.name] = child.name

        for i, plugin in enumerate(plugins, start=1):
            label = plugin_labels.get(plugin, plugin)
            typer.echo(f"  {i}. {plugin} — {label}")

    finally:
        if tmp_root is not None:
            shutil.rmtree(tmp_root, ignore_errors=True)

    plugin_idx = _pick_index(f"Select plugin [1-{len(plugins)}]: ", len(plugins))
    plugin = plugins[plugin_idx]

    confirm = typer.confirm(f"Run {pack}/{plugin}?")
    if not confirm:
        typer.echo("Cancelled.")
        raise typer.Exit(0)

    return pack, plugin

def register(app: typer.Typer):

    @app.command("run", help="Run a workflow: lazyops run <pack>/<plugin> [args...]")
    def run_workflow(
        target: str | None = typer.Argument(default=None, help="pack/plugin, e.g. aws/addpatchclasstag"),
        extra_args: list[str] | None = typer.Argument(None),
    ):
        if target is None:
            pack, plugin = _interactive_run()
        else:
            pack, plugin = _parse_target(target)
        _run_target(pack, plugin, list(extra_args or []))