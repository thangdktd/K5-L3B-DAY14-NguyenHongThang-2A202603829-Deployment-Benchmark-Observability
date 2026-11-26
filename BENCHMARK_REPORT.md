# Benchmark & Observability Report — Day 14

**Họ tên:** Nguyễn Hồng Thắng
**MSSV:** 2A202603829
**Ngày chạy:** 2026-11-26
**Môi trường:** Windows 11, WSL2 Ubuntu, Docker Desktop 29.9.3, 4 CPU / 8 GB RAM (local); Python 3.11, FastAPI và mock LLM. CP8 dùng Nginx, agent, Prometheus, Grafana, Jaeger và Locust. Compose CP8 không có Redis.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Đảm bảo 95% user thấy phản hồi < 0.5s — ngưỡng UX chấp nhận được |
| Error rate `/ask` | < 2% | Theo dõi response khác 200; CP8 trả 503 khi mock upstream lỗi. Rate limit 429 và cost guard 402 thuộc agent CP5, không phải cơ chế của stack CP8. |
| Accuracy trên golden dataset | ≥ 80% | Quality gate: agent phải trả lời đúng ít nhất 80% câu hỏi trong dataset |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3.7 | 208.7 | 248.3 | 1723.6 | 0.33% | ✅ PASS |
| 10 | 42.4 | 213.4 | 292.8 | 446.6 | 0.33% | ✅ PASS |
| 50 | 32.6 | 506.0 | 4686.3 | 6679.1 | 0.33% | ❌ FAIL |
| 100 | 32.9 | 1906.1 | 5889.7 | 6903.4 | 0.67% | ❌ FAIL |

**Nhận xét:** RPS tăng từ 3.7 ở concurrency 1 lên 42.4 ở concurrency 10. Ở concurrency 50 và 100, RPS giảm xuống khoảng 32.9, còn p95 tăng lên 4686.3 ms và 5889.7 ms. Mỗi JSON ghi nhận một lượt 300 request. Không có lượt lặp hoặc profile để xác định nguyên nhân, nên không thể kết luận đây là nghẽn event loop hay mock LLM.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) | SLO |
|---|---|---|---|---|
| 0 | 219.3 | 307.6 | 344.3 | ✅ PASS |
| 0.03 (mặc định) | 290.2 | 437.1 | 1730.6 | ✅ PASS |
| 0.1 | 358.8 | 1698.9 | 1726.8 | ❌ FAIL |

**Nhận xét:** Khi `MOCK_SLOW_RATE` tăng từ 0.03 lên 0.1, average tăng 68.6 ms, còn p99 giảm 3.8 ms, gần như không đổi. p95 tăng từ 437.1 ms lên 1698.9 ms, vượt SLO 500 ms. Average không cho thấy rõ nhóm request chậm, nên cần theo dõi p95 và p99.

Mỗi mức là một lượt 300 request. Không có lượt lặp để đo độ dao động, nên không xem mức giảm p99 3.8 ms là cải thiện có ý nghĩa.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.6 | 109.0 | 112.9 |
| Tổng cost (USD) | $0.000411 | $0.000759 | $0.000784 |
| Cost / câu đúng (USD) | $0.000411 | $0.0000362 | $0.0000341 |
| Quality gate trong JSON | ❌ FAIL ở 80% | ✅ PASS ở 80% | ✅ PASS ở 100% |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 | `token`, `hết hạn`, `chữ ký` | Thêm entry `["jwt", "xác thực"]` mô tả claims, chữ ký, thời gian hết hạn và khác biệt với API key tĩnh |
| scaling-03 | `cpu`, `memory`, `custom metrics` | Thêm entry `["hpa", "kubernetes"]` mô tả HPA scale pod theo CPU, memory hoặc custom metrics |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

