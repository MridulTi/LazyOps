from __future__ import annotations
from registry.config import load_config,save_config

class PackError(Exception):
    pass

def list_packs() -> list[str]:
    return load_config().get("packs") or []

def pack_installed(name:str) -> bool:
    return name in list_packs()

def add_pack(name:str) -> None:
    if not name:
        raise PackError("pack name is required")

    config = load_config()
    packs = config.setdefault("packs",[])

    if name in packs:
        raise PackError(f"Pack already installed: {name}")

    packs.append(name)
    save_config(config)

def remove_pack(name:str) -> None:
    config = load_config()
    packs = config.get("packs") or []

    if name not in packs:
        raise PackError(f"Pack not installed: {name}")

    config["packs"] = [p for p in packs if p !=name]
    save_config(config)