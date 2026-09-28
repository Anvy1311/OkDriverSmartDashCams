# Security Architecture

## Threat model

The platform handles camera locations, operational video, vehicle/person identifiers, and law-enforcement-adjacent watchlist data. Important threats include unauthorized camera access, credential leakage, malicious stream URLs, event spoofing, duplicate alert storms, privilege escalation, database theft, log tampering, and cross-department data leakage.

## Implemented prototype controls

- PBKDF2-SHA256 password hashing with a per-password salt.
- HMAC-signed, expiring access tokens with HTTP-only cookies and bearer compatibility.
- Optional, constant-time-checked `X-Analytics-Key` authentication for service-to-service event ingestion; unset by default.
- Role-based authorization for administrative mutations and operator workflows.
- Pydantic bounds/length validation and SQLAlchemy parameter binding.
- Secret-free stream references; URLs containing embedded credentials or credential/signature query parameters are rejected.
- Synthetic heartbeat collection is restricted to `sim://` sources; production health must arrive through the authenticated heartbeat or gateway boundary.
- Audit records for authentication, onboarding, updates, heartbeat, ingestion, alert creation, and alert actions.
- Request rate limiting, CORS allow-list, `X-Content-Type-Options`, frame protection, referrer policy, and duration headers.
- GIS tile settings are configurable, HTTPS-only outside localhost, and served to authenticated browsers with visible provider attribution; bulk/offline prefetch is not implemented.
- Environment-based configuration and `.env` ignored by Git.
- Seeded demo passwords are configurable through `DEMO_ADMIN_PASSWORD` and `DEMO_OPERATOR_PASSWORD`; they are synthetic development defaults, not production secrets.

## Production control plane

1. Terminate TLS 1.2+ at a managed load balancer or ingress and redirect HTTP to HTTPS.
2. Set `COOKIE_SECURE=true`; use `Strict`/`Lax` site policy based on the deployment topology.
3. Replace the signed development token with an OIDC/OAuth2 identity provider and short-lived access tokens plus refresh-token rotation.
4. Store stream and vendor credentials in a managed secret vault. The registry stores only a vault reference and credential version.
5. Use mTLS or workload identity between edge gateways, queues, analytics workers, and central services.
6. Segment camera networks, gateway networks, analytics networks, and operator networks with firewalls and default-deny policies.
7. Encrypt database, object storage, backups, and queue transport with managed keys and rotation.
8. Put the API behind a WAF, enforce request-size limits, and use a distributed rate limiter backed by Redis.
9. Enforce department and row-level authorization, export controls, and need-to-know watchlist visibility.
10. Redact analytics metadata and logs by default; prohibit raw video and unrestricted personal data in application logs.
11. Write audit records to append-only/WORM storage with synchronized clocks and alerting on privileged actions.
12. Apply retention and deletion schedules approved by the data owner; preserve legal-hold evidence separately.

## Role matrix

| Capability | Operator | Admin | Edge/service identity |
| --- | ---: | ---: | ---: |
| View registry, GIS, events, alerts | Yes | Yes | Scoped |
| View live feed | Yes | Yes | Gateway only |
| Edit/disable camera | No | Yes | Scoped onboarding identity |
| Manage watchlist | No | Yes | Approved sync identity |
| Ingest analytics | Yes | Yes | Yes, scoped key/mTLS |
| Acknowledge/resolve alert | Yes | Yes | No |
| Export registry | Yes | Yes | Approved export job |

## Incident response

Keep a source/credential revocation runbook, preserve gateway and audit logs, isolate a compromised department connector, rotate service credentials, invalidate sessions, and notify the responsible data owner. Test restore and credential rotation procedures at least twice a year.

## Privacy

Vehicle and person identifiers are operational/security data. The included records are synthetic. Production collection should be purpose-limited, access-logged, minimized, encrypted, and retained only under approved policy. Video playback should be audited separately from metadata access.
