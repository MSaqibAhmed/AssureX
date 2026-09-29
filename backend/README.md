# AssureX Claim Engine backend

FastAPI/PyMongo/RQ backend at `/api/v1`. See the parent README for the integrated frontend setup, CORS, Compose and real browser acceptance workflow. This directory retains independent dependencies and runtime commands.

## Run

Use Python 3.12. TensorFlow, PyTorch and OCR dependencies are large; installation may take several minutes.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `MONGO_URI` to a transaction-capable MongoDB Atlas cluster, `SESSION_SECRET` to a random value of at least 32 characters, and `REDIS_URL`. Keep `.env` private. For local HTTP only, set `COOKIE_SECURE=false`; production requires HTTPS and secure cookies. No default real credentials are provided.

Native execution also needs Tesseract and Poppler on PATH. The Docker image installs both. Linux remains the production deployment target. The non-Docker Windows acceptance suite uses a portable community Redis build and real RQ SimpleWorkers with killable model subprocesses; it does not establish Linux or Atlas deployment behavior.

```sh
python -m database.init_schema
python -m dataset_generator.generate --seed 42
python -m src.ml.python_model.train
python -m src.ml.gtm_adapter.train
python -m reports.compare_30
```

Seed demo users and register trained artifacts using an explicit `DEMO_PASSWORD` environment variable of at least 12 characters:

```sh
python -m database.seed_demo
uvicorn src.main:app --host 127.0.0.1 --port 8000 --no-access-log
python -m src.jobs.dispatcher
python -m src.jobs.worker
```

Run the last three commands in separate processes. Alternatively:

```sh
docker compose up --build
```

Atlas remains external. Evidence is in a private Docker volume and is never mounted as public static content. API documentation is at `/docs`; the generated OpenAPI specification is at `/openapi.json`.

## API usage

Service routing is server-owned. The `settings` document `_id: "claim_routing"` has a `value` mapping product categories (or `default`) to `{center_id, reviewer_id}`. Demo seeding installs the central service center and demo reviewer without overwriting existing settings. New claims snapshot these assignments; routing changes do not reassign historical claims. Configured destinations must be active, otherwise creation returns 503. Without configured routing, the center remains unassigned and an active reviewer is chosen deterministically. Customer payloads cannot assign staff or centers. Production routing settings should be provisioned by an operator; there is no public reassignment endpoint.

RQ 2.12 or later is required for atomic unique enqueue. Competing dispatchers acknowledge an already-enqueued intent; lost queued/running Redis jobs are reconciled from the outbox. Exhausted failed jobs remain failed for operator review rather than being retried indefinitely.

Register/login returns `{data: {user, csrf_token}, request_id, version}` and sets the HttpOnly `assurex_session` cookie. Send the returned `csrf_token` as `X-CSRF-Token` with every authenticated mutation. `GET /api/v1/me` returns the current user and CSRF token. Cross-site browser mutations are denied. CORS permits only the explicit CORS_ORIGINS environment allowlist with credentials.

All normal JSON successes use `{data, request_id, version}`. Errors use `{code, message, field_errors}`. PDF and evidence downloads return binary bodies. IDs are opaque strings; the user-facing claim number is a separate `public_claim_id`.

The exact requested routes are tracked by `src/api/routes.py:ROUTES` and tested against OpenAPI. Product PATCH currently accepts the complete editable product representation. Claim PATCH takes `{version, status, facts}`. Submission takes `{version, status}` and an `Idempotency-Key` header. The key must be at least eight characters. Replaying a committed submission with the same key and request returns the same job ID. A different payload with that key returns 409.

Uploads are multipart: `file`, `document_type`, `version`, `status`. Document types are `receipt`, `serial_photo`, `warranty`, `diagnostic`, `supporting`. The response contains `document_id` and `job_id`. Wait for extraction completion before submitting. `GET /documents/{id}/ocr` supplies extraction runs, fields and a user-bound download link valid for two minutes. To preserve the specified route inventory, that link uses the same route with `download=true`, `expires`, and `signature` query parameters. Download checks session, role, object scope, expiry, signature and resolved storage path.

Reviews take `{version, status, evaluation_id, action, reason}` where action is `approve`, `reject` or `request_info`. AI output always routes to Manual Review. Only the assigned reviewer can append an approval or rejection. Historical evaluation/review records are not updated by these handlers. Reports require `evaluation_id` and optionally `review_id` query parameters; the server verifies both belong to the accessible claim.

## Models and evidence

The generator creates 1,500 unique synthetic rows with rubric labels (500 each), splits groups before rendering, then creates 2,100 training cards and 225 cards per held-out split. Provenance and split hashes are written under `data/`. Both models consume the allowlisted feature builder. The cards contain facts only.

