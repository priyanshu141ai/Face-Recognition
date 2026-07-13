# Coolify staging deployment

This guide deploys a private staging Face API for synthetic test users only. It does not authorize production attendance, employee biometric collection, production liveness claims, or production calibration claims.

## Responsibility split

### A. Codex can perform locally

- Validate code, tests, Docker configuration, migrations, model metadata, and safe templates.
- Prepare this guide and `deploy/coolify/staging.env.example`.
- Run isolated local PostgreSQL/Redis contract tests.
- Provide sanitized verification commands and review results.

### B. The user must perform in Coolify

- Make the reviewed Git branch available to Coolify.
- Create the project, PostgreSQL, Redis, application, internal networking, domain, HTTPS, backups, secrets, and mounts.
- Upload model artifacts through an approved secure transfer path.
- Run the one-time migration commands and start/restart the application.

### C. Copy from Coolify without posting it in chat

- PostgreSQL internal URL.
- Redis internal URL.
- Generated resource names/hostnames.
- Staging application domain.
- Deployment ID, commit and non-secret status output.

Passwords, bearer tokens and cryptographic keys must stay in Coolify runtime secrets. Do not mark them as Docker build variables.

### D. Validate after deployment

- HTTPS, `/healthz`, `/readyz`, docs-disabled behavior and authentication matrix.
- PostgreSQL/Redis isolated integration tests.
- Real YuNet/ArcFace smoke with an ignored synthetic/approved test image.
- Persistence/restart, safe failure checks, logs, resources and a small load smoke.

## Resource layout

Create one Coolify project/environment containing:

```text
ESS/Test Client
  -> HTTPS face-api-staging:8080
       -> Coolify internal face-postgres-staging:5432
       -> Coolify internal face-redis-staging:6379
       -> /app/models (read-only bind mount)
```

Suggested names:

- `face-api-staging`
- `face-postgres-staging`
- `face-postgres-staging-tests`
- `face-redis-staging`
- `face-redis-staging-tests`

Only the Face API receives a public HTTPS domain. Do not enable public ports for PostgreSQL or Redis during normal operation. Coolify provides internal URLs when resources share a network/project.

For production, prefer no public Face API domain: ESS Gateway and Face API should share a private Coolify network and only ESS should be public. If staging temporarily exposes the Face API, enforce HTTPS, firewall/source allowlisting, rate limits, and bearer/assertion checks. Real mTLS belongs at the reverse proxy/network layer; no client-supplied certificate header is trusted. Because Uvicorn currently trusts forwarded headers from `*`, direct container ingress must remain blocked or trusted proxy CIDRs must be narrowed before production.

## Confirmed repository contract

| Item | Actual value |
| --- | --- |
| Build pack | Dockerfile |
| Dockerfile/base directory | `/Dockerfile`, `/` |
| Container port | `8080` |
| Startup | one Uvicorn worker, `app.main:app`, `0.0.0.0:8080` |
| Docker healthcheck | `GET /readyz`; 30 s interval/timeout, 120 s start period, 3 retries |
| Liveness endpoint | `/healthz` checks the process only |
| Readiness endpoint | `/readyz` checks calibration, YuNet/ArcFace, database/schema, configured liveness and Redis |
| Migration | `python -m alembic upgrade head` |
| Migration verification | `python scripts/verify_database_migration.py` (no positional arguments) |
| PostgreSQL URL | `postgresql+psycopg://USER:PASSWORD@INTERNAL_HOST:5432/DATABASE` |
| Redis URL | `redis://...` or `rediss://...` |
| Models | `/app/models` |
| Calibration | `/app/calibration`; tracked research profiles are copied into the image |
| Writable app data | `/app/data` exists, but PostgreSQL staging must not use SQLite there |
| Proxy headers | enabled; forwarded IPs currently trust `*`, so direct container ingress must be blocked |

`ENVIRONMENT=staging` also requires signed ES256 gateway assertions, public JWKS verification, request binding, and rejection of unsigned identity headers. Device attestation can remain explicitly deferred only in staging.

