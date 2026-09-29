# Automated security verification scope

The non-Docker suite covers session authentication, forbidden role injection, CSRF rejection, customer/center/reviewer scoping, optimistic-update conflicts, signed evidence URLs (owner binding, expiry and tampering), randomized private evidence storage, content/MIME checks, invalid images, encrypted/page-capped PDFs, PDF JavaScript name trees and annotation launch actions, immutable submitted evidence and versioned evaluation history.

The local image-model adapter rejects reordered/invalid probability contracts appropriately, including NaN, bad sums and incorrect output shapes. Missing artifacts and bounded model failures produce explicit manual-review recommendations rather than fabricated predictions. The summary loader is local-only, disables remote code, and requires safetensors. Summary content is validated against source facts; unavailable or ungrounded output uses a labeled factual fallback.

The initial dependency audit identified advisories in Transformers 4.57.6. The environment was upgraded to non-yanked Transformers 5.17.0 with compatible dependencies; the refreshed `dependency-audit.json` reports no known vulnerabilities across 105 packages at audit time. `uv pip check` passed. The Windows version snapshot is not a hash-locked supply-chain guarantee, and advisory databases can change.

Signed download query strings must not be written to access logs. The documented API command and disposable test server disable default access logging. Production observability should redact query strings and use request IDs without evidence or credentials.

These are automated checks, not an independent penetration test or proof of production readiness. HTTPS/reverse-proxy configuration, secret rotation, rate limits, network controls, production backups and sustained uptime still require deployment-level review. Docker verification is explicitly excluded from this test request. Atlas-specific verification requires a test-only external cluster; no real credentials are used by the local runner.
