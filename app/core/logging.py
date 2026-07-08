import logging
from typing import Any


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = str(getattr(record, "msg", ""))
        return "data:image" not in message and "base64" not in message.lower()


def configure_logging() -> None:
    logger = logging.getLogger("face_recognition_backend")
    if logger.handlers:
        return
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)
    logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(f"face_recognition_backend.{name}")


def log_event(logger: logging.Logger, **fields: Any) -> None:
    logger.info("event", extra={"event_fields": fields})
