# -*- coding: utf-8 -*-
"""
즐겨찾기(포인트) 목록. data/favorite.json 에 저장.
형식: [ {"name", "lat", "lon", "direction", "start_lat", "start_lon", "end_lat", "end_lon"}, ... ]
기준좌표(lat,lon), 시작좌표(start_lat,start_lon), 종료좌표(end_lat,end_lon).
"""
import json
from pathlib import Path
from typing import Any
from gps_log_generator_app.runtime_paths import get_runtime_root

# 프로젝트 루트 기준 data 폴더
_PROJECT_ROOT = get_runtime_root()
_DATA_DIR = _PROJECT_ROOT / "data"
_FAVORITE_PATH = _DATA_DIR / "favorite.json"


def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_favorites() -> list[dict[str, Any]]:
    """data/favorite.json 에서 목록 로드. 없거나 오류 시 빈 리스트."""
    if not _FAVORITE_PATH.exists():
        return []
    try:
        with open(_FAVORITE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return [
            x
            for x in data
            if isinstance(x, dict) and "name" in x and "lat" in x and "lon" in x
        ]
    except (json.JSONDecodeError, OSError):
        return []


def save_favorites(items: list[dict[str, Any]]) -> None:
    """목록을 data/favorite.json 에 저장."""
    _ensure_data_dir()
    with open(_FAVORITE_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
