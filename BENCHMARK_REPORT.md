# Benchmark & Observability Report — Day 14

> Mọi con số lấy từ report JSON / CSV / screenshot trong repo: `06-lab-complete/benchmark-observability/develop/reports/`, `06-lab-complete/benchmark-observability/production/benchmark-results/`, `screenshots/`.

**Họ tên:** Vũ Hải Tuấn
**Ngày chạy:** 2026-11-25
**Môi trường:** Ubuntu 26.04 LTS, Intel Core Ultra 5 225H (14 luồng), 30 GB RAM, Docker 29.8 (snap), Python 3.14 (develop chạy trực tiếp, không Docker)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | LLM nhỏ mất ~120–200 ms/call; 500 ms chừa chỗ cho retrieval + mạng mà người dùng vẫn thấy "nhanh". Đặt theo p95 để 95% người dùng được đảm bảo, không bị average che tail. |
| Error rate `/ask` | < 2 % | Mock LLM có ~1% lỗi upstream nền; 2% = gấp đôi mức nền, vượt nghĩa là có sự cố thật chứ không phải nhiễu. Alert đặt lỏng hơn (5% trong 1 phút) để tránh alert fatigue. |
| Accuracy trên golden dataset | ≥ 90 % | v2 ban đầu đạt 91.3%; ngưỡng 90% chặn được regression đáng kể (mất ≥ 1 câu so với baseline cũng bị gate "không regression" chặn riêng). |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

`--requests 300`, file: `06-lab-complete/benchmark-observability/develop/reports/load_v2_c{1,10,50,100}.json`

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.13 | 191.9 | 223.1 | 1711.1 | 0.33% | ✅ PASS |
| 10 | 36.28 | 190.2 | 221.7 | 1687.3 | 1.00% | ✅ PASS |
| 50 | 111.01 | 203.2 | 271.1 | 1699.9 | 2.67% | ❌ FAIL (error rate) |
| 100 | 66.02 | 337.4 | 2478.4 | 2844.4 | 1.00% | ❌ FAIL (p95) |

