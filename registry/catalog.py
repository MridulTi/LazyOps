from __future__ import annotations

import shutil

import yaml

from registry.fetch import FetchError, fetch_pack_dir
from registry.packs import list_packs
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
    for pack in list_packs():
        tmp_root = None
        try:
            tmp_root, pack_dir = fetch_pack_dir(url, ref, path_prefix, pack)
            for child in sorted(pack_dir.iterdir()):
                if not child.is_dir() or child.name == "pack.yaml":
                    continue
                yaml_path = child / "workflow.yaml"
                if not yaml_path.is_file():
                    continue
                workflow = yaml.safe_load(yaml_path.read_text()) or {}
                results.append({
                    "pack": pack,
                    "plugin": child.name,
                    "workflow": workflow,
                })
        except FetchError as exc:
            raise CatalogError(f"Failed to load pack {pack}: {exc}") from exc
        finally:
            if tmp_root is not None:
                shutil.rmtree(tmp_root, ignore_errors=True)
    return results
