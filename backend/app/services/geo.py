import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx
from rapidfuzz import process, utils
from shapely.geometry import Point, shape
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Work

_GEOJSON_CACHE: Optional[List[Dict[str, Any]]] = None
_GEOJSON_LOADED_PATH: Optional[str] = None


def reverse_geocode(lat: float, lng: float) -> Tuple[Optional[str], Optional[str]]:
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat,
        "lon": lng,
        "format": "jsonv2",
    }
    headers = {
        "User-Agent": "CivicQuestApp/1.0 (https://github.com/CivicQuest; civicquest-admin@gmail.com)",
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                address = data.get("address", {})
                state_text = address.get("state")
                district_text = (
                    address.get("state_district")
                    or address.get("county")
                    or address.get("district")
                    or address.get("city")
                    or address.get("town")
                )
                return state_text, district_text
    except Exception:
        # Fall back to None on network failure, timeout, etc.
        pass
    return None, None


def match_to_dataset(
    state_text: Optional[str],
    district_text: Optional[str],
    db: Session,
) -> Tuple[Optional[str], Optional[str]]:
    if not state_text:
        return None, None

    # Find closest state from distinct values in works table
    states = [s[0] for s in db.query(Work.state).distinct().all() if s[0]]
    if not states:
        return None, None

    state_match = process.extractOne(
        state_text,
        states,
        processor=utils.default_process,
        score_cutoff=85,
    )
    if not state_match:
        return None, None

    matched_state = state_match[0]
    matched_district = None

    if district_text:
        districts = [
            d[0]
            for d in db.query(Work.district)
            .filter(Work.state == matched_state)
            .distinct()
            .all()
            if d[0]
        ]
        if districts:
            district_match = process.extractOne(
                district_text,
                districts,
                processor=utils.default_process,
                score_cutoff=85,
            )
            if district_match:
                matched_district = district_match[0]

    return matched_state, matched_district


def _load_geojson_features(geojson_path: str) -> List[Dict[str, Any]]:
    global _GEOJSON_CACHE, _GEOJSON_LOADED_PATH
    if _GEOJSON_CACHE is not None and _GEOJSON_LOADED_PATH == geojson_path:
        return _GEOJSON_CACHE

    p = Path(geojson_path)
    if not p.is_file():
        return []

    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            features = data.get("features", [])
            _GEOJSON_CACHE = features
            _GEOJSON_LOADED_PATH = geojson_path
            return features
    except Exception:
        return []


def find_constituency(lat: float, lng: float) -> Optional[str]:
    path = settings.GEOJSON_PATH
    if not path:
        return None

    features = _load_geojson_features(path)
    if not features:
        return None

    point = Point(lng, lat)  # Note: (x=longitude, y=latitude)

    for feature in features:
        try:
            geom = feature.get("geometry")
            if not geom:
                continue
            poly = shape(geom)
            if poly.contains(point):
                props = feature.get("properties", {})
                # Look for common constituency name keys
                constituency = (
                    props.get("PC_NAME")
                    or props.get("pc_name")
                    or props.get("constituency")
                    or props.get("CONSTITUENCY")
                    or props.get("name")
                    or props.get("NAME")
                )
                if constituency:
                    return str(constituency).strip()
        except Exception:
            continue

    return None
