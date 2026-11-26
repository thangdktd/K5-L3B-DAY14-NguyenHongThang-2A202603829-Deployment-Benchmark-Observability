# MISSION ANSWERS — Day 14 (K5)

## Part 1: Localhost vs Production (CP1)

### 1. Ít nhất 5 anti-pattern trong `01-localhost-vs-production/develop/app.py`
1. **Hardcoded secrets** (`develop/app.py` dòng 17–18): `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`. Nếu push lên GitHub sẽ lộ ngay thông tin nhạy cảm. Trong `production/app.py` (dòng 24), cấu hình được đọc từ `settings` (environment variables).
2. **Không có config management theo môi trường** (`develop/app.py` dòng 21–22): `DEBUG = True`, `MAX_TOKENS = 500` được gán cứng. `production/app.py` dùng `settings` từ `config.py` để tách biệt cấu hình dev/staging/prod.
3. **Dùng `print()` thay cho structured logging và log lộ secret** (`develop/app.py` dòng 33–34, 38): `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` vừa khó thu thập/phân tích trong log aggregator, vừa làm rò rỉ API key ra stdout. `production/app.py` (dòng 28–32, 111–115) dùng `logging` định dạng JSON và không log secret.
4. **Thiếu health check / readiness endpoint** (`develop/app.py` dòng 42–43): Không có `/health` hay `/ready`, nên nền tảng orchestration (Docker, Kubernetes, Railway, Render) không biết khi nào container sống hoặc sẵn sàng nhận traffic. `production/app.py` có `is_ready` và quản lý vòng đời qua `lifespan` (dòng 36, 40–68).
5. **Bind `localhost`, port cố định `8000`, bật `reload=True`** (`develop/app.py` dòng 49–54): `host="localhost"` khiến container không nhận được traffic từ bên ngoài; `port=8000` không đọc biến `PORT` do cloud platform cấp; `reload=True` gây tốn tài nguyên và không an toàn trên production. `production/app.py` bind `0.0.0.0` và đọc `settings.port`.

### 2. Bảng so sánh `develop/app.py` vs `production/app.py`

| Tiêu chí | `develop/app.py` | `production/app.py` | Giải thích |
|---|---|---|---|
| Secrets & Config | Hardcode trực tiếp (`OPENAI_API_KEY`, `DATABASE_URL`) | Đọc từ `settings` (`config.py` / env vars) | Tránh lộ secret lên Git, dễ đổi cấu hình theo môi trường (12-Factor). |
| Logging | `print(...)`, có dòng in cả `OPENAI_API_KEY` | `logging` định dạng JSON (`logger.info(json.dumps(...))`) | Log JSON dễ parse bởi Datadog/Loki; tuyệt đối không log secret. |
| Lifecycle & Health | Không có `/health`, `/ready`, không có `lifespan` | Có `lifespan` + cờ `is_ready` | Giúp platform kiểm tra liveness/readiness và xử lý khởi động/tắt an toàn. |
| Network & Port | `host="localhost"`, `port=8000`, `reload=True` | `0.0.0.0`, port từ `PORT` env var | Container cần `0.0.0.0` để nhận traffic ngoài; cloud platform cấp `PORT` động. |
| CORS | Không cấu hình | `CORSMiddleware` với `settings.allowed_origins` | Kiểm soát domain được phép gọi API từ trình duyệt. |

### 3. Kết quả chạy thử `develop/app.py`
Khi gọi `ask_agent('Hello')` trong `01-localhost-vs-production/develop/app.py`:
```text
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this
[DEBUG] Response: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.
RESPONSE: {'answer': 'Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.'}
```
*(Bằng chứng thực tế cho thấy `develop/app.py` in thẳng API key ra stdout qua `print()`.)*

---

## Part 2: Docker & Containerization (CP2)

### 1. Kích thước image đo thực tế (`docker images my-agent`)
- `my-agent:develop`: **1.67GB** (content size: 426MB)
- `my-agent:advanced`: **240MB** (content size: 57.4MB)
- **Tỷ lệ giảm kích thước:** `(1 - 240 / 1670) × 100% ≈ 85.63%`

### 2. Giải thích tối ưu Dockerfile
- **Multi-stage build**: Tách stage `builder` (chứa `gcc`, `libpq-dev`, công cụ build) khỏi stage `runtime` (`python:3.11-slim` sạch, chỉ copy `.local` packages đã cài), giúp giảm mạnh dung lượng và bề mặt tấn công.
- **Thứ tự layer (`COPY requirements.txt` trước `COPY . .`)**: Docker cache layer `pip install -r requirements.txt`; khi chỉ sửa code Python mà không đổi `requirements.txt`, Docker tái sử dụng cache thay vì cài lại toàn bộ dependencies.

