from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.security_errors import SecurityDomainError
from app.schemas.liveness import DeviceProof
from app.services.ess_repository import EssRepository


ALGORITHM = "ECDSA_P256_SHA256"
CANONICAL_VERSION = "v1"


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_public_key(public_key_pem: str) -> tuple[ec.EllipticCurvePublicKey, str]:
    if len(public_key_pem.encode("utf-8")) > 4096:
        raise SecurityDomainError("device_public_key_invalid", "The device public key is invalid.", status_code=422)
    try:
        key = serialization.load_pem_public_key(public_key_pem.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise SecurityDomainError("device_public_key_invalid", "The device public key is invalid.", status_code=422) from exc
    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
        raise SecurityDomainError(
            "device_public_key_unsupported",
            "Only an ECDSA P-256 public key is supported.",
            status_code=422,
        )
    der = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return key, hashlib.sha256(der).hexdigest()


def canonical_payload(record: dict[str, object], nonce: str) -> bytes:
    payload = {
        "version": CANONICAL_VERSION,
        "challenge_id": str(record["challenge_id"]),
        "nonce": nonce,
        "user_id": str(record["user_id"]),
        "device_id": str(record["device_id"]),
        "operation": str(record["operation"]),
        "issued_at": utc(record["issued_at"]).isoformat(),
        "expires_at": utc(record["expires_at"]).isoformat(),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


@dataclass(frozen=True)
class IssuedDeviceChallenge:
    challenge_id: str
    nonce: str
    user_id: str
    device_id: str
    operation: str
    issued_at: datetime
    expires_at: datetime


class DeviceProofService:
    def __init__(self, repository: EssRepository, ttl_seconds: int) -> None:
        self.repository = repository
        self.ttl_seconds = ttl_seconds

    def issue(self, user_id: str, device_id: str, operation: str) -> IssuedDeviceChallenge:
        now = datetime.now(timezone.utc)
        nonce = secrets.token_urlsafe(32)
        record = {
            "challenge_id": str(uuid4()),
            "user_id": user_id,
            "device_id": device_id,
            "nonce_hash": hashlib.sha256(nonce.encode("ascii")).hexdigest(),
            "operation": operation,
            "issued_at": now,
            "expires_at": now + timedelta(seconds=self.ttl_seconds),
            "status": "issued",
        }
        self.repository.create_device_challenge(**record)
        return IssuedDeviceChallenge(nonce=nonce, **{k: record[k] for k in (
            "challenge_id", "user_id", "device_id", "operation", "issued_at", "expires_at"
        )})

    def verify(
        self,
        proof: DeviceProof | None,
        *,
        user_id: str,
        device_id: str,
        operation: str,
        public_key_pem: str,
    ) -> str:
        if proof is None:
            raise SecurityDomainError("device_proof_required", "Cryptographic device proof is required.", status_code=401)
        record = self.repository.get_device_challenge(proof.challenge_id)
        if not record:
            raise SecurityDomainError("device_challenge_invalid", "The device challenge is invalid.", status_code=401)
        if record["used_at"] is not None:
            raise SecurityDomainError("device_challenge_reused", "The device challenge was already used.", status_code=409)
        if utc(record["expires_at"]) <= datetime.now(timezone.utc):
            raise SecurityDomainError("device_challenge_expired", "The device challenge has expired.", status_code=409)
        if record["user_id"] != user_id or record["device_id"] != device_id or record["operation"] != operation:
            raise SecurityDomainError("device_proof_scope_invalid", "The device proof does not match this request.", status_code=403)
        if not secrets.compare_digest(
            str(record["nonce_hash"]), hashlib.sha256(proof.nonce.encode("utf-8")).hexdigest()
        ):
            raise SecurityDomainError("device_nonce_invalid", "The device challenge nonce is invalid.", status_code=403)
        key, fingerprint = validate_public_key(public_key_pem)
        try:
            signature = base64.b64decode(proof.signature, validate=True)
            key.verify(signature, canonical_payload(record, proof.nonce), ec.ECDSA(hashes.SHA256()))
        except (binascii.Error, InvalidSignature, ValueError) as exc:
            raise SecurityDomainError("device_signature_invalid", "Device signature verification failed.", status_code=403) from exc
        if not self.repository.consume_device_challenge(proof.challenge_id):
            raise SecurityDomainError("device_challenge_reused", "The device challenge was already used.", status_code=409)
        return fingerprint
