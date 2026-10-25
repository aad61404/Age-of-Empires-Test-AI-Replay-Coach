# V2 系統工程學習與實作計畫

更新日期：2026-10-25

## 目標

這份計畫不是 CRUD 功能清單，而是一條可驗收的後端與 AI 系統工程學習路線。以 AoE2 Replay Coach 為實驗系統，完成後應能回答：

1. 一台指定規格的機器，在可接受的延遲與錯誤率下能服務多少流量？
2. 瓶頸位於 API、Replay parser、PostgreSQL、背景工作或 LLM 的哪一層？
3. 任務失敗、重複送達、服務重啟或模型更換時，系統是否仍然正確且可重算？
4. AI 輸出的事實、推論、版本、品質與成本能否追蹤？

最終交付物：

- 可運行的 FastAPI + PostgreSQL + worker 系統。
- 可重現的 k6 壓測腳本與固定測試資料集。
- 單機容量報告，列出硬體、版本、負載模型、p95/p99、吞吐量及瓶頸。
- AI eval dataset 與模型／prompt 回歸報告。
- 架構決策紀錄（ADR）及故障演練結果。

## 核心架構

本計畫的第一個低成本部署 profile 使用「雲端公開服務 + Mac parser worker」。
服務邊界、資料流、安全限制與逐步 milestone 見
[Hybrid Cloud Architecture](HYBRID-CLOUD-ARCHITECTURE.md)。

```text
Client
  │
  ▼
FastAPI ───────────────► PostgreSQL
  │                         │
  │ 建立 job（快速回應）     │ SELECT ... FOR UPDATE SKIP LOCKED
  ▼                         ▼
202 Accepted             Parser Workers
                            │
                            ├──► normalized replay / metrics / diff
                            │
                            └──► AI job ──► CoachProvider

Metrics / Logs / Traces ──► Prometheus + Grafana + OpenTelemetry
Load generation ──────────► k6
```

架構原則：

- HTTP request 不同步執行 replay parsing 或 LLM 呼叫。
- PostgreSQL 是第一階段唯一持久化與 job queue；有量測證據後才考慮 Redis、RabbitMQ 或 Kafka。
- 所有可重試工作都必須冪等，不能只依賴「正常情況只執行一次」。
- deterministic computation 先完成，LLM 僅做需要語言與判斷的解釋。
- 每個結論都能追溯到 replay、parser、規則、prompt 與 model 版本。
- 先定義 SLO 和測試條件，再談「單機可撐多少」。

## 建議學習材料

以官方文件與大學課程為主；每個主題學完立即在本專案實作。

| 主題 | 主要材料 | 本專案練習 |
|---|---|---|
| 資料庫原理 | CMU 15-445、PostgreSQL 官方文件 | schema、index、transaction、EXPLAIN |
| 索引與查詢 | Use The Index, Luke、PostgreSQL EXPLAIN 文件 | 比較索引前後 query plan |
| 資料密集系統 | Designing Data-Intensive Applications | replication、queue、idempotency 決策 |
| 分散式系統 | MIT 6.5840（選讀） | retry、delivery semantics、failure modes |
| SRE | Google SRE Book / Workbook | SLI、SLO、error budget、runbook |
| 系統效能 | Systems Performance（Brendan Gregg） | CPU、memory、disk、network 飽和分析 |
| 負載測試 | Grafana k6 官方文件 | smoke、baseline、stress、spike、soak |
| 可觀測性 | OpenTelemetry、Prometheus 官方文件 | logs、metrics、traces correlation |
| AI 工程 | OpenAI Cookbook、Full Stack Deep Learning、AI Engineering | structured output、eval、cost、fallback |

建議閱讀順序不是把所有書看完才動手，而是「讀最小必要章節 → 實作 → 量測 → 寫結論」。

## 24 週執行路線

預設每週 8～10 小時。若時間較少，延長週數，不要刪除驗收項目。

### Phase 0：建立基準與實驗規則（第 1～2 週）

學習：

- throughput、latency、concurrency、utilization、saturation。
- p50、p95、p99 與平均值的差異。
- Little's Law：`concurrency = throughput × latency`。
- SLI、SLO、error budget。

實作：

- 固定 benchmark machine 規格與 OS。
- 建立小／中／大三種 replay corpus，記錄 SHA-256。
- 記錄目前 CLI 單執行緒解析時間、CPU、峰值記憶體與輸出大小。
- 建立 `docs/benchmarks/`，保留原始結果與環境資訊。

驗收：同一個 benchmark 至少執行五次，報告中能區分 warm-up 與正式樣本。

### Phase 1：PostgreSQL 與資料模型（第 3～6 週）

學習：

