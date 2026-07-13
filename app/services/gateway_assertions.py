from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import jwt
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security_errors import SecurityDomainError
from app.schemas.gateway import DeviceAttestationClaim, GatewayAssertionClaims
from app.services.ess_repository import EssRepository
from app.services.security_audit import SecurityAuditService


REQUIRED_CLAIMS = [
    "iss", "aud", "sub", "iat", "nbf", "exp", "jti", "tenant_id", "user_id",
    "device_id", "action", "request_id", "http_method", "request_path",
    "device_key_version", "session_id", "gateway_version",
]


def _csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


@lru_cache(maxsize=8)
def _load_jwks(path_value: str, modified_ns: int) -> dict[str, object]:
    del modified_ns
    path = Path(path_value)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("JWKS exceeds the size limit")
    document = json.loads(path.read_text(encoding="utf-8"))
    keys = document.get("keys") if isinstance(document, dict) else None
    if not isinstance(keys, list) or not keys:
        raise ValueError("JWKS must contain public keys")
    loaded: dict[str, object] = {}
    for item in keys:
        if not isinstance(item, dict):
            raise ValueError("JWKS key is invalid")
        kid = item.get("kid")
        if not isinstance(kid, str) or not kid or kid in loaded:
            raise ValueError("JWKS kid is missing or duplicated")
        if item.get("kty") != "EC" or item.get("crv") != "P-256" or "d" in item:
            raise ValueError("JWKS must contain public P-256 EC keys")
        if item.get("alg", "ES256") != "ES256" or item.get("use", "sig") != "sig":
            raise ValueError("JWKS key policy is invalid")
        if "key_ops" in item and "verify" not in item["key_ops"]:
            raise ValueError("JWKS key cannot verify signatures")
        loaded[kid] = jwt.algorithms.ECAlgorithm.from_jwk(json.dumps(item))
    return loaded


def ensure_gateway_trust_ready(settings: Settings) -> None:
    if not settings.gateway_assertion_required:
        return
    if not settings.gateway_jwks_path or not settings.gateway_assertion_issuer or not settings.gateway_assertion_audience:
        raise RuntimeError("gateway trust is not configured")
    path = Path(settings.gateway_jwks_path)
    _load_jwks(str(path.resolve()), path.stat().st_mtime_ns)


