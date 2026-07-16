# Run The App

Use these commands from the backend folder:

```powershell
cd "C:\projects\Face Recognition\face-recognition-backend"
. ..\.venv\Scripts\Activate.ps1
```

If packages are missing:

```powershell
python -m pip install -r requirements.txt
```

## 1. Run Mock Mode

Mock mode is for API testing. Real face recognition nahi hota.

```powershell
.\scripts\start_mock_mode.ps1
```

Open:

```text
http://127.0.0.1:8000/docs
```

Check:

```powershell
python scripts\check_active_model_mode.py --expected mock
```

## 2. Run Real Mode

Real mode YuNet + ArcFace ONNX use karta hai.

Required local files:

```text
models/face_detection_yunet_2023mar.onnx
models/face-recognition-resnet100-arcface.onnx
```

Start:

```powershell
.\scripts\start_real_mode.ps1
```

Check:

```powershell
python scripts\check_active_model_mode.py --expected real
```

Expected:

```text
active_mode=real
detector=yunet_2023mar_opencv
recognizer=arcface_r100_onnx
embedding_dim=512
```

## 3. Run With API Token

Use this when testing protected endpoints.

```powershell
$env:API_BEARER_TOKEN="my-secret-token"
python -m uvicorn app.main:app --reload
```

Auth test:

```powershell
python scripts\test_authentication.py --base-url http://127.0.0.1:8000 --token my-secret-token
```

## 4. Test Images

Single image:

```powershell
python scripts\manual_test_single_image.py "test_images\priyanshu.png"
```

Compare two images:

```powershell
python scripts\manual_test_compare_images.py "test_images\test_1.png" "test_images\test_2.png"
```

With token:

```powershell
python scripts\manual_test_compare_images.py "test_images\test_1.png" "test_images\test_2.png" --token my-secret-token
```

## 5. Verify Everything

```powershell
python -m pytest -q
python scripts\validate_model_artifacts.py
python scripts\smoke_test_api.py --base-url http://127.0.0.1:8000
```

## 6. Stop App

In the terminal running Uvicorn:

```text
Ctrl + C
```

## Common Issues

```text
No module named uvicorn
```

Fix:

```powershell
python -m pip install -r requirements.txt
```

```text
Unable to connect to the remote server
```

Server running nahi hai. Start mock or real mode.

```text
401 Unauthorized
```

`API_BEARER_TOKEN` set hai. Correct bearer token bhejo.

```text
no_face_detected
```

Real detector image me face detect nahi kar pa raha. Clear, front-facing face image use karo.



cd "C:\projects\Face Recognition\face-recognition-backend"
. ..\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
.\scripts\start_real_mode.ps1

python scripts\check_active_model_mode.py --expected real

python scripts\manual_test_compare_images.py "test_images\test_1.png" "test_images\test_2.png"