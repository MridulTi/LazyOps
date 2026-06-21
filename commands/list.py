import typer

from registry.catalog import CatalogError, iter_installed_workflows


def register(app:typer.Typer):
    
    @app.command("list",help="List all commands")
    def list_workflows():
        try:
            items = iter_installed_workflows()
        except CatalogError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        if not items:
            typer.echo("No workflows found.")
            typer.echo("Install packs: lazyops pack add aws")
            return
        for i, item in enumerate(items, start=1):
            wf = item["workflow"]
            name = wf.get("name", item["plugin"])
            typer.echo(f"{i}. {item['pack']}/{item['plugin']} — {name}")