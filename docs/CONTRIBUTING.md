# Contribution Notes

Keep API changes covered by tests and update `docs/API.md` when a contract changes. Preserve the event idempotency and one-alert-per-event invariants. Do not commit `.env`, database files, stream credentials, private keys, or real watchlist data. Keep vendor-specific code inside an adapter module and keep the core registry/analytics services vendor-neutral.
