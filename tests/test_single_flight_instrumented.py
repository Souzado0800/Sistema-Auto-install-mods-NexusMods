import asyncio
import pytest
from downloads.single_flight import SingleFlightGroup


@pytest.mark.asyncio
async def test_single_flight_instrumented_20_callers():
    """
    Simulates 20 concurrent dependencies requesting the exact same Nexus File ID.
    Asserts:
      - Total real network/worker executions == 1.
      - 19 callers wait and reuse the single in-flight result.
      - All 20 callers receive the identical payload.
    """
    group = SingleFlightGroup()
    network_call_count = 0
    key = "nexus_mysummercar_file_99999"

    async def simulated_network_download():
        nonlocal network_call_count
        network_call_count += 1
        # Simulate real network latency (50ms)
        await asyncio.sleep(0.05)
        return {"file_id": 99999, "bytes": b"MOD_DATA_BYTES", "sha256": "abc123def456"}

    # Launch 20 concurrent coroutines requesting the exact same key
    tasks = [group.do(key, simulated_network_download) for _ in range(20)]
    results = await asyncio.gather(*tasks)

    # Verification
    assert len(results) == 20
    assert network_call_count == 1, f"Expected exactly 1 network call, got {network_call_count}"

    first = results[0]
    for r in results:
        assert r == first
        assert r["file_id"] == 99999
