"""Tests for SingleFlight request coalescer."""

import asyncio
import pytest

from downloads.single_flight import SingleFlightGroup


@pytest.mark.asyncio
async def test_single_flight_coalescing():
    """Verify that multiple concurrent requests for the same key execute only once."""
    group = SingleFlightGroup()
    execution_count = 0

    async def simulated_download():
        nonlocal execution_count
        execution_count += 1
        await asyncio.sleep(0.05)  # Simulate network transfer
        return "DOWNLOAD_RESULT_PATH"

    # Spawn 5 concurrent tasks requesting the same canonical key
    tasks = [
        group.execute("mysummercar:123:456", simulated_download)
        for _ in range(5)
    ]

    results = await asyncio.gather(*tasks)

    # All 5 coroutines must receive the identical result
    assert all(r == "DOWNLOAD_RESULT_PATH" for r in results)
    # The actual network download must have executed EXACTLY once
    assert execution_count == 1