## Staging security decision

Use this explicit non-production mode:

- Real YuNet and ArcFace, CPU provider.
- Bearer authentication enabled behind the ESS/test gateway.
- P-256 device proof required; legacy device-ID-only disabled.
- PostgreSQL and Redis required.
- Embedding return disabled and API docs disabled.
- Liveness explicitly disabled because no validated provider exists.
- `ALLOW_LEGACY_SINGLE_IMAGE_VERIFICATION=true` is staging-only for controlled one-probe verification tests. Face registration still requires front/left/right. This is not liveness and must never authorize production attendance.
- Existing ArcFace LFW research calibration may be loaded, but `REQUIRE_APPROVED_DEPLOYMENT_CALIBRATION=false`. Its display score is not identity probability.

Do not use `ENVIRONMENT=production` to imitate production. Production intentionally refuses disabled liveness and legacy single-image verification.

## PostgreSQL setup in Coolify

1. Project -> staging environment -> **New Resource** -> **PostgreSQL**.
2. Name it `face-postgres-staging` and create an isolated database/user with a generated password.
3. Enable persistent storage and a scheduled backup destination if available.
4. Keep **Public Port/Accessible over the internet** disabled.
5. Copy the internal URL directly into the application's secret `DATABASE_URL`; do not paste it into chat or a tracked file.
6. Set `DATABASE_AUTO_CREATE=false` and run Alembic before expecting readiness.
7. Create `face-postgres-staging-tests` separately for integration/race tests. Never run destructive tests or downgrade against the main staging database.

For a restore drill, restore a backup only into a separate database resource, verify schema/counts, and record recovery time. Without an isolated restore target and configured backup destination, report backup/restore as BLOCKED.

## Redis setup in Coolify

1. Project -> staging environment -> **New Resource** -> **Redis**.
2. Name it `face-redis-staging`; enable authentication and the chosen staging persistence policy if supported.
3. Keep public exposure disabled.
4. Copy the internal URL directly into the application runtime secret `REDIS_URL`.
5. Set `RATE_LIMIT_BACKEND=redis` and initially `APP_REPLICA_COUNT=1`.
6. Create a separate `face-redis-staging-tests` service/database for expiry/destructive contract tests. Never flush the main staging Redis.

## Environment-variable matrix

All variables below are read at process startup; changing any value requires an application restart/redeploy. Use `deploy/coolify/staging.env.example` only as a name/value guide. Set all secrets as runtime-only variables, not build variables.

### General

| Variable | Req | Placeholder/source | Secret | Staging value | Validation | Restart |
| --- | --- | --- | --- | --- | --- | --- |
| `ENVIRONMENT` | Yes | repository policy | No | `staging` | activates staging checks | Yes |
| `BACKEND_VERSION` | Yes | release/commit label | No | `<staging-release-id>` | returned by readiness | Yes |
| `ENABLE_API_DOCS` | Yes | policy | No | `false` | staging rejects `true` | Yes |
| `ALLOW_API_DOCS_IN_PRODUCTION` | No | policy | No | `false` | production-only override | Yes |
| `CORS_ALLOWED_ORIGINS` | Yes | ESS staging origin | No | `https://<ess-staging-domain>` | empty/wildcard rejected | Yes |
| `LOG_LEVEL` | No | operator | No | `INFO` | parsed at startup | Yes |
| `MAX_IMAGE_MB` | No | repository default | No | `5` | decoded payload limit | Yes |
| `MAX_IMAGE_PIXELS` | No | repository default | No | `20000000` | decoded pixel/decompression guard | Yes |

Three-angle enrollment plus liveness frames makes Base64 JSON larger than the
old one-image request. Set the reverse-proxy body limit from the measured mobile
capture profile, allow protocol overhead, and keep it finite. The application
enforces per-image compressed-byte and pixel limits, but the proxy must reject an
oversized total HTTP body before application allocation. Start face-operation
timeouts at 30 seconds and re-measure p95 under staging concurrency. Keep the
initial 2 GiB memory limit until three-capture profiling proves a lower safe value.

