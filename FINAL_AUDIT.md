# Final audit Day14

Ngày kiểm tra: 26/11/2026, GMT+7. Căn cứ chính là [RUBRIC.md](RUBRIC.md), [SUBMISSION.md](SUBMISSION.md), [CHECKPOINTS.md](CHECKPOINTS.md) và các ghi chú K5 trong [README.md](README.md). Khi mẫu cũ khác hướng dẫn K5, dùng hướng dẫn K5. Ví dụ code CP5 nằm trong `06-lab-complete/`, CP3 lấy JWT ở `/auth/token`, Cloud Run chỉ cần đọc pipeline.

## Trạng thái checkpoint

| CP | Kết quả audit | Bằng chứng |
|---|---|---|
| CP0 | Đúng tên repo, nhánh làm việc `thangdktd`, repo GitHub Public; WSL2 và Docker có sẵn | Git metadata, GitHub API; CP3 runtime `posix` |
| CP1 | Có 5 anti-pattern, output develop, bảng so sánh và giải thích shutdown | [Mission Part 1](MISSION_ANSWERS.md#part-1-localhost-vs-production-cp1) |
| CP2 | Có 4 câu Dockerfile, kích thước image, tỷ lệ giảm, sơ đồ stack và Nginx 200 | [Mission Part 2](MISSION_ANSWERS.md#part-2-docker--containerization-cp2) |
| CP3 | Đã bổ sung curl thực tế 401/200/429 trong WSL2, không lưu token; process riêng đã dừng | [Output gốc](reports/evidence/cp3-curl.txt) |
| CP4 | Redis giữ history qua 3 instance, phân biệt health/readiness, giải thích SIGTERM | [Mission Part 5](MISSION_ANSWERS.md#part-5-scaling--reliability-cp4) |
| CP5 | Giữ kết quả full grader trước: PASS 12/12, 41/41 checks; runtime source không đổi từ `4617c63` | [Provenance CP5](reports/evidence/cp5-provenance.json), checklist trong Mission |
| CP6 | Render còn chạy; kiểm lại health 200, ready 200, ask thiếu key 401; ảnh kiểm thử có key 200 còn hợp lệ | [Deployment](DEPLOYMENT.md), [HTTP mới](reports/evidence/cloud-endpoints.json), [ảnh test](screenshots/test.png) |
| CP7 | Đủ 10 JSON; load concurrency 1/10/50/100 và 3 slow rates; v2_fixed 23/23, 0 regression, gate 100% PASS | [Benchmark report](BENCHMARK_REPORT.md), [JSON fixed](reports/eval_v2_fixed.json) |
| CP8 | Đủ CSV scale 1/3, bốn ảnh trực tiếp kiểm tra, trace/log khớp, hai SLO alerts cùng FIRING, bổ sung C/D/E | [Report](BENCHMARK_REPORT.md#4-observability-stack-production), [review ảnh](reports/evidence/screenshot-review.json) |

## Những phần bổ sung trong phiên này

- Giữ nguyên AI log và nội dung hợp lệ của các phiên trước; ghi thêm AI log Codex, không tự gán công việc của Codex cho Copilot hoặc Antigravity.
- Thêm bằng chứng curl CP3 và script kiểm thử riêng, tự dừng process trong `finally`. Không đụng cổng CP8 hoặc cloud.
- Hoàn thiện bốn câu Dockerfile, sơ đồ stack, giải thích graceful shutdown, pipeline Cloud Run và câu trả lời metrics/Grafana.
- Bổ sung Histogram Exercise 7.1 cùng kiểm thử HTTP. Không đổi thuật toán benchmark/eval hoặc golden dataset; không chạy lại các lượt CP7 chính thức.
- Lưu nguyên JSON trace và các dòng log liên quan từ container trước khi recreate; đối chiếu ID, span, status và duration.
- Phát hiện ảnh alert cũ là INACTIVE. Học viên trực tiếp chụp lại hai alert FIRING. Giữ ảnh cũ ở `screenshots/original/`; không chỉnh ảnh để tạo bằng chứng.
- Hoàn thành thêm thí nghiệm C/D/E, đo thời điểm quan sát alert, phân biệt cost mock với tiền cloud thật. Khôi phục cấu hình mặc định.
- Sao chép đủ 8 CSV gốc vào `benchmark-results/`; giữ nguyên số liệu và phân biệt aggregate với `/ask`.
- Thêm `utils/final_audit.py` để kiểm tra artifacts và đối chiếu báo cáo, không thay grader chính thức. Thêm `.venv-wsl/` vào `.gitignore`.

## Tự đánh giá theo từng tiêu chí

Đây là **điểm dự kiến để Lab Coach xác nhận**, không phải điểm chính thức. Full grader chỉ xác nhận 12 tiêu chí kỹ thuật của CP5, không tự cấp điểm toàn bài. Dấu "grader" dưới đây chỉ phạm vi bằng chứng kỹ thuật; deployment thật và các câu trả lời vẫn cần người chấm kiểm tra.

| Phần / tiêu chí | Tối đa | Dự kiến | Căn cứ xác nhận |
|---|---:|---:|---|
| Part 1, Exercise 1.1, 5 anti-pattern | 2 | 2 | Mission, đối chiếu source; Lab Coach |
| Part 1, Exercise 1.2, chạy develop | 2 | 2 | Output đã ghi trong Mission; Lab Coach |
| Part 1, Exercise 1.3, bảng so sánh | 4 | 4 | Mission; Lab Coach |
| Part 2, Exercise 2.1, Dockerfile | 2 | 2 | Câu trả lời theo Dockerfile thực tế; Lab Coach |
| Part 2, Exercise 2.2, build/run container | 2 | 2 | Image và output CP2 đã ghi; Lab Coach |
| Part 2, Exercise 2.3, multi-stage | 2 | 2 | 1.67 GB so với 240 MB, giảm 85.63%; Lab Coach |
| Part 2, Exercise 2.4, Compose | 2 | 2 | Sơ đồ Nginx/agent/Redis/Qdrant và HTTP 200; Lab Coach |
| Part 3, deploy nền tảng chính | 4 | 4 | Render, 4 mã HTTP trong ảnh; Lab Coach |
| Part 3, so sánh nền tảng còn lại | 3 | 3 | TOML/YAML trong Mission; Lab Coach |
| Part 3, Cloud Run pipeline | 1 | 1 | Test, build, push, deploy, service.yaml; Lab Coach |
| Part 4, API key | 2 | 2 | Giải thích và kết quả CP5/cloud; Lab Coach |
| Part 4, JWT | 2 | 2 | CP3 curl 401/200, đúng endpoint; Lab Coach |
| Part 4, rate limiting | 2 | 2 | Request 11 trả 429, Retry-After; Lab Coach |
| Part 4, cost guard | 2 | 2 | Giải thích CP3/CP5, Redis CP5; Lab Coach |
| Part 5, health/readiness | 2 | 2 | Health 200, ready 503 khi Redis dừng; Lab Coach |
| Part 5, graceful shutdown | 2 | 2 | Giải thích source CP4 và runtime CP5; Lab Coach |
| Part 5, stateless | 2 | 2 | Redis giữ 10 messages qua 3 instance; Lab Coach |
| Part 5, load balance | 1 | 1 | Ba instance IDs trong Mission; Lab Coach |
| Part 5, test stateless | 1 | 1 | Output test_stateless đã ghi; Lab Coach |
| Part 6, POST /ask hoạt động | 10 | 10 | Full grader CP5 PASS + cloud screenshot; Lab Coach |
| Part 6, xử lý lỗi | 5 | 5 | Full grader CP5; Lab Coach |
| Part 6, Dockerfile multi-stage | 4 | 4 | Full grader CP5; Lab Coach |
| Part 6, image < 500 MB | 2 | 2 | Grader ghi 238 MB; Lab Coach |
| Part 6, Compose agent + Redis | 2 | 2 | Full grader CP5; Lab Coach |
| Part 6, config từ env | 2 | 2 | Full grader CP5; Lab Coach |
| Part 6, API key | 4 | 4 | Full grader CP5; Lab Coach |
| Part 6, rate limit Redis | 4 | 4 | Full grader CP5; Lab Coach |
| Part 6, cost guard 402 | 4 | 4 | Full grader CP5; Lab Coach |
| Part 6, không hardcode secret thật | 3 | 3 | Source/config review + scan; Lab Coach |
| Part 6, health | 2 | 2 | Full grader CP5, cloud 200; Lab Coach |
| Part 6, readiness khi mất Redis | 2 | 2 | Full grader CP5; Lab Coach |
| Part 6, SIGTERM an toàn | 3 | 3 | Full grader CP5, docker stop 0.8 s/exit 0; Lab Coach |
| Part 6, stateless Redis | 3 | 3 | Full grader CP5; Lab Coach |
| Part 6, public URL | 5 | 5 | Render đang chạy, screenshot và HTTP; Lab Coach |
| Part 6, config nền tảng | 3 | 3 | railway.toml hợp lệ, Render deploy Docker; Lab Coach |
| Part 6, env trên nền tảng | 2 | 2 | Service có API auth và Redis ready; không xuất secret; Lab Coach |
| Part 7, load test & SLO | 4 | 4 | 7 load JSON, bảng và phân tích; Lab Coach |
| Part 7, eval & gate | 5 | 5 | 3 eval JSON, v2_fixed 23/23, no regression; Lab Coach |
| Part 7, observability stack | 4 | 4 | Grafana có lịch sử tải, API snapshot và 4 câu Exercise 7.4; Lab Coach |
| Part 7, tracing | 3 | 3 | Trace chậm/lỗi, span ms và JSON log khớp; Lab Coach |
| Part 7, alerts & chaos | 4 | 4 | Ảnh hai alert FIRING, poll timestamps, A–E; Lab Coach |
| **Tổng thô** | **120** | **120** | **Dự kiến 100/100 sau quy đổi, chưa phải điểm chính thức** |

Lưu ý chấm: Grafana chụp lúc traffic tức thời đã về 0; ảnh vẫn có lịch sử tải, hai instance và p95. Snapshot Prometheus bổ sung lưu p95/avg và traffic theo instance sau lượt tạo tải. Lab Coach quyết định mức đầy đủ của bằng chứng theo rubric. Không biến số liệu này thành một benchmark khác.

## Kiểm tra artifacts và an toàn Git

Chạy từ gốc repo:

```powershell
python utils/final_audit.py --self-test
git diff --check
git diff --stat
git diff --cached --check
```

[Kết quả kiểm tra máy](reports/evidence/final-validation.json) ghi JSON/CSV, dimensions/hash và định dạng ảnh thực tế, đối chiếu bảng số liệu, trace-log, alerts, links và protected files. PNG được kiểm CRC/decompress; JPEG được decode bằng Pillow có sẵn trên máy audit. Hai ảnh `dashboard.png` và `running.png` thực chất là JPEG, giữ nguyên bytes và tên theo hồ sơ học viên. Năm ảnh còn lại là PNG. Không đổi nội dung ảnh để sửa đuôi file. Chạy script audit trên máy khác cần Pillow để kiểm hai ảnh JPEG này.

Tất cả 10 CP7 JSON và 8 CSV nộp bài khớp bản gốc. Hai file grader và golden dataset khớp blob của `origin/main`, sau xử lý line endings chuẩn của Git. Code runtime CP5 khớp commit `4617c63`.

Không commit `.env`, JWT, GitHub token, API key cá nhân hay Redis credentials. Các giá trị demo có sẵn trong đề không được coi là credentials triển khai. Kiểm tra cả candidates và lịch sử Git; scan pattern không thay thế kiểm tra thủ công các diff mới. Không thêm cache, virtualenv hoặc file tạm. [Provenance CP5](reports/evidence/cp5-provenance.json) không chứa secret.

## Checklist deliverables

- [x] `MISSION_ANSWERS.md`: Part 1–5, grader checklist và AI logs.
- [x] `DEPLOYMENT.md`: URL, commands, env names, ảnh và giới hạn lần kiểm lại.
- [x] `BENCHMARK_REPORT.md`: đủ sáu mục template, SLO, load, eval, observability, scaling, kết luận.
- [x] `reports/`: 10 JSON bắt buộc, giữ nguyên số liệu; `reports/evidence/` chứa raw evidence bổ sung.
- [x] `benchmark-results/`: 8 CSV scale 1/3; cùng dữ liệu ở production path.
- [x] `screenshots/`: 3 ảnh deployment và 4 ảnh CP8 đã xem trực tiếp; ảnh INACTIVE lưu riêng.
- [x] Source CP5 trong `06-lab-complete/`, `.env.example`, Docker/Compose và railway config.
- [x] Sửa KB đúng file develop; bổ sung question-length Histogram. Không sửa dataset hoặc grader.
- [x] Script audit và collectors trong `utils/`, ghi mục đích và phạm vi rõ ràng.
- [x] Đủ bằng chứng nghiệm thu để chuyển sang commit/push/PR; stack CP8 đã dừng và có receipt.

## Docker và bàn giao Git

Agent đã khôi phục `MOCK_ERROR_RATE=0.01`, `MOCK_SLOW_RATE=0.03`, `AGENT_VERSION=v2`, `LLM_MODEL=mock-llm-small`; [receipt](reports/evidence/chaos-cde.json). Sau khi bằng chứng đã lưu và audit PASS, đã chạy đúng `docker compose -p k5-day14-observability -f 06-lab-complete/benchmark-observability/production/docker-compose.yml down`, không thêm `-v`, không prune. [Receipt dừng Docker](reports/evidence/docker-shutdown.json) xác nhận exit 0 lúc 22:44:50 GMT+7, không còn container CP8, giữ cả 2 volume và tập container ngoài project không đổi. Cloud Render được giữ để chấm bài.

Commit cuối, URL Pull Request, kết quả CI/merge và trạng thái `main` được đối chiếu với GitHub sau khi tạo commit, và trả trong báo cáo cuối phiên. Không ghi trước một commit hash hoặc trạng thái merge chưa xảy ra vào artifact này.

Việc còn lại của học viên sau bàn giao là nộp link repository lên LMS trước deadline và giữ cloud chạy tới khi được chấm. Theo lịch chung, deadline là 23:59 GMT+7 ngày 26/11/2026, trừ thông báo khác của Lab Coach. Không tự sửa ngày commit.
