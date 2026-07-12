from __future__ import annotations

import os

from registry.config import load_config

DEFAULT_CMDB_URL = "https://cmdb.paytmpayments.com"


def get_cmdb_url(override: str | None = None) -> str:
    """Resolve CMDB base URL: flag/env > config.yaml > default."""
    if override:
        return override.rstrip("/")
    env_url = os.environ.get("LAZYOPS_CMDB_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    config = load_config()
    cmdb = config.get("cmdb") or {}
    if isinstance(cmdb, dict):
        cfg_url = (cmdb.get("url") or "").strip()
        if cfg_url:
            return cfg_url.rstrip("/")
    return DEFAULT_CMDB_URL
