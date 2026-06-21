import typer

from registry.catalog import CatalogError, iter_installed_workflows


def _matches(query: str, pack: str, plugin: str, workflow_data: dict) -> bool:
    q = query.lower()
    haystack = " ".join(
        [
            pack,
            plugin,
            f"{pack}/{plugin}",
            str(workflow_data.get("id", "")),
            str(workflow_data.get("name", "")),
            str(workflow_data.get("description", "")),
        ]
    ).lower()
    return q in haystack



def register(app: typer.Typer):

    @app.command("search", help="Search details about any command")
    def search_workflows(query: str):
        try:
            items = iter_installed_workflows()
        except CatalogError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
        matches = 0
        for item in items:
            pack = item["pack"]
            plugin = item["plugin"]
            workflow_data = item["workflow"]
            if not _matches(query, pack, plugin, workflow_data):
                continue
            matches += 1
            wf_id = workflow_data.get("id", plugin)
            inputs = workflow_data.get("inputs") or []
            print(f"\033[1mId\033[0m: {pack}/{wf_id}")
            print(f"\033[1mName\033[0m: {workflow_data.get('name', wf_id)}")
            print(f"\033[1mWhat i do?\033[0m: {workflow_data.get('description', '')}")
            if inputs:
                print("\033[1mInputs\033[0m:")
                for inp in inputs:
                    label = "required" if inp.get("required") else "optional"
                    print(f"  - {inp['name']} ({label})")
            else:
                print("\033[1mInputs\033[0m: none")
            arg_names = [inp["name"] for inp in inputs if inp.get("required")]
            args = " ".join(f"<{name}>" for name in arg_names)
            target = f"{pack}/{plugin}"
            print(f"\n\033[1msyntax\033[0m: lazyops run {target}{(' ' + args) if args else ''}")
            print()
        if matches == 0:
            typer.echo(f"No workflows matched '{query}'.")