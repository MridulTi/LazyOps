from __future__ import annotations

import shutil,yaml
import subprocess
import tempfile
from pathlib import Path


class FetchError(Exception):
    pass


def _run_git(args: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(
        ["git",*args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode !=0:
        msg=(result.stderr or result.stdout or "").strip()
        raise FetchError(msg or f"git {''.join(args)} failed")


def plugin_relpath(path_prefix: str, pack: str, plugin: str) -> str:
    prefix = path_prefix.strip('/')
    return f"{prefix}/{pack}/{plugin}"


def fetch_plugin_dir(
    url: str,
    ref: str,
    path_prefix: str,
    pack: str,
    plugin: str
) -> Path:
    """
    Sparse-clone one workflow dir at ref.
    Returns path to the plugin dir (contains workflow.yaml).
    Caller deletes parent temp dir when done.
    """
    rel = plugin_relpath(path_prefix, pack, plugin)
    tmp_root = Path(tempfile.mkdtemp(prefix="lazyops-"))
    repo_dir = tmp_root / "repo"
    try:
        _run_git(
            [
                "clone",
                "--depth", "1",
                "--filter=blob:none",
                "--sparse",
                "--branch", ref,
                url,
                str(repo_dir),
            ]
        )
        _run_git(["sparse-checkout", "set", rel], cwd=repo_dir)
        workflow_dir = repo_dir / rel
        if not (workflow_dir / "workflow.yaml").is_file():
            raise FetchError(
                f"Workflow not found: {pack}/{plugin} at ref={ref} ({rel})"
            )
        dest = tmp_root / pack / plugin
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(workflow_dir), str(dest))
        shutil.rmtree(repo_dir, ignore_errors=True)
        return dest
    except Exception:
        shutil.rmtree(tmp_root, ignore_errors=True)
        raise

def fetch_pack_dir(
    url: str,
    ref: str,
    path_prefix: str,
    pack: str,
) -> tuple[Path, Path]:
    """
    Sparse-clone plugins/<pack>/ once.
    Returns (tmp_root, pack_dir). Caller must rm tmp_root when done.
    """
    rel = f"{path_prefix.strip('/')}/{pack}"
    tmp_root = Path(tempfile.mkdtemp(prefix="lazyops-pack-"))
    repo_dir = tmp_root / "repo"

    try:
        _run_git(
            [
                "clone",
                "--depth", "1",
                "--filter=blob:none",
                "--sparse",
                "--branch", ref,
                url,
                str(repo_dir),
            ]
        )
        _run_git(["sparse-checkout", "set", rel], cwd=repo_dir)

        pack_dir = repo_dir / rel
        if not pack_dir.is_dir():
            raise FetchError(f"Pack not found: {pack}")

        dest = tmp_root / pack
        shutil.move(str(pack_dir), str(dest))
        shutil.rmtree(repo_dir, ignore_errors=True)
        return tmp_root, dest

    except Exception:
        shutil.rmtree(tmp_root, ignore_errors=True)
        raise

def list_pack_plugins(
    url: str,
    ref: str,
    path_prefix: str,
    pack: str,
) -> list[str]:
    """List plugin folder names under a pack (for pack list / interactive run)."""
    prefix = path_prefix.strip("/")
    pack_path = f"{prefix}/{pack}"
    tmp_root = Path(tempfile.mkdtemp(prefix="lazyops-ls-"))
    repo_dir = tmp_root / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    try:
        _run_git(["init"], cwd=repo_dir)
        _run_git(["remote", "add", "origin", url], cwd=repo_dir)
        _run_git(["fetch", "--depth", "1", "origin", ref], cwd=repo_dir)
        result = subprocess.run(
            ["git", "ls-tree", "-d", "--name-only", f"FETCH_HEAD:{pack_path}"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise FetchError(result.stderr.strip() or f"Pack not found: {pack}")
        names = []
        for line in result.stdout.splitlines():
            name = line.strip()
            if name and name != "pack.yaml":
                names.append(name)
        return sorted(names)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

def read_plugin_workflow(
    url: str,
    ref: str,
    path_prefix: str,
    pack: str,
    plugin: str
) -> dict:
    """Read workflow.yaml for one plugin at ref (no full clone)"""
    rel = plugin_relpath(path_prefix, pack , plugin) + "/workflow.yaml"
    tmp_root = Path(tempfile.mkdtemp(prefix="lazyops-yaml-"))
    repo_dir = tmp_root / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    try:
        _run_git(["init"], cwd=repo_dir)
        _run_git(["remote", "add", "origin", url], cwd=repo_dir)
        _run_git(["fetch", "--depth", "1", "origin", ref], cwd=repo_dir)

        result = subprocess.run(
            ["git","show",f"FETCH_HEAD:{rel}"],
            cwd=repo_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise FetchError(f"Missing workflow.yaml for {pack}/{plugin}")

        return yaml.safe_load(result.stdout) or {}
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)