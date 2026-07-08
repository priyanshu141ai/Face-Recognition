Set-Location (Join-Path $PSScriptRoot "..")
$env:DETECTOR_PROVIDER = "mock"
$env:RECOGNIZER_PROVIDER = "mock"
python -m uvicorn app.main:app --reload
