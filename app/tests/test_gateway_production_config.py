import pytest

from app.core.config import validate_deployment_settings
from app.tests.test_production_security_config import _secure, _staging


@pytest.mark.parametrize(
    "override,expected",
    [
        ({"gateway_assertion_required": False}, "signed gateway assertions"),
        ({"allow_unsigned_identity_headers": True}, "unsigned identity headers"),
        ({"gateway_assertion_issuer": None}, "GATEWAY_ASSERTION_ISSUER"),
        ({"gateway_assertion_audience": None}, "GATEWAY_ASSERTION_AUDIENCE"),
        ({"gateway_allowed_tenants": ""}, "GATEWAY_ALLOWED_TENANTS"),
        ({"gateway_jwks_path": None}, "GATEWAY_JWKS_PATH"),
        ({"gateway_assertion_allowed_algorithms": "HS256"}, "exactly ES256"),
        ({"gateway_assertion_max_ttl_seconds": 121}, "between 1 and 120"),
        ({"gateway_jti_replay_ttl_seconds": 60}, "cover assertion TTL"),
        ({"require_recent_device_attestation": False}, "REQUIRE_RECENT_DEVICE_ATTESTATION"),
        ({"allowed_attestation_app_identifiers": ""}, "ALLOWED_ATTESTATION_APP_IDENTIFIERS"),
    ],
)
def test_production_gateway_policy_fails_closed(override, expected) -> None:
    with pytest.raises(RuntimeError, match=expected):
        validate_deployment_settings(_secure(**override))


def test_staging_requires_gateway_assertions_but_can_defer_attestation() -> None:
    validate_deployment_settings(_staging(require_recent_device_attestation=False))
