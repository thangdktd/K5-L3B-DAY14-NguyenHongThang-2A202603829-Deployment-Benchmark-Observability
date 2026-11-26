"""Run the CP3 sample in an isolated WSL process and retain redacted curl output."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def main():
    if os.name != "posix":
        raise SystemExit("Run with the WSL Python environment.")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = dict(os.environ, JWT_SECRET=secrets.token_urlsafe(48), PYTHONDONTWRITEBYTECODE="1")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT / "04-api-gateway/production", env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    evidence = [f"WSL runtime: {os.name}; Python {sys.version.split()[0]}",
                "Source: 04-api-gateway/production; isolated single-worker uvicorn", f"Base URL: {base}"]
    try:
        for _ in range(900):
            try:
                urllib.request.urlopen(base + "/health", timeout=1).close()
                break
            except OSError:
                if server.poll() is not None:
                    raise RuntimeError("CP3 server exited before readiness")
                time.sleep(0.1)
        else:
            raise RuntimeError("CP3 server did not become ready")

        def curl(path, payload, token=None):
            args = ["curl", "--silent", "--show-error", "--include", "--max-time", "15",
                    "-X", "POST", base + path, "-H", "Content-Type: application/json"]
            if token:
                args += ["-H", "Authorization: Bearer " + token]
            args += ["--data-binary", json.dumps(payload)]
            return subprocess.run(args, check=True, capture_output=True, text=True).stdout

        request = {"question": "Docker container la gi?"}
        unauthorized = curl("/ask", request)
        assert unauthorized.startswith("HTTP/1.1 401"), unauthorized
        evidence += ["\n$ curl -i -X POST $BASE/ask -H 'Content-Type: application/json' -d '<question JSON>'", unauthorized]
        # Credentials are documented sample fixtures. Never retain the login response or JWT.
        from importlib import import_module
        sys.path.insert(0, str(ROOT / "04-api-gateway/production"))
        demo = import_module("auth").DEMO_USERS
        login = curl("/auth/token", {"username": "student", "password": demo["student"]["password"]})
        token = json.loads(login.split("\n\n", 1)[1])["access_token"]
        codes = []
        for index in range(1, 12):
            response = curl("/ask", request, token)
            code = int(response.split()[1])
            codes.append(code)
            if index in (1, 11):
                evidence += [f"\n$ curl -i -X POST $BASE/ask -H 'Authorization: Bearer <REDACTED>' -H 'Content-Type: application/json' -d '<question JSON>' # authenticated request {index}", response]
        assert codes == [200] * 10 + [429], codes
        evidence += ["Authenticated HTTP sequence: " + json.dumps(codes)]
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        evidence += [f"Isolated CP3 process stopped: pid={server.pid}, exit_code={server.returncode}"]
        destination = ROOT / "reports/evidence/cp3-curl.txt"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("\n".join(evidence) + "\n", encoding="utf-8")
    print("CP3 PASS: 401, 10 x 200, 429; process stopped; reports/evidence/cp3-curl.txt")


if __name__ == "__main__":
    main()
