import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    environment: str = "development"
    api_bearer_token: str | None = None
    gateway_assertion_required: bool = False
    allow_unsigned_identity_headers: bool = True
    gateway_assertion_issuer: str | None = None
    gateway_assertion_audience: str | None = None
    gateway_allowed_tenants: str = ""
    gateway_assertion_allowed_algorithms: str = "ES256"
    gateway_jwks_path: str | None = None
    gateway_assertion_max_ttl_seconds: int = 90
    gateway_assertion_clock_skew_seconds: int = 5
    gateway_jti_replay_ttl_seconds: int = 120
    require_recent_device_attestation: bool = False
    device_attestation_max_age_seconds: int = 120
    allowed_attestation_providers: str = "play_integrity,app_attest"
    allowed_attestation_verdicts: str = "MEETS_DEVICE_INTEGRITY,VALID"
    allowed_attestation_app_identifiers: str = ""
    ess_database_path: str = "data/ess.sqlite3"
    biometric_encryption_key: str | None = None
    biometric_encryption_key_version: int = 1
    device_reset_token: str | None = None
    cors_allowed_origins: str = "*"
    enable_api_docs: bool = True
    client_validation_rate_limit_per_minute: int = 30
    max_image_mb: float = 5.0
    max_image_pixels: int = 20_000_000
    log_level: str = "INFO"
    provider: str = "mock"
    version: str = "phase-5"
    detector_provider: str = "mock"
    recognizer_provider: str = "mock"
    yunet_model_path: str = "models/face_detection_yunet_2023mar.onnx"
    yunet_score_threshold: float = 0.85
    yunet_nms_threshold: float = 0.3
    yunet_top_k: int = 5000
    min_face_size: int = 20
    max_image_dimension: int = 640
    arcface_model_path: str = "models/face-recognition-resnet100-arcface.onnx"
    mobilefacenet_model_path: str = "models/mobilefacenet.onnx"
    mobilefacenet_input_size: int = 112
    mobilefacenet_embedding_dim: int = 512
    mobilefacenet_sha256: str = "9cc6e4a75f0e2bf0b1aed94578f144d15175f357bdc05e815e5c4a02b319eb4f"
    insightface_model_name: str = "buffalo_l"
    insightface_det_size: int = 640
    insightface_ctx_id: int = -1
    arcface_input_size: int = 112
    arcface_embedding_dim: int = 512
    arcface_sha256: str = "f3a6bc281e72f88862f5748b53be3d76b3b48f8f1ab1f4a537941bdc4e1b01da"
    arcface_normalization: str = "raw_rgb_0_255"
    arcface_use_gpu: bool = False
    onnx_providers: str = "CPUExecutionProvider"
    face_inference_concurrency: int = 2
    ort_intra_op_threads: int = 2
    ort_inter_op_threads: int = 1
    match_threshold: float = 0.40
    match_threshold_override: bool = False
    calibration_dir: str = "calibration"
    calibration_profile_path: str | None = None
    require_calibration: bool = False
    use_calibrated_threshold: bool = True
    return_embeddings_default: bool = False
    allow_embedding_return: bool = False
    benchmark_output_dir: str = "benchmark_reports"
    benchmark_target_fmr_values: str = "1e-3,1e-4,1e-5"
    benchmark_default_models: str = "arcface_onnx,mobilefacenet_onnx"
    benchmark_save_per_pair: bool = True
    database_url: str | None = None
    database_auto_create: bool = True
    allow_sqlite_in_production: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_connect_timeout_seconds: int = 10
    liveness_required: bool = False
    liveness_provider: str = "disabled"
    liveness_challenge_ttl_seconds: int = 90
    liveness_max_attempts: int = 3
    liveness_required_capture_count: int = 3
    liveness_assertion_secret: str | None = None
    allow_legacy_single_image_verification: bool = False
    replay_window_seconds: int = 600
    capture_max_age_seconds: int = 120
    device_proof_required: bool = True
    device_challenge_ttl_seconds: int = 60
    allow_legacy_device_id_only: bool = False
    rate_limit_backend: str = "memory"
    redis_url: str | None = None
    app_replica_count: int = 1
    client_create_limit_per_hour: int = 20
    face_verify_limit_per_minute: int = 5
    face_register_limit_per_hour: int = 3
    face_lifecycle_limit_per_hour: int = 3
    liveness_challenge_limit_per_minute: int = 5
    device_verify_limit_per_minute: int = 10
    device_register_limit_per_hour: int = 5
    device_reset_limit_per_hour: int = 3
    device_rotate_limit_per_hour: int = 3
    device_revoke_limit_per_hour: int = 3
    low_level_face_limit_per_minute: int = 30
    failed_face_attempt_window_seconds: int = 600
    failed_face_attempt_limit: int = 5
    face_cooldown_seconds: int = 900
    audit_hash_key: str | None = None
    allow_api_docs_in_production: bool = False
    require_approved_deployment_calibration: bool = False
    approved_calibration_profile_path: str | None = None
    deployment_min_genuine_pairs: int = 0
    deployment_min_impostor_pairs: int = 0
    deployment_target_fmr: float | None = None
    deployment_max_fnmr_at_target_fmr: float | None = None
    deployment_max_failure_to_acquire_rate: float | None = None
    deployment_max_p95_latency_ms: float | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        environment = os.getenv("ENVIRONMENT", "development").strip().lower()
        optional_float = lambda name: float(os.environ[name]) if os.getenv(name) else None

        def positive_int(name: str, default: int) -> int:
            try:
                value = int(os.getenv(name, str(default)))
            except ValueError as exc:
                raise RuntimeError(f"{name} must be an integer") from exc
            if value < 1:
                raise RuntimeError(f"{name} must be at least 1")
            return value

        return cls(
            environment=environment,
            api_bearer_token=os.getenv("API_BEARER_TOKEN") or None,
            gateway_assertion_required=os.getenv(
                "GATEWAY_ASSERTION_REQUIRED", "true" if environment in {"staging", "production"} else "false"
            ).lower() == "true",
            allow_unsigned_identity_headers=os.getenv(
                "ALLOW_UNSIGNED_IDENTITY_HEADERS", "false" if environment in {"staging", "production"} else "true"
            ).lower() == "true",
            gateway_assertion_issuer=os.getenv("GATEWAY_ASSERTION_ISSUER") or None,
            gateway_assertion_audience=os.getenv("GATEWAY_ASSERTION_AUDIENCE") or None,
            gateway_allowed_tenants=os.getenv("GATEWAY_ALLOWED_TENANTS", ""),
            gateway_assertion_allowed_algorithms=os.getenv("GATEWAY_ASSERTION_ALLOWED_ALGORITHMS", "ES256"),
            gateway_jwks_path=os.getenv("GATEWAY_JWKS_PATH") or None,
            gateway_assertion_max_ttl_seconds=int(os.getenv("GATEWAY_ASSERTION_MAX_TTL_SECONDS", "90")),
            gateway_assertion_clock_skew_seconds=int(os.getenv("GATEWAY_ASSERTION_CLOCK_SKEW_SECONDS", "5")),
            gateway_jti_replay_ttl_seconds=int(os.getenv("GATEWAY_JTI_REPLAY_TTL_SECONDS", "120")),
            require_recent_device_attestation=os.getenv("REQUIRE_RECENT_DEVICE_ATTESTATION", "false").lower() == "true",
            device_attestation_max_age_seconds=int(os.getenv("DEVICE_ATTESTATION_MAX_AGE_SECONDS", "120")),
            allowed_attestation_providers=os.getenv("ALLOWED_ATTESTATION_PROVIDERS", "play_integrity,app_attest"),
            allowed_attestation_verdicts=os.getenv("ALLOWED_ATTESTATION_VERDICTS", "MEETS_DEVICE_INTEGRITY,VALID"),
            allowed_attestation_app_identifiers=os.getenv("ALLOWED_ATTESTATION_APP_IDENTIFIERS", ""),
            ess_database_path=os.getenv("ESS_DATABASE_PATH", "data/ess.sqlite3"),
            biometric_encryption_key=os.getenv("BIOMETRIC_ENCRYPTION_KEY") or None,
            biometric_encryption_key_version=int(os.getenv("BIOMETRIC_ENCRYPTION_KEY_VERSION", "1")),
            device_reset_token=os.getenv("DEVICE_RESET_TOKEN") or None,
            cors_allowed_origins=os.getenv("CORS_ALLOWED_ORIGINS", "*"),
            enable_api_docs=os.getenv(
                "ENABLE_API_DOCS", "false" if environment == "production" else "true"
            ).lower() == "true",
            client_validation_rate_limit_per_minute=int(
                os.getenv("CLIENT_VALIDATION_RATE_LIMIT_PER_MINUTE", "30")
            ),
            max_image_mb=float(os.getenv("MAX_IMAGE_MB", "5.0")),
            max_image_pixels=int(os.getenv("MAX_IMAGE_PIXELS", "20000000")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            provider=os.getenv("MODEL_PROVIDER", "mock"),
            version=os.getenv("BACKEND_VERSION", "phase-5"),
            detector_provider=os.getenv("DETECTOR_PROVIDER", "mock"),
            recognizer_provider=os.getenv("RECOGNIZER_PROVIDER", "mock"),
            yunet_model_path=os.getenv("YUNET_MODEL_PATH", "models/face_detection_yunet_2023mar.onnx"),
            yunet_score_threshold=float(os.getenv("YUNET_SCORE_THRESHOLD", "0.85")),
            yunet_nms_threshold=float(os.getenv("YUNET_NMS_THRESHOLD", "0.3")),
            yunet_top_k=int(os.getenv("YUNET_TOP_K", "5000")),
            min_face_size=int(os.getenv("MIN_FACE_SIZE", "20")),
            max_image_dimension=int(os.getenv("MAX_IMAGE_DIMENSION", "640")),
            arcface_model_path=os.getenv("ARCFACE_MODEL_PATH", "models/face-recognition-resnet100-arcface.onnx"),
            mobilefacenet_model_path=os.getenv("MOBILEFACENET_MODEL_PATH", "models/mobilefacenet.onnx"),
            mobilefacenet_input_size=int(os.getenv("MOBILEFACENET_INPUT_SIZE", "112")),
            mobilefacenet_embedding_dim=int(os.getenv("MOBILEFACENET_EMBEDDING_DIM", "512")),
            mobilefacenet_sha256=os.getenv("MOBILEFACENET_SHA256", "9cc6e4a75f0e2bf0b1aed94578f144d15175f357bdc05e815e5c4a02b319eb4f"),
            insightface_model_name=os.getenv("INSIGHTFACE_MODEL_NAME", "buffalo_l"),
            insightface_det_size=int(os.getenv("INSIGHTFACE_DET_SIZE", "640")),
            insightface_ctx_id=int(os.getenv("INSIGHTFACE_CTX_ID", "-1")),
            arcface_input_size=int(os.getenv("ARCFACE_INPUT_SIZE", "112")),
            arcface_embedding_dim=int(os.getenv("ARCFACE_EMBEDDING_DIM", "512")),
            arcface_sha256=os.getenv("ARCFACE_SHA256", "f3a6bc281e72f88862f5748b53be3d76b3b48f8f1ab1f4a537941bdc4e1b01da"),
            arcface_normalization=os.getenv("ARCFACE_NORMALIZATION", "raw_rgb_0_255"),
            arcface_use_gpu=os.getenv("ARCFACE_USE_GPU", "false").lower() == "true",
            onnx_providers=os.getenv("ONNX_PROVIDERS", "CPUExecutionProvider"),
            face_inference_concurrency=positive_int("FACE_INFERENCE_CONCURRENCY", 2),
            ort_intra_op_threads=positive_int("ORT_INTRA_OP_THREADS", 2),
            ort_inter_op_threads=positive_int("ORT_INTER_OP_THREADS", 1),
            match_threshold=float(os.getenv("MATCH_THRESHOLD", "0.40")),
            match_threshold_override=os.getenv("MATCH_THRESHOLD") is not None,
            calibration_dir=os.getenv("CALIBRATION_DIR", "calibration"),
            calibration_profile_path=os.getenv("CALIBRATION_PROFILE_PATH") or None,
            require_calibration=os.getenv("REQUIRE_CALIBRATION", "false").lower() == "true",
            use_calibrated_threshold=os.getenv("USE_CALIBRATED_THRESHOLD", "true").lower() == "true",
            return_embeddings_default=os.getenv("RETURN_EMBEDDINGS_DEFAULT", "false").lower() == "true",
            allow_embedding_return=os.getenv("ALLOW_EMBEDDING_RETURN", "false").lower() == "true",
            benchmark_output_dir=os.getenv("BENCHMARK_OUTPUT_DIR", "benchmark_reports"),
            benchmark_target_fmr_values=os.getenv("BENCHMARK_TARGET_FMR_VALUES", "1e-3,1e-4,1e-5"),
            benchmark_default_models=os.getenv("BENCHMARK_DEFAULT_MODELS", "arcface_onnx,mobilefacenet_onnx"),
            benchmark_save_per_pair=os.getenv("BENCHMARK_SAVE_PER_PAIR", "true").lower() == "true",
            database_url=os.getenv("DATABASE_URL") or None,
            database_auto_create=os.getenv(
                "DATABASE_AUTO_CREATE", "false" if environment == "production" else "true"
            ).lower() == "true",
            allow_sqlite_in_production=os.getenv("ALLOW_SQLITE_IN_PRODUCTION", "false").lower() == "true",
            db_pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            db_max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            db_connect_timeout_seconds=int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "10")),
            liveness_required=os.getenv(
                "LIVENESS_REQUIRED", "true" if environment == "production" else "false"
            ).lower() == "true",
            liveness_provider=os.getenv("LIVENESS_PROVIDER", "disabled").strip().lower(),
            liveness_challenge_ttl_seconds=int(os.getenv("LIVENESS_CHALLENGE_TTL_SECONDS", "90")),
            liveness_max_attempts=int(os.getenv("LIVENESS_MAX_ATTEMPTS", "3")),
            liveness_required_capture_count=int(os.getenv("LIVENESS_REQUIRED_CAPTURE_COUNT", "3")),
            liveness_assertion_secret=os.getenv("LIVENESS_ASSERTION_SECRET") or None,
            allow_legacy_single_image_verification=os.getenv(
                "ALLOW_LEGACY_SINGLE_IMAGE_VERIFICATION", "false"
            ).lower() == "true",
            replay_window_seconds=int(os.getenv("REPLAY_WINDOW_SECONDS", "600")),
            capture_max_age_seconds=int(os.getenv("CAPTURE_MAX_AGE_SECONDS", "120")),
            device_proof_required=os.getenv(
                "DEVICE_PROOF_REQUIRED", "true"
            ).lower() == "true",
            device_challenge_ttl_seconds=int(os.getenv("DEVICE_CHALLENGE_TTL_SECONDS", "60")),
            allow_legacy_device_id_only=os.getenv("ALLOW_LEGACY_DEVICE_ID_ONLY", "false").lower() == "true",
            rate_limit_backend=os.getenv("RATE_LIMIT_BACKEND", "memory").strip().lower(),
            redis_url=os.getenv("REDIS_URL") or None,
            app_replica_count=int(os.getenv("APP_REPLICA_COUNT", "1")),
            client_create_limit_per_hour=int(os.getenv("CLIENT_CREATE_LIMIT_PER_HOUR", "20")),
            face_verify_limit_per_minute=int(os.getenv("FACE_VERIFY_LIMIT_PER_MINUTE", "5")),
            face_register_limit_per_hour=int(os.getenv("FACE_REGISTER_LIMIT_PER_HOUR", "3")),
            face_lifecycle_limit_per_hour=int(os.getenv("FACE_LIFECYCLE_LIMIT_PER_HOUR", "3")),
            liveness_challenge_limit_per_minute=int(os.getenv("LIVENESS_CHALLENGE_LIMIT_PER_MINUTE", "5")),
            device_verify_limit_per_minute=int(os.getenv("DEVICE_VERIFY_LIMIT_PER_MINUTE", "10")),
            device_register_limit_per_hour=int(os.getenv("DEVICE_REGISTER_LIMIT_PER_HOUR", "5")),
            device_reset_limit_per_hour=int(os.getenv("DEVICE_RESET_LIMIT_PER_HOUR", "3")),
            device_rotate_limit_per_hour=int(os.getenv("DEVICE_ROTATE_LIMIT_PER_HOUR", "3")),
            device_revoke_limit_per_hour=int(os.getenv("DEVICE_REVOKE_LIMIT_PER_HOUR", "3")),
            low_level_face_limit_per_minute=int(os.getenv("LOW_LEVEL_FACE_LIMIT_PER_MINUTE", "30")),
            failed_face_attempt_window_seconds=int(os.getenv("FAILED_FACE_ATTEMPT_WINDOW_SECONDS", "600")),
            failed_face_attempt_limit=int(os.getenv("FAILED_FACE_ATTEMPT_LIMIT", "5")),
            face_cooldown_seconds=int(os.getenv("FACE_COOLDOWN_SECONDS", "900")),
            audit_hash_key=os.getenv("AUDIT_HASH_KEY") or None,
            allow_api_docs_in_production=os.getenv("ALLOW_API_DOCS_IN_PRODUCTION", "false").lower() == "true",
            require_approved_deployment_calibration=os.getenv(
                "REQUIRE_APPROVED_DEPLOYMENT_CALIBRATION", "false"
            ).lower() == "true",
            approved_calibration_profile_path=os.getenv("APPROVED_CALIBRATION_PROFILE_PATH") or None,
            deployment_min_genuine_pairs=int(os.getenv("DEPLOYMENT_MIN_GENUINE_PAIRS", "0")),
            deployment_min_impostor_pairs=int(os.getenv("DEPLOYMENT_MIN_IMPOSTOR_PAIRS", "0")),
            deployment_target_fmr=optional_float("DEPLOYMENT_TARGET_FMR"),
            deployment_max_fnmr_at_target_fmr=optional_float("DEPLOYMENT_MAX_FNMR_AT_TARGET_FMR"),
            deployment_max_failure_to_acquire_rate=optional_float("DEPLOYMENT_MAX_FAILURE_TO_ACQUIRE_RATE"),
            deployment_max_p95_latency_ms=optional_float("DEPLOYMENT_MAX_P95_LATENCY_MS"),
        )