- **v1**: accuracy 4.3%, cost $0.000411, p50 159.5 ms. Gate 80% không đạt.
- **v2**: accuracy 91.3%, cost $0.000759, p50 186.6 ms. Gate 80% đạt, nhưng chưa đạt mục tiêu bài tập 23/23.
- **v2_fixed**: accuracy 100%, cost $0.000784, p50 199.3 ms. Gate 100% đạt, không có regression so với baseline trong JSON.
- v2_fixed tốn thêm 3.3% tổng cost so với v2, nhưng cost trên mỗi câu đúng giảm từ $0.0000362 xuống $0.0000341. Cả hai bản v2 tốn tổng cost cao hơn v1 vì trả lời đúng nhiều câu hơn.

`run_eval.py` trả exit code `1` khi quality gate thất bại. Trong CI, dùng `--min-accuracy 1.0 --baseline reports/eval_v2.json` và chặn merge khi exit code khác `0`.

---

## 4. Observability stack (production)

### 4.1 Screenshot

Học viên trực tiếp chụp cả bốn ảnh; Codex mở từng file và đối chiếu API telemetry. Không chỉnh sửa nội dung ảnh.

- [x] [Grafana](screenshots/grafana-dashboard.png): dashboard `Day 14 — AI Agent Overview`, Traffic, Error rate, Latency p95 và Instances up. Tại lúc chụp: traffic 0.0 req/s, error 0.00%, p95 1.90 s, 2 instances; đồ thị có lịch sử tải. Không dùng giá trị tức thời này làm benchmark scaling.
- [x] [Trace chậm](screenshots/jaeger-slow-trace.png): ID `f97793940f004263c4db7441e264b065`, 3.2 s, HTTP 200, 4 spans, `agent.run` 485 ms.
- [x] [Trace lỗi](screenshots/jaeger-error-trace.png): ID `c34cb9ba78a06c551110b3357b8eac11`, 97.9 ms, HTTP 503, 4 spans và dấu lỗi. Event `exception` được xác nhận trong JSON trace gốc.
- [x] [Prometheus](screenshots/prometheus-alert-firing.png): `AgentHighErrorRate` và `AgentHighLatencyP95` cùng FIRING. Học viên chụp lại lúc 22:29 ngày 26/11/2026, sau khi Codex phát hiện ảnh cũ là INACTIVE. [Ảnh cũ](screenshots/original/prometheus-alert-inactive-user.png) được giữ nguyên để đối chiếu.

> Stack CP8 chạy local: Nginx chuyển request tới hai agent; Prometheus scrape và evaluate mỗi 5 giây; Grafana provision dashboard `Day 14 — AI Agent Overview`; Jaeger nhận OTLP ở cổng 4318. Compose CP8 không có Redis. [Biên bản kiểm ảnh, SHA-256](reports/evidence/screenshot-review.json).

**Trả lời Exercise 7.4:** [Snapshot Prometheus](reports/evidence/golden-signals-snapshot.json) lúc `2026-11-26T15:31:29Z`, tức khoảng 22:31:29 GMT+7, cho thấy p95 1.904 s và average 0.622 s. p95 lớn gấp khoảng 3.06 average, phù hợp lượt cố ý tạo tail latency. RPS theo instance là 4.654 và 4.634, chia gần đều trong cửa sổ này; không suy rộng ra mọi thời điểm. Input tokens/s 532.685 cao hơn output 295.936 vì prompt có system prompt và context retrieval. `GET http://localhost:8080/metrics` trả 404 do Nginx chặn đúng location này; Prometheus scrape trực tiếp agent trong mạng nội bộ để tránh public metrics.

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert hoặc cách phát hiện | Thời gian quan sát | Panel phản ánh |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` FIRING, error rate `/ask` > 5% liên tục 1 phút | 69.864 s từ lúc bắt đầu tải final audit; config fault đã có từ trước | Error rate |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` FIRING, p95 `/ask` > 1 s liên tục 2 phút | 129.062 s từ lúc bắt đầu tải, cùng lượt A | Latency p95 |
| C | `LLM_MODEL=mock-llm-large`, lỗi/chậm trả mặc định | `LLMCostBurnRateHigh` FIRING, tốc độ cost > $2/giờ | 155.493 s từ lệnh đổi config, 132.946 s từ bắt đầu tải C | LLM cost / cost burn rate |
| D | `docker pause` một agent trong 75 s rồi unpause | `AgentInstanceDown` FIRING, `up == 0` ít nhất 30 s | 46.521 s từ lúc bắt đầu thao tác pause; có scrape/evaluation delay | Instances up |
| E | `AGENT_VERSION=v1`, `MOCK_ERROR_RATE=0`, `MOCK_SLOW_RATE=0` | Eval trên 23 câu gốc chỉ đúng 1/23 (4.35%); gate 100% phải fail | Eval sau khi recreate v1; không sửa golden dataset | Continuous eval / accuracy, không phải Golden Signals |

