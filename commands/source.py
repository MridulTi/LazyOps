import typer

from registry import source as source_registry
from registry.config import CONFIG_PATH

source_app = typer.Typer(help="Manage workflow sources (git branches, tags, local paths)")


def register(app: typer.Typer):
    app.add_typer(source_app, name="source")


@source_app.command("show")
def source_show():
    try:
        src = source_registry.get_source()
    except source_registry.SourceError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    typer.echo(f"url:          {src['url']}")
    typer.echo(f"ref:          {src['ref']}")
    typer.echo(f"path_prefix:  {src.get('path_prefix', 'plugins')}")


@source_app.command("update")
def source_update(
    ref: str = typer.Option(..., "--ref", "-r", help="New branch or tag"),
):
    try:
        entry = source_registry.update_source_ref(ref)
    except source_registry.SourceError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    typer.secho(f"Source updated to ref: {entry['ref']}", fg=typer.colors.GREEN)


@source_app.command("init")
def source_init(
    url: str = typer.Argument(..., help="Git URL of lazyops-plugins repo"),
    ref: str = typer.Option("v1.0.0", "--ref", "-r", help="Branch or tag (version)"),
    path_prefix: str = typer.Option("plugins", "--path-prefix", help="Root dir in repo"),
):
    try:
        entry = source_registry.init_source(url, ref, path_prefix)
    except source_registry.SourceError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    typer.secho("Source configured", fg=typer.colors.GREEN)
    typer.echo(f"  url:          {entry['url']}")
    typer.echo(f"  ref:          {entry['ref']}")
    typer.echo(f"  path_prefix:  {entry['path_prefix']}")
    typer.echo(f"  config:       {CONFIG_PATH}")