- relational model、normalization、primary/foreign key。
- B-tree、複合索引、selectivity、covering index。
- ACID、MVCC、isolation level、lock、deadlock。
- WAL、vacuum、connection pool、JSONB 取捨。
- `EXPLAIN (ANALYZE, BUFFERS)` 與 `pg_stat_statements`。

實作：

- 建立 migration，不允許由 ORM 啟動時偷偷建表。
- 建立 `replays`、`players`、`events`、`analysis_runs`、`jobs`、`ai_runs`。
- replay 以 SHA-256 去重；衍生結果保留 parser/ruleset 版本。
- 比較 event row-per-event、JSONB 與混合模型的大小和查詢效能。
- 為實際查詢建立索引，保留索引前後的 query plan。

最低資料契約：

```text
replays:      id, sha256, source, game_version, created_at
analysis_runs: replay_id, parser_name, parser_version, ruleset_version, status
events:       analysis_run_id, player_id, occurred_ms, event_type, entity_id, payload
jobs:         type, dedupe_key, status, attempts, available_at, lease_until, last_error
ai_runs:      analysis_run_id, provider, model, prompt_version, input_hash,
              output, token_usage, latency_ms, validation_status
```

驗收：

- migrations 可從空 DB 建立，也能完整 rollback 開發期 migration。
- 同一 replay 重傳不產生重複資料。
- 主要查詢附上 `EXPLAIN (ANALYZE, BUFFERS)` 與理由。
- 以至少 10 萬、100 萬 event 量級測量 DB 大小與查詢延遲。

### Phase 2：API、背景工作與可靠性（第 7～10 週）

學習：

- HTTP semantics、status code、pagination、problem details。
- timeout、retry、exponential backoff、jitter、circuit breaker。
- idempotency、at-least-once delivery、backpressure。
- connection pool 與 bounded concurrency。

實作：

- `POST /replays`：上傳後建立工作並回傳 `202 Accepted`。
- `GET /jobs/{id}`：查詢 queued/running/succeeded/failed 狀態。
- `GET /replays/{id}`、metrics、diff 與 coach 查詢端點。
- worker 以 `FOR UPDATE SKIP LOCKED` 領取工作。
- heartbeat/lease 處理 worker crash；超過重試次數進 dead-letter 狀態。
- `dedupe_key = replay_sha256 + parser_version + ruleset_version`。
- API、parser 與 LLM 各自設定 timeout 與 concurrency limit。

驗收：

- 同一 request 重送 10 次只產生一份邏輯結果。
- worker 在執行中被終止後，job 能自動恢復。
- DB 或 provider 暫時失效時不形成無限制重試風暴。
- queue 滿載時 API 有明確的限流或拒絕策略。

### Phase 3：可觀測性（第 11～13 週）

學習：

- RED：Rate、Errors、Duration。
- USE：Utilization、Saturation、Errors。
- structured logs、metrics、distributed traces。
- cardinality、sampling 與 telemetry 成本。

實作：

- 每個 request/job 有 correlation ID。
- Prometheus metrics 至少包含 request rate/error/duration、queue depth/age、parse duration、DB pool、LLM latency/tokens/cost。
- OpenTelemetry trace 串起 API → DB → worker → AI provider。
- Grafana dashboard 顯示 SLO、資源飽和與最老 job 年齡。
- 啟用慢查詢與 `pg_stat_statements`。

驗收：收到「系統變慢」問題時，能從 dashboard 和 trace 在 15 分鐘內定位到主要層級。

### Phase 4：k6 與單機容量（第 14～17 週）

學習：

- open/closed workload model。
- coordinated omission。
- smoke、baseline、load、stress、spike、soak test。
- bottleneck analysis 與 capacity knee。

實作腳本：

```text
loadtest/
  smoke.js       少量請求，驗證腳本和環境
  read.js        replay/metrics/diff 查詢流量
  upload.js      replay 上傳與 job 建立
  mixed.js       接近真實比例的讀寫混合負載
  spike.js       突增流量及恢復能力
  soak.js        2～8 小時，找 memory/connection leak
  data/          固定測試 replay 與 ID，不放敏感資料
```

每輪測試固定並記錄：

- CPU 型號／核心數、RAM、磁碟、OS、容器限制。
- Git commit、Python/PostgreSQL/k6 版本與所有 config。
- dataset 大小、cache 狀態、是否包含 LLM stub。
- arrival rate、duration、資料分布與 endpoint 比例。
- throughput、p50/p95/p99、error rate、queue age。
- CPU、memory、disk IOPS/latency、network、DB connections/locks。

第一版 SLO（完成 baseline 後再校準）：

- 查詢 API：p95 < 300 ms、p99 < 800 ms。
- 建立 job：p95 < 500 ms。
- 非預期 HTTP error rate < 1%。
- 穩態 queue oldest age 不持續增長。
- 30 分鐘穩態後記憶體無單調成長。

