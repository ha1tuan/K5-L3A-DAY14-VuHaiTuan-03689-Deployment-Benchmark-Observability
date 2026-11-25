# Deployment Information

## Public URL
https://lab14-production-74711270.up.railway.app

## Platform
Railway (project `lab14`, environment `production`)

| Service | Vai trò | Ghi chú |
|---------|---------|---------|
| `lab14` | Agent Part 6 (`06-lab-complete/`) | Build bằng `Dockerfile` (multi-stage, `python:3.11-slim`, user non-root), cấu hình trong `06-lab-complete/railway.toml` |
| `Redis` | State dùng chung cho rate limiter + cost guard | Database Redis của Railway, có volume `redis-volume`; agent kết nối qua mạng nội bộ `redis.railway.internal:6379` |

Deploy bằng lệnh:
```bash
cd 06-lab-complete
railway up
```

## Test Commands

Đặt biến trước khi chạy (key lấy trong tab **Variables** của service `lab14` trên Railway, không ghi vào repo):
```bash
export BASE="https://lab14-production-74711270.up.railway.app"
export AGENT_API_KEY="<key đặt trên Railway>"
```

4 lệnh tự kiểm của CP6 (chỉ in mã HTTP, không lộ key):
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # 200
```

Kết quả đo ngày 2026-11-25:

| Lệnh | Mong đợi | Thực tế |
|------|----------|---------|
| `GET /health` | 200 | 200 |
| `GET /ready` | 200 | 200 |
| `POST /ask` không có key | 401 | 401 |
| `POST /ask` có `X-API-Key` | 200 | 200 |

### Health Check
```bash
curl "$BASE/health"
```

### API Test (with authentication)
```bash
curl -X POST "$BASE/ask" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# {"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) ...","cost_usd":1.6e-05}
```

## Environment Variables Set

Trên service `lab14` (Railway → Variables):

| Biến | Giá trị | Ghi chú |
|------|---------|---------|
| `AGENT_API_KEY` | secret (64 ký tự hex, sinh bằng `openssl rand -hex 32`) | Chỉ đặt trên Railway, không có trong code / git |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` | Reference variable trỏ sang service Redis |
| `PORT` | do Railway cấp | `Dockerfile` chạy `uvicorn ... --port ${PORT:-8000}` |

Các biến còn lại (`ENVIRONMENT`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD`) dùng giá trị mặc định trong `06-lab-complete/app/config.py`.

## Screenshots
- [Deployment dashboard: Redis + lab14 Online, deploy logs](screenshots/anh2.png)
- [Test results: 4 lệnh CP6](screenshots/test.png)
