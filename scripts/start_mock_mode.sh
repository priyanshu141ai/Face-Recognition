#!/usr/bin/env sh
cd "$(dirname "$0")/.."
export DETECTOR_PROVIDER="mock"
export RECOGNIZER_PROVIDER="mock"
python -m uvicorn app.main:app --reload
