# Non-Docker acceptance scope

Command: `.venv\Scripts\python.exe -m database.run_local_tests --full --junitxml=reports/non-docker-tests.xml`

The runner provisions only temporary local databases, private evidence and loopback services. Docker is excluded. Real infrastructure consists of MongoDB 8.0.17 (single-node replica set), community Windows Redis 7.4.9, RQ 2.12, Tesseract 5.5.2, Uvicorn, and the saved Python/Keras/local T5 artifacts.

| Area | Test evidence |
|---|---|
| Functional workflows | All four roles; product update; warranty; service records; private comments; uploads; correction; submit/replay; review/request-info/resubmit/approval/close; pinned reports; notifications |
| Concurrency | Same-key simultaneous submits; competing reviewers; optimistic version conflicts; atomic queue uniqueness |
| Recovery | Redis process killed and restarted; durable Mongo outbox replayed by surviving production dispatcher; scheduled RQ retry; worker timeout; result deduplication |
| OCR | Actual clean, seven-degree rotated, mildly blurred generated receipts; corrupt/encrypted/oversized/active-content rejection; ambiguous date and amount handling |
| Models | Both saved classifiers in queue pipeline; class reordering; invalid values/shapes; timeout and unavailable-artifact behavior; actual local T5 generation and grounding fallback |
| Scale | 10,000 synthetic claims, 100 identities, 20 concurrent clients, 800 HTTP requests; scopes and exact counts asserted |
| Timing | Three cold and five warm upload-complete-to-commit samples; OCR and automatic confirmation calls included; summary queue drained between samples |
| Security | Cross-owner/center access, role injection, CSRF, signed URL binding/tampering/expiry, private storage, PDF active content, dependency advisory audit |

The 2-second load-test p95 assertion is a local diagnostic threshold, not a requirement supplied by the user. A failed measurement is retained, not silently relaxed. The 5-second end-to-end requirement is recorded separately for cold and warm results; passing workflow assertions does not imply passing that performance requirement.

Local summary generation has a 30-second production limit. A separate 120-second diagnostic test checks that weights can actually load and generate; its report includes the budget and measured time. Passing the diagnostic does not mean cold summary generation always fits the production budget. Timed-out or ungrounded summaries remain labeled factual fallbacks and never alter recommendations.

## Not established by these tests

- Atlas connectivity, managed-cluster permissions and deployment behavior: requires a test-only Atlas URI.
- 99% business-hours uptime: requires an agreed observation period on an actual deployment.
- Real-world model accuracy: requires independently labeled real claims, not more synthetic fixtures.
- Independent security audit, production TLS/network/backup controls, or sustained concurrent inference throughput.
- Docker build/runtime behavior: explicitly excluded by the user.

The image OCR fixtures are controlled tests, not a measured accuracy claim for arbitrary photographs, languages, layouts or severe blur. The load test verifies scoped read traffic, not every endpoint at peak production concurrency. Both qualifications must remain attached to any summary of results.
