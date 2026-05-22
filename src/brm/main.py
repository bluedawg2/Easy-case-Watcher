"""FastAPI application entry point for the Bankruptcy Rule Monitor API.

Mounts:
    /review  — review-queue API (plan 01-05)
    /changes — pull-delivery API (plan 01-05)

CORS is configured for the local Vite dev server (http://localhost:5173).
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from brm.api.pull import router as pull_router
from brm.api.review import router as review_router
from brm.lifecycle import IllegalTransitionError

app = FastAPI(title="Bankruptcy Rule Monitor API")

# ---------------------------------------------------------------------------
# CORS — allow the local Vite dev server and same-origin production deploys
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(IllegalTransitionError)
async def illegal_transition_handler(
    request: Request, exc: IllegalTransitionError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(review_router)
app.include_router(pull_router)
