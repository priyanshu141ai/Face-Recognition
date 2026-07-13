# Rate limiting and cooldown

Sensitive actions are limited across IP, user, and device scopes. Client creation/validation, device challenge/register/verify/rotate/revoke/reset, liveness challenge, face register/verify/lifecycle, and low-level `/v1/faces/*` routes are covered. Limits are environment-configured in `.env.example`.

Development can use the thread-safe in-memory sliding-window adapter. Multi-process/multi-replica production must use Redis; startup rejects memory-only limiting when `APP_REPLICA_COUNT>1`. Redis increments and expiry are performed atomically.

Face non-matches update a database-backed failure window. The configured threshold starts a time-limited progressive cooldown, capped at four times the base duration. A successful verification clears the record; an elapsed cooldown is audited and decayed. This avoids permanent lockout while still slowing repeated attacks.

Blocked calls return HTTP 429, `Retry-After`, and:

```json
{"detail":{"request_id":null,"code":"rate_limited","message":"Too many attempts. Try again later.","retry_after_seconds":120}}
```

Application limiting complements, rather than replaces, reverse-proxy body/rate limits and network isolation.
