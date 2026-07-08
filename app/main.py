from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routes_faces import router as faces_router
from app.api.v1.routes_health import router as health_router
from app.api.v1.routes_models import router as models_router
from app.core.errors import FaceQualityError, InvalidImagePayloadError
from app.core.logging import configure_logging

load_dotenv()
configure_logging()

app = FastAPI(title="Face Recognition Backend", version="phase-4.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(faces_router)
app.include_router(models_router)


@app.exception_handler(FaceQualityError)
async def face_quality_handler(_, exc: FaceQualityError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error_code": exc.code, "message": exc.message})


@app.exception_handler(InvalidImagePayloadError)
async def invalid_image_handler(_, exc: InvalidImagePayloadError) -> JSONResponse:
    return JSONResponse(status_code=415, content={"error_code": "invalid_image_payload", "message": exc.message})


@app.exception_handler(FileNotFoundError)
async def missing_model_handler(_, exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"error_code": "model_not_found", "message": str(exc)})


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "face-recognition-backend", "version": "phase-4.1"}