class GatewayAssertionService:
    def __init__(
        self,
        settings: Settings,
        repository: EssRepository,
        audit: SecurityAuditService,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.audit = audit

    def verify(
        self,
        assertion: str,
        *,
        method: str,
        path: str,
        request_id: str | None,
        expected_action: str,
        require_active_device: bool,
    ) -> GatewayAssertionClaims:
        try:
            claims = self._decode(assertion)
            self._validate_binding(claims, method, path, request_id, expected_action)
            self._validate_attestation(claims.device_attestation)
            if require_active_device:
                self._validate_device(claims)
            self._claim_jti(claims)
        except SecurityDomainError as exc:
            self.audit.record("gateway_assertion_rejected", "blocked", reason_code=exc.code)
            raise
        self.audit.record(
            "gateway_assertion_accepted", "allowed", user_id=claims.user_id,
            device_id=claims.device_id, request_id=claims.request_id,
        )
        return claims

    def _decode(self, assertion: str) -> GatewayAssertionClaims:
        settings = self.settings
        if not settings.gateway_jwks_path or not settings.gateway_assertion_issuer or not settings.gateway_assertion_audience:
            raise SecurityDomainError("gateway_trust_not_configured", "Gateway trust is not configured.", status_code=503)
        try:
            header = jwt.get_unverified_header(assertion)
            if header.get("alg") != "ES256" or not isinstance(header.get("kid"), str):
                raise SecurityDomainError("gateway_algorithm_rejected", "Gateway assertion algorithm is not allowed.", status_code=401)
            path = Path(settings.gateway_jwks_path)
            keys = _load_jwks(str(path.resolve()), path.stat().st_mtime_ns)
            key = keys.get(header["kid"])
            if key is None:
                raise SecurityDomainError("gateway_key_unknown", "Gateway signing key is not trusted.", status_code=401)
            payload = jwt.decode(
                assertion,
                key=key,
                algorithms=["ES256"],
                issuer=settings.gateway_assertion_issuer,
                audience=settings.gateway_assertion_audience,
                leeway=settings.gateway_assertion_clock_skew_seconds,
                options={"require": REQUIRED_CLAIMS},
            )
            claims = GatewayAssertionClaims.model_validate(payload)
        except SecurityDomainError:
            raise
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise SecurityDomainError("gateway_jwks_invalid", "Gateway trust keys are unavailable.", status_code=503) from exc
        except jwt.ExpiredSignatureError as exc:
            raise SecurityDomainError("gateway_assertion_expired", "Gateway assertion has expired.", status_code=401) from exc
        except jwt.ImmatureSignatureError as exc:
            raise SecurityDomainError("gateway_assertion_not_yet_valid", "Gateway assertion is not yet valid.", status_code=401) from exc
        except jwt.InvalidIssuerError as exc:
            raise SecurityDomainError("gateway_issuer_invalid", "Gateway assertion issuer is not trusted.", status_code=401) from exc
        except jwt.InvalidAudienceError as exc:
            raise SecurityDomainError("gateway_audience_invalid", "Gateway assertion audience is not allowed.", status_code=401) from exc
        except (jwt.InvalidTokenError, ValidationError, TypeError) as exc:
            raise SecurityDomainError("gateway_assertion_invalid", "Gateway assertion validation failed.", status_code=401) from exc
        now = int(datetime.now(timezone.utc).timestamp())
        if claims.sub != claims.user_id or claims.exp <= claims.iat or claims.exp - claims.iat > settings.gateway_assertion_max_ttl_seconds:
            raise SecurityDomainError("gateway_claims_invalid", "Gateway assertion claims are invalid.", status_code=401)
        if claims.iat > now + settings.gateway_assertion_clock_skew_seconds:
            raise SecurityDomainError("gateway_assertion_invalid", "Gateway assertion validation failed.", status_code=401)
        if claims.tenant_id not in _csv(settings.gateway_allowed_tenants):
            raise SecurityDomainError("gateway_tenant_mismatch", "Gateway tenant is not allowed.", status_code=403)
        return claims

    @staticmethod
    def _validate_binding(
        claims: GatewayAssertionClaims,
        method: str,
        path: str,
        request_id: str | None,
        expected_action: str,
    ) -> None:
        if not request_id:
            raise SecurityDomainError("request_id_required", "X-Request-ID is required.", status_code=422)
        action_matches = (
            claims.action.startswith(expected_action[:-1])
            if expected_action.endswith("*") else claims.action == expected_action
        )
        if claims.action != expected_action and not (expected_action.endswith("*") and action_matches):
            raise SecurityDomainError("gateway_action_mismatch", "Gateway action does not match this endpoint.", status_code=403)
        if (
            claims.http_method != method.upper()
            or claims.request_path != path
            or claims.request_id != request_id
        ):
            raise SecurityDomainError("gateway_request_mismatch", "Gateway assertion does not match this request.", status_code=403)

    def _validate_attestation(self, claim: DeviceAttestationClaim | None) -> None:
        if claim is None:
            if self.settings.require_recent_device_attestation:
                raise SecurityDomainError("device_attestation_required", "Recent device attestation is required.", status_code=403)
            return
        providers = _csv(self.settings.allowed_attestation_providers)
        verdicts = _csv(self.settings.allowed_attestation_verdicts)
        app_ids = _csv(self.settings.allowed_attestation_app_identifiers)
        expected_platform = {"play_integrity": "android", "app_attest": "ios"}.get(claim.provider)
        now = int(datetime.now(timezone.utc).timestamp())
        if claim.provider not in providers or expected_platform != claim.platform:
            raise SecurityDomainError("device_attestation_provider_invalid", "Device attestation provider is not allowed.", status_code=403)
        if claim.verdict not in verdicts:
            raise SecurityDomainError("device_attestation_rejected", "Device attestation verdict was rejected.", status_code=403)
        if not app_ids or claim.app_identifier not in app_ids:
            raise SecurityDomainError("device_attestation_app_invalid", "Device attestation app is not allowed.", status_code=403)
        if not now - self.settings.device_attestation_max_age_seconds <= claim.checked_at <= now + self.settings.gateway_assertion_clock_skew_seconds:
            raise SecurityDomainError("device_attestation_stale", "Device attestation is not recent.", status_code=403)

    def _validate_device(self, claims: GatewayAssertionClaims) -> None:
        record = self.repository.get_device_security_state(claims.user_id, claims.device_id)
        if not record:
            raise SecurityDomainError("device_not_registered", "The asserted device is not registered.", status_code=403)
        if record.get("revoked_at") is not None:
            raise SecurityDomainError("device_revoked", "The asserted device is revoked.", status_code=403)
        if int(record.get("key_version") or 0) != claims.device_key_version:
            raise SecurityDomainError("device_key_version_mismatch", "The asserted device key version is stale.", status_code=403)
        attestation = claims.device_attestation
        if attestation is not None and record.get("platform") != attestation.platform:
            raise SecurityDomainError("device_attestation_platform_mismatch", "Device attestation platform does not match registration.", status_code=403)

    def _claim_jti(self, claims: GatewayAssertionClaims) -> None:
        scope = self.audit.privacy_hash(f"{claims.iss}:{claims.tenant_id}") or "gateway"
        fingerprint = hashlib.sha256(claims.jti.encode("utf-8")).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(seconds=self.settings.gateway_jti_replay_ttl_seconds)
        if not self.repository.claim_replay_record(scope, fingerprint, "gateway_jti", expires):
            raise SecurityDomainError("gateway_assertion_replayed", "Gateway assertion was already used.", status_code=409)
