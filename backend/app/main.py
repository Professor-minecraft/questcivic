from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
import app.models  # Registers all models with Base.metadata
from app.routers.auth import auth_router, me_router
from app.routers.auditor import router as auditor_router
from app.routers.auditor_complaints import router as auditor_complaints_router
from app.routers.auditor_me import router as auditor_me_router
from app.routers.complaints import router as complaints_router
from app.routers.location import router as location_router
from app.routers.profile import router as profile_router
from app.routers.submissions import router as submissions_router
from app.routers.works import router as works_router
from app.routers.leaderboard import router as leaderboard_router
from app.routers.staff_auth import router as staff_auth_router
from app.routers.admin_auditors import router as admin_auditors_router
from app.routers.auditor_invite import router as auditor_invite_router
from app.routers.admin_views import router as admin_views_router
from app.routers.admin_reviews import router as admin_reviews_router
from app.routers.signup import router as signup_router
from app.routers.login import router as login_router
from app.routers.password_reset import router as password_reset_router
from app.security import init_auditor_credentials, init_admin_credentials


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup
    Base.metadata.create_all(bind=engine)
    # Create in-memory bcrypt hashes at startup
    init_auditor_credentials()
    init_admin_credentials()
    yield


app = FastAPI(title="MPLADS Work Verification Portal", lifespan=lifespan)

from pathlib import Path
from fastapi.staticfiles import StaticFiles

# CORS configuration: parses comma-separated FRONTEND_ORIGIN, localhost allowed only in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve local uploads directly if storage is local or backward-compatible local files exist
uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Routers
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(profile_router)
app.include_router(location_router)
app.include_router(auditor_router)
app.include_router(auditor_me_router)
app.include_router(works_router)
app.include_router(submissions_router)
app.include_router(complaints_router)
app.include_router(auditor_complaints_router)
app.include_router(leaderboard_router)
app.include_router(staff_auth_router)
app.include_router(admin_auditors_router)
app.include_router(auditor_invite_router)
app.include_router(admin_views_router)
app.include_router(admin_reviews_router)
app.include_router(signup_router)
app.include_router(login_router)
app.include_router(password_reset_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
