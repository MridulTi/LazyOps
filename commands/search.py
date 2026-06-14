from registry.discover import discover_workflow_path, read_workflow
import typer


def _matches(query: str, workflow_id: str, workflow_data: dict) -> bool:
    q = query.lower()
    haystack = " ".join(
        [
            workflow_id,
            str(workflow_data.get("id", "")),
            str(workflow_data.get("name", "")),
            str(workflow_data.get("description", "")),
        ]
    ).lower()
    return q in haystack


def register(app: typer.Typer):

    @app.command("search", help="Search details about any command")
    def search_workflows(query: str):
        matches = 0

        for workflow_path in discover_workflow_path():
            workflow_id = workflow_path.parent.name
            try:
                workflow_data = read_workflow(workflow_path)
            except Exception as exc:
                typer.secho(
                    f"Skipping {workflow_id}: invalid workflow.yaml ({exc})",
                    fg=typer.colors.RED,
                    err=True,
                )
                continue

            if not _matches(query, workflow_id, workflow_data):
                continue

            matches += 1
            wf_id = workflow_data.get("id", workflow_id)
            inputs = workflow_data.get("inputs") or []

            print(f"\033[1mId\033[0m: {wf_id}")
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
            print(f"\n\033[1msyntax\033[0m: lazyops run {wf_id}{(' ' + args) if args else ''}")
            print()

        if matches == 0:
            typer.echo(f"No workflows matched '{query}'.")
