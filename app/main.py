from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routes_faces import router as faces_router
from app.api.v1.routes_ess import router as ess_router
from app.api.v1.routes_health import router as health_router
from app.api.v1.routes_models import router as models_router
from app.api.v1.routes_liveness import router as liveness_router
from app.core.config import cors_origins, get_settings, validate_deployment_settings
from app.core.errors import FaceQualityError, InvalidImagePayloadError
from app.core.security_errors import SecurityDomainError
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
app.include_router(liveness_router)


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            security = operation.get("security", []) if isinstance(operation, dict) else []
            names = {name for item in security for name in item}
            if {"ServiceBearer", "GatewayAssertion"}.issubset(names):
                operation["security"] = [{"ServiceBearer": [], "GatewayAssertion": []}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request, exc: RequestValidationError) -> JSONResponse:
    if request.url.path == "/api/ess/face/register":
        errors = exc.errors()
        types = {error["type"] for error in errors}
        locations = [tuple(str(part) for part in error["loc"]) for error in errors]
        if "duplicate_enrollment_angle" in types:
            code, message = "duplicate_enrollment_angle", "Each enrollment angle must be provided once."
        elif any("enrollment_images" in location for location in locations) or "invalid_enrollment_angles" in types:
            code, message = "invalid_enrollment_angles", "Enrollment requires front, left, and right captures."
        else:
            code, message = "invalid_image_payload", "An enrollment image payload is invalid."
        return JSONResponse(status_code=422, content={"detail": {"code": code, "message": message}})
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})


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


@app.exception_handler(SecurityDomainError)
async def security_domain_error_handler(request, exc: SecurityDomainError) -> JSONResponse:
    request_id = request.headers.get("X-Request-ID")
    if request_id and (len(request_id) > 128 or not all(character.isalnum() or character in "._:-" for character in request_id)):
        request_id = None
    detail = {
        "request_id": request_id,
        "code": exc.code,
        "message": exc.message,
        "retry_after_seconds": exc.retry_after_seconds,
    }
    headers = {"Retry-After": str(exc.retry_after_seconds)} if exc.retry_after_seconds else None
    return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=headers)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "face-recognition-backend", "version": "phase-5"}
