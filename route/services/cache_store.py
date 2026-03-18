import json
from pathlib import Path

from django.conf import settings


_MEMORY_CACHE = {}


def _cache_path(name: str) -> Path:
    return Path(settings.BASE_DIR) / 'data' / name


def load_json_cache(name: str):
    path = _cache_path(name)
    cache_key = str(path)
    if cache_key in _MEMORY_CACHE:
        return _MEMORY_CACHE[cache_key]

    if not path.exists():
        _MEMORY_CACHE[cache_key] = {}
        return _MEMORY_CACHE[cache_key]

    try:
        _MEMORY_CACHE[cache_key] = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        _MEMORY_CACHE[cache_key] = {}
    return _MEMORY_CACHE[cache_key]


def save_json_cache(name: str, data):
    path = _cache_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')
    _MEMORY_CACHE[str(path)] = data

