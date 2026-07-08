import logging

from app.core.logging import SensitiveDataFilter
from app.validation.checks import check_no_sensitive_logging_patterns


def test_sensitive_log_patterns_fail_validation() -> None:
    text = "Authorization: Bearer abc data:image/png;base64,xxx raw image embedding traceback"
    assert check_no_sensitive_logging_patterns(text).status == "FAIL"


def test_sensitive_filter_blocks_raw_payload_messages() -> None:
    filt = SensitiveDataFilter()
    blocked = logging.LogRecord("x", logging.INFO, __file__, 1, "base64 payload embedding", (), None)
    allowed = logging.LogRecord("x", logging.INFO, __file__, 1, "request completed", (), None)
    assert filt.filter(blocked) is False
    assert filt.filter(allowed) is True