The Python trainer compares Logistic Regression, Random Forest and Gradient Boosting using train-only preprocessing and five-fold stratified CV. Validation macro-F1, invalid-to-valid errors and latency select the winner; the test set is opened afterward. Saved artifacts include the pipeline, feature schema, dataset hashes, metrics and confusion matrix. Git SHA is null when the project is not in a Git repository.

The image trainer produces a from-scratch Keras image classifier compatible with the Teachable Machine inference interface. It is **not an export trained through Google's web UI**. Its preprocessing matches the [official Google Keras export snippet](https://github.com/googlecreativelab/teachablemachine-community/blob/master/snippets/markdown/image/tensorflow/keras.md): RGB, centered 224×224 image fit, float32 normalization to [-1,1]. Class mapping is stored explicitly in `artifacts/gtm/labels.json`.

The optional local summary wrapper loads the downloaded `google/flan-t5-small` files from `artifacts/summary` without network access. It uses greedy generation and an 80-token limit; unavailable, timed-out or unsupported output produces a tagged factual fallback. It runs as a separate job after the decision commit, with a 30-second process limit. Download/cache this model before deployment if local generation is required. The summary is never an input to either classifier or the decision engine.

## Tests and verification

```sh
pytest -q --cov=src --cov-report=term-missing --cov-report=xml:reports/coverage.xml
```

Set `MONGO_TEST_URI` to a disposable transaction-capable test database service to enable MongoDB integration tests. They create and drop only a randomly named `assurex_test_*` database. The ordinary unit suite does not contact a database.

Optional local test infrastructure (Docker required):

```sh
docker compose -f docker-compose.test.yaml up -d --wait
# MONGO_TEST_URI=mongodb://localhost:27018/?replicaSet=rs0&directConnection=true
# REDIS_TEST_URL=redis://localhost:6380/15
pytest -q
docker compose -f docker-compose.test.yaml down
```

The test MongoDB uses memory-backed storage and is separate from production Atlas. Its data disappears when the container is removed.

On this Windows verification host, portable MongoDB 8.0.17 is extracted under `private/test-tools`. Run `python -m database.run_local_tests` for the MongoDB/API suite, or **`python -m database.run_local_tests --full`** for all local non-Docker acceptance tests. Full mode additionally requires:

- The [Redis Windows community release 7.4.9](https://github.com/redis-windows/redis-windows/releases/tag/7.4.9), MSYS2 ZIP without service, extracted under `private/test-tools/redis`. Verified ZIP SHA256: `98af6511ca35601cc8d8200a92318e00f9d2d5425a9f7f3e8f699d3bdd59dcf6`.
- A workspace Conda environment: `conda create --prefix ./private/test-tools/ocr-env --channel conda-forge --override-channels tesseract=5.5.2 -y`. The runner adds its `Library/bin` to child-process PATH and uses `share/tessdata` for language files.
- Saved classifier artifacts and local summary weights described above. No remote inference is used.

The runner refuses occupied test ports, then starts loopback MongoDB (27018), API (18000), and, in full mode, Redis (6380). It shuts them down, drops randomly named test databases and cleans its temporary evidence directory afterward. The restart test briefly launches an additional Redis process on a dynamically selected loopback port and kills only that process. The load test creates 10,000 synthetic records and exercises 100 user identities with 20 concurrent clients. No Docker, system service or production credentials are used. Binary caches and database engine files remain under ignored `private/test-tools` for reuse.

`requirements.windows.lock.txt` records the tested Windows dependency versions; it is not a Linux lockfile. Existing Playwright API/HTTPX tests exercise real HTTP APIs. The added `tests/test_browser_live.py` launches the parent project's actual Chrome browser workflow against the built frontend and real services; see the parent README. Access logging is disabled in the example startup command to avoid logging signed download URL query strings; configure redacted production request logging separately.

Acceptance outputs are `reports/ocr-images.json`, `reports/load-10000.json`, `reports/end-to-end.json`, `reports/summary-real.json`, `reports/dependency-audit.json` and `reports/coverage.xml`. The full pipeline uses three cold and five warm samples, with summary jobs drained between samples; its performance result is not a sustained concurrent inference benchmark. Failed timing targets are recorded as false rather than disguised as passing functional assertions.

See `reports/verification.md` for executed checks and outstanding acceptance work. Synthetic model accuracy does not establish real-world accuracy. The five-second pipeline target, 10,000-claim capacity, concurrent-user behavior and 99% availability require deployment measurements and are not guaranteed by source code or unit tests.

## Contract reconciliation

See `CONTRACT_RECONCILIATION.md` for the historical standalone audit and the parent `docs/INTEGRATION_CHANGELOG.md` and `docs/verification/WORKFLOW_VERIFICATION.md` for the integration. The frontend now consumes backend lifecycle states and recommendations. `GET /api/v1/claims/{id}/documents` lists scoped public document metadata so evidence can be reopened after refresh.
