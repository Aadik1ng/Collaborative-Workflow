"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.collaborators import router as collaborators_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.projects import router as projects_router
from app.api.v1.workspaces import router as workspaces_router

api_router = APIRouter()

# Include all routers
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(projects_router, prefix="/projects", tags=["Projects"])
api_router.include_router(workspaces_router, tags=["Workspaces"])
api_router.include_router(collaborators_router, tags=["Collaborators"])
api_router.include_router(jobs_router, prefix="/jobs", tags=["Jobs"])
