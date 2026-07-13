import json
import time
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import ec


class TestGatewaySigner:
    __test__ = False

    def __init__(self, kid: str = "test-key-1") -> None:
        self.kid = kid
        self._private_key = ec.generate_private_key(ec.SECP256R1())

    def public_jwk(self) -> dict:
        value = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(self._private_key.public_key()))
        return {**value, "kid": self.kid, "use": "sig", "alg": "ES256"}

    def write_public_jwks(self, path, *others: "TestGatewaySigner") -> None:
        path.write_text(
            json.dumps({"keys": [self.public_jwk(), *(item.public_jwk() for item in others)]}),
            encoding="utf-8",
        )

    def sign(self, *, action: str, path: str, request_id: str, **overrides) -> str:
        now = int(time.time())
        payload = {
            "iss": "https://gateway.test",
            "aud": "face-api-test",
            "sub": "user-001",
            "iat": now,
            "nbf": now,
            "exp": now + 60,
            "jti": str(uuid4()),
            "tenant_id": "tenant-001",
            "user_id": "user-001",
            "device_id": "device-0001",
            "action": action,
            "request_id": request_id,
            "http_method": "GET",
            "request_path": path,
            "device_key_version": 1,
            "session_id": "session-0001",
            "gateway_version": "test-v1",
        }
        omitted = overrides.pop("_omit", ())
        payload.update(overrides)
        for name in omitted:
            payload.pop(name, None)
        return jwt.encode(payload, self._private_key, algorithm="ES256", headers={"kid": self.kid})
