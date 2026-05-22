"""Admin CLI — drives run_ingest + run_summarize for the seeded FRBP source.

Usage:
    python -m brm.run_pipeline            # live fetch
    python -m brm.run_pipeline FEED_FILE  # fixture replay (local captured HTML file)
"""

import asyncio
import sys

from sqlalchemy import select

from brm.db import SessionLocal, engine, Base
from brm.ingest.rss import FrbpSourceAdapter
from brm.models.source import Source
from brm.pipeline import run_ingest, run_summarize
from brm.seed import seed


async def main(feed_file: str | None = None) -> None:
    async with SessionLocal() as session:
        async with session.begin():
            await seed(session)

    async with SessionLocal() as session:
        async with session.begin():
            source = (
                await session.execute(select(Source).where(Source.layer == "FRBP"))
            ).scalars().first()

            if source is None:
                print("ERROR: No FRBP source found after seeding.", file=sys.stderr)
                sys.exit(1)

            adapter = FrbpSourceAdapter(feed_file=feed_file)
            change = await run_ingest(session, source, adapter)

            if change is None:
                print("No change detected (UNCHANGED, FETCH_FAILED, or first-fetch baseline).")
                return

            print(f"Change id={change.id} status={change.status!r} — running summarize...")
            change = await run_summarize(session, change)
            print(f"Change id={change.id} final status={change.status!r}")
            if change.summary:
                print(f"  headline: {change.summary.get('headline', '?')}")
            if change.summary_error:
                print(f"  error: {change.summary_error}")


if __name__ == "__main__":
    feed_file = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(feed_file))
