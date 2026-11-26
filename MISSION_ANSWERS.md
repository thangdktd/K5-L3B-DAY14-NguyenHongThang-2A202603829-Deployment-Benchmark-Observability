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
| Shutdown | Không có cleanup trong lifecycle | `lifespan` thực hiện cleanup khi dừng | Uvicorn ngừng nhận request mới, đợi request đang chạy rồi giải phóng kết nối. |

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

### Exercise 2.1: Bốn câu hỏi Dockerfile

1. Base image thực tế trong `02-docker/develop/Dockerfile` là `python:3.11`, gồm hệ điều hành và Python runtime. Không nhầm với base slim của bản production.
2. `WORKDIR /app` đặt thư mục mặc định cho các lệnh tiếp theo và tiến trình trong container.
3. Copy requirements trước source để Docker tái sử dụng layer cài dependencies khi chỉ đổi code.
4. `CMD` cung cấp lệnh hoặc tham số mặc định, bị thay bởi command sau tên image trong `docker run`. `ENTRYPOINT` xác định executable; command bổ sung thường trở thành tham số. Vẫn có thể thay executable bằng `--entrypoint`.

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

```mermaid
flowchart LR
    Client -->|80/443| Nginx
    Nginx -->|8000| Agent
    Agent -->|6379| Redis
    Agent -->|6333| Qdrant
```

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

## Part 3: Cloud Deployment (CP6)

- **Public URL:** `https://k5-l3b-day14-nguyenhongthang-2a202603829.onrender.com`
- **Kiểm thử:** `/health` → `200`, `/ready` → `200`, `POST /ask` (không key) → `401`.
- **So sánh `railway.toml` vs `render.yaml`:** `railway.toml` dùng định dạng TOML ngắn gọn tập trung vào `builder` (`DOCKERFILE`), `healthcheckPath` và `restartPolicyType` cho từng service; trong khi `render.yaml` dùng YAML dạng Infrastructure-as-Code cho phép khai báo nhiều service cùng lúc (Web Service + Redis) kèm `envVars`, `plan` và `healthCheckPath`.
- **Pipeline GCP Cloud Run (`03-cloud-deployment/production-cloud-run/`):**
  1. Bước `test` cài dependencies và chạy `pytest tests/`.
  2. Bước `build` chờ test, build image gắn `$COMMIT_SHA` và `latest`, dùng cache layer.
  3. Bước `push` đẩy image vào `gcr.io/$PROJECT_ID/ai-agent`.
  4. Bước `deploy` chạy `gcloud run deploy` ở `asia-southeast1`, dùng Secret Manager và giới hạn 1–10 instances.
  5. `service.yaml` mô tả Knative service, CPU/RAM, concurrency 80, secret và probe `/health`, `/ready`. Chỉ đọc pipeline, không tạo tài nguyên GCP.

---

## Part 4: API Security (CP3)

- Bản develop đọc API key từ `AGENT_API_KEY` và yêu cầu header `X-API-Key`. Thiếu key trả `401`. Bản develop có giá trị mặc định dành cho demo, nên production phải đặt key qua biến môi trường.
- Bản production cấp JWT qua `POST /auth/token`. Token dùng HS256 và hết hạn sau 60 phút. `/ask` yêu cầu bearer token. Thiếu hoặc hết hạn token trả `401`; token không hợp lệ trả `403`.
- Rate limiter cho phép user 10 request/phút và admin 100 request/phút. Khi vượt giới hạn, API trả `429`. Bộ đếm nằm trong RAM, nên không chia sẻ giữa nhiều worker và mất khi tiến trình khởi động lại.
- Cost guard giới hạn $1/ngày cho mỗi user và $10/ngày toàn hệ thống. Vượt giới hạn user trả `402`; vượt giới hạn toàn hệ thống trả `503`.
- `JWT_SECRET` có giá trị mặc định chỉ dành cho demo. Production phải đặt một secret riêng qua biến môi trường.

**Bằng chứng runtime đã bổ sung:** [Output curl gốc](reports/evidence/cp3-curl.txt), chạy trong WSL2 Ubuntu với Python 3.14.4, `os.name=posix`, trên cổng loopback riêng `59561`. Dùng đúng `POST /auth/token` và tài khoản demo của source; JWT và secret chỉ nằm trong bộ nhớ, không lưu vào bài. Request thiếu bearer trả `401`, 10 request được xác thực trả `200`, request thứ 11 trả `429` và có `Retry-After: 59`. Tiến trình riêng đã được dừng, không đổi stack CP8 hoặc cloud CP6.

