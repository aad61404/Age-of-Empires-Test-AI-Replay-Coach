# 雲端部署交接紀錄

更新日期：2026-10-26（Asia/Taipei）

這份文件提供給後續接手的 AI 或開發者。它記錄從架構規劃、供應商評估到 Hetzner 帳號準備的實際進度，以及下一步的安全執行順序。

## 一句話現況

目前位於 **Hybrid Cloud 計畫的 M3 前置作業：雲端帳號及付款已完成，但尚未建立任何會計費的 Server**。

不要把「Hetzner 帳號可進入 Cloud Console」誤認為「服務已部署」。目前沒有已確認的 VM、IP、DNS、SSH、Docker、PostgreSQL 或公開 API。

## 最終方向

本專案採用低成本、可搬移的 Hybrid Cloud 路線：

```text
使用者瀏覽器
      │ HTTPS
      ▼
Hetzner Cloud VM
  Caddy + FastAPI + PostgreSQL + Replay Storage
      │ outbound HTTPS claim/result
      ▼
家中 MacBook Air
  Replay Parser + Metrics + Diff Worker
```

核心原則：

- 雲端 VM 是公開入口及資料的唯一真相來源。
- MacBook Air 執行 CPU 密集的 Replay parsing，但不開放任何 Internet inbound port。
- 第一版以 Docker Compose 和單機 PostgreSQL 為主，不先加入 Kubernetes、Redis、RabbitMQ 或 Kafka。
- LLM 最後才加入，只解釋 deterministic parser、metrics 與 diff 的結果。
- 先用 k6 找出一台機器的穩定上限，再討論水平擴充。

完整架構及 milestones 見 [HYBRID-CLOUD-ARCHITECTURE.md](HYBRID-CLOUD-ARCHITECTURE.md)。

## 已完成的規劃與決策

### 1. 供應商比較

已比較：

- Hetzner 歐洲：最低固定成本，適合第一階段部署及容量實驗；台灣連線延遲較高。
- Vultr / Linode 日本：成本較高，但台灣互動延遲較低且 VPS 套餐簡單。
- AWS / GCP / Azure：適合第二階段學習企業雲、IAM、Managed Database、Queue、Object Storage 和 Load Balancer；單一 VM 的帳單較複雜。

目前決策：**第一台 VM 使用 Hetzner；完成單機與 Hybrid 實驗後，再考慮 GCP 台灣或 AWS 台北做比較。**

### 2. 第一台 VM 的預定規格

尚未購買，預定設定如下：

| 項目 | 預定值 |
|---|---|
| Provider | Hetzner Cloud |
| Location | Falkenstein 或 Nuremberg，選建立頁面上可用且價格相同者 |
| OS | Ubuntu 24.04 LTS |
| VM class | Shared vCPU |
| Plan | CX23，若介面供應或名稱改變則選約 2 vCPU / 4 GB RAM 的最低合適方案 |
| Network | IPv4 + IPv6 |
| Backups | 初期不啟用付費自動備份；部署完成後另做可驗證備份 |
| Server name | `aoe-replay-coach` |
| Deployment | Docker Compose |

建立前必須再次確認畫面上的每月／每小時計價，不能只依賴本文件中的舊價格。

## Hetzner 帳號實際狀態

2026-10-26 已透過 Hetzner 網頁確認：

- 帳號可以登入 Hetzner Cloud Console。
- 付款方式顯示為 Credit card，帳戶幣別為 EUR。
- Transactions 顯示 2026-10-25 有一筆 `Payment €25.00`。
- Invoices 顯示 `NO INVOICES FOUND`。
- Credit 頁當時顯示 `Current balance: €0.00`；可能是入帳顯示時序或帳務處理方式，後續若要判斷可用餘額，應重新在官方頁面確認，不能自行假定。
- Cloud Console 已有 `Default` project，畫面提供 `CREATE SERVER`。
- 尚未建立任何 Server。
- Hetzner 顯示 2FA 尚未啟用；使用者目前瀏覽器停在 `https://accounts.hetzner.com/tfa`。

不要把信用卡完整資料、密碼、OTP、2FA seed、QR code、recovery code 或私人識別資料寫進 Git、聊天摘要、終端輸出或日誌。

## 目前階段對照

| 工作 | 狀態 | 證據／備註 |
|---|---|---|
| Hybrid 架構與責任邊界 | 已完成規劃 | `docs/HYBRID-CLOUD-ARCHITECTURE.md` |
| Provider 比較與第一台選擇 | 已決定 | 第一台使用 Hetzner |
| Hetzner 註冊／驗證／付款 | 已完成 | Cloud Console 可用，交易記錄 €25 |
| 2FA | 進行中／尚未確認完成 | 目前停在 Hetzner 2FA 頁面 |
| SSH key | 尚未執行 | 需決定由 Windows 或 Mac 作為管理端；建議各自使用不同 key |
| 建立 Hetzner Server | 尚未執行 | 點擊最終建立按鈕前會開始計費，必須由使用者確認 |
| Linux 安全初始化 | 尚未執行 | 沒有 VM，因此沒有可設定目標 |
| Docker / Caddy / PostgreSQL | 尚未部署 | M3 後續工作 |
| DNS / HTTPS | 尚未設定 | 需要使用者提供或決定網域 |
| Mac Worker | 尚未連接雲端 | M5 工作 |
| k6 容量測試 | 尚未執行 | M7 工作；不可在被測 VM 本機執行 k6 |

## 下一位 AI 的執行順序

### Step 1：完成 2FA（目前下一步）

