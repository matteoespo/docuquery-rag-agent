"""Analytics endpoint against the real langsmith Client signature."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import create_autospec, patch

from langsmith import Client

from backend.api.routers import get_analytics


def run(status: str, seconds: float, tokens: int):
    start = datetime(2026, 1, 1)
    return SimpleNamespace(
        status=status, start_time=start, end_time=start + timedelta(seconds=seconds),
        prompt_tokens=tokens, completion_tokens=0,
    )


def test_analytics_uses_a_supported_list_runs_signature():
    # autospec enforces Client.list_runs' real parameters: an argument removed
    # from langsmith (like execution_order) raises TypeError, which the endpoint
    # would otherwise swallow and report as all zeros.
    client = create_autospec(Client, instance=True)
    client.list_runs.return_value = [run("success", 2.0, 100), run("error", 4.0, 300)]

    with patch("backend.api.routers.Client", return_value=client):
        data = get_analytics()

    assert data["total_requests"] == 2
    assert data["success_rate"] == 50.0
    assert data["avg_latency"] == 3.0
    assert data["total_tokens"] == 400
    assert "est_savings" not in data
    assert client.list_runs.call_args.kwargs["is_root"] is True
