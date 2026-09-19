from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import LeaderboardResponse
from app.security import get_current_user

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


def _mask_name(email: str) -> str:
    """Return first 2 letters of the email local part + '***'."""
    local = email.split("@")[0]
    prefix = local[:2] if len(local) >= 2 else local
    return f"{prefix}***"


def _format_leaderboard_name(user: User) -> str:
    """
    Format leaderboard name:
    - full name (trimmed, spaces collapsed, at most 60 characters) when present
    - otherwise masked email name
    """
    if user.name and user.name.strip():
        collapsed = " ".join(user.name.strip().split())
        if collapsed:
            return collapsed[:60]
    return _mask_name(user.email)


@router.get("", response_model=LeaderboardResponse)
def get_leaderboard(
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the top-N users by XP (descending, tiebreak by user id ascending).
    Only users with xp > 0 are listed.
    Equal XP shares the same rank (dense-ish: rank = 1 + count of users with MORE xp).
    The response never contains email or user id.
    """
    # Fetch all users with xp > 0, ordered by xp desc then id asc
    all_ranked = (
        db.query(User)
        .filter(User.xp > 0)
        .order_by(User.xp.desc(), User.id.asc())
        .all()
    )

    # Assign ranks: rank = 1 + number of users with strictly more XP
    # Pre-compute a mapping: xp_value -> rank
    # Because rows are sorted xp desc, we track the rank using a counter
    items = []
    rank_for_xp: dict[int, int] = {}
    counter = 1  # position pointer (1-based)

    for user in all_ranked:
        if user.xp not in rank_for_xp:
            rank_for_xp[user.xp] = counter
        counter += 1  # always advance position; rank stays the same for ties

    # Build the leaderboard slice
    for user in all_ranked[:limit]:
        rank = rank_for_xp[user.xp]
        items.append(
            {
                "rank": rank,
                "name": _format_leaderboard_name(user),
                "xp": user.xp,
                "is_me": user.id == current_user.id,
            }
        )

    # Compute "me" section
    my_rank = None
    if current_user.xp > 0:
        if current_user.xp in rank_for_xp:
            my_rank = rank_for_xp[current_user.xp]
        else:
            # current_user has xp > 0 but was not in all_ranked (shouldn't happen, but be safe)
            my_rank = None

    return LeaderboardResponse(
        items=items,
        me={"rank": my_rank, "xp": current_user.xp},
    )
