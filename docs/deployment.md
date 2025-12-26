# Deployment

- FastAPI surface at `src/cuga/backend/app.py` exposes `/health`, `/plan`, `/execute` (streaming SSE).
- Auth: `X-Token` header compared to `AGENT_TOKEN` env; budgets enforced via `AGENT_BUDGET_CEILING` and `X-Budget-Spent`.
- Configure via `configs/deploy/fastapi.yaml`; run with `uvicorn cuga.backend.app:app`.