由使用者親自完成：

1. 使用 authenticator app 掃描 Hetzner QR code。
2. 輸入一次性驗證碼完成綁定。
3. 將 recovery codes 保存到使用者自己的密碼管理器或離線安全位置。
4. 登出再登入一次，確認 2FA 可用。

AI 不應讀取、保存、轉錄或提交 QR seed、OTP、密碼及 recovery codes。

### Step 2：建立 SSH key

先確認主要管理來源：

- 目前 Codex 工作環境是 Windows 專案目錄。
- 家中 MacBook Air 未來會作為 worker。
- 建議 Windows 與 Mac 各自建立獨立 Ed25519 SSH key，方便個別撤銷，不共用 private key。

執行要求：

- private key 永遠只留在產生它的機器。
- 只把 `.pub` 公鑰貼到 Hetzner。
- 不把任何 key 加入 repository。
- 若本機已存在 key，先列出並辨識，禁止覆蓋既有 private key。

### Step 3：建立第一台 Server

在 Hetzner `Default` project 中進入 `CREATE SERVER`，依「預定規格」填好設定。

**在最終 Create & Buy／Create Server 動作前停下來，向使用者展示：**

- Location
- Image
- Server type 與 CPU 架構
- vCPU / RAM / Disk
- IPv4 是否另行計費
- Backup 是否關閉
- 顯示的每小時與每月上限價格
- Server name

這一步會開始產生費用，必須取得使用者當下確認後才能提交。

### Step 4：最小安全初始化

Server 建立後依序完成：

1. 記錄公網 IP，但不要提交可能敏感的管理資訊或 secret。
2. 只以 SSH key 登入，建立非 root 管理帳號。
3. 確認新帳號可使用 `sudo` 且能重新登入，再考慮停用 root SSH／密碼登入。
4. 啟用主機 firewall；第一階段只允許：
   - `22/tcp`：限制管理來源 IP，若來源 IP 不固定則先不要鎖死。
   - `80/tcp`：HTTP，供 Caddy redirect／ACME。
   - `443/tcp`：HTTPS。
5. 絕不公開 `5432/tcp`、Docker socket 或監控管理介面。
6. 安裝安全更新，再安裝 Docker Engine 與 Compose plugin。

任何 SSH hardening 都必須保留目前已驗證可用的 session，並在新 session 測試成功後才關閉舊路徑，避免把使用者鎖在主機外。

### Step 5：先部署最小垂直切片

第一輪不是直接完成全部產品，而是部署：

```text
Caddy
FastAPI /health 與 /ready
PostgreSQL（只在 private Docker network）
一個可重啟的 worker container
```

驗收：

- Internet 只能連到 80/443，以及受限制的 SSH。
- `/health` 表示 process alive；`/ready` 必須真的檢查 PostgreSQL 等依賴。
- reboot 後 containers 能依 restart policy 恢復。
- 從空 VM 可依 repository 文件重建。

### Step 6：接續產品與 Hybrid milestones

依序執行 M4 至 M7：

1. 公開 upload / job / report API 與前端。
2. Mac worker 只透過 outbound HTTPS claim、heartbeat、complete/fail。
3. 備份、restore 演練、structured logs 與基本監控。
4. 從另一台機器執行 k6，分開測 read、upload/job creation、parser 與 mixed workload。
5. 報告 p50/p95/p99、error rate、queue age、CPU、RAM、disk、DB connections，以及第一個飽和資源。

## 交接時不可自行假定的事項

後續 AI 必須重新查證或詢問，不可猜測：

- 2FA 是否已完成。
- €25 是否已成為可扣抵餘額。
- Hetzner CX23 當下價格及是否仍可用。
- 使用者要由 Windows、Mac 或兩者管理 SSH。
- 使用者是否已有網域，以及 DNS 在哪個 registrar 管理。
- 家中 Mac 的型號、RAM、CPU 架構、macOS 版本和是否能長時間保持喚醒。
- 是否允許建立開始計費的 VM。

## 給下一位 AI 的安全與操作指引

- 先讀本文件、`docs/HYBRID-CLOUD-ARCHITECTURE.md`、`docs/STATUS.md` 和 `docs/V2-SYSTEM-ENGINEERING-PLAN.md`。
- repository 目前可能有使用者或前一位 AI 的未提交變更；先執行 `git status`，不得覆蓋或重置。
- 需要操作 Hetzner 網頁時，先閱讀目前畫面，只做與使用者要求一致的操作。
- 2FA、密碼、付款資料與 recovery codes 一律交由使用者本人處理。
- 建機、啟用付費備份、調高方案、購買 IP 或其他會產生費用的最終動作，必須在動作當下再次確認。
- 不要先上 Kubernetes。第一版以 Docker Compose 完成可重建、可觀測、可備份的單機系統。
- 不要把 PostgreSQL、Mac SSH 或 worker 管理端點直接暴露到 Internet。
- 不要在被測 Hetzner VM 上執行 k6，否則 load generator 會搶走被測服務的 CPU/RAM，結果失真。

## 下一次對話的建議開場

可直接把下面這段交給下一位 AI：

> 請先閱讀 `docs/CLOUD-DEPLOYMENT-HANDOFF.md` 與其中連結的架構文件。我們現在位於 Hetzner M3 前置階段：付款與 Default project 已完成，但沒有建立 Server；目前先確認 2FA 是否完成，再安全地建立 SSH key。不要提交或保存任何 secret，也不要在未取得我當下確認前執行會開始計費的 Create Server 動作。
