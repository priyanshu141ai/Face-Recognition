# API Authentication

Authentication ka matlab hai API ko sirf allowed app/backend use kar sake.

Is backend me simple bearer-token auth hai. Env var:

```text
API_BEARER_TOKEN
```

## Local Development

Local dev me token empty chhod sakte ho:

```powershell
$env:API_BEARER_TOKEN=""
python -m uvicorn app.main:app --reload
```

Token empty hai to protected endpoints public chalenge. Ye sirf local testing ke liye hai.

## Production / App Integration

Production me token required rakho:

```powershell
$env:API_BEARER_TOKEN="my-secret-token"
python -m uvicorn app.main:app --reload
```

App developer har protected request me ye header bhejega:

```text
Authorization: Bearer my-secret-token
```

## Protected Endpoints

```text
GET  /v1/models/current
POST /v1/faces/detect
POST /v1/faces/embed
POST /v1/faces/verify
```

## Public Endpoints

```text
GET /healthz
GET /readyz
```

`/readyz` public rakha gaya hai local/container health checks ke liye. Isme secret token ya embeddings expose nahi hote.

## curl Tests

Without token:

```powershell
curl http://127.0.0.1:8000/v1/models/current
```

Expected when token is enabled:

```text
401 Unauthorized
```

Wrong token:

```powershell
curl -H "Authorization: Bearer wrong-token" http://127.0.0.1:8000/v1/models/current
```

Correct token:

```powershell
curl -H "Authorization: Bearer my-secret-token" http://127.0.0.1:8000/v1/models/current
```

Expected:

```text
200 OK
```

## Python Requests Example

```python
import requests

headers = {"Authorization": "Bearer my-secret-token"}
response = requests.get("http://127.0.0.1:8000/v1/models/current", headers=headers)
print(response.status_code, response.json())
```

## Auth Test Script

```powershell
python scripts\test_authentication.py --base-url http://127.0.0.1:8000 --token my-secret-token
```

Expected output:

```text
healthz public                  PASS  200  ok
models/current no token         PASS  401  protected
models/current wrong token      PASS  401  protected
models/current correct token    PASS  200  authorized
faces/verify no token           PASS  401  protected
faces/verify correct token      PASS  200/422 authorized path reached
```

## Common Errors

```text
401 Missing Authorization header
```

Header missing hai ya token enabled hai.

```text
401 Invalid token
```

Token wrong hai.

```text
Token set nahi hai, API public chal rahi hai
```

`API_BEARER_TOKEN` empty hai. Production me ye unsafe hai.

## Production Warning

Bearer token initial backend-to-app integration ke liye okay hai. Production hardening later add karo:

- HTTPS
- JWT/user authentication if needed
- API gateway
- rate limiting
- token rotation
- IP/domain restrictions if applicable
