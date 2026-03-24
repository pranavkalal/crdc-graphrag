"""Standalone entry point for the pilot ingestion workflow."""

import asyncio


async def run_pilot_ingest() -> None:
    """Placeholder orchestration entry point for processing the pilot corpus."""
    raise NotImplementedError("Pilot ingestion has not been implemented yet.")


def main() -> int:
    """Run the placeholder ingestion script."""
    try:
        asyncio.run(run_pilot_ingest())
    except NotImplementedError as exc:
        print(exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