```text
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
{"detail":"Authentication required. Include: Authorization: Bearer <token>"}

HTTP/1.1 200 OK
{"question":"Docker container la gi?","answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}

HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
retry-after: 59
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

Lệnh dùng `curl -i -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Docker container la gi?"}'`. Với request có xác thực, thêm `-H "Authorization: Bearer $TOKEN"`; giá trị token không in ra terminal hoặc report. File bằng chứng chứa toàn bộ response headers và chuỗi mã HTTP.

API key được kiểm tra trong dependency `verify_api_key`; rotate bằng cách cập nhật `AGENT_API_KEY` ở môi trường rồi restart service. JWT được server xác minh chữ ký và hạn dùng. Rate limit dùng sliding window theo user; admin dùng bucket 100/phút thay vì bỏ mọi giới hạn.

Cost guard kiểm ngân sách trước khi gọi LLM, tính chi phí từ input/output tokens sau khi gọi rồi cộng usage. Giới hạn request/phút không giới hạn chi phí mỗi request, nên vẫn cần budget. CP3 là bản demo RAM với ngân sách ngày; CP5 dùng Redis và `DAILY_BUDGET_USD`, theo hợp đồng K5 trong `06-lab-complete/README.md`, thay cho ví dụ tháng trong CODE_LAB.

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

### 3. Graceful shutdown (Exercise 5.2)

Uvicorn xử lý SIGTERM bằng cách ngừng nhận request mới và đợi request đang chạy hoàn tất. Lifecycle shutdown đặt readiness về false và dọn tài nguyên. Trong `05-scaling-reliability/develop/app.py`, `_in_flight_requests` theo dõi request; cleanup chờ tối đa 30 giây. Không dùng SIGKILL vì app không có cơ hội cleanup. Kết quả runtime SIGTERM và `docker stop` của agent CP5 đã có trong checklist bên dưới; không coi phần đọc source CP4 là một lượt test SIGTERM mới.

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

---

## Part 7: Benchmark (CP7)

### Metrics (Exercise 7.1)

Counter `http_requests_total` chỉ tăng khi có request; Gauge `agent_in_flight_requests` tăng/giảm theo số request đang xử lý; Histogram `http_request_duration_seconds` phân bố latency thành bucket. Đã bổ sung Histogram `agent_question_length_chars` với buckets 20, 50, 100, 200, 500, 1000, 2000 ký tự. [Kiểm thử HTTP](reports/evidence/exercise-7-1-metrics.txt) ghi nhận câu hỏi `Docker?` có count 1, sum 7. Hai URL không tồn tại dùng chung label `route="unmatched"`; không dùng URL thật hay độ dài câu hỏi làm label vì cardinality không giới hạn.

### Load test theo concurrency

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO p95 < 500 ms |
|---|---:|---:|---:|---:|---:|---|
| 1 | 3.7 | 208.7 | 248.3 | 1723.6 | 0.33% | Đạt |
| 10 | 42.4 | 213.4 | 292.8 | 446.6 | 0.33% | Đạt |
| 50 | 32.6 | 506.0 | 4686.3 | 6679.1 | 0.33% | Không đạt |
| 100 | 32.9 | 1906.1 | 5889.7 | 6903.4 | 0.67% | Không đạt |

Mỗi mức là một lượt 300 request. Không có lượt lặp hoặc profile để xác định nguyên nhân thay đổi throughput và latency.

### Tác động của MOCK_SLOW_RATE

| MOCK_SLOW_RATE | Average (ms) | p95 (ms) | p99 (ms) | SLO p95 < 500 ms |
|---|---:|---:|---:|---|
| 0 | 219.3 | 307.6 | 344.3 | Đạt |
| 0.03 | 290.2 | 437.1 | 1730.6 | Đạt |
| 0.1 | 358.8 | 1698.9 | 1726.8 | Không đạt |

p99 giảm 3.8 ms giữa hai mức 0.03 và 0.1. p95 tăng lên 1698.9 ms ở mức 0.1.

### Eval và quality gate

| Phiên bản | Accuracy | Cost (USD) | Quality gate |
|---|---:|---:|---|
| v1 | 1/23 (4.3%) | $0.000411 | Không đạt ở ngưỡng 80% |
| v2 | 21/23 (91.3%) | $0.000759 | Đạt ngưỡng 80%, chưa đạt mục tiêu 23/23 |
| v2_fixed | 23/23 (100%) | $0.000784 | Đạt ngưỡng 100% |