**Nhận xét:** RPS tăng gần tuyến tính từ 1 → 10 (4.1 → 36.3, ×8.8) vì mỗi request chủ yếu là *chờ* LLM (`await asyncio.sleep`), một event loop xử lý song song được nhiều request mà latency gần như không đổi (p50 ≈ 190 ms). Từ 10 → 50 RPS chỉ tăng ×3 và p95 bắt đầu tăng (222 → 271 ms): agent chạy **1 process Python**, phần CPU (parse JSON, pydantic, ghi log, metrics) bắt đầu thành nút thắt. Tới 100, RPS còn *giảm* (66 req/s) và p50 nhảy lên 337 ms, p95 2.5 s: request xếp hàng chờ event loop (và client load test chạy cùng máy cũng tranh CPU) — hệ thống đã qua điểm bão hoà, thêm concurrency chỉ làm tăng hàng đợi (Little's law: latency = concurrency / throughput). Error rate 2.67% ở mức 50 là nhiễu mẫu nhỏ (8/300 lỗi 503 ngẫu nhiên của mock, tỉ lệ nền 1%), không do tải. Kết luận: 1 instance giữ được SLO tới khoảng 10–50 concurrency; muốn hơn phải scale ngang.

### 2.2 Tail latency

`--requests 300 --concurrency 20`, file: `reports/load_v2_slow_{0,0.03,0.1}.json`

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 195.0 | 225.3 | 238.3 |
| 0.03 (mặc định) | 253.1 | 229.5 | 1711.3 |
| 0.1 | 374.6 | 1703.8 | 1728.0 |

**Nhận xét:** **p99** nhạy nhất: chỉ 3% request chậm đã đẩy p99 từ 238 → 1711 ms (×7) trong khi p95 gần như không đổi (225 → 230 ms) và avg chỉ tăng 30%. Khi tỉ lệ chậm vượt 5% (0.1) thì p95 cũng nhảy lên 1.7 s. Average gộp request nhanh và chậm thành một con số "trông ổn" (253 ms ở mức 0.03) và che mất việc cứ 100 người dùng thì 3 người phải chờ ~1.7 s — vì vậy SLO phải đặt theo percentile (p95/p99), là thứ người dùng thật cảm nhận. Ngoài ra RPS cũng giảm (99 → 59 → 46 req/s) vì với concurrency cố định, request chậm giữ chỗ lâu hơn.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

File: `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json`

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.2 | 109.1 | 117.5 |
| Tổng cost (USD) | 0.000406 | 0.000762 | 0.000823 |
| Cost / câu đúng (USD) | 0.00040575 | 0.00003627 | 0.00003580 |
| Quality gate | FAIL (accuracy ≥ 80%) | PASS (≥ 80%, 0 regression so với v1) | PASS (≥ 100%, 0 regression so với v2) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 | `token`, `hết hạn`, `chữ ký` | Thêm entry KB kích hoạt bởi `jwt` / `api key`: JWT là token tự chứa claims, có chữ ký số và thời điểm hết hạn (`exp`), khác API key cố định. |
| scaling-03 | `cpu`, `memory`, `custom metrics` | Thêm entry KB kích hoạt bởi `hpa` / `kubernetes` / `autoscal`: HPA scale theo CPU, memory hoặc custom metrics qua Metrics API / Prometheus Adapter. |

Trước khi sửa, cả hai câu không khớp entry nào trong `KNOWLEDGE_BASE` nên retrieval trả rỗng và mock LLM trả câu chung chung. Từ khoá kích hoạt mới không xuất hiện trong câu hỏi nào khác của dataset nên không gây regression (eval cuối: 2 câu cải thiện, 0 regression).

**Quality gate trong CI (Exercise 7.3):** `run_eval.py` trả exit code 1 khi accuracy < `--min-accuracy` hoặc có câu regression so với `--baseline`. Thử eval v1 với `--baseline reports/eval_v2.json` → **exit code 1** (20 câu regression, gate ❌ FAIL). Job GitHub Actions ở `.github/workflows/eval-quality-gate.yml` khởi động agent v2 rồi chạy `run_eval.py --min-accuracy 1.0 --baseline reports/eval_v2_fixed.json`; step fail → job fail → đặt job này là *required status check* trong branch protection thì PR không merge được.

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:** v2 (RAG) tốn gần gấp đôi token mỗi câu (57 → 109) và tổng cost tăng ~1.9×, latency eval tăng nhẹ (p50 167 → 190 ms, thêm bước retrieval ~20 ms). Đổi lại accuracy tăng từ 4% lên 91%, nên **cost / câu đúng giảm ~11×** (0.000406 → 0.0000363 USD). So "cost / câu" thì v1 rẻ hơn, nhưng câu trả lời sai là vô giá trị — "cost / câu đúng" mới phản ánh chi phí để tạo ra giá trị cho người dùng. Bản sửa KB thêm ~8 token/câu nhưng cost / câu đúng còn giảm thêm vì đúng thêm 2 câu.

---

## 4. Observability stack (production)

Stack chạy bằng `docker compose -p k5-day14-observability up -d --build`. Port phía host của Nginx đổi sang **8088** và Grafana sang **3001** bằng một file override ngoài repo, vì 8080 (Jenkins) và 3000 trên máy đã có dịch vụ khác. Trong container mọi thứ giữ nguyên.

Sửa 1 lỗi trong `production/Dockerfile`: agent crash `ModuleNotFoundError: uvicorn` vì package được copy vào `/home/agent/.local` nhưng HOME của user `agent` là `/app`. Đã thêm `ENV PYTHONUSERBASE=/home/agent/.local`.

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals): [screenshots/grafana-dashboard.png](screenshots/grafana-dashboard.png) (đang chạy Locust 100 user), [screenshots/grafana-experiments.png](screenshots/grafana-experiments.png) (20 phút gồm các thí nghiệm A–E)
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian): [screenshots/jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png)
- [x] Một trace lỗi trong Jaeger (có event `exception`): [screenshots/jaeger-error-trace.png](screenshots/jaeger-error-trace.png). Trace `27024069d1f86099e301deb86e1b4147`: span `chat mock-llm-small` và `agent.run` có status ERROR và event `exception` (`utils.mock_llm.LLMError: Upstream LLM error: 503 Service Unavailable (mock)`), `POST /ask` trả 503.
- [x] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**: [screenshots/prometheus-alert-firing.png](screenshots/prometheus-alert-firing.png). **FIRING (2)**: `AgentHighErrorRate` + `LLMCostBurnRateHigh` cùng lúc (trong thí nghiệm A).

