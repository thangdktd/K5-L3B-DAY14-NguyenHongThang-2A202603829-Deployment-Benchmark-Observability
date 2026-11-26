"""Stop only the completed CP8 project, preserving all its Docker volumes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "k5-day14-observability"


def docker(*args):
    return subprocess.run(["docker", *args], cwd=ROOT, check=True,
                          capture_output=True, text=True, encoding="utf-8").stdout


def digest(values):
    return hashlib.sha256("\n".join(sorted(values)).encode()).hexdigest()


def main():
    evidence = ROOT / "reports/evidence"
    audit = json.loads((evidence / "final-validation.json").read_text(encoding="utf-8"))
    if audit["status"] != "PASS":
        raise RuntimeError("Final validation must pass before stopping CP8")
    for name, entry in audit["screenshots"].items():
        if hashlib.sha256((ROOT / "screenshots" / name).read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError("Screenshot changed after validation")
    own = docker("ps", "-aq", "--filter", f"label=com.docker.compose.project={PROJECT}").splitlines()
    all_before = docker("ps", "-aq").splitlines()
    others = set(all_before) - set(own)
    details = json.loads(docker("inspect", *own)) if own else []
    volumes = sorted({mount["Name"] for obj in details for mount in obj.get("Mounts", [])
                      if mount["Type"] == "volume"})
    configs = []
    for obj in details:
        if obj["Config"]["Labels"].get("com.docker.compose.service") != "agent":
            continue
        env = dict(item.split("=", 1) for item in obj["Config"]["Env"] if "=" in item)
        config = {k: env[k] for k in ("MOCK_ERROR_RATE", "MOCK_SLOW_RATE", "AGENT_VERSION", "LLM_MODEL")}
        if config != {"MOCK_ERROR_RATE": "0.01", "MOCK_SLOW_RATE": "0.03", "AGENT_VERSION": "v2", "LLM_MODEL": "mock-llm-small"}:
            raise RuntimeError("Restore agent defaults before stopping")
        configs.append(config)
    started = datetime.now(timezone.utc).isoformat()
    output = docker("compose", "-p", PROJECT, "-f",
                    "06-lab-complete/benchmark-observability/production/docker-compose.yml", "down")
    remaining = docker("ps", "-aq", "--filter", f"label=com.docker.compose.project={PROJECT}").splitlines()
    all_after = set(docker("ps", "-aq").splitlines())
    volume_names = set(docker("volume", "ls", "-q").splitlines())
    if remaining or all_after != others or not set(volumes) <= volume_names:
        raise RuntimeError("Docker post-stop verification failed; inspect actual state")
    result = {"started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(),
              "project": PROJECT, "command": "docker compose -p k5-day14-observability -f 06-lab-complete/benchmark-observability/production/docker-compose.yml down",
              "exit_code": 0, "project_containers_remaining": 0, "restored_agent_configs_before_stop": configs,
              "retained_volume_count": len(volumes), "all_project_volumes_retained": True,
              "other_container_count": len(others), "other_container_ids_sha256": digest(others),
              "other_containers_unchanged": True, "cloud_deployment_modified": False}
    (evidence / "docker-shutdown.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