Lượt final audit dùng cấu hình fault đã tồn tại `MOCK_ERROR_RATE=0.2`, `MOCK_SLOW_RATE=0.3`; không coi đây là hai thử nghiệm độc lập. Script [collect_observability_evidence.py](utils/collect_observability_evidence.py) tạo tải 12 workers trong 420 giây, từ `15:24:01.939376Z` đến `15:31:03.239786Z`, và poll trạng thái alert mỗi khoảng 5 giây. [Dữ liệu quan sát](reports/evidence/alert-observation.json) ghi 5242 responses: 4140 HTTP 200, 1088 HTTP 503, 2 HTTP 502 và 12 HTTP 504. Lượt này chỉ phục vụ telemetry và screenshot, không ghi đè CSV scaling.

`AgentHighErrorRate` được quan sát FIRING lần đầu lúc `15:25:11.803738Z`, sau 69.864 giây kể từ lúc bắt đầu tải. `AgentHighLatencyP95` FIRING lần đầu lúc `15:26:11.001223Z`, sau 129.062 giây. Cả hai có `activeAt=2026-11-26T15:24:07.401817116Z`; `activeAt` là lúc điều kiện bắt đầu pending, không phải lúc FIRING. Sai số quan sát khoảng một chu kỳ poll cộng thời gian API. Không có timestamp thay đổi fault config từ phiên trước nên không báo một số đo giả từ lúc đổi cấu hình.

Alert lỗi dùng ngưỡng 5%, còn SLO trong báo cáo là 2%. Alert latency dùng ngưỡng 1 giây, còn SLO là 500 ms. Vì vậy, alert có thể chưa firing dù dịch vụ đã vi phạm SLO.

[Thí nghiệm C](reports/evidence/chaos-c-observation.json) có 6335 responses: 6263 HTTP 200, 71 HTTP 503, 1 HTTP 502; chỉ tạo telemetry, không phải scaling benchmark. Snapshot cuối C ghi burn rate khoảng $41.99/giờ theo bảng giá mock, không phải hóa đơn cloud hay tiền thực tế. [Dữ liệu C/D/E và khôi phục cấu hình](reports/evidence/chaos-cde.json) lưu toàn bộ cấu hình không nhạy cảm, các lần poll và kết quả từng câu eval E. Lượt E không có error/latency/instance-down alert trong snapshot cuối, nhưng cost alert cũ của C còn FIRING do cửa sổ 5 phút. Không gọi đó là "mọi alert đều tắt" và không quy cost alert cũ cho accuracy regression. Các thí nghiệm này nối tiếp trong một Prometheus, không phải phép so sánh cô lập.

Đã khôi phục agent v2, model small, `MOCK_ERROR_RATE=0.01`, `MOCK_SLOW_RATE=0.03` lúc `2026-11-26T15:38:00.146034Z`. Việc dừng stack và giữ volume được ghi tại [Final audit](FINAL_AUDIT.md).

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Đây là **accuracy regression**, không thể phát hiện bằng metrics hạ tầng khi latency và error rate vẫn ổn. Cách xử lý:
1. **Continuous eval**: Chạy eval pipeline định kỳ (mỗi deploy) so sánh accuracy với baseline threshold.
2. **Shadow eval metric**: Expose một gauge `accuracy_score` từ định kỳ chạy eval subset, alert khi dưới 80%.
3. **User feedback loop**: Thu thập thumbs up/down từ user, alert khi negative rate cao.
4. **A/B comparison**: So sánh session có cùng câu hỏi giữa v1 và v2 để phát hiện regression.

