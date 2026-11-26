"""Validate the saved Day14 submission without rerunning graders or benchmarks."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "06-lab-complete/benchmark-observability/develop"
PROD = ROOT / "06-lab-complete/benchmark-observability/production"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def check_eval(report, baseline=None):
    results = report["results"]
    require(len(results) == report["total"] == 23, "eval must contain 23 questions")
    require(len({r["id"] for r in results}) == 23, "duplicate eval question")
    passed = sum(r["passed"] for r in results)
    require(passed == report["passed"], "eval passed count mismatch")
    require(round(passed / 23, 4) == report["accuracy"], "eval accuracy mismatch")
    regressions = [] if baseline is None else [r["id"] for r in results if not r["passed"] and
        next(b for b in baseline["results"] if b["id"] == r["id"])["passed"]]
    require(regressions == report["quality_gate"]["regressions"], "eval regression mismatch")
    require(report["quality_gate"]["passed"] ==
            (report["accuracy"] >= report["quality_gate"]["min_accuracy"] and not regressions), "quality gate mismatch")


def png_dimensions(path):
    data = path.read_bytes()
    if data.startswith(b"\xff\xd8\xff"):
        # Preserve student evidence bytes even when a JPEG was named .png.
        from PIL import Image
        with Image.open(path) as picture:
            picture.verify()
        with Image.open(path) as picture:
            picture.load()
            dimensions = picture.size
        require(dimensions[0] >= 600 and dimensions[1] >= 400, f"screenshot too small: {path.name}")
        return dimensions
    require(data[:8] == b"\x89PNG\r\n\x1a\n", f"invalid PNG signature: {path.name}")
    position, dimensions, pixels = 8, None, b""
    ended = False
    while position < len(data):
        size = struct.unpack(">I", data[position:position + 4])[0]
        kind = data[position + 4:position + 8]
        payload = data[position + 8:position + 8 + size]
        crc = struct.unpack(">I", data[position + 8 + size:position + 12 + size])[0]
        require(zlib.crc32(kind + payload) & 0xFFFFFFFF == crc, f"PNG CRC mismatch: {path.name}")
        if kind == b"IHDR":
            dimensions = struct.unpack(">II", payload[:8])
        if kind == b"IDAT":
            pixels += payload
        position += size + 12
        if kind == b"IEND":
            ended = True
            break
    require(ended and bool(zlib.decompress(pixels)), f"incomplete PNG: {path.name}")
    require(dimensions[0] >= 600 and dimensions[1] >= 400, f"screenshot too small: {path.name}")
    return dimensions


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="reports/evidence/final-validation.json")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        from copy import deepcopy
        fixture = read_json(ROOT / "reports/eval_v2_fixed.json")
        for field, value in [("total", 22), ("passed", 22), ("accuracy", 0.9)]:
            bad = deepcopy(fixture)
            bad[field] = value
            try:
                check_eval(bad)
            except ValueError:
                continue
            raise ValueError(f"negative control failed: {field}")
        bad = deepcopy(fixture)
        bad["quality_gate"]["passed"] = False
        try:
            check_eval(bad)
        except ValueError:
            pass
        else:
            raise ValueError("negative control failed: gate")
        print("Negative controls PASS: total, passed, accuracy, quality gate")

    expected = {f"load_v2_c{c}.json" for c in (1, 10, 50, 100)} | {
        f"load_v2_slow_{r}.json" for r in ("0", "0.03", "0.1")} | {
        f"eval_{v}.json" for v in ("v1", "v2", "v2_fixed")}
    require({p.name for p in (ROOT / "reports").glob("*.json")} == expected, "missing or extra CP7 JSON")
    report_text = (ROOT / "BENCHMARK_REPORT.md").read_text(encoding="utf-8")
    table_rows = [[c.strip() for c in line.strip().strip("|").split("|")]
                  for line in report_text.splitlines() if line.startswith("|")]
    loads = {}
    for name in sorted(expected):
        target = ROOT / "reports" / name
        require(target.read_bytes() == (DEV / "reports" / name).read_bytes(), f"JSON source copy mismatch: {name}")
        data = read_json(target)
        if name.startswith("load_"):
            require(data["total_requests"] == sum(data["status_codes"].values()) == 300, f"request count: {name}")
            errors = sum(v for k, v in data["status_codes"].items() if k != "200")
            require(round(errors / 300, 4) == data["error_rate"], f"error rate: {name}")
            require(data["latency_ms"]["p50"] <= data["latency_ms"]["p95"] <= data["latency_ms"]["p99"], f"percentiles: {name}")
            if name.startswith("load_v2_c"):
                row = next(r for r in table_rows if len(r) == 7 and r[0] == str(data["concurrency"]))
                observed = [float(r.rstrip("%")) for r in row[1:6]]
                expected_values = [round(data["rps"], 1), *[data["latency_ms"][k] for k in ("p50", "p95", "p99")], round(data["error_rate"] * 100, 2)]
                require(observed == expected_values, f"benchmark table mismatch: {name}")
            else:
                rate = name.removeprefix("load_v2_slow_").removesuffix(".json")
                row = next(r for r in table_rows if r[0].startswith(rate) and len(r) == 5 and "(" not in r[1])
                require([float(x) for x in row[1:4]] == [data["latency_ms"][k] for k in ("avg", "p95", "p99")], f"slow table mismatch: {name}")
            loads[name] = {k: data[k] for k in ("total_requests", "rps", "error_rate", "latency_ms")}
    v1, v2, fixed = [read_json(ROOT / "reports" / f"eval_{v}.json") for v in ("v1", "v2", "v2_fixed")]
    check_eval(v1)
    check_eval(v2, v1)
    check_eval(fixed, v2)
    require(fixed["passed"] == 23 and fixed["quality_gate"]["min_accuracy"] == 1.0, "final gate not 100%")
    eval_section = report_text.split("## 3.", 1)[1].split("## 4.", 1)[0]
    eval_rows = {r[0]: r[1:] for r in table_rows if len(r) == 4 and r[0] in
                 ("Accuracy", "Avg tokens / câu", "Tổng cost (USD)", "Cost / câu đúng (USD)", "Quality gate trong JSON")}
    require(bool(eval_section), "missing eval report section")
    for index, data in enumerate((v1, v2, fixed)):
        require(f"{data['passed']}/{data['total']}" in eval_rows["Accuracy"][index], "eval report fraction mismatch")
        require(eval_rows["Accuracy"][index].startswith(f"{data['accuracy']:.1%}"), "eval report accuracy mismatch")
        for label, key, tolerance in [("Avg tokens / câu", "avg_tokens", 0.001),
                                       ("Tổng cost (USD)", "total_cost_usd", 0.0000005),
                                       ("Cost / câu đúng (USD)", "cost_per_correct_usd", 0.0000005)]:
            require(abs(float(eval_rows[label][index].replace("$", "")) - data[key]) <= tolerance,
                    f"eval report numeric mismatch: {label}")
        require(("PASS" in eval_rows["Quality gate trong JSON"][index]) == data["quality_gate"]["passed"],
                "eval report gate mismatch")
    scaling = {}
    scaling_text = report_text.split("## 5.", 1)[1].split("## 6.", 1)[0]
    scaling_rows = [[c.strip() for c in line.strip().strip("|").split("|")]
                    for line in scaling_text.splitlines() if line.startswith("|")]
    for number in (1, 3):
        for source in (PROD / "benchmark-results").glob(f"scale_{number}_*.csv"):
            require(source.read_bytes() == (ROOT / "benchmark-results" / source.name).read_bytes(), f"CSV copy mismatch: {source.name}")
            with source.open(encoding="utf-8", newline="") as stream:
                reader = csv.reader(stream)
                header = next(reader)
                require(all(len(row) == len(header) for row in reader if row), f"invalid CSV rows: {source.name}")
        with (ROOT / "benchmark-results" / f"scale_{number}_stats.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        aggregate = next(r for r in rows if r["Name"] == "Aggregated")
        detail = [r for r in rows if r["Name"] != "Aggregated"]
        for field in ("Request Count", "Failure Count"):
            require(int(aggregate[field]) == sum(int(r[field]) for r in detail), f"CSV aggregate: {field}")
        row = next(r for r in scaling_rows if len(r) == 6 and r[0] == str(number))
        require([float(x) for x in row[1:5]] == [round(float(aggregate["Requests/s"]), 1),
                *[float(aggregate[k]) for k in ("50%", "95%", "99%")]], "scaling report percentile/RPS mismatch")
        require(int(re.match(r"\d+", row[5])[0]) == int(aggregate["Failure Count"]), "scaling report failure count mismatch")
        scaling[str(number)] = {k: aggregate[k] for k in ("Request Count", "Failure Count", "Requests/s", "50%", "95%", "99%")}
    protected = ["06-lab-complete/check_production_ready.py", "06-lab-complete/benchmark-observability/develop/eval/golden_dataset.jsonl"]
    require(not git("diff", "origin/main", "--", *protected), "protected grader/dataset modified")
    cp5 = ["06-lab-complete/app", "06-lab-complete/utils", "06-lab-complete/Dockerfile", "06-lab-complete/requirements.txt", "06-lab-complete/docker-compose.yml", "06-lab-complete/railway.toml"]
    require(not git("diff", "4617c63", "--", *cp5), "CP5 source changed since valid grader run")
    screenshot_review = read_json(ROOT / "reports/evidence/screenshot-review.json")
    images = {}
    for filename in ("dashboard.png", "running.png", "test.png", "grafana-dashboard.png", "jaeger-slow-trace.png", "jaeger-error-trace.png", "prometheus-alert-firing.png"):
        path = ROOT / "screenshots" / filename
        dimensions = png_dimensions(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        require(screenshot_review[filename]["sha256"] == digest, f"screenshot changed after visual review: {filename}")
        images[filename] = {"dimensions": dimensions, "sha256": digest,
                            "actual_format": "JPEG" if path.read_bytes().startswith(b"\xff\xd8\xff") else "PNG"}
    for file in [ROOT / name for name in ("MISSION_ANSWERS.md", "DEPLOYMENT.md", "BENCHMARK_REPORT.md", "FINAL_AUDIT.md")]:
        content = file.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", content):
            if not re.match(r"https?://|#", target):
                path = file.parent / target.split("#")[0]
                require(path.exists() or path == ROOT / args.out, f"broken link in {file.name}: {target}")
    candidates = git("ls-files", "-co", "--exclude-standard", "-z").decode().split("\0")
    patterns = {"github_token": r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b",
                "jwt": r"\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\b",
                "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"}
    for filename in filter(None, candidates):
        path = ROOT / filename
        require(not any(part in (".venv-wsl", "__pycache__", "node_modules") for part in path.parts), f"cache or virtualenv staged: {filename}")
        require(not (path.name.startswith(".env") and path.name != ".env.example"), f"secret env file included: {filename}")
        require(path.stat().st_size < 10 * 1024 * 1024, f"unnecessary large file: {filename}")
        if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for category, pattern in patterns.items():
            require(not re.search(pattern, text), f"possible {category}: {filename} (value withheld)")
        if path.suffix == ".json":
            json.loads(text)
        if path.suffix == ".jsonl":
            for line in text.splitlines():
                if line.strip():
                    json.loads(line)
    for category, pattern in patterns.items():
        require(not re.search(pattern.encode(), git("log", "--all", "-p", "--format=")), f"possible {category} in Git history (value withheld)")
    require(not git("log", "--all", "--format=%H", "--", ".env", "*.env"), "env file exists in Git history")
    require(not git("diff", "--check"), "git whitespace errors")
    evidence = ROOT / "reports/evidence"
    correlation = []
    logs = [json.loads(line) for p in evidence.glob("*-selected.jsonl") for line in p.read_text(encoding="utf-8").splitlines() if line]
    for tid, status in [("f97793940f004263c4db7441e264b065", 200), ("c34cb9ba78a06c551110b3357b8eac11", 503)]:
        trace = read_json(evidence / f"trace-{tid}.json")["data"][0]
        root_span = next(s for s in trace["spans"] if s["operationName"] == "POST /ask")
        entry = next(x for x in logs if x["trace_id"] == tid and x["event"] == "http_request")
        require(entry["span_id"] == root_span["spanID"] and entry["status"] == status, "trace/log correlation mismatch")
        require(next(t["value"] for t in root_span["tags"] if t["key"] == "http.status_code") == status, "trace HTTP status mismatch")
        correlation.append({"trace_id": tid, "duration_ms": root_span["duration"] / 1000, "log_ms": entry["ms"], "status": status})
    observation = read_json(evidence / "alert-observation.json")
    require(any({"AgentHighErrorRate", "AgentHighLatencyP95"} <= {
        a["labels"]["alertname"] for a in o.get("alerts", []) if a["state"] == "firing"}
        for o in observation["observations"]), "two simultaneous firing alerts not recorded")
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "status": "PASS", "cp7_json_count": 10,
              "cp5": "Reuse PASS 12/12 at 4617c63; source unchanged", "protected_files_unchanged": True,
              "loads": loads, "scaling": scaling, "screenshots": images, "trace_log": correlation,
              "scope": "Saved artifacts and guarded consistency checks; rubric points require Lab Coach review"}
    (ROOT / args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Final validation PASS: JSON/CSV, report tables, 7 visually reviewed images, trace/log, alerts, protected files, Git hygiene")


if __name__ == "__main__":
    main()