### 3. Sơ đồ các service trong stack (`02-docker/production/docker-compose.yml`)
- `nginx` (`nginx:alpine`, cổng `80`/`443`) → reverse proxy chuyển tiếp request tới `agent:8000`
- `agent` (`k5-day14-docker-agent`, cổng nội bộ `8000`) → kết nối `redis:6379` và `qdrant:6333`
- `redis` (`redis:7-alpine`, `6379/tcp`)
- `qdrant` (`qdrant/qdrant:v1.9.0`, `6333-6334/tcp`)

### 4. Kết quả kiểm thử qua Nginx (`curl -sS -i http://localhost/health`)
```text
HTTP/1.1 200 OK
Server: nginx
Content-Type: application/json
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"status":"ok","uptime_seconds":0.9,"version":"2.0.0","timestamp":"2026-11-26T08:07:05.780932"}
```

---

## Part 5: Scaling & Reliability (CP4)

### 1. Kết quả chạy 3 instances & `test_stateless.py`
- Chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3`.
- 5 requests trong cùng `Session ID: c43af69f-89c6-44ea-97aa-89df6a1b4bb9` được Nginx load-balance qua cả 3 instances: `{'instance-190be8', 'instance-b4094a', 'instance-3dff39'}`.
- Kết quả: `Total messages: 10`, `✅ Session history preserved across all instances via Redis!`.

### 2. Liveness (`/health`) vs Readiness (`/ready`)
- Khi Redis hoạt động: `/health` → `200`, `/ready` → `200`.
- Khi Redis dừng (`docker compose -p k5-day14-scaling stop redis`): `/health` → `200`, `/ready` → `503`.
- **Giải thích:** `/health` (liveness) chỉ kiểm tra tiến trình app còn sống hay không; nếu `/health` trả lỗi, orchestrator sẽ restart container một cách vô ích khi lỗi nằm ở Redis. `/ready` (readiness) kiểm tra các dependency (Redis) có sẵn sàng nhận traffic hay không để load balancer tạm ngưng chuyển request tới instance đó.
- **Stateless:** Nếu lưu session trong RAM của từng instance, khi Nginx chuyển request tiếp theo sang instance khác sẽ bị mất lịch sử hội thoại; lưu tập trung ở Redis giúp mọi instance chia sẻ cùng một state.

---

## Part 6: Final Project — `06-lab-complete/` (CP5)

Chạy `python check_production_ready.py` trong WSL2 Ubuntu (`os.name=posix`):

```text
📋 Checklist Deliverable
   ✅ Dockerfile (multi-stage, < 500 MB)
   ✅ docker-compose.yml (agent + redis)
   ✅ .dockerignore
   ✅ Health check endpoint (GET /health)
   ✅ Readiness endpoint (GET /ready)
   ✅ API Key authentication
   ✅ Rate limiting
   ✅ Cost guard
   ✅ Config từ environment variables
   ✅ Structured logging
   ✅ Graceful shutdown
   ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
Result: 12/12 tiêu chí đạt · 41/41 checks passed
🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

- Kích thước Docker image production: **238 MB** (< 500 MB).
- `docker stop`: exit code `0`, `0.8s`.
- Structured logging: `28` dòng JSON hợp lệ.

---

## AI Log
- **CP0–CP1**: Dùng AI hỗ trợ kiểm tra môi trường WSL2/Docker, hướng dẫn cài WSL2 Ubuntu lên ổ D, tạo nhánh `thangdktd`, và đối chiếu các anti-pattern giữa `01-localhost-vs-production/develop/app.py` và `production/app.py`. Mọi file code và kết quả lệnh đều được kiểm chứng trực tiếp trên máy.
- **CP2 & CP4**: Dùng AI hỗ trợ chạy build Docker (`my-agent:develop` 1.67GB, `my-agent:advanced` 240MB, giảm 85.63%), kiểm thử Nginx và stack 3 instances (`test_stateless.py`, `/health` 200, `/ready` 503 khi Redis dừng).
- **CP5 (`06-lab-complete/`)**: Dùng AI hỗ trợ triển khai các module `app/config.py`, `app/auth.py`, `app/redis_client.py`, `app/rate_limiter.py`, `app/cost_guard.py`, `app/main.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml`; tự kiểm chứng toàn bộ bằng `check_production_ready.py` đạt **PASS 12/12 (41/41 checks passed)**.