### 4.3 Debug bằng trace

Hai trace trong ảnh đã được xuất trực tiếp từ Jaeger API và ghép với log thực tế từ `docker logs` trước khi recreate container:

| Trace | HTTP | Root span (ms) | `agent.run` (ms) | Retrieval (ms) | Chat LLM (ms) |
|---|---:|---:|---:|---:|---:|
| `f97793940f004263c4db7441e264b065` | 200 | 3183.520 | 484.962 | 84.897 | 399.487 |
| `c34cb9ba78a06c551110b3357b8eac11` | 503 | 97.943 | 93.148 | 21.163 | 70.564 |

Ở trace chậm, root `POST /ask` dài nhất tổng thể. Span con dài nhất là `agent.run`, chiếm 15.23% root; trong đó chat LLM chiếm 399.487 ms, khoảng 82.38% thời gian `agent.run`. `agent.run` bắt đầu ở offset 2405.703 ms. Khoảng 2.406 s trước đó chưa có child span giải thích, nên chưa thể kết luận LLM, CPU hay event loop là nguyên nhân của toàn bộ 3.184 s. Cần thêm span quanh queue/auth/middleware và profiling cho lần điều tra tiếp theo.

Log HTTP chậm, giữ nguyên JSON từ container:

```json
{"ts": "2026-11-26T12:22:40.058144+00:00", "level": "INFO", "service": "observable-agent", "instance": "2b4cc69f5521", "event": "http_request", "trace_id": "f97793940f004263c4db7441e264b065", "span_id": "53b9cccaf3aace1c", "request_id": "7df175a01a65", "method": "POST", "route": "/ask", "status": 200, "ms": 3096.5}
```

Log upstream lỗi và HTTP tương ứng:

```json
{"ts": "2026-11-26T12:21:39.514405+00:00", "level": "INFO", "service": "observable-agent", "instance": "9c3ea5064c37", "event": "llm_error", "trace_id": "c34cb9ba78a06c551110b3357b8eac11", "span_id": "43ed2a0bbce21b3e", "request_id": "a3b38f93fa29", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
{"ts": "2026-11-26T12:21:39.515219+00:00", "level": "INFO", "service": "observable-agent", "instance": "9c3ea5064c37", "event": "http_request", "trace_id": "c34cb9ba78a06c551110b3357b8eac11", "span_id": "43ed2a0bbce21b3e", "request_id": "a3b38f93fa29", "method": "POST", "route": "/ask", "status": 503, "ms": 96.5}
```

Log middleware đo 3096.5/96.5 ms, còn root trace đo 3183.520/97.943 ms vì hai timer nằm ở các lớp instrumentation khác nhau. Không ép các số phải bằng nhau. `llm_ms=188.1` của log `llm_call` là latency mô phỏng do mock trả về; span chat đo wall time 399.487 ms, bao gồm thời gian chờ thực tế. Raw evidence: [trace chậm](reports/evidence/trace-f97793940f004263c4db7441e264b065.json), [trace lỗi có exception](reports/evidence/trace-c34cb9ba78a06c551110b3357b8eac11.json), [log instance 1](reports/evidence/k5-day14-observability-agent-1-selected.jsonl), [log instance 2](reports/evidence/k5-day14-observability-agent-2-selected.jsonl).

