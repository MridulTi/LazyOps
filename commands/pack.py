import typer

from registry import packs as pack_registry
from registry.fetch import FetchError, list_pack_plugins
from registry.source import SourceError, get_source

pack_app = typer.Typer(help="Manage installed workflow packs (aws,kubernetes,...)")

def register(app: typer.Typer):
    app.add_typer(pack_app,name="pack")

@pack_app.command("add")
def pack_add(name:str=typer.Argument(...,help="Pack id eg. aws")):
    try:
        pack_registry.add_pack(name)
    except pack_registry.PackError as exc:
        typer.secho(str(exc),fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    typer.secho(f"Installed pack: {name}", fg=typer.colors.GREEN)
    typer.secho("Run workflow with: lazyops run <pack>/<plugin>")

@pack_app.command("list")
def pack_list(pack: str | None = typer.Argument(None, help="Optional pack id to list plugins")):
    if pack is None:
        items = pack_registry.list_packs()
        if not items:
            typer.echo("No packs installed.")
            typer.echo("Install one: lazyops pack add aws")
            return
        try:
            source = get_source()
        except SourceError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        for name in items:
            try:
                plugins = list_pack_plugins(
                    source["url"],
                    source["ref"],
                    source.get("path_prefix", "plugins"),
                    name,
                )
                typer.echo(f"{name} ({len(plugins)} plugins)")
            except FetchError as exc:
                typer.echo(f"{name} (failed to list: {exc})")
    else:
        try:
            source = get_source()
            plugins = list_pack_plugins(
                source["url"],
                source["ref"],
                source.get("path_prefix", "plugins"),
                pack,
            )
        except SourceError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        except FetchError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        if not plugins:
            typer.echo(f"No plugins found in pack: {pack}")
            return
        for plugin in plugins:
            typer.echo(f"{pack}/{plugin}")

@pack_app.command("remove")
def pack_remove(name: str = typer.Argument(..., help="Pack id to remove")):
    try:
        pack_registry.remove_pack(name)
    except pack_registry.PackError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    typer.secho(f"Removed pack: {name}", fg=typer.colors.GREEN)