Dòng log của trace lỗi (`docker compose -p k5-day14-observability logs agent | grep 27024069d1f86099e301deb86e1b4147`):

```json
{"ts": "2026-11-25T11:10:26.272478+00:00", "level": "INFO", "service": "observable-agent", "instance": "811a824e727d", "event": "llm_error", "trace_id": "27024069d1f86099e301deb86e1b4147", "span_id": "81b0801ca6bd8f92", "request_id": "49b037ace480", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
{"ts": "2026-11-25T11:10:26.273471+00:00", "level": "INFO", "service": "observable-agent", "instance": "811a824e727d", "event": "http_request", "trace_id": "27024069d1f86099e301deb86e1b4147", "span_id": "81b0801ca6bd8f92", "request_id": "49b037ace480", "method": "POST", "route": "/ask", "status": 503, "ms": 95.9}
```

### 4.2 Thí nghiệm "phá hệ thống"

Tải nền: Locust headless 30 user (`--no-deps`), 2 instance agent. Mỗi thí nghiệm đổi biến môi trường rồi `docker compose up -d` (agent được recreate). Thời gian đo bằng cách poll `GET /api/v1/alerts` của Prometheus mỗi 5 s, tính từ lúc lệnh `up -d` / `docker pause` xong.

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (giá trị lúc firing ≈ 17%) | pending +25 s → **firing +86 s** | Golden Signals → *Error rate*; *Requests/s theo status code* (503 tăng); *LLM calls theo kết quả* (error) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | pending +26 s → **firing +147 s** | *Latency /ask p50/p95/p99*: p95 = 1912 ms, p99 = 1982 ms nhưng avg chỉ 617 ms |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | pending +18 s (activeAt 18:16:37) → firing ≈ **+138 s** (`for: 2m`) | *Cost burn rate (USD/giờ)*: $2.32 → **$33.29/giờ (×14.4)**; p95 /ask 291 → 684 ms, LLM p95 ≈ 496 ms |
| D | `docker pause` 1 instance | `AgentInstanceDown` | pending +11 s → **firing +41 s** | *Instances up* 2 → 1; Nginx log 29 lỗi `504 upstream timed out` nhưng panel *Error rate* của agent vẫn xanh |
| E | `AGENT_VERSION=v1` | Không có | — | *Retrieval hit ratio* mất dữ liệu (v2: 87% hit → v1: không còn retrieval), *Tokens/s* 1710 → 1056, bảng *Phiên bản đang chạy* đổi sang v1; error rate 0.39%, p95 199 ms, tức là còn "đẹp" hơn v2 |

