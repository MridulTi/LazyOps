from registry.discover import discover_workflows
import typer


def register(app:typer.Typer):
    
    @app.command("list",help="List all commands")
    def list_workflows():
        cnt=0
        for workflows in discover_workflows():
            cnt+=1
            print(f'{cnt}. {workflows}')