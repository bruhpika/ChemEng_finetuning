# E2E Test Suite Ready

## Test Runner
- **Command**: `python scripts/verify_loading_ux.py`
- **Expected**: Runs FastAPI backend, executes all tiers, and exits with code 0. (Note: currently fails on Tier 1 with AssertionError because the backend doesn't support the `MOCK_MODEL_LOADING_TIME` latency configuration yet).

## Coverage Summary
| Tier | Count | Description |
|------|------:|-------------|
| 1. Feature Coverage | 5 | Verifies `/api/status` is loading and `/api/chat` returns 503 during model startup. |
| 2. Boundary & Corner | 5 | Verifies `/api/status` is ready/fallback and `/api/chat` returns 200 after loading completes. |
| 3. Cross-Feature | 4 | Verifies multiple concurrent chat requests are handled without server crash/hang, returning 503. |
| 4. Real-World Application | 3 | Verifies seamless transition: launch, poll until ready, first chat query succeeds. |
| **Total** | **17** | Total individual test verifications across the suite. |

## Feature Checklist
| Feature | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---------|:------:|:------:|:------:|:------:|
| Status API (`GET /api/status`) | 3 | 2 | ✓ | ✓ |
| Chat API (`POST /api/chat`) | 2 | 3 | ✓ | ✓ |
