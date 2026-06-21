from __future__ import annotations

from registry.config import load_config, save_config


class SourceError(Exception):
    pass


def init_source(url: str, ref: str = "v1.0.0", path_prefix: str = "plugins") -> dict:
    if not url:
        raise SourceError("url is required")
    config = load_config()
    config["source"] = {
        "url": url,
        "ref": ref,
        "path_prefix": path_prefix,
    }
    save_config(config)
    return config["source"]


def get_source() -> dict:
    config = load_config()
    source = config.get("source")
    if not source or not isinstance(source, dict) or not source.get("url"):
        raise SourceError(
            "No source configured. Run: lazyops source init <git-url> --ref v1.0.0"
        )
    return source


def update_source_ref(ref: str) -> dict:
    if not ref:
        raise SourceError("ref is required")
    config = load_config()
    source = config.get("source")
    if not source or not isinstance(source, dict) or not source.get("url"):
        raise SourceError("No source configured. Run: lazyops source init first")
    source["ref"] = ref
    save_config(config)
    return source
