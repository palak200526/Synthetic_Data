from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.controllers.dataset_controller import (
    router as dataset_router
)
from backend.controllers.profile_controller import (
    router as profile_router
)
from backend.controllers.configuration_controller import (
    router as configuration_router
)

from backend.controllers.generation_controller import (
    router as generation_router
)

from backend.controllers.evaluation_controller import (
    router as evaluation_router
)

from backend.controllers.dashboard_controller import (
    router as dashboard_router
)

from backend.controllers.report_controller import (
    router as report_router
)

from backend.controllers.download_controller import (
    router as download_router
)

from backend.controllers.id_generation_controller import (
    router as id_generation_router,
)

from backend.controllers.preprocessing_controller import router as preprocessing_router

from backend.controllers.relationship_controller import (
    router as relationship_router,
)

app = FastAPI(
    title="Synthetic Data Platform API",
    description="Backend API for the Synthetic Data Platform",
    version="1.0.0",
)


# CORS CONFIGURATION
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# COMMON ERROR HANDLING
@app.exception_handler(ValueError)
async def value_error_handler(
    request: Request,
    exc: ValueError
):
    return JSONResponse(
        status_code=400,
        content={
            "status": "error",
            "message": str(exc)
        }
    )


@app.get("/")
def root():
    return {
        "message": "Synthetic Data Platform API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


# ROUTERS
app.include_router(dataset_router)
app.include_router(profile_router)
app.include_router(configuration_router)
app.include_router(dataset_router)
app.include_router(profile_router)
app.include_router(configuration_router)

app.include_router(generation_router)
app.include_router(evaluation_router)
app.include_router(dashboard_router)
app.include_router(report_router)
app.include_router(download_router)
app.include_router(id_generation_router)
app.include_router(preprocessing_router)
app.include_router(relationship_router)