`eval_v2_fixed.json` đạt 23/23 sau khi bổ sung entry JWT và HPA vào knowledge base. Gate trong JSON ghi 0 regression. Mười file JSON trong `reports/` hợp lệ về cú pháp và giống các file nguồn. `run_eval.py` trả exit code `1` khi gate thất bại. Trong CI, dùng `--min-accuracy 1.0 --baseline reports/eval_v2.json` và chặn merge khi exit code khác `0`.

## Part 8: Observability (CP8)

### Stack và scaling

Compose project `k5-day14-observability` dùng file `06-lab-complete/benchmark-observability/production/docker-compose.yml`. Stack không có Redis.

| Instances | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures | Error rate |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 59.1 | 210 | 1700 | 2900 | 281 | 4.0% |
| 3 | 63.9 | 200 | 710 | 1700 | 69 | 0.9% |

Đây là hai lượt đo riêng biệt. Chưa có dữ liệu lặp để chứng minh nguyên nhân hoặc độ ổn định của mức cải thiện. Không quy kết kết quả cho Redis.

Lượt tạo tải final audit có 5242 responses trong khoảng 420 giây: 4140 HTTP 200, 1088 HTTP 503, 2 HTTP 502, 12 HTTP 504. Dữ liệu này chỉ dùng để quan sát và chụp alert, không phải benchmark scaling. [Raw observation](reports/evidence/alert-observation.json).

### Alerts

- `AgentHighErrorRate`: error rate `/ask` > 5% trong 1 phút.
- `AgentHighLatencyP95`: p95 `/ask` > 1 giây trong 2 phút.
- Cả hai alert cùng FIRING trong lượt final audit. Error alert được thấy sau 69.864 s; latency alert sau 129.062 s kể từ bắt đầu tải lúc `2026-11-26T15:24:01.939376Z`. Poll khoảng 5 s. Config fault đã có từ phiên trước nên đây không phải số đo từ lúc đổi config. `activeAt=2026-11-26T15:24:07.401817116Z` là lúc pending, không phải lúc FIRING.
- Ngưỡng alert lỏng hơn SLO trong báo cáo: error rate 5% so với SLO 2%, p95 1 giây so với SLO 500 ms.
- Đã bổ sung C/D/E: model large làm cost alert FIRING; pause một agent làm instance-down alert FIRING; v1 chỉ đạt 1/23 câu eval. Lượt E không phát sinh SLO alert mới nhưng cost alert cũ còn tồn tại do cửa sổ 5 phút. Dùng continuous eval và quality gate để phát hiện accuracy regression. [Bằng chứng C/D/E](reports/evidence/chaos-cde.json).

### Trace và log

- Trace chậm `f97793940f004263c4db7441e264b065`: 3.2 giây, HTTP 200, 4 spans. Span con dài nhất hiển thị là `agent.run` với 485 ms. Các span con không giải thích đủ thời lượng root span.
- Trace lỗi `c34cb9ba78a06c551110b3357b8eac11`: 97.9 ms, HTTP 503, 4 spans.
- Đã lưu trace JSON từ Jaeger và log JSON gốc của container, khớp cả `trace_id`, root `span_id`, request ID và HTTP status. Xem [phân tích trace và log](BENCHMARK_REPORT.md#43-debug-bằng-trace). Root trace chậm là 3183.520 ms; `agent.run` 484.962 ms bắt đầu sau root 2405.703 ms. Không quy toàn bộ độ chậm cho LLM khi khoảng chờ này chưa có span giải thích.

### Screenshots bắt buộc

Bốn ảnh dưới đây đã được mở và kiểm tra trực tiếp. Học viên tự chụp cả bốn ảnh, bao gồm chụp lại ảnh Prometheus lúc hai alert cùng FIRING trong phiên final audit:

- `screenshots/grafana-dashboard.png`
- `screenshots/jaeger-slow-trace.png`
- `screenshots/jaeger-error-trace.png`
- `screenshots/prometheus-alert-firing.png`

Ảnh Prometheus INACTIVE ban đầu được giữ ở [bản gốc](screenshots/original/prometheus-alert-inactive-user.png). Ảnh nộp chính hiện thấy cả `AgentHighErrorRate` và `AgentHighLatencyP95` FIRING. [Kết quả kiểm ảnh và SHA-256](reports/evidence/screenshot-review.json) ghi rõ nội dung từng ảnh. Traffic dùng chụp alert được tách khỏi hai lượt scaling chính thức.



