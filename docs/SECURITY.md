# Security

The current implementation enforces:

- HTTPS-only requests when `require_https` is true
- IP allowlist checks before token validation
- `password_verify()` against the stored `token_hash`
- HMAC-SHA256 signatures using the presented token for each request
- replay-window validation
- per-IP rate limiting
- a master enable switch

The config file is generated outside the repository and embedded into the packaged plugin ZIP for first install. Local plaintext tokens live under `~/.wrs/sites/<site>/local.config.json`.

