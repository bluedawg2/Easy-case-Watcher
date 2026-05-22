# Bankruptcy Rule Monitor — backend package

# --- Windows event loop policy guard -------------------------------------
# psycopg 3's async driver cannot run on Windows' default ProactorEventLoop;
# it requires a SelectorEventLoop. Setting the policy here — at package
# import, before any entry point (brm.seed, brm.run_pipeline, the Uvicorn
# dev server, future Procrastinate worker) creates an event loop — ensures
# every async path gets a psycopg-compatible loop without per-call-site
# patches. This is a no-op on Linux/macOS, so production containers are
# unaffected.
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# -------------------------------------------------------------------------
