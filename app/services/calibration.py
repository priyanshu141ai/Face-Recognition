class ScoreCalibrator:
    def __init__(self, version: str = "linear_mock_v1") -> None:
        self.version = version

    def calibrate(self, similarity: float) -> float:
        return round(float(similarity * 100.0), 2)
