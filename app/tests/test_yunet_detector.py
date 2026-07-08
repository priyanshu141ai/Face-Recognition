import os

import pytest

os.environ.setdefault("DETECTOR_PROVIDER", "mock")

from app.models.mock_detector import MockFaceDetector
from app.models.yunet_detector import YuNetFaceDetector


def test_mock_detector_still_works(monkeypatch):
    detector = MockFaceDetector()
    detections = detector.detect(b"test-image")
    assert len(detections) == 1


def test_yunet_missing_model_raises_clear_error(monkeypatch):
    monkeypatch.setattr("app.models.yunet_detector.os.path.exists", lambda path: False)
    with pytest.raises(FileNotFoundError, match="YuNet model not found"):
        YuNetFaceDetector()


def test_yunet_detect_uses_fake_output(monkeypatch):
    class FakeDetector:
        def __init__(self):
            self.input_size = None

        def setInputSize(self, size):
            self.input_size = size

        def detect(self, image):
            return [[10.0, 20.0, 30.0, 40.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 0.95]], None

    monkeypatch.setattr("app.models.yunet_detector.os.path.exists", lambda path: True)
    monkeypatch.setattr("app.models.yunet_detector.cv2.FaceDetectorYN.create", lambda *args, **kwargs: FakeDetector())
    monkeypatch.setattr("app.models.yunet_detector.cv2.imdecode", lambda *args, **kwargs: __import__("numpy").zeros((3, 3, 3), dtype=__import__("numpy").uint8))
    detector = YuNetFaceDetector()
    detections = detector.detect(b"\x89PNG\r\n\x1a\n")
    assert len(detections) == 1
    assert detections[0].bbox_xywh[0] == 10.0
    assert detections[0].landmarks5[0][0] == 2.0
    assert detections[0].detection_confidence == 0.95
