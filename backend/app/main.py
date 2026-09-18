from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
import app.models  # Registers all models with Base.metadata
from app.routers.auth import auth_router, me_router
from app.routers.auditor import router as auditor_router
from app.routers.location import router as location_router
from app.routers.submissions import router as submissions_router
from app.routers.works import router as works_router
from app.security import init_auditor_credentials


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup
    Base.metadata.create_all(bind=engine)
    # Create in-memory bcrypt hash of AUDITOR_PASSWORD on startup
    init_auditor_credentials()
    yield


app = FastAPI(title="MPLADS Work Verification Portal", lifespan=lifespan)

# CORS configuration for FRONTEND_ORIGIN only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(location_router)
app.include_router(auditor_router)
app.include_router(works_router)
app.include_router(submissions_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
