"""Complete optional chaos C/D/E locally; restore the repository defaults."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/evidence"
COMPOSE = ["docker", "compose", "-p", "k5-day14-observability", "-f",
           "06-lab-complete/benchmark-observability/production/docker-compose.yml"]


def now():
    return datetime.now(timezone.utc).isoformat()


def run(args, env=None):
    return subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=True).stdout


def configure(**values):
    env = dict(os.environ, MOCK_ERROR_RATE="0.01", MOCK_SLOW_RATE="0.03",
               AGENT_VERSION="v2", LLM_MODEL="mock-llm-small")
    env.update(values)
    run(COMPOSE + ["up", "-d", "--no-deps", "agent"], env)
    time.sleep(15)  # Nginx DNS refresh is 10 seconds.
    return {key: env[key] for key in ("MOCK_ERROR_RATE", "MOCK_SLOW_RATE", "AGENT_VERSION", "LLM_MODEL")}


def alerts():
    with urllib.request.urlopen("http://127.0.0.1:9090/api/v1/alerts", timeout=10) as response:
        return json.load(response)["data"]["alerts"]


def main():
    result = {"started_at": now(), "purpose": "chaos experiments C/D/E, not scaling benchmark"}
    paused = None
    try:
        result["C"] = {"change_started_at": now(), "config": configure(LLM_MODEL="mock-llm-large")}
        print("C: large model configured; collecting 210 seconds", flush=True)
        run([sys.executable, "utils/collect_observability_evidence.py", "--seconds", "210", "--workers", "20",
             "--out", "reports/evidence/chaos-c-observation.json"])
        result["C"].update(ended_at=now(), alerts=alerts())
        result["D"] = {"change_started_at": now(), "observations": []}
        paused = run(COMPOSE + ["ps", "-q", "agent"]).splitlines()[0]
        run(["docker", "pause", paused])
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline:
            result["D"]["observations"].append({"observed_at": now(), "alerts": alerts()})
            time.sleep(5)
        run(["docker", "unpause", paused])
        paused = None
        result["D"]["ended_at"] = now()
        result["E"] = {"change_started_at": now(), "config": configure(
            AGENT_VERSION="v1", MOCK_ERROR_RATE="0", MOCK_SLOW_RATE="0"), "results": []}
        dataset = ROOT / "06-lab-complete/benchmark-observability/develop/eval/golden_dataset.jsonl"
        for line in dataset.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            request = urllib.request.Request("http://127.0.0.1:8080/ask", method="POST",
                data=json.dumps({"question": item["question"]}).encode(),
                headers={"Content-Type": "application/json", "X-API-Key": os.getenv("AGENT_API_KEY", "day14-lab-key")})
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.load(response)
            missing = [keyword for keyword in item["expected_keywords"] if keyword.lower() not in body["answer"].lower()]
            score = 1 - len(missing) / len(item["expected_keywords"])
            result["E"]["results"].append({"id": item["id"], "passed": score >= 0.6,
                "missing_keywords": missing, "agent_version": body["agent_version"], "trace_id": body["trace_id"]})
        result["E"].update(ended_at=now(), passed=sum(r["passed"] for r in result["E"]["results"]),
                           total=len(result["E"]["results"]), alerts=alerts())
    finally:
        if paused:
            run(["docker", "unpause", paused])
        result["restoration_started_at"] = now()
        result["restored_config"] = configure()
        result["ended_at"] = now()
        (OUT / "chaos-cde.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("C/D/E saved; agent defaults restored", flush=True)


if __name__ == "__main__":
    main()
