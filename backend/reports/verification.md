# Non-Docker verification — 2026-09-27

## Final result

**89 passed, 1 failed, 0 skipped**, 552.86 seconds. Command: `.venv\Scripts\python.exe -m database.run_local_tests --full --junitxml=reports/non-docker-tests.xml`.

The failing test is the 10,000-claim load test's **2-second p95 diagnostic threshold**: measured **3.105 seconds** for a reports-plus-dashboard pair. All 800 HTTP requests succeeded and returned correctly scoped counts/data. The threshold has not been relaxed. The load test used 100 identities and 20 concurrent clients; the 100-claim baseline p95 was 3.578 seconds, versus 3.105 seconds with 10,000 claims. This supports storage-scale correctness in this scenario, not unrestricted production capacity.

Statement coverage: **70% overall**, OCR **96%**, policy rules **98%**, decision/comparison **100%**, submission service **95%**. Separate API, RQ and model subprocess execution is not counted in coverage. See `coverage.xml` and `non-docker-tests.xml`.

## Newly verified using real local services

- MongoDB 8.0.17 replica-set transactions: simultaneous same-key submissions, stale updates, competing reviewers, immutable evaluation history and retry deduplication.
- Redis 7.4.9 / RQ 2.12: atomic unique enqueue, execution, scheduled retry, job timeout, acknowledgment-loss replay, actual Redis process kill/restart and durable Mongo outbox recovery by the surviving production dispatcher.
- Tesseract 5.5.2: **8/8 fields correct** on each clean, seven-degree rotated and mildly blurred generated receipt. This is controlled-fixture accuracy, not arbitrary-document accuracy.
- HTTP workflow across customer, service, reviewer and admin roles: product/warranty changes, repair/replacement records, routed access, private comments, uploads/OCR corrections, submission/replay, both saved models, summary, request-info/resubmit, version changes, approval/close, historical reports and notifications.
- Security checks: cross-owner/center denial, forbidden role injection, CSRF, signed evidence URL binding/expiry/tampering, private storage, corrupt/encrypted/page-capped documents, PDF JavaScript and annotation-action rejection, non-finite/negative amounts and malformed model probabilities.
- Local flan-t5-small generation after upgrading Transformers: generated text failed conservative grounding checks and correctly returned the factual fallback. Final diagnostic wall time **27.457 seconds**. Earlier cold attempts exceeded the production 30-second budget and fell back on timeout. The diagnostic has an explicit 120-second ceiling; production remains 30 seconds.
- Dependency audit: **no known vulnerabilities across 105 packages** in the final snapshot; dependency compatibility check passed. Transformers 4.57.6 advisories prompted upgrade to non-yanked 5.17.0. Advisory results are time-specific, not a security guarantee.

## End-to-end performance

Measured last-upload-complete → committed evaluation, including queue polling, text-PDF OCR, automatic evidence-confirmation API calls, submission, both models and database commit. Summary jobs were drained between sequential samples.

| State | Samples | p50 | p95 | Maximum | Five-second target |
|---|---:|---:|---:|---:|---|
| Cold worker/model processes | 3 | 23.561 s | 23.675 s | 23.687 s | **Failed** |
| Warm worker/model processes | 5 | 3.845 s | 4.262 s | 4.279 s | Met in these samples |

No model failures occurred. Passing functional assertions does not imply cold-start or sustained concurrent inference performance passes. Timing results are in `end-to-end.json`; load measurements are in `load-10000.json`.

## Fixes made during verification

- Corrected OCR grouping to use block/paragraph/line identifiers instead of line number alone.
- Rejected PDF JavaScript name trees and annotation actions/attachments.
- Enforced exactly three image-model labels/outputs and validated probability contracts.
- Made dispatcher dependency failures retryable without logging connection strings.
- Bounded Redis test-client retries so shutdown cannot stall the runner.
- Added claim scope/status/ID indexes matching filtered report pagination.
- Hardened local summary loading with no remote code and safetensors; limited CPU threads.
- Preserved private uploads on ambiguous commit outcomes but removed files on definitive stale-update aborts.
- Earlier fixes include idempotency-key shadowing, server-owned service routing and configurable expiry-notification deduplication.

## Existing model/data deliverables

Seed-42 dataset: 1,500 unique synthetic claims (500 per class), train/validation/test 1,050/225/225, 2,550 card images. Both saved classifiers scored **225/225 (100%)**, macro-F1 1.0, on the held-out synthetic test split; matrices are diagonal 75/75/75. The Keras image model is GTM-compatible, not trained through Google's web UI. These scores do not establish real-world accuracy. The 30-claim comparison and reproducible generators remain supplied.

## Excluded or externally blocked acceptance

- **Docker:** explicitly excluded by the user; not built or run.
- **Atlas-specific tests:** pending a disposable Atlas URI; local replica-set results do not establish Atlas permissions/connectivity or production deployment behavior.
- **99% uptime:** requires an agreed observation period on a deployment.
- **Real-world accuracy:** requires independently labeled real claim data.
- **Independent security review and deployment controls:** not replaced by automated checks; see `security-checks.md`.
- **Sustained concurrent inference / arbitrary OCR layouts:** not established by the scoped measurements above.

All locally provisioned non-Docker test cases have been executed, but the suite is **not all green**, and production acceptance is not established. Do not describe the latency failures or external blockers as completed requirements.

## Cleanup and reproducibility

The runner stopped its MongoDB, Redis and API services, removed temporary test databases and generated evidence, and left portable tools/caches under ignored `private/test-tools`. No listeners remained on test ports 27018, 6380 or 18000 after the final run. No production credentials, system services or frontend changes were used.

See `non-docker-scope.md` for scope, `README.md` for setup, `requirements.windows.lock.txt` for installed versions, and the JSON/XML files in this directory for evidence.
