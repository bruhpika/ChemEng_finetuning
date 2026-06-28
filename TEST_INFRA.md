# E2E Test Infra: ChemE-LLM Model Loading Graceful Handling

## Test Philosophy
- **Opaque-box, requirement-driven**: Test the system externally via its HTTP API endpoints (`/api/status` and `/api/chat`) simulating the user experience. No internal module dependencies.
- **Robust cleanup**: The test runner launches the server and ensures that the uvicorn processes are terminated cleanly under all execution outcomes.
- **Latency simulation**: Utilizes an environment variable `MOCK_MODEL_LOADING_TIME` to control model load time so that startup UX can be reliably tested.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---------|---------------------|:------:|:------:|:------:|:------:|
| 1 | Status API (`GET /api/status`) | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 2 | Chat API during warmup (`POST /api/chat`) | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |

### Test Case Definition
- **Tier 1 - Feature Coverage (Loading State UX)**:
  1. GET `/api/status` returns HTTP 200 OK.
  2. GET `/api/status` returns status `"loading"`.
  3. GET `/api/status` response schema contains `"mode"`, `"retriever_ready"`, and `"model_ready"`.
  4. POST `/api/chat` during loading returns HTTP 503 Service Unavailable.
  5. POST `/api/chat` during loading returns JSON error detail: `"Model is currently loading. Please try again shortly."`.
- **Tier 2 - Boundary & Corner Cases (Post-Loading Normal UX)**:
  1. GET `/api/status` transitions to `"ready"` or `"fallback"` after loading time expires.
  2. GET `/api/status` does not return `"loading"` after transition.
  3. POST `/api/chat` returns HTTP 200 OK after transition.
  4. POST `/api/chat` returns non-empty answer after transition.
  5. POST `/api/chat` response contains correct keys (`"answer"`, `"sources_md"`, `"mode"`, `"sources"`).
- **Tier 3 - Cross-Feature Combinations (Concurrent Requests)**:
  1. Fire multiple concurrent chat requests to the server during the loading state.
  2. All concurrent requests must immediately receive HTTP 503.
  3. The server does not block, hang, or crash.
  4. The server remains responsive to status queries.
- **Tier 4 - Real-World Application Scenarios (Seamless Transition)**:
  1. Start backend, poll status endpoint until it changes from `loading` to `ready`/`fallback`.
  2. Immediately send first chat request.
  3. The first chat request must succeed without delay or error.

## Test Architecture
- **Test Runner**: Location: `scripts/verify_loading_ux.py`. Invocation: `python scripts/verify_loading_ux.py`.
- **Port Isolation**: Uses custom ports `8081` (Tiers 1-2), `8082` (Tier 3), and `8083` (Tier 4) to run server processes independently.
- **Pass/Fail Semantics**: Exits with code `0` on success and non-zero code (e.g. `1`) on failure, printing detailed diagnostics and server logs.

## Coverage Thresholds
- **Tier 1 (Feature Coverage)**: ≥5 test cases per feature covering equivalence classes during warmup.
- **Tier 2 (Boundary & Corner Cases)**: ≥5 test cases per feature covering post-warmup transitions.
- **Tier 3 (Cross-Feature Combinations)**: Verification of multiple concurrent chats during startup.
- **Tier 4 (Real-World Application Scenarios)**: Real-world user flow: start, poll, chat.