Ghi chú: với model small và 100 user, cost đã ≈ $5/giờ nên `LLMCostBurnRateHigh` (ngưỡng $2/giờ) firing ngay sau benchmark scaling, trước cả thí nghiệm C. Ngưỡng này đặt cho tải ~30 user. Ở C, alert đã resolve trước khi đổi model, rồi pending lại sau 18 s.

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Đây là lỗi **chất lượng**, không phải lỗi hạ tầng: latency, error rate, instance đều tốt hơn, nên metric 4 Golden Signals không bắt được. Cách phát hiện:
1. **Chặn trước khi deploy:** quality gate eval trong CI (`run_eval.py --baseline`, Mục 3). Deploy v1 sẽ fail vì 20 câu regression.
2. **Metric chất lượng proxy + alert:** alert khi `retrieval hit ratio` < 50% trong 10 phút hoặc khi `agent_info{version}` khác version mong đợi. Thêm cảnh báo khi tokens/câu hoặc độ dài câu trả lời đổi đột ngột so với baseline.
3. **Online eval / canary:** chạy golden dataset định kỳ (synthetic probe, vd 5 phút/lần) vào production, xuất `eval_accuracy` thành metric và alert khi < SLO 90%. Có thể chấm mẫu một phần traffic thật bằng LLM-as-judge.
4. **Tín hiệu người dùng:** tỉ lệ 👎 / hỏi lại / escalate sang người thật.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất tìm được (trong thí nghiệm B, lọc log `http_request` 3 phút gần nhất, lấy `ms` lớn nhất). Ảnh: [screenshots/jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png)

- `trace_id`: `eaaed62fe00f4d269a9316828c769513`
- Tổng thời gian: 1976.9 ms
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (1661.5 ms, 84%). `agent.retrieve_context` chỉ 19.8 ms (1%). Khoảng ~300 ms trước khi `agent.run` bắt đầu là thời gian request chờ trong agent (instance bị giới hạn 0.5 CPU khi có tải). → Request chậm vì **LLM upstream chậm**, không phải code retrieval.
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T11:11:25.521394+00:00", "level": "INFO", "service": "observable-agent", "instance": "0930a93979aa", "event": "llm_call", "trace_id": "eaaed62fe00f4d269a9316828c769513", "span_id": "44b1ea2fbd9d9016", "request_id": "be07a55a307f", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 37, "output_tokens": 24, "cost_usd": 2e-05, "llm_ms": 1661.5}
{"ts": "2026-11-25T11:11:25.522222+00:00", "level": "INFO", "service": "observable-agent", "instance": "0930a93979aa", "event": "http_request", "trace_id": "eaaed62fe00f4d269a9316828c769513", "span_id": "44b1ea2fbd9d9016", "request_id": "be07a55a307f", "method": "POST", "route": "/ask", "status": 200, "ms": 1976.9}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
File: `06-lab-complete/benchmark-observability/production/benchmark-results/scale_{1,3}_stats.csv`, số liệu dòng `POST /ask` (mỗi agent giới hạn `cpus: 0.5`).

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 57.99 | 210 | 740 | 1700 | 73 / 6913 (1.06%, đều là 503) |
| 3 | 59.79 | 200 | 270 | 1700 | 77 / 7126 (1.08%, đều là 503) |

Kiểm tra phân tải lúc chạy 3 instance (Prometheus, `increase(http_requests_total{route="/ask"}[2m])`): 2410 / 2414 / 2407 request mỗi instance, Nginx chia đều.

> Lưu ý khi chạy: compose khai báo `deploy.replicas: 2` cho agent, nên `docker compose run locust ...` (không có `--no-deps`) tự đưa agent về 2 replica, xoá instance thứ 3 và tạo thêm instance thứ 2 khi đang đo 1 instance. Hai file CSV ở trên được chạy lại với `docker compose run --rm --no-deps locust ...` và đã kiểm tra số container agent trước/sau mỗi lần chạy (1 và 3).

**Giải thích kết quả:** Scale lên 3 **cải thiện rõ p95** (740 → 270 ms), avg giảm 290 → 245 ms. Với 1 instance giới hạn 0.5 CPU, phần CPU của request (FastAPI, pydantic, log JSON, metrics, export trace) làm request xếp hàng khi có 100 user: p50 vẫn ổn nhưng p95 vượt SLO 500 ms. 3 instance chia tải, hết xếp hàng, p95 về gần mức latency LLM thuần (~200–270 ms).

