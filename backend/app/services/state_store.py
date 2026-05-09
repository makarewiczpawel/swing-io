"""
State Store — proste persystowanie stanu w JSON na dysku.

Używa katalogu z `STATE_DIR` env (default: `/data` na Railway, `./.state` lokalnie).
Atomowy zapis: write do `.tmp` → rename. Tolerancja błędów: brak pliku = pusty stan.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DIR = "/data" if os.path.isdir("/data") else "./.state"
_STATE_DIR = Path(os.environ.get("STATE_DIR", _DEFAULT_DIR))
_lock = threading.Lock()


def _ensure_dir() -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning(f"Cannot create state dir {_STATE_DIR}: {e}")


def load(name: str) -> Optional[Any]:
    path = _STATE_DIR / f"{name}.json"
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load state {name}: {e}")
        return None


def save(name: str, data: Any) -> bool:
    _ensure_dir()
    path = _STATE_DIR / f"{name}.json"
    tmp  = path.with_suffix(".tmp")
    try:
        with _lock:
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(data, f, default=str, ensure_ascii=False)
            tmp.replace(path)
        return True
    except Exception as e:
        logger.error(f"Failed to save state {name}: {e}")
        return False