### Authentication and encrypted data

| Variable | Req | Placeholder/source | Secret | Staging value | Validation | Restart |
| --- | --- | --- | --- | --- | --- | --- |
| `API_BEARER_TOKEN` | Yes | generated in secret manager | Yes | masked | missing rejected | Yes |
| `GATEWAY_ASSERTION_REQUIRED` | Yes | policy | No | `true` | staging rejects `false` | Yes |
| `ALLOW_UNSIGNED_IDENTITY_HEADERS` | Yes | policy | No | `false` | staging rejects `true` | Yes |
| `GATEWAY_ASSERTION_ISSUER` | Yes | ESS identity | No | `https://<ess-staging-domain>` | exact match | Yes |
| `GATEWAY_ASSERTION_AUDIENCE` | Yes | Face API identity | No | `face-api-staging` | exact match | Yes |
| `GATEWAY_ALLOWED_TENANTS` | Yes | approved client IDs | No | comma-separated allowlist | claim membership | Yes |
| `GATEWAY_JWKS_PATH` | Yes | public-key mount | No | `/run/secrets/gateway-public.jwks.json` | verification input | Yes |
| `BIOMETRIC_ENCRYPTION_KEY` | Yes | valid Fernet key | Yes | masked | missing/invalid rejected | Yes |
| `BIOMETRIC_ENCRYPTION_KEY_VERSION` | Yes | key inventory | No | `1` | positive in production | Yes |
| `DEVICE_RESET_TOKEN` | Yes | generated admin secret | Yes | masked | missing rejected | Yes |
| `AUDIT_HASH_KEY` | Yes | generated audit HMAC secret | Yes | masked | missing rejected | Yes |

### Models and calibration

| Variable | Req | Placeholder/source | Secret | Staging value | Validation | Restart |
| --- | --- | --- | --- | --- | --- | --- |
| `DETECTOR_PROVIDER` | Yes | repository | No | `yunet` | staging rejects other providers | Yes |
| `RECOGNIZER_PROVIDER` | Yes | repository | No | `arcface_onnx` | staging rejects other providers | Yes |
| `YUNET_MODEL_PATH` | Yes | model mount | No | `/app/models/face_detection_yunet_2023mar.onnx` | readiness loads it | Yes |
| `ARCFACE_MODEL_PATH` | Yes | model mount | No | `/app/models/face-recognition-resnet100-arcface.onnx` | readiness loads it | Yes |
| `ARCFACE_SHA256` | Yes | pinned repository value | No | pinned hash from template | runtime checksum match | Yes |
| `ONNX_PROVIDERS` | Yes | target runtime | No | `CPUExecutionProvider` | ONNX session creation | Yes |
| `CALIBRATION_DIR` | Yes | image path | No | `/app/calibration` | profile lookup | Yes |
| `CALIBRATION_PROFILE_PATH` | No | exact research profile | No | empty | overrides directory lookup | Yes |
| `REQUIRE_CALIBRATION` | Yes | policy | No | `true` | staging rejects `false` | Yes |
| `USE_CALIBRATED_THRESHOLD` | Yes | policy | No | `true` | selects profile threshold | Yes |
| `REQUIRE_APPROVED_DEPLOYMENT_CALIBRATION` | Yes | current limitation | No | `false` | staging rejects `true` until approved data exists | Yes |
| `APPROVED_CALIBRATION_PROFILE_PATH` | No | future approval | No | empty | not used in this phase | Yes |

`MODEL_PROVIDER` is a legacy setting and is not the active provider selector. `YUNET_SHA256` is not a supported variable; do not invent it.

### Database

