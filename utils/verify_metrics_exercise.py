"""Check Exercise 7.1 against the real develop app without rerunning benchmarks."""
import importlib.util
import os
from pathlib import Path
import sys


root = Path(__file__).resolve().parents[1]
develop = root / "06-lab-complete/benchmark-observability/develop"
sys.path.insert(0, str(develop))
os.environ.update(AGENT_VERSION="v2", MOCK_ERROR_RATE="0", MOCK_SLOW_RATE="0")
spec = importlib.util.spec_from_file_location("develop_metrics_app", develop / "app.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from fastapi.testclient import TestClient

with TestClient(module.app) as client:
    response = client.post("/ask", json={"question": "Docker?"})
    assert response.status_code == 200, response.text
    client.get("/unknown-one")
    client.get("/unknown-two")
    metrics = client.get("/metrics").text
    assert 'agent_question_length_chars_count 1.0' in metrics
    assert 'agent_question_length_chars_sum 7.0' in metrics
    assert 'route="unmatched"' in metrics
    assert '/unknown-one' not in metrics and '/unknown-two' not in metrics
    lines = [line for line in metrics.splitlines() if line.startswith((
        "# TYPE agent_question_length_chars", "agent_question_length_chars",
        "# TYPE http_requests_total", "# TYPE agent_in_flight_requests",
        "http_requests_total", "agent_in_flight_requests"))]
    (root / "reports/evidence/exercise-7-1-metrics.txt").write_text(
        "GET /metrics after POST /ask {question: Docker?} and two unknown routes\n" +
        "\n".join(lines) + "\nPASS: histogram count=1, sum=7; unknown paths share unmatched label.\n", encoding="utf-8")
print("Exercise 7.1 PASS: real HTTP metrics, count=1, sum=7; bounded route labels")
