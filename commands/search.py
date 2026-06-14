from registry.discover import *
import typer


def register(app:typer.Typer):
    
    @app.command("search",help="Search details about any command")
    def search_workflows(workflow_name:str):
        lines=[]
        for workflow_path in discover_workflow_path():
            i=[]
            if workflow_name in workflow_path.parent.name:
                workflow_data=read_workflow(workflow_path)
                print(f"\033[1mName\033[0m: {workflow_data['name']}")
                print(f"\033[1mWhat i do?\033[0m: {workflow_data['description']}")
                for inp in workflow_data['inputs']:
                    print(inp['name'])
                    if inp['required']:
                        print("\033[1m- required\033[0m")
                    else:
                        print("\033[1m- optional\033[0m")
                    i.append(inp['name'])
                args=" ".join(f"<{name}>" for name in i)
                print(f"\n\033[1msyntax\033[0m: lazyops run {workflow_name} {args}")
        return