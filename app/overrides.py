import json
import os
from typing import Any, Dict

DEFAULT = {
    "ignore_movies": [],
    "ignore_franchises": [],
    "ignore_directors": [],
    "ignore_actors": [],
    "wishlist_movies": [],
}

def load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return dict(DEFAULT)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in DEFAULT.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return dict(DEFAULT)

def save_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def add_unique(lst, value):
    if value not in lst:
        lst.append(value)

def remove_value(lst, value):
    try:
        lst.remove(value)
    except ValueError:
        pass