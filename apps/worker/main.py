"""Prefect worker entrypoint.

Phase 0: registers a no-op flow to prove the worker boots and Prefect
can execute a flow. Subsequent phases register the process_case_event flow.
"""

import asyncio

from prefect import flow


@flow(name="noop")
async def noop_flow() -> str:
    """No-op flow used to verify worker and Prefect connectivity."""
    return "ok"


if __name__ == "__main__":
    asyncio.run(noop_flow())
