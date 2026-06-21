#!/usr/bin/env python3
"""Generate LazyOps workflows from learn directory scripts."""

import re
import shutil
import os
from pathlib import Path

LEARN_DIR = Path(os.environ.get("LEARN_DIR", "."))
WORKFLOWS_DIR = Path(__file__).parent.parent / "workflows"


def to_workflow_id(filename: str) -> str:
    stem = Path(filename).stem
    return re.sub(r"[_\s]+", "-", stem).lower()


def to_display_name(filename: str) -> str:
    stem = Path(filename).stem
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", stem)
    words = re.sub(r"[-_]+", " ", words)
    return " ".join(word.capitalize() for word in words.split())


def extract_description(script_path: Path) -> str:
    fallback = to_display_name(script_path.name)
    try:
        text = script_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return fallback

    skip_markers = ("===", "---", "Usage:", "#!/")
    skip_exact = {"config", "configuration", "settings", "imports", "constants"}
    for line in text.splitlines()[:40]:
        stripped = line.strip()
        if stripped.startswith("#") and len(stripped) > 2:
            comment = stripped.lstrip("#").strip()
            if (
                comment
                and not comment.startswith("!")
                and comment.lower() not in skip_exact
                and not any(marker in comment for marker in skip_markers)
                and len(comment) > 8
            ):
                return comment[:120]
        if stripped.startswith(('"""', "'''")):
            doc = stripped.strip("\"'")
            if doc and len(doc) > 8:
                return doc[:120]

    return fallback


def extract_argparse_inputs(script_path: Path) -> list[dict]:
    try:
        text = script_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    inputs = []
    seen = set()
    patterns = [
        r'add_argument\s*\(\s*["\'](--[\w-]+)["\']',
        r'add_argument\s*\(\s*["\']([\w-]+)["\']',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            arg = match.group(1).lstrip("-").replace("-", "_")
            if arg in seen or arg in {"help", "version"}:
                continue
            seen.add(arg)
            inputs.append({"name": arg.replace("_", "-"), "required": False})

    positional = re.findall(
        r'add_argument\s*\(\s*["\'](\w+)["\']\s*,\s*(?:type=|help=|required=True)',
        text,
    )
    for arg in positional:
        name = arg.replace("_", "-")
        if name not in seen:
            seen.add(name)
            inputs.append({"name": name, "required": True})

    return inputs[:10]


def extract_bash_inputs(script_path: Path) -> list[dict]:
    try:
        text = script_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    inputs = []
    for match in re.finditer(r'\$\{?(\d+)\}?', text):
        idx = int(match.group(1))
        if idx == 0:
            continue
        name = f"arg{idx}"
        if not any(i["name"] == name for i in inputs):
            inputs.append({"name": name, "required": True})
    return inputs


def build_workflow_yaml(
    workflow_id: str,
    name: str,
    description: str,
    runtime: str,
    entrypoint: str,
    inputs: list[dict],
) -> str:
    lines = [
        f"id: {workflow_id}",
        "",
        f"name: {name}",
        "",
        f"description: {description}",
        "",
        f"runtime: {runtime}",
        "",
        f"entrypoint: {entrypoint}",
        "",
        "version: 1.0.0",
    ]
    if inputs:
        lines.extend(["", "inputs:"])
        for inp in inputs:
            lines.append(f"  - name: {inp['name']}")
            if inp.get("required"):
                lines.append("    required: true")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    scripts = sorted(
        p
        for p in LEARN_DIR.iterdir()
        if p.is_file() and p.suffix in {".sh", ".py"}
    )

    created = 0
    updated = 0

    for script in scripts:
        workflow_id = to_workflow_id(script.name)
        workflow_dir = WORKFLOWS_DIR / workflow_id
        workflow_dir.mkdir(parents=True, exist_ok=True)

        is_python = script.suffix == ".py"
        runtime = "python" if is_python else "bash"
        entrypoint = "script.py" if is_python else "script.sh"
        dest_script = workflow_dir / entrypoint

        existed = dest_script.exists()
        shutil.copy2(script, dest_script)
        if is_python:
            dest_script.chmod(dest_script.stat().st_mode | 0o111)
        else:
            dest_script.chmod(dest_script.stat().st_mode | 0o111)

        inputs = (
            extract_argparse_inputs(script)
            if is_python
            else extract_bash_inputs(script)
        )
        yaml_content = build_workflow_yaml(
            workflow_id=workflow_id,
            name=to_display_name(script.name),
            description=extract_description(script),
            runtime=runtime,
            entrypoint=entrypoint,
            inputs=inputs,
        )
        (workflow_dir / "workflow.yaml").write_text(yaml_content, encoding="utf-8")

        if existed:
            updated += 1
        else:
            created += 1

    print(f"Processed {len(scripts)} scripts ({created} created, {updated} updated)")


if __name__ == "__main__":
    main()