Trong production, lấy `trace_id` từ response header `X-Trace-ID` hoặc log, tìm đúng ID trong Jaeger, rồi lọc log bằng ID đó. Đối chiếu `request_id`, `span_id`, instance, HTTP status và timestamp để phân biệt request đồng thời. Với trace lỗi này, span `chat mock-llm-small` ghi `exception.type=utils.mock_llm.LLMError` và message upstream 503, giúp khoanh vùng lỗi provider thay vì nhầm với lỗi auth.

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Từ `benchmark-results/scale_1_stats.csv` (1 instance, 100 users) và `benchmark-results/scale_3_stats.csv` (3 instances, 100 users):

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 59.1 | 210 | 1700 | 2900 | 281 (4.0%) |
| 3 | 63.9 | 200 | 710 | 1700 | 69 (0.9%) |

**Nhận xét:** Scale từ 1 lên 3 instances tăng RPS từ 59.1 lên 63.9 (+8%), giảm p95 từ 1700 ms xuống 710 ms (-58%), giảm p99 từ 2900 ms xuống 1700 ms (-41%), và giảm error rate từ 4.0% xuống 0.9%. Đây là hai lượt đo riêng biệt. Chưa có lượt lặp hoặc profiling để xác định nguyên nhân hay khẳng định mức cải thiện sẽ lặp lại. Compose CP8 không có Redis, nên Redis không thể được nêu là nút thắt của các lượt đo này.

Bảng trên lấy dòng **Aggregated**, gồm cả `/ask` và `/health`. Scale 1 có 7041 request/281 failures, error rate 3.9909%; scale 3 có 7600 request/69 failures, error rate 0.9079%. Riêng `/ask`: scale 1 đạt 53.444 RPS, p95 1700 ms, 271/6364 failures; scale 3 đạt 58.419 RPS, p95 750 ms, 69/6946 failures. Cả hai vẫn không đạt SLO p95 `/ask` < 500 ms.

Speedup quan sát được là `63.9195197629533 / 59.128930258060294 = 1.0810×`. Scaling efficiency theo số replica là `1.0810 / 3 × 100% = 36.03%`. Đây là phép tính trên hai file CSV, không phải cam kết công suất hay bằng chứng bottleneck. Mỗi agent bị giới hạn 0.5 CPU/256 MB theo Compose; Locust dùng think time 0.5–2 s và phân bố task `/ask`:`/health` là 10:1. Các giới hạn và mô hình tải này ảnh hưởng kết quả; chưa đo mức bão hòa của load generator hoặc profile CPU/I/O, nên không quy nguyên nhân cho một thành phần cụ thể.

Các CSV gốc và bản sao nộp bài được giữ byte-identical, gồm stats, history, failures và exceptions cho cả hai mức. Các lượt tạo tải final audit và chaos A–E được lưu riêng trong `reports/evidence/`.

---

## 6. Kết luận

- **3 điều học được về benchmark & observability:**
  1. **Tail latency quan trọng hơn average**: p95/p99 phản ánh trải nghiệm user thực tế; average che giấu slow requests. Một service có avg=250ms nhưng p99=2000ms là service chất lượng thấp.
  2. **Observability = Metrics + Traces + Logs (3 trụ cột)**: Metrics (Prometheus/Grafana) phát hiện *vấn đề gì*, Traces (Jaeger) phát hiện *tại sao/ở đâu*, Logs phát hiện *chi tiết lỗi*. Cần cả 3 để debug hiệu quả.
  3. **Scaling không phải silver bullet**: Scale 1→3 instances giảm p95 58% và failure rate 77%, nhưng không giải quyết được quality regression (experiment E) hay nút thắt tại DB/cache. Phải đo trước khi scale.

- **Nếu đưa agent này lên production thật, sẽ thêm:**
  - `accuracy_score` gauge (từ continuous eval pipeline) + alert khi < 80%
  - `llm_cost_usd_total` counter per model để track spend real-time
  - Span attribute `model_name` và `token_count` trong mỗi LLM call trace
  - Alert: `cost_per_hour > threshold` để không vượt budget
  - Dashboard: Cost efficiency (cost / correct answer) theo thời gian
  - Uptime monitor (external): Ping từ ngoài để phát hiện cold start delays (Render free tier)
