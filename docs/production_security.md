# Production security

The service now has replay-resistant challenges, P-256 device possession proof, configurable abuse controls, SQLAlchemy/Alembic persistence, and deployment-calibration gates. It is still **not production-ready by configuration alone**: a validated liveness/anti-spoof provider, representative field validation, PostgreSQL/Redis services, gateway isolation, monitoring, backups, and risk-owner approval remain deployment responsibilities.

Phase 4 provider status is **WAITING FOR PROVIDER SELECTION**. The generic HMAC `external_assertion` adapter is integration scaffolding, not evidence of official provider verification or spoof resistance. Production deployment must remain blocked until the selection, server-verification, sandbox, privacy, licensing, and representative attack-test gates in `docs/liveness_provider_selection.md` are complete.

## Trust boundary

Use `Mobile App -> ESS Backend/Gateway -> Face API`. The gateway authenticates the user, owns the service bearer, and signs short-lived ES256 assertions. The Face API owns only the public JWKS. The mobile device owns only its non-exportable P-256 private key. Attendance is written by ESS only after a successful server response.

## Fail-closed production configuration

`ENVIRONMENT=production` also rejects missing gateway issuer/audience/JWKS configuration, unsigned identity headers, non-ES256 policy, excessive assertion lifetime, insufficient replay retention, and missing recent device attestation/app allowlist. See `.env.example`; never copy placeholders into production.

Production should use:

- real YuNet/ArcFace artifacts with pinned hashes;
- an independently validated liveness SDK/service behind `external_assertion`;
- PostgreSQL with migrations applied before the application starts;
- Redis whenever more than one process or replica serves traffic;
- HTTPS and ingress restricted to the ESS gateway;
- secret management, audit export, alerts, backups, restore drills, and rollback tests.

## Security data

Fernet-encrypted embeddings remain encrypted at rest. No raw image is stored. Replay records contain short-lived hashes. Audit events contain HMAC-hashed user/device identifiers and outcome codes, not images, embeddings, tokens, signatures, public/private key material, or request bodies.

The global device reset token remains an emergency/admin control, not the final account-recovery design. Protect it with an authenticated support workflow, approval, audit, and rotation.
