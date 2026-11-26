"""Generate telemetry for screenshots, not an official scaling benchmark."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request


def now():
    return datetime.now(timezone.utc).isoformat()


def get_json(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=480)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--out", default="reports/evidence/alert-observation.json")
    args = parser.parse_args()
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    deadline = time.monotonic() + args.seconds
    counts = Counter()
    lock = threading.Lock()
    result = {"purpose": "screenshot/alert verification, NOT scaling benchmark", "started_at": now(),
              "configuration": {"workers": args.workers, "seconds": args.seconds}, "observations": []}
    key = os.getenv("AGENT_API_KEY", "day14-lab-key")

    def worker():
        while not stop.is_set() and time.monotonic() < deadline:
            request = urllib.request.Request("http://127.0.0.1:8080/ask", method="POST",
                data=b'{"question":"Docker container la gi?"}',
                headers={"Content-Type": "application/json", "X-API-Key": key})
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    response.read()
                    code = str(response.status)
            except urllib.error.HTTPError as exc:
                exc.read()
                code = str(exc.code)
            except OSError as exc:
                code = type(exc).__name__
            with lock:
                counts[code] += 1
            stop.wait(0.1)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(worker) for _ in range(args.workers)]
        try:
            while time.monotonic() < deadline:
                try:
                    snapshot = get_json("http://127.0.0.1:9090/api/v1/alerts")
                    result["observations"].append({"observed_at": now(), "alerts": snapshot["data"]["alerts"]})
                    result["status_counts"] = dict(counts)
                    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    if "first_both_firing_at" not in result:
                        firing = {a["labels"]["alertname"] for a in snapshot["data"]["alerts"] if a["state"] == "firing"}
                        if {"AgentHighErrorRate", "AgentHighLatencyP95"} <= firing:
                            result["first_both_firing_at"] = now()
                            print("Both alerts FIRING at " + result["first_both_firing_at"], flush=True)
                except OSError as exc:
                    result["observations"].append({"observed_at": now(), "error": type(exc).__name__})
                stop.wait(min(5, max(0, deadline - time.monotonic())))
        finally:
            stop.set()
        for future in futures:
            future.result()
    result.update(ended_at=now(), status_counts=dict(counts))
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "observations"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
