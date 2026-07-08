Set-Location (Join-Path $PSScriptRoot "..")
$env:DETECTOR_PROVIDER = "yunet"
$env:RECOGNIZER_PROVIDER = "arcface_onnx"
$env:YUNET_MODEL_PATH = "models/face_detection_yunet_2023mar.onnx"
$env:ARCFACE_MODEL_PATH = "models/face-recognition-resnet100-arcface.onnx"
python -m uvicorn app.main:app --reload
