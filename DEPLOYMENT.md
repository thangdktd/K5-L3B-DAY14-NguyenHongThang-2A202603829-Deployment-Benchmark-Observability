# Deployment — Day 14 (CP6)

## 1. Thông tin triển khai
- **Nền tảng:** Render (Web Service + Render Key Value / Redis)
- **Public URL:** `https://k5-l3b-day14-nguyenhongthang-2a202603829.onrender.com`
- **Thư mục deploy:** `06-lab-complete/` (Docker)
- **Nhánh Git:** `thangdktd`

## 2. Biến môi trường đã cấu hình (đã che giá trị nhạy cảm)
- `AGENT_API_KEY`: `<configured-in-render-env>`
- `REDIS_URL`: `<internal-render-redis-url>`
- `RATE_LIMIT_PER_MINUTE`: `10`
- `DAILY_BUDGET_USD`: `1.0`
- `ENVIRONMENT`: `production`
- `PORT`: do Render cấp; log deployment cho thấy app lắng nghe cổng nền tảng.

Không ghi giá trị API key hoặc Redis URL vào hồ sơ. `DAILY_BUDGET_USD` là ngân sách ngày theo hợp đồng CP5; không gọi nhầm là ngân sách tháng.

## 3. Kiểm thử Public URL
```bash
BASE="https://k5-l3b-day14-nguyenhongthang-2a202603829.onrender.com"

curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # 200
```

Kết quả thực tế:
- `GET /health`: `200`
- `GET /ready`: `200`
- `POST /ask` (không có `X-API-Key`): `401`
- `POST /ask` (có `X-API-Key` hợp lệ): `200` (tự kiểm tra với key cá nhân)

## 4. Kiểm chứng trong final audit

Ngày 26/11/2026 lúc khoảng 22:24 GMT+7, kiểm lại public URL từ máy audit: `/health` trả 200 với `{"status":"ok"}`, `/ready` trả 200 với `{"status":"ready","redis":true}`, `POST /ask` không key trả 401. [HTTP response gốc](reports/evidence/cloud-endpoints.json) lưu thời điểm UTC và body, không lưu secret.

Không có key cloud trong phiên audit, nên không tuyên bố đã chạy lại request xác thực. Bằng chứng 200 có key lấy từ [ảnh test của học viên](screenshots/test.png), trong đó thấy đủ chuỗi `health: 200`, `ready: 200`, `ask_no_key: 401`, `ask_with_key: 200`; giá trị key đã được che. Source CP5 không đổi từ commit deploy `4617c63`, nên bằng chứng này được giữ lại.

## 5. Screenshots deployment

- [Render dashboard](screenshots/dashboard.png): service Free, trạng thái Live, commit `4617c63`, đúng public URL.
- [Service running](screenshots/running.png): log startup, Uvicorn lắng nghe cổng nền tảng và thông báo service live.
- [Bốn lệnh kiểm thử](screenshots/test.png): 200/200/401/200, không lộ key.

## 6. Duy trì để chấm bài

Giữ service Render và Redis đang hoạt động tới khi Lab Coach chấm xong. Gói Free có thể cold start sau thời gian không có request; chờ service khởi động rồi kiểm tra lại `/health` và `/ready`. Phiên final audit không tạo service, thay plan, thay secrets hoặc phát sinh tài nguyên cloud mới. Dừng Docker observability local không ảnh hưởng URL này.
