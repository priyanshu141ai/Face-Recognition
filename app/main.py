from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routes_faces import router as faces_router
from app.api.v1.routes_ess import router as ess_router
from app.api.v1.routes_health import router as health_router
from app.api.v1.routes_models import router as models_router
from app.core.config import cors_origins, get_settings, validate_deployment_settings
from app.core.errors import FaceQualityError, InvalidImagePayloadError
from app.core.logging import configure_logging

load_dotenv()
configure_logging()
settings = get_settings()
validate_deployment_settings(settings)
allowed_origins = cors_origins(settings)

app = FastAPI(
    title="Face Recognition Backend",
    version="phase-5",
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials="*" not in allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(faces_router)
app.include_router(models_router)
app.include_router(ess_router)


@app.exception_handler(FaceQualityError)
async def face_quality_handler(_, exc: FaceQualityError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error_code": exc.code, "message": exc.message})


@app.exception_handler(InvalidImagePayloadError)
async def invalid_image_handler(_, exc: InvalidImagePayloadError) -> JSONResponse:
    return JSONResponse(status_code=415, content={"error_code": "invalid_image_payload", "message": exc.message})


@app.exception_handler(FileNotFoundError)
async def missing_model_handler(_, exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error_code": "model_not_found", "message": "Required model artifact is unavailable"},
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "face-recognition-backend", "version": "phase-5"}