Hai chỉ số **không đổi**:
- **RPS** (~58–60 req/s): Locust là tải *đóng*, 100 user, mỗi user chờ `between(0.5, 2)` s (trung bình 1.25 s) giữa các request, nên tối đa khoảng 100 / (1.25 + 0.25) ≈ 65 req/s cho cả `/ask` và `/health`. Thông lượng bị giới hạn bởi bộ tạo tải chứ không phải agent. Muốn thấy RPS tăng phải tăng số user.
- **p99 = 1700 ms**: đây là ~3% request "slow" của mock LLM (`MOCK_SLOW_RATE=0.03`, +1500 ms). Độ chậm nằm ở upstream LLM, nên thêm instance không giảm được. Failures ~1% cũng là lỗi upstream (`MOCK_ERROR_RATE=0.01`).

→ Sau khi scale, **nút thắt còn lại là LLM**: panel LLM latency p95 giữ ~200 ms và tail 1.7 s bất kể số instance. Muốn giảm tail cần timeout + retry/hedging request, cache câu trả lời, hoặc đổi provider/model, chứ không phải thêm container.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. **Average nói dối, percentile thì không.** Chỉ 3% request chậm làm p99 tăng ×7 (238 → 1711 ms) trong khi avg chỉ tăng 30% và p95 gần như không đổi. SLO và alert phải đặt theo p95/p99. Số liệu load test cũng phải đọc cùng điều kiện đo: bộ tạo tải đóng (Locust có `wait_time`) giới hạn RPS, nên RPS không đổi khi scale chưa chắc là do agent.
  2. **Scale ngang chỉ chữa được nút thắt của chính service.** 3 instance kéo p95 từ 740 về 270 ms vì hết xếp hàng CPU, nhưng p99 1.7 s (LLM chậm) và lỗi upstream 1% không đổi. Trace cho thấy 84% thời gian nằm ở span LLM, nên cần timeout/retry/cache/đổi provider chứ không phải thêm container.
  3. **Metrics, traces, logs chỉ mạnh khi nối với nhau, và vẫn có điểm mù.** Alert báo *có* vấn đề (error rate, p95, instance down) trong 40–150 s, trace chỉ *ở đâu*, `trace_id` trong log cho *chi tiết*. Nhưng lỗi ở Nginx (504 khi pause instance) không hiện trên metric của agent, và lỗi chất lượng (v1) không làm alert nào đỏ. Vì vậy cần giám sát ở tầng LB/synthetic và eval chất lượng liên tục. Ngoài ra, chính quy trình benchmark cũng cần kiểm chứng: `docker compose run` âm thầm đưa agent về `replicas: 2` và làm sai lần đo đầu tiên.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  - **Tầng LB / synthetic:** `nginx_http_requests_total{status="5xx"}` hoặc blackbox probe `/ask` từ bên ngoài; alert khi tỉ lệ 502/504 > 1% (bắt được thí nghiệm D mà metric agent bỏ sót).
  - **Chất lượng:** `eval_accuracy` từ online eval định kỳ (alert < 90%), `retrieval_hit_ratio` < 50%, alert khi `agent_info{version}` lệch version mong đợi, tỉ lệ feedback tiêu cực.
  - **SLO burn-rate alert nhiều cửa sổ** (1h & 6h, theo error budget 2%) thay cho ngưỡng tĩnh, để giảm alert fatigue mà vẫn bắt được sự cố âm ỉ.
  - **LLM:** p99 LLM latency theo model, tỉ lệ timeout/retry/429 của provider, cost theo ngày so với budget (đã có cost guard ở Part 6: alert khi dùng > 80% budget ngày), token/câu.
  - **Saturation:** CPU/memory container, độ dài hàng đợi / in-flight theo instance, kết hợp autoscaling theo in-flight hoặc p95.
