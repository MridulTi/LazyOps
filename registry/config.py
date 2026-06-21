from __future__ import annotations

from pathlib import Path
import yaml,os

DEFAULT_CONFIG_DIR = Path(os.environ.get("LAZYOPS_CONFIG_DIR", str(Path.home() / ".lazyops")))
CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG = {"source": None, "packs": []}


def ensure_config_dir() -> None:
    DEFAULT_CONFIG_DIR.mkdir(parents=True,exist_ok=True)

def _migrate_config(data: dict) -> dict:
    """Normalize config to source + packs; migrate legacy sources[]."""
    if not isinstance(data, dict):
        data = {}
    # Legacy: sources[] → single source (first entry only)
    if "source" not in data and isinstance(data.get("sources"), list):
        legacy = data["sources"]
        if legacy:
            first = legacy[0]
            data["source"] = {
                "url": first.get("url", ""),
                "ref": first.get("ref", "v1.0.0"),
                "path_prefix": first.get("path_prefix", "plugins"),
            }
        del data["sources"]
    if data.get("source") is None:
        data["source"] = None
    elif isinstance(data["source"], dict):
        src = data["source"]
        data["source"] = {
            "url": src.get("url", ""),
            "ref": src.get("ref", "v1.0.0"),
            "path_prefix": src.get("path_prefix", "plugins"),
        }
    if "packs" not in data or not isinstance(data["packs"], list):
        data["packs"] = []
    return data

def load_config() -> dict:
    ensure_config_dir()
    if not CONFIG_PATH.is_file():
        return dict(DEFAULT_CONFIG)
    with CONFIG_PATH.open("r",encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return _migrate_config(data)

def save_config(data: dict) -> None:
    ensure_config_dir()
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)