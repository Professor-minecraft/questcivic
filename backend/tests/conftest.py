import pytest
from app.main import app
from app.database import get_db


@pytest.fixture(autouse=True)
def manage_dependency_overrides(request):
    fname = request.node.fspath.basename
    if "test_staff_auth" in fname:
        import tests.test_staff_auth as tsa
        app.dependency_overrides[get_db] = tsa.override_get_db
    elif "test_leaderboard" in fname:
        import tests.test_leaderboard as tlb
        app.dependency_overrides[get_db] = tlb.override_get_db
    else:
        app.dependency_overrides.pop(get_db, None)

    yield

    if "test_staff_auth" in fname or "test_leaderboard" in fname:
        app.dependency_overrides.pop(get_db, None)
