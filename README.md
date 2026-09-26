# Age of Empires II Replay Coach

AoE2 replay 分析工具。V1 規劃為 Python CLI：解析 replay、時間線、指標、兩場比較與 AI 解釋。

## 目前狀態

M0 開發環境、M1-prep 解析驗證、M1 normalized parser 與 M1.1 timeline 已建置。
另提供 replay collector 與 M1.2 初版 command metrics；比較與 AI 功能尚未實作。
完整設計見 [PLAN.MD](PLAN.MD)。

## macOS 快速開始

需要 Git、uv 與 Python 3.12。專案透過 `backend/.python-version` 固定 Python 3.12，
依賴版本記錄於 `backend/uv.lock`，不需要改動系統預設 Python。

```sh
# 在專案根目錄執行
make install
make doctor
make check
```

uv 會建立 `backend/.venv`。若需要先安裝 Python，可執行 `uv python install 3.12`。
編輯器的 Python interpreter 請選擇 `backend/.venv/bin/python`。

## Windows / 不使用 Make

在 PowerShell 或其他 shell 執行相同的 uv 指令：

```sh
cd backend
uv sync --locked
uv run --locked aoe2coach doctor
uv run --locked ruff check src tests
uv run --locked ruff format --check src tests
uv run --locked mypy src
uv run --locked pytest --cov=aoe2coach
```

Windows 編輯器 interpreter 為 `backend/.venv/Scripts/python.exe`。
跨作業系統時重新執行 `uv sync --locked` 建立環境，不要複製 `.venv`。

## Replay 樣本

將真實 `.aoe2record` 放入 `replays/`（已排除於 Git）。

```sh
cd backend
uv run --locked aoe2coach spike ../replays/de-66.6.aoe2record -o ../replays/de-66.6.spike.json
```

`spike` 輸出原始 operations、毫秒時間、操作統計、parser 版本和對局資訊。
成功退出碼為 0；解析失敗或部分解析為 1，JSON 會保留錯誤與可用資料。
檔案可能很大，建議使用 `-o`。輸出包含玩家名稱與聊天資料。

已用三份官方測試錄影驗證，見 [解析驗證報告](docs/parser-spike.md)。
樣本不提交 Git；來源與 SHA-256 記錄於 [replay-sources.json](docs/replay-sources.json)。
在新環境可依該檔的 URL 下載樣本至 `replays/`。

### 收集近期天梯 Replay

從 AoE2 Insights、AoE2 Companion 或官方對戰資料取得 `gameId` 和其中一位玩家的
`profileId`，即可嘗試從 Microsoft／World's Edge 的暫存端點下載：

```sh
cd backend
uv run --locked aoe2coach collect 156900198 2858362
```

預設寫入 `replays/`，自動處理 ZIP、計算 SHA-256 並更新 `replays/manifest.json`。
可用 `-d` 指定其他目錄。官方不保證每場 replay 都存在，舊檔也可能已被清除；下載失敗
不會建立 manifest 項目。Replay 與本機 manifest 均由 `.gitignore` 排除。

## 開發指令

- `make install`：依 lockfile 安裝依賴與開發工具。
- `make doctor`：檢查 Python 與套件版本。
- `make check`：執行 lint、格式、型別與測試。
- `make format`：格式化 Python 程式碼。

CI 設定涵蓋 macOS、Linux 與 Windows；遠端執行結果需推送後確認。

## 正式 JSON 解析

```sh
cd backend
uv run --locked aoe2coach parse ../replays/de-66.6.aoe2record -o ../replays/result.json
```

不提供 `-o` 時 JSON 輸出到 stdout。Schema 為 `aoe2coach.replay.v1`，包含來源 SHA-256、
parser/game 版本、對局與玩家、事件、操作統計及完整度。事件時間 `time_ms` 為遊戲毫秒。
BUILD_COMMAND / QUEUE_COMMAND / RESEARCH_COMMAND 均代表下達指令，不能視為完成。
ORDER 保留為 TARGET_COMMAND；未知解碼保留 UNKNOWN，其他已解碼操作保留 OTHER。
entity_id 保留 parser 提供的原始 ID；entity_name 使用 Replay 對應的 aocref 資料集查詢。
未知名稱為 null，parser metadata 記錄 dataset_id 與 reference_version。名稱為參考標籤，非遊戲狀態驗證。

`status=ok` 退出碼 0；`partial` 或 `failed` 退出碼 1，仍輸出可用資料與錯誤。
`ok` 不代表比賽已結束或每個指令都已驗證。CHAT 保留原始 payload，不推測發話者。
目前唯一 adapter 是 mgz；未實作備援 parser 或相容版本白名單，版本資訊由解析 header 取得。

三份真實錄影 CLI 驗證結果見 [parse-results.json](docs/parse-results.json)。

## 玩家時間線（M1.1 初版）

```sh
cd backend
uv run --locked aoe2coach timeline ../replays/de-66.6.aoe2record --player 1 -o ../replays/timeline.json
uv run --locked aoe2coach timeline ../replays/de-66.6.aoe2record --player 1 --format text
```

輸出指定玩家全部已歸屬指令，按遊戲毫秒與檔案位置排序。JSON 保留來源、版本、
解析狀態與警告；文字格式顯示時間、指令類型和 entity ID。
無玩家 ID 的事件不推測歸屬，輸出其總數與警告。partial 輸出保留退出碼 1。
無效玩家、failed 解析或缺少玩家資訊時回報錯誤，不產生誤導時間線。
已加入建築／單位／科技名稱對照；軍事單位分類與升級完成事件尚未加入。

## 玩家指令指標（M1.2 初版）

```sh
cd backend
uv run --locked aoe2coach metrics ../replays/de-66.6.aoe2record --player 1
```

輸出 raw APM、時代研究指令、軍營／馬廄／靶場建造指令與首次排隊指令時間。
APM 計入已解碼且歸屬該玩家的命令，排除聊天、投降與解碼失敗；它不是 eAPM。
所有 timing 都是下令時間，不代表建造、生產或研究完成時間。

## 本機網頁 Demo

```sh
cd backend
uv run python ../scripts/build_demo.py ../replays/de-66.6.aoe2record
cd ..
python3 -m http.server 8765 --bind 127.0.0.1 --directory demo
```

開啟 http://127.0.0.1:8765 。支援玩家切換、指令類型篩選、名稱搜尋與分頁。
Demo 載入預先解析的一場真實錄影，尚無上傳、AI 分析或線上部署。
生成的 demo/replay.json 排除於 Git；更換 Replay 後重新執行 build_demo.py 並重新整理頁面。