| Variable | Req | Placeholder/source | Secret | Staging value | Validation | Restart |
| --- | --- | --- | --- | --- | --- | --- |
| `DATABASE_URL` | Yes | Coolify PostgreSQL internal URL | Yes | masked `postgresql+psycopg://...` | PostgreSQL required; readiness pings/schema-checks | Yes |
| `DATABASE_AUTO_CREATE` | Yes | migration policy | No | `false` | staging rejects `true` | Yes |
| `ALLOW_SQLITE_IN_PRODUCTION` | Yes | policy | No | `false` | no effect on staging PostgreSQL | Yes |
| `DB_POOL_SIZE` | Yes | operator | No | `5` | must be positive | Yes |
| `DB_MAX_OVERFLOW` | Yes | operator | No | `10` | SQLAlchemy pool setting | Yes |
| `DB_CONNECT_TIMEOUT_SECONDS` | Yes | operator | No | `10` | must be positive | Yes |

### Redis and abuse controls

| Variable | Req | Placeholder/source | Secret | Staging value | Validation | Restart |
| --- | --- | --- | --- | --- | --- | --- |
| `RATE_LIMIT_BACKEND` | Yes | policy | No | `redis` | staging rejects other backends | Yes |
| `REDIS_URL` | Yes | Coolify Redis internal URL | Yes | masked `redis://...` | scheme checked; readiness pings | Yes |
| `APP_REPLICA_COUNT` | Yes | Coolify | No | `1` | must be positive | Yes |
| `CLIENT_VALIDATION_RATE_LIMIT_PER_MINUTE` | Yes | repository default | No | `30` | limiter configuration | Yes |
| `CLIENT_CREATE_LIMIT_PER_HOUR` | Yes | repository default | No | `20` | limiter configuration | Yes |
| `FACE_VERIFY_LIMIT_PER_MINUTE` | Yes | repository default | No | `5` | limiter configuration | Yes |
| `FACE_REGISTER_LIMIT_PER_HOUR` | Yes | repository default | No | `3` | limiter configuration | Yes |
| `FACE_LIFECYCLE_LIMIT_PER_HOUR` | Yes | repository default | No | `3` | limiter configuration | Yes |
| `LIVENESS_CHALLENGE_LIMIT_PER_MINUTE` | Yes | repository default | No | `5` | limiter configuration | Yes |
| `DEVICE_VERIFY_LIMIT_PER_MINUTE` | Yes | repository default | No | `10` | limiter configuration | Yes |
| `DEVICE_REGISTER_LIMIT_PER_HOUR` | Yes | repository default | No | `5` | limiter configuration | Yes |
| `DEVICE_RESET_LIMIT_PER_HOUR` | Yes | repository default | No | `3` | limiter configuration | Yes |
| `DEVICE_ROTATE_LIMIT_PER_HOUR` | Yes | repository default | No | `3` | limiter configuration | Yes |
| `DEVICE_REVOKE_LIMIT_PER_HOUR` | Yes | repository default | No | `3` | limiter configuration | Yes |
| `LOW_LEVEL_FACE_LIMIT_PER_MINUTE` | Yes | repository default | No | `30` | limiter configuration | Yes |
| `FAILED_FACE_ATTEMPT_WINDOW_SECONDS` | Yes | repository default | No | `600` | cooldown window | Yes |
| `FAILED_FACE_ATTEMPT_LIMIT` | Yes | repository default | No | `5` | cooldown trigger | Yes |
| `FACE_COOLDOWN_SECONDS` | Yes | repository default | No | `900` | cooldown duration | Yes |

### Device proof, staging liveness and disclosure