找單機上限的方法：

1. 先用 stub 關閉外部 LLM 變因。
2. 從低 arrival rate 開始，每階段增加 20%～30%。
3. 每階段維持足夠時間，等待 queue 與 cache 穩定。
4. 找出 p95/p99、錯誤率或 queue age 首次違反 SLO 的區間。
5. 在該區間縮小步幅重測至少三次。
6. 最大穩定容量定義為「持續滿足 SLO 且 backlog 不成長」的最高負載，不採瞬時峰值。
7. 一次只修改一個變因，重新測量並保存差異。

驗收：任何人依報告與腳本，都能在相同規格機器上重現近似結果；報告清楚指出第一個飽和資源。

### Phase 5：AI 系統工程（第 18～21 週）

學習：

- structured output、schema validation、grounding。
- offline eval、regression test、human rubric。
- prompt injection、資料邊界與最小權限。
- token、latency、cost budget；rate limit 與 fallback。

實作：

- cache key 包含 input hash、parser/ruleset、prompt、provider、model 版本。
- CoachingReport 嚴格 schema 驗證，失敗可重試或退回 rule-based baseline。
- 每項 observation 引用 evidence ID；grounding validator 阻止無來源事實。
- 建立匿名化 golden dataset，涵蓋正常、缺資料、parser partial 與 adversarial input。
- CI 跑 deterministic eval；provider eval 可排程或手動執行。
- 記錄 tokens、成本、延遲、validation result，不記錄 secret。
- 設定每場／每日成本上限與 provider rate-limit backpressure。

AI eval 維度：

- Groundedness：陳述是否有 replay/benchmark evidence。
- Correctness：數字、時間與玩家歸屬是否正確。
- Helpfulness：建議是否具體且有優先順序。
- Calibration：相關性不能被寫成因果結論。
- Robustness：partial data 時是否明確揭露限制。
- Cost/latency：品質改善是否值得額外成本。

驗收：更換 prompt 或 model 前後都有可比較結果；任何歷史輸出可由版本資訊判斷是否需要重算。

### Phase 6：整合、故障演練與作品整理（第 22～24 週）

實作：

- 撰寫 ADR：PostgreSQL queue、event storage、idempotency、AI provider boundary。
- 演練 worker crash、DB connection exhaustion、慢查詢、provider timeout、poison job。
- 建立 runbook：告警含義、查詢方式、降級與恢復步驟。
- 完成容量報告、架構圖、限制與下一步擴展條件。

驗收：

- 新環境可依 README 一次啟動。
- 自動測試、migration、smoke load test 在 CI 通過。
- 故障演練不丟失 replay，且不產生不可控重複結果。
- 能用證據回答「增加 API worker、DB tuning 或 parser worker，哪個最有效」。

## 每週固定節奏

每週 8～10 小時可分配為：

- 2 小時：閱讀一個核心概念，只做短筆記。
- 4 小時：在專案中實作最小垂直切片。
- 2 小時：測試、壓測與故障注入。
- 1 小時：寫結果、圖表、ADR 或 runbook。
- 1 小時：回顧假設，決定下一週唯一主要問題。

每週必須留下可驗證證據：commit、測試、query plan、benchmark raw data 或 ADR；不以「看完課程」作為完成標準。

## 容量報告模板

```markdown
# Capacity Report: <commit>

## Environment
- CPU / RAM / Disk / OS / container limits
- Application / PostgreSQL / k6 versions
- Relevant configuration

## Workload
- Dataset and hashes
- Endpoint mix and arrival model
- Warm/cold cache and test duration
- LLM real/stubbed

## SLO
- Latency, error, queue-age thresholds

## Results
- Requests/s and jobs/min
- p50 / p95 / p99
- Error rate and queue age
- CPU / memory / disk / DB pool

## Capacity knee
- Highest repeatable load satisfying SLO
- First saturated resource and evidence

## Experiment
- One change made
- Before/after results
- Decision and next hypothesis
```

## Definition of Done

V2 不是「API 可以動」就完成。以下條件需全部成立：

- schema、migration、索引與主要 query plan 經過驗證。
- 上傳、解析、分析、AI 都有狀態、冪等鍵、timeout 與重試邊界。
- logs、metrics、traces 足以定位瓶頸與失敗。
- k6 測試可重現，單機上限有明確 SLO 與硬體前提。
- AI output 有 evidence、版本、eval、成本和 fallback。
- 故障演練、容量報告、ADR、runbook 都保存在 repository。

完成這些後，再根據實測瓶頸決定是否拆服務、加入 Redis／專用 queue、DB read replica 或水平擴展；沒有量測證據前不預先增加基礎設施。
