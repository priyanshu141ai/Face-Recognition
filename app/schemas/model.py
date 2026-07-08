from pydantic import BaseModel


class ModelInfo(BaseModel):
    detector: str
    recognizer: str
    preprocessing: str
    threshold: str
    calibration: str


class ReadyResponse(BaseModel):
    status: str
    models_loaded: bool
    provider: str
    version: str