| Variable | Req | Placeholder/source | Secret | Staging value | Validation | Restart |
| --- | --- | --- | --- | --- | --- | --- |
| `DEVICE_PROOF_REQUIRED` | Yes | policy | No | `true` | required in staging | Yes |
| `DEVICE_CHALLENGE_TTL_SECONDS` | Yes | repository default | No | `60` | challenge expiry | Yes |
| `ALLOW_LEGACY_DEVICE_ID_ONLY` | Yes | policy | No | `false` | rejected in staging | Yes |
| `LIVENESS_REQUIRED` | Yes | current limitation | No | `false` | staging requires explicit disabled mode | Yes |
| `LIVENESS_PROVIDER` | Yes | current limitation | No | `disabled` | not production liveness | Yes |
| `LIVENESS_ASSERTION_SECRET` | No | future provider | Yes | unset | unused while disabled | Yes |
| `ALLOW_LEGACY_SINGLE_IMAGE_VERIFICATION` | Yes | staging-only integration | No | `true` | production rejects it | Yes |
| `LIVENESS_CHALLENGE_TTL_SECONDS` | Yes | repository default | No | `90` | challenge expiry | Yes |
| `LIVENESS_MAX_ATTEMPTS` | Yes | repository default | No | `3` | challenge attempts | Yes |
| `LIVENESS_REQUIRED_CAPTURE_COUNT` | Yes | repository default | No | `3` | ignored while disabled | Yes |
| `REPLAY_WINDOW_SECONDS` | Yes | repository default | No | `600` | replay retention | Yes |
| `CAPTURE_MAX_AGE_SECONDS` | Yes | repository default | No | `120` | capture freshness | Yes |
| `ALLOW_EMBEDDING_RETURN` | Yes | disclosure policy | No | `false` | staging rejects `true` | Yes |
| `RETURN_EMBEDDINGS_DEFAULT` | Yes | disclosure policy | No | `false` | retained disabled | Yes |

## Model artifact delivery

Required local artifacts:

| File | Expected size | Hash policy |
| --- | ---: | --- |
| `face_detection_yunet_2023mar.onnx` | 232,589 bytes | repository currently has no YuNet checksum setting |
| `face-recognition-resnet100-arcface.onnx` | 261,036,388 bytes | SHA-256 pinned in `ARCFACE_SHA256` |
| `mobilefacenet.onnx` | 13,616,099 bytes | optional; pinned only if selected |

1. Transfer the two required files to the Coolify server through the approved SSH/SFTP channel. Do not use Git or Docker build arguments.
2. Place them under the recommended host directory `/data/coolify/face-api-staging/models`.
3. Make the directory/file group readable by container GID 999 and not writable by the application; keep the host copy administrator-owned.
4. Application -> **Persistent Storage** -> add bind mount:
   - Source: `/data/coolify/face-api-staging/models`
   - Destination: `/app/models`
   - Read-only: enabled.
5. If the current Coolify UI cannot produce a read-only bind, stop and inspect the generated deployment instead of accepting a writable model mount.
6. In the container terminal run `python scripts/validate_model_artifacts.py --models-dir /app/models` and record only PASS/FAIL.
7. Verify the mount is read-only and that no ONNX artifact exists in the built image layers.

A missing/unreadable/mismatched required model must keep `/readyz` at 503.

## Calibration artifact

Tracked `calibration/*.json` files are copied into the image at `/app/calibration`. For ArcFace, the research profile's provider and pinned model SHA-256 match the configured recognizer. It is an LFW research operating point, not deployment-population approval, and its scaled score is not a real-world identity probability.

## Coolify application settings

| Setting | Value |
| --- | --- |
| Source | `https://github.com/priyanshu141ai/Face-Recognition.git` |
| Branch | reviewed remote staging branch; do not deploy uncommitted local state |
| Build pack | Dockerfile |
| Base directory | `/` |
| Dockerfile | `/Dockerfile` |
| Port Exposes | `8080` |
| Domain | `https://face-api-staging.<user-domain>` |
| Force HTTPS | enabled |
| Replica count | 1 |
| Healthcheck | Dockerfile `/readyz` (dependency readiness) |
| Liveness probe for diagnosis | manual `/healthz` |
| Deployment timeout | at least 600 s initially |
| Initial runtime limit | 2 vCPU / 2 GiB RAM, then tune from measurements |
| Restart policy | restart on failure/unless stopped; avoid restart loop for migration jobs |
| Storage | read-only model bind at `/app/models`; no SQLite data mount needed |
| Environment | runtime-only values from the matrix; no secret build variables |

Coolify's Dockerfile build pack defaults to port 3000, so explicitly change **Port Exposes** to 8080. The Dockerfile healthcheck takes precedence when both Dockerfile and UI healthchecks are enabled.

## Migration workflow

The verification script accepts no positional arguments; `--help` is safe and does not connect.

Safest initial workflow:

