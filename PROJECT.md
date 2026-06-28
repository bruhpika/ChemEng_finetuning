# Project: ChemE-LLM Model Loading Graceful Handling

## Architecture
- **Backend (FastAPI)**: Serves `/api/chat` and a new `/api/status` endpoint. When the LLM is loading in the background, `/api/chat` returns HTTP 503 Service Unavailable, and `/api/status` reports `"loading"`.
- **Frontend (Next.js)**: Polls `/api/status` on mount. If `"loading"`, displays a non-blocking banner/overlay and disables input. Once `"ready"` or `"fallback"`, enables normal chat.
- **E2E Testing**: Independent tests calling `/api/status` and `/api/chat` before and after loading completes.

## Milestones
| # | Name | Track | Scope | Dependencies | Status |
|---|------|-------|-------|--------------|--------|
| E1 | E2E Test Suite | E2E Testing | Build E2E test harness and cases (Tiers 1-4) | None | DONE (Conv: b5d1534d-b91a-444b-ad2f-eb5e6ab1817e) |
| I1 | Backend Status & Chat | Implementation | Add `/api/status` and handle `/api/chat` during startup | None | IN_PROGRESS (Conv: aa30d3c6-3d88-4bef-b327-b5e4821f83d6) |
| I2 | Frontend Polling & UI | Implementation | Add polling, loading banner/overlay, disable chat during loading | I1 | IN_PROGRESS (Conv: aa30d3c6-3d88-4bef-b327-b5e4821f83d6) |
| I3 | E2E Verification & Hardening | Implementation | Run E2E test suite (Phase 1) and adversarial checks (Phase 2) | E1, I2 | IN_PROGRESS (Conv: aa30d3c6-3d88-4bef-b327-b5e4821f83d6) |

## Interface Contracts
### Frontend ↔ Backend Status API
- **Endpoint**: `GET /api/status`
- **Response Format**:
  ```json
  {
    "status": "loading" | "ready" | "fallback",
    "mode": "finetuned" | "base" | "rag_only" | "none",
    "retriever_ready": boolean,
    "model_ready": boolean
  }
  ```

### Frontend ↔ Backend Chat API (during startup)
- **Endpoint**: `POST /api/chat`
- **Response when loading**: `HTTP 503 Service Unavailable`
  ```json
  {
    "detail": "Model is currently loading. Please try again shortly."
  }
  ```

## Code Layout
- `app.py`: FastAPI server configuration and endpoints.
- `frontend/src/app/page.tsx`: Next.js main chat component and state.
- `scripts/verify_loading_ux.py`: E2E verification script.
