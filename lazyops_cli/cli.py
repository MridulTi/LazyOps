import typer
from pathlib import Path
import importlib


app = typer.Typer()

COMMANDS_DIR = Path(__file__).parent.parent / "commands"


def discover_commands():
    commands = []
    for path in COMMANDS_DIR.iterdir():
        if path.is_file() and path.suffix == ".py" and path.name != "__init__.py":
            module=importlib.import_module(f"commands.{path.stem}")
            if hasattr(module,"register"):
                module.register(app)


@app.command()
def intro(name: str = "World"):
    print(f"Hello {name}")

# This function will be targeted by your custom CLI name
discover_commands()

def run():
    app()

if __name__ == "__main__":
    run()