1. Wait for PostgreSQL and Redis resources to be healthy.
2. Build the application from the exact reviewed commit. It may remain unhealthy before schema creation.
3. Open the new application container's Coolify terminal and run:

   ```sh
   python -m alembic upgrade head
   python scripts/verify_database_migration.py
   ```

4. Record only exit status/backend/table-count summary; never print `DATABASE_URL`.
5. Restart the application and wait for `/readyz` 200.

For later schema releases, use a temporary no-domain migration resource/container built from the same commit and attached to the same internal network. Run the two commands once, require exit 0, stop the migration resource, then deploy the application. Do not rely blindly on Coolify's pre-deploy field: current Coolify documentation says it runs in the existing container, which may not contain the new migration. Never enable `DATABASE_AUTO_CREATE` and never downgrade the staging database.

## Post-deployment validation

Keep the correct token in a local environment variable; never put it in command history or chat.

```powershell
$baseUrl = "https://face-api-staging.<user-domain>"
curl.exe -fsS "$baseUrl/healthz"
curl.exe -fsS "$baseUrl/readyz"
python scripts/check_active_model_mode.py --base-url $baseUrl --expected real
python scripts/smoke_test_api.py --base-url $baseUrl
```

Required checks:

- HTTPS works and HTTP redirects to HTTPS.
- `/healthz` 200 and `/readyz` 200.
- `/docs`, `/redoc`, `/openapi.json` return 404.
- `/v1/models/current` without/wrong token returns 401; correct token returns 200.
- `/v1/faces/detect`, `/embed`, `/verify` without token return 401.
- Safe real-image detect and verify execute without printing image/Base64/embedding.
- PostgreSQL schema/connectivity and Redis ping pass.
- Logs contain none of the sensitive categories listed in the security policy.

Run live service tests only with isolated test URLs held in process environment:

```powershell
python -m pytest -q
```

The PostgreSQL and Redis contract tests must execute rather than skip. Do not point `TEST_POSTGRES_URL` or `TEST_REDIS_URL` at the primary staging resources.

## Safe failure and operational checks

Use a temporary deployment/local container for missing model, wrong DB/Redis URL, wrong calibration, missing migration and model permission tests. Expected readiness is 503 while `/healthz` remains 200. Invalid bearer remains 401. Do not damage the main staging resources.

Record sanitized image size, memory after model load, idle CPU, startup/readiness time, one verification latency, restart count, database connectivity/pool setting, Redis ping and log scan result. Optional load smoke is limited to concurrency 1, 3 and 5 with approved synthetic input.

## Manual checkpoint before live deployment

Confirm only these non-secret statements:

- [ ] Reviewed branch is available remotely to Coolify.
- [ ] Coolify staging project exists.
- [ ] Main and isolated-test PostgreSQL resources are ready.
- [ ] Main and isolated-test Redis resources are ready.
- [ ] Internal URLs were added directly to Coolify runtime secrets.
- [ ] Required models were uploaded and mounted read-only.
- [ ] Staging domain and HTTPS certificate are ready.
- [ ] All runtime secrets/variables were added; no secrets are build variables.
- [ ] Migration workflow is configured.

Respond with non-secret confirmations only, such as `PostgreSQL ready`, `Redis ready`, `models mounted`, `variables added`, and `deployment started`. Do not paste credentials.

## Official Coolify references

- [Dockerfile build pack](https://coolify.io/docs/applications/build-packs/dockerfile)
- [Databases and internal URLs](https://coolify.io/docs/databases/)
- [PostgreSQL](https://coolify.io/docs/databases/postgresql)
- [Redis](https://coolify.io/docs/databases/redis)
- [Database backups](https://coolify.io/docs/databases/backups)
- [Environment variables](https://coolify.io/docs/knowledge-base/environment-variables)
- [Persistent storage](https://coolify.io/docs/knowledge-base/persistent-storage)
- [Health checks](https://coolify.io/docs/knowledge-base/health-checks)
- [Terminal](https://coolify.io/docs/knowledge-base/internal/terminal)
