import tempfile
from pathlib import Path


def cache_dir() -> Path:
    return Path(tempfile.gettempdir()) / "shop-price-cache"


def init_cache() -> Path:
    d = cache_dir()
    d.mkdir()  # bug: fails if an earlier run left it behind, and nothing removes it
    (d / "prices.json").write_text("{}")
    return d
