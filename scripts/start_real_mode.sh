#!/usr/bin/env sh
cd "$(dirname "$0")/.."
export DETECTOR_PROVIDER="yunet"
export RECOGNIZER_PROVIDER="arcface_onnx"
export YUNET_MODEL_PATH="models/face_detection_yunet_2023mar.onnx"
export ARCFACE_MODEL_PATH="models/face-recognition-resnet100-arcface.onnx"
export REQUIRE_CALIBRATION="true"
python -m uvicorn app.main:app --workers 1
