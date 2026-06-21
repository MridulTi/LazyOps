import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def venv_python() -> str:
    candidate = PROJECT_ROOT / ".venv" / "bin" / "python"
    if candidate.is_file():
        return str(candidate)
    return sys.executable
