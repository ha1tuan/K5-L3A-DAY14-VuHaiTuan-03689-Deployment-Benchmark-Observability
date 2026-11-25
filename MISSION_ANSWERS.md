# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

<!-- TODO: Exercise 1.1, 1.3 -->

## Part 2: Docker

<!-- TODO: Exercise 2.1, 2.3 (số MB đo được) -->

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment
- URL: https://lab14-production-74711270.up.railway.app
- Thư mục deploy: `06-lab-complete/` (agent Part 6), cấu hình `06-lab-complete/railway.toml`
- Redis: service Redis của Railway, agent nối bằng `REDIS_URL=${{Redis.REDIS_URL}}`
- `AGENT_API_KEY`: đặt trong Railway Variables, không ghi vào code
- Kết quả 4 lệnh tự kiểm CP6: `/health` 200 · `/ready` 200 · `/ask` không key 401 · `/ask` có key 200 (chi tiết trong [DEPLOYMENT.md](DEPLOYMENT.md))
- Screenshot: [dashboard](screenshots/dashboard.png), [test](screenshots/terminal.png)

### Exercise 3.2: So sánh `railway.toml` và `render.yaml`

| Khía cạnh | `railway.toml` | `render.yaml` |
|-----------|----------------|---------------|
| Định dạng / phạm vi | TOML, cấu hình **một service** (build + deploy của agent) | YAML Blueprint, khai báo **cả hạ tầng**: web service + Key Value (Redis) |
| Build | `builder = "DOCKERFILE"`, `dockerfilePath` | `runtime: docker`, `dockerfilePath`, `dockerContext`; cần `rootDir: 06-lab-complete` vì file không nằm ở gốc repo |
| Redis | Không khai báo trong file: tạo database Redis trên dashboard/CLI rồi nối bằng reference variable `${{Redis.REDIS_URL}}` | Khai báo service `type: keyvalue` ngay trong file, nối bằng `fromService.property: connectionString` |
| Secret | Không có chỗ cho secret trong file, đặt bằng dashboard hoặc `railway variables --set` | Khai báo tên biến trong file nhưng không ghi giá trị: `generateValue: true` (Render tự sinh) hoặc `sync: false` (nhập tay) |
| Health check | `healthcheckPath = "/health"` + `healthcheckTimeout = 100`: Railway chỉ chuyển traffic sang bản deploy mới khi `/health` trả 200 | `healthCheckPath: /health`: dùng cho zero-downtime deploy và kiểm tra liên tục khi đang chạy |
| Restart | `restartPolicyType = "ON_FAILURE"`, tối đa 3 lần | Không cấu hình trong file, Render tự restart |
| PORT | Railway cấp `PORT`, Dockerfile đọc `${PORT:-8000}` | Render cũng cấp `PORT` (mặc định 10000), dùng chung Dockerfile |

**Vì sao khác nhau:** Railway coi mỗi service là một thực thể riêng quản lý trên canvas. `railway.toml` chỉ là config-as-code cho build/deploy của một service, còn việc nối các service (Redis) và secret được làm trên nền tảng. Render Blueprint là infrastructure-as-code: một file mô tả toàn bộ stack để tạo lại từ đầu bằng một lần sync, nên phải chứa cả Redis và cách nối biến môi trường, đồng thời có cơ chế riêng (`generateValue`/`sync: false`) để không lộ secret trong repo.

### Exercise 3.3: Pipeline Cloud Run (`03-cloud-deployment/production-cloud-run/`)
1. **Trigger:** push lên nhánh `main` thì Cloud Build chạy `cloudbuild.yaml`.
2. **Test:** chạy `pytest tests/` trong image `python:3.11-slim`. Test fail thì pipeline dừng, không build.
3. **Build & Push:** build Docker image gắn 2 tag `$COMMIT_SHA` và `latest` (dùng `--cache-from latest` để tận dụng layer cache), rồi push lên Container Registry.
4. **Deploy:** `gcloud run deploy` image theo `$COMMIT_SHA` lên region `asia-southeast1`, min 1 / max 10 instance, 512Mi, 1 CPU. Secret (`OPENAI_API_KEY`) lấy từ Secret Manager, không ghi trong file.
5. `service.yaml` mô tả cùng service đó theo kiểu khai báo (Knative): `containerConcurrency: 80`, liveness probe `/health`, startup probe `/ready`, `AGENT_API_KEY` lấy qua `secretKeyRef`. Áp dụng bằng `gcloud run services replace`.

## Part 4: API Security

<!-- TODO: Exercise 4.1-4.3 (output 401 / 200 / 429), 4.4 -->

## Part 5: Scaling & Reliability

<!-- TODO -->
