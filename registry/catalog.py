from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml

from registry.fetch import FetchError, fetch_pack_dir, list_local_plugins
from registry.packs import list_packs
from registry.paths import PROJECT_ROOT
from registry.source import SourceError, get_source


class CatalogError(Exception):
    pass


def iter_installed_workflows() -> list[dict]:
    """
    Return metadata for every plugin under installed packs.
    Each item: {pack, plugin, workflow}
    """
    try:
        source = get_source()
    except SourceError as exc:
        raise CatalogError(str(exc)) from exc
    url = source["url"]
    ref = source["ref"]
    path_prefix = source.get("path_prefix", "plugins")
    results: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()

    def _append_local(pack: str) -> None:
        for plugin in list_local_plugins(pack):
            key = (pack, plugin)
            if key in seen_keys:
                continue
            yaml_path = PROJECT_ROOT / "plugins" / pack / plugin / "workflow.yaml"
            env_root = os.environ.get("LAZYOPS_PLUGINS_ROOT", "").strip()
            if env_root:
                alt = Path(env_root) / pack / plugin / "workflow.yaml"
                if alt.is_file():
                    yaml_path = alt
            if not yaml_path.is_file():
                continue
            workflow = yaml.safe_load(yaml_path.read_text()) or {}
            seen_keys.add(key)
            results.append({"pack": pack, "plugin": plugin, "workflow": workflow})

    for pack in list_packs():
        _append_local(pack)
        tmp_root = None
        try:
            tmp_root, pack_dir = fetch_pack_dir(url, ref, path_prefix, pack)
            for child in sorted(pack_dir.iterdir()):
                if not child.is_dir() or child.name == "pack.yaml":
                    continue
                yaml_path = child / "workflow.yaml"
                if not yaml_path.is_file():
                    continue
                key = (pack, child.name)
                if key in seen_keys:
                    continue
                workflow = yaml.safe_load(yaml_path.read_text()) or {}
                seen_keys.add(key)
                results.append({
                    "pack": pack,
                    "plugin": child.name,
                    "workflow": workflow,
                })
        except FetchError as exc:
            if not any(r["pack"] == pack for r in results):
                import sys
                print(f"Warning: skipping pack {pack}: {exc}", file=sys.stderr)
        finally:
            if tmp_root is not None:
                shutil.rmtree(tmp_root, ignore_errors=True)
    return results
