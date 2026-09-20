from pathlib import Path
import json

from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(tags=["browser"])


def _state_path() -> Path:
    settings = get_settings()
    return Path(settings.data_dir) / "browser-state.json"


def _load_state() -> dict:
    path = _state_path()
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"tabs": [], "favorites": []}


def _save_state(state: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


@router.get("/services/tabs")
def get_tabs():
    state = _load_state()
    return {"tabs": state.get("tabs", [])}


@router.put("/services/tabs")
def save_tabs(payload: dict):
    state = _load_state()
    tabs = payload.get("tabs", [])
    state["tabs"] = tabs if isinstance(tabs, list) else []
    _save_state(state)
    return {"ok": True, "tabs": state["tabs"]}


@router.get("/services/favorites")
def get_favorites():
    state = _load_state()
    return {"favorites": state.get("favorites", [])}


@router.put("/services/favorites")
def save_favorites(payload: dict):
    state = _load_state()
    favorites = payload.get("favorites", [])
    state["favorites"] = favorites if isinstance(favorites, list) else []
    _save_state(state)
    return {"ok": True, "favorites": state["favorites"]}