def get_settings() -> Settings:
    return Settings.from_env()


def cors_origins(settings: Settings) -> list[str]:
    return [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]


def _validate_gateway_settings(settings: Settings, environment: str) -> None:
    if not settings.gateway_assertion_required or settings.allow_unsigned_identity_headers:
        raise RuntimeError(f"{environment.title()} requires signed gateway assertions and rejects unsigned identity headers")
    missing = [
        name for name, value in (
            ("GATEWAY_ASSERTION_ISSUER", settings.gateway_assertion_issuer),
            ("GATEWAY_ASSERTION_AUDIENCE", settings.gateway_assertion_audience),
            ("GATEWAY_ALLOWED_TENANTS", settings.gateway_allowed_tenants),
            ("GATEWAY_JWKS_PATH", settings.gateway_jwks_path),
        ) if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required {environment} gateway settings: {', '.join(missing)}")
    algorithms = [value.strip() for value in settings.gateway_assertion_allowed_algorithms.split(",") if value.strip()]
    if algorithms != ["ES256"]:
        raise RuntimeError("GATEWAY_ASSERTION_ALLOWED_ALGORITHMS must be exactly ES256")
    if settings.gateway_assertion_max_ttl_seconds <= 0 or settings.gateway_assertion_max_ttl_seconds > 120:
        raise RuntimeError("GATEWAY_ASSERTION_MAX_TTL_SECONDS must be between 1 and 120")
    if settings.gateway_assertion_clock_skew_seconds < 0 or settings.gateway_assertion_clock_skew_seconds > 30:
        raise RuntimeError("GATEWAY_ASSERTION_CLOCK_SKEW_SECONDS must be between 0 and 30")
    if settings.gateway_jti_replay_ttl_seconds < (
        settings.gateway_assertion_max_ttl_seconds + settings.gateway_assertion_clock_skew_seconds
    ):
        raise RuntimeError("GATEWAY_JTI_REPLAY_TTL_SECONDS must cover assertion TTL and clock skew")
    if settings.device_attestation_max_age_seconds <= 0:
        raise RuntimeError("DEVICE_ATTESTATION_MAX_AGE_SECONDS must be positive")
    if settings.require_recent_device_attestation and not settings.allowed_attestation_app_identifiers.strip():
        raise RuntimeError("ALLOWED_ATTESTATION_APP_IDENTIFIERS is required when device attestation is required")
    if environment == "production" and not settings.require_recent_device_attestation:
        raise RuntimeError("REQUIRE_RECENT_DEVICE_ATTESTATION must be true in production")


def _validate_staging_settings(settings: Settings) -> None:
    _validate_gateway_settings(settings, "staging")
    missing = [
        name for name, value in (
            ("API_BEARER_TOKEN", settings.api_bearer_token),
            ("BIOMETRIC_ENCRYPTION_KEY", settings.biometric_encryption_key),
            ("DEVICE_RESET_TOKEN", settings.device_reset_token),
            ("AUDIT_HASH_KEY", settings.audit_hash_key),
        ) if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required staging settings: {', '.join(missing)}")
    try:
        from cryptography.fernet import Fernet

        Fernet(settings.biometric_encryption_key.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise RuntimeError("BIOMETRIC_ENCRYPTION_KEY is invalid") from exc
    if settings.detector_provider != "yunet" or settings.recognizer_provider != "arcface_onnx":
        raise RuntimeError("Staging requires YuNet and ArcFace ONNX providers")
    if not cors_origins(settings) or "*" in cors_origins(settings):
        raise RuntimeError("CORS_ALLOWED_ORIGINS must list explicit origins in staging")
    if settings.enable_api_docs:
        raise RuntimeError("API documentation must be disabled in staging")
    if not settings.require_calibration:
        raise RuntimeError("REQUIRE_CALIBRATION must be true in staging")
    if settings.liveness_required or settings.liveness_provider != "disabled":
        raise RuntimeError("Staging liveness must remain explicitly disabled until a validated provider is configured")
    if not settings.device_proof_required or settings.allow_legacy_device_id_only:
        raise RuntimeError("Staging requires device proof and rejects legacy device-ID-only authentication")
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required in staging")
    try:
        from sqlalchemy.engine import make_url

        database_backend = make_url(settings.database_url).get_backend_name()
    except Exception as exc:
        raise RuntimeError("DATABASE_URL is invalid") from exc
    if database_backend != "postgresql":
        raise RuntimeError("Staging DATABASE_URL must use PostgreSQL")
    if settings.database_auto_create:
        raise RuntimeError("DATABASE_AUTO_CREATE must be false in staging; run Alembic migrations")
    if settings.rate_limit_backend != "redis" or not settings.redis_url:
        raise RuntimeError("Staging requires Redis rate limiting and REDIS_URL")
    if not settings.redis_url.startswith(("redis://", "rediss://")):
        raise RuntimeError("REDIS_URL must use redis:// or rediss://")
    if settings.app_replica_count <= 0:
        raise RuntimeError("APP_REPLICA_COUNT must be positive")
    if settings.allow_embedding_return:
        raise RuntimeError("Embedding return must be disabled in staging")
    if settings.require_approved_deployment_calibration:
        raise RuntimeError("Approved deployment calibration is not available for staging")
    if settings.db_pool_size <= 0 or settings.db_connect_timeout_seconds <= 0:
        raise RuntimeError("Staging database pool and timeout settings must be positive")


def validate_deployment_settings(settings: Settings) -> None:
    if settings.face_inference_concurrency < 1:
        raise RuntimeError("FACE_INFERENCE_CONCURRENCY must be at least 1")
    if settings.ort_intra_op_threads < 1:
        raise RuntimeError("ORT_INTRA_OP_THREADS must be at least 1")
    if settings.ort_inter_op_threads < 1:
        raise RuntimeError("ORT_INTER_OP_THREADS must be at least 1")
    if settings.max_image_mb <= 0 or settings.max_image_pixels <= 0:
        raise RuntimeError("Image size and pixel limits must be positive")
    if settings.environment == "staging":
        _validate_staging_settings(settings)
        return
    if settings.environment != "production":
        return

    _validate_gateway_settings(settings, "production")

    missing = [
        name
        for name, value in (
            ("API_BEARER_TOKEN", settings.api_bearer_token),
            ("BIOMETRIC_ENCRYPTION_KEY", settings.biometric_encryption_key),
            ("DEVICE_RESET_TOKEN", settings.device_reset_token),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required production settings: {', '.join(missing)}")
    try:
        from cryptography.fernet import Fernet

        Fernet(settings.biometric_encryption_key.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise RuntimeError("BIOMETRIC_ENCRYPTION_KEY is invalid") from exc
    if settings.detector_provider == "mock" or settings.recognizer_provider == "mock":
        raise RuntimeError("Mock face providers are not allowed in production")
    if not cors_origins(settings) or "*" in cors_origins(settings):
        raise RuntimeError("CORS_ALLOWED_ORIGINS must list explicit origins in production")
    if settings.enable_api_docs and not settings.allow_api_docs_in_production:
        raise RuntimeError("API documentation must be disabled in production")
    if not settings.require_calibration:
        raise RuntimeError("REQUIRE_CALIBRATION must be true in production")
    if not settings.liveness_required:
        raise RuntimeError("LIVENESS_REQUIRED must be true in production")
    if settings.liveness_provider in {"disabled", "mock"}:
        raise RuntimeError("A real liveness provider is required in production")
    if settings.liveness_provider != "external_assertion":
        raise RuntimeError("LIVENESS_PROVIDER is unsupported in production")
    if settings.liveness_provider == "external_assertion" and not settings.liveness_assertion_secret:
        raise RuntimeError("LIVENESS_ASSERTION_SECRET is required for external liveness assertions")
    if settings.allow_legacy_single_image_verification:
        raise RuntimeError("Legacy single-image verification is not allowed in production")
    if not settings.device_proof_required:
        raise RuntimeError("DEVICE_PROOF_REQUIRED must be true in production")
    if settings.allow_legacy_device_id_only:
        raise RuntimeError("Legacy device-ID-only authentication is not allowed in production")
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required in production")
    try:
        from sqlalchemy.engine import make_url

        database_backend = make_url(settings.database_url).get_backend_name()
    except Exception as exc:
        raise RuntimeError("DATABASE_URL is invalid") from exc
    if database_backend not in {"sqlite", "postgresql"}:
        raise RuntimeError("DATABASE_URL must use PostgreSQL or SQLite")
    if database_backend == "sqlite" and not settings.allow_sqlite_in_production:
        raise RuntimeError("SQLite is not allowed in production")
    if settings.database_auto_create:
        raise RuntimeError("DATABASE_AUTO_CREATE must be false in production; run Alembic migrations")
    if settings.rate_limit_backend not in {"memory", "redis"}:
        raise RuntimeError("RATE_LIMIT_BACKEND must be memory or redis")
    if settings.rate_limit_backend == "redis" and not settings.redis_url:
        raise RuntimeError("REDIS_URL is required for Redis rate limiting")
    if settings.redis_url and not settings.redis_url.startswith(("redis://", "rediss://")):
        raise RuntimeError("REDIS_URL must use redis:// or rediss://")
    if settings.app_replica_count > 1 and settings.rate_limit_backend != "redis":
        raise RuntimeError("Redis rate limiting is required for multiple replicas")
    if not settings.audit_hash_key:
        raise RuntimeError("AUDIT_HASH_KEY is required in production")
    if settings.require_approved_deployment_calibration and not settings.approved_calibration_profile_path:
        raise RuntimeError("APPROVED_CALIBRATION_PROFILE_PATH is required")
    if settings.require_approved_deployment_calibration:
        if settings.deployment_min_genuine_pairs <= 0 or settings.deployment_min_impostor_pairs <= 0:
            raise RuntimeError("Deployment pair-count gates require risk-owner approved positive values")
        required_gates = {
            "DEPLOYMENT_TARGET_FMR": settings.deployment_target_fmr,
            "DEPLOYMENT_MAX_FNMR_AT_TARGET_FMR": settings.deployment_max_fnmr_at_target_fmr,
            "DEPLOYMENT_MAX_FAILURE_TO_ACQUIRE_RATE": settings.deployment_max_failure_to_acquire_rate,
            "DEPLOYMENT_MAX_P95_LATENCY_MS": settings.deployment_max_p95_latency_ms,
        }
        missing_gates = [name for name, value in required_gates.items() if value is None]
        if missing_gates:
            raise RuntimeError("Missing deployment validation gates: " + ", ".join(missing_gates))
        if not 0 < settings.deployment_target_fmr < 1:
            raise RuntimeError("DEPLOYMENT_TARGET_FMR must be between 0 and 1")
        if not 0 <= settings.deployment_max_fnmr_at_target_fmr <= 1:
            raise RuntimeError("DEPLOYMENT_MAX_FNMR_AT_TARGET_FMR must be between 0 and 1")
        if not 0 <= settings.deployment_max_failure_to_acquire_rate <= 1:
            raise RuntimeError("DEPLOYMENT_MAX_FAILURE_TO_ACQUIRE_RATE must be between 0 and 1")
        if settings.deployment_max_p95_latency_ms <= 0:
            raise RuntimeError("DEPLOYMENT_MAX_P95_LATENCY_MS must be positive")

    positive_values = {
        "LIVENESS_CHALLENGE_TTL_SECONDS": settings.liveness_challenge_ttl_seconds,
        "DEVICE_CHALLENGE_TTL_SECONDS": settings.device_challenge_ttl_seconds,
        "REPLAY_WINDOW_SECONDS": settings.replay_window_seconds,
        "CAPTURE_MAX_AGE_SECONDS": settings.capture_max_age_seconds,
        "CLIENT_VALIDATION_RATE_LIMIT_PER_MINUTE": settings.client_validation_rate_limit_per_minute,
        "FACE_VERIFY_LIMIT_PER_MINUTE": settings.face_verify_limit_per_minute,
        "FACE_REGISTER_LIMIT_PER_HOUR": settings.face_register_limit_per_hour,
        "FACE_LIFECYCLE_LIMIT_PER_HOUR": settings.face_lifecycle_limit_per_hour,
        "LIVENESS_CHALLENGE_LIMIT_PER_MINUTE": settings.liveness_challenge_limit_per_minute,
        "DEVICE_VERIFY_LIMIT_PER_MINUTE": settings.device_verify_limit_per_minute,
        "DEVICE_REGISTER_LIMIT_PER_HOUR": settings.device_register_limit_per_hour,
        "DEVICE_RESET_LIMIT_PER_HOUR": settings.device_reset_limit_per_hour,
        "LOW_LEVEL_FACE_LIMIT_PER_MINUTE": settings.low_level_face_limit_per_minute,
        "FAILED_FACE_ATTEMPT_LIMIT": settings.failed_face_attempt_limit,
        "FACE_COOLDOWN_SECONDS": settings.face_cooldown_seconds,
        "DB_POOL_SIZE": settings.db_pool_size,
        "DB_CONNECT_TIMEOUT_SECONDS": settings.db_connect_timeout_seconds,
        "BIOMETRIC_ENCRYPTION_KEY_VERSION": settings.biometric_encryption_key_version,
    }
    invalid = [name for name, value in positive_values.items() if value <= 0]
    if invalid:
        raise RuntimeError(f"Production security settings must be positive: {', '.join(invalid)}")
    if settings.require_approved_deployment_calibration:
        from app.services.calibration import ScoreCalibrator

        ScoreCalibrator.from_settings(settings)
