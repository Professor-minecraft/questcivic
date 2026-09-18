from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Work
from app.schemas import (
    LocationOptionsResponse,
    LocationResolveRequest,
    LocationResolveResponse,
)
from app.security import get_current_user
from app.services.geo import find_constituency, match_to_dataset, reverse_geocode

router = APIRouter(prefix="/location", tags=["location"])


@router.get("/options", response_model=LocationOptionsResponse)
def get_location_options(
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Distinct sorted states
    states = sorted([
        s[0]
        for s in db.query(Work.state).distinct().all()
        if s[0]
    ])

    districts = []
    if state:
        districts = sorted([
            d[0]
            for d in db.query(Work.district)
            .filter(Work.state == state)
            .distinct()
            .all()
            if d[0]
        ])

    constituencies = []
    if state and district:
        # Constituencies come from Lok Sabha rows only
        constituencies = sorted([
            c[0]
            for c in db.query(Work.constituency)
            .filter(
                Work.source == "LS",
                Work.state == state,
                Work.district == district,
                Work.constituency.isnot(None),
                Work.constituency != "",
            )
            .distinct()
            .all()
            if c[0]
        ])

    return LocationOptionsResponse(
        states=states,
        districts=districts,
        constituencies=constituencies,
    )


@router.post("/resolve", response_model=LocationResolveResponse)
def resolve_location(
    req: LocationResolveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 1. Reverse geocode via Nominatim
    state_text, district_text = reverse_geocode(req.lat, req.lng)

    # 2. Match to dataset
    matched_state, matched_district = (None, None)
    if state_text:
        matched_state, matched_district = match_to_dataset(state_text, district_text, db)

    # 3. Find constituency via geojson if available
    constituency = find_constituency(req.lat, req.lng)

    # 4. If constituency is None, find constituency_options for resolved state & district
    constituency_options = []
    if constituency is None and matched_state and matched_district:
        constituency_options = sorted([
            c[0]
            for c in db.query(Work.constituency)
            .filter(
                Work.source == "LS",
                Work.state == matched_state,
                Work.district == matched_district,
                Work.constituency.isnot(None),
                Work.constituency != "",
            )
            .distinct()
            .all()
            if c[0]
        ])

    return LocationResolveResponse(
        state=matched_state,
        district=matched_district,
        constituency=constituency,
        constituency_options=constituency_options,
    )
