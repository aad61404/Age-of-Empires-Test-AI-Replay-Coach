# 專案現況（2026-10-22）

## 已完成

- M0：Python 3.12、uv lockfile、Makefile、pytest、ruff、strict mypy。
- CI 已設定 macOS / Linux / Windows；尚未確認遠端執行結果。
- M1-prep：spike 指令及三份官方錄影驗證、來源 URL 與 SHA-256。
- M1 初版：Pydantic schema、ReplayParser Protocol、mgz adapter、parse CLI。
- Replay collector：以 game/profile ID 下載官方暫存 Replay、解 ZIP、雜湊與本機 manifest。
- Corpus audit：批次統計 parser、版本、解析狀態、unknown 與 player attribution coverage。
- M1.2 初版：保守的 command timing 與 raw APM；不推測完成時間或 eAPM。
- Parser fallback：mgz failed 時改用 aoe2rec-py；舊版可解析 Replay 維持 mgz 行為。
- M1.3：兩場 Replay structured diff、顯著門檻、最早偏差與非因果 downstream differences。
- M1.4 foundation：CoachProvider contract、rule-based baseline、結構化 evidence 與 grounding validator。
- JSON 保留指令毫秒時間、原始 payload、來源與版本，以及 ok / partial / failed 狀態。

## 本次盤點驗證

`ruff`、格式、strict mypy 與 pytest 全部通過；34 項測試通過，總覆蓋率 85%。
三份真實錄影的先前驗證為 2 份 ok、1 份 partial，詳見 parse-results.json。
本次未重新執行三份錄影解析。

## 尚未完成

1. M1.1 初版 timeline 已完成：玩家篩選、排序、JSON／文字輸出、完整度與未知歸屬警告；名稱對照已加入，細部分類待補。
2. M1.2 後續：軍事單位分類與更多可可靠計算的指標。
3. M1.3 已完成初版；仍需以真實同類對局驗證 threshold 與指標解讀。
4. M1.4 後續：實際 LLM provider、structured-output integration 與 AI eval dataset。

## 已知限制

- 已有 parser fallback，但沒有獨立版本路由、相容性白名單或完整最新版本 corpus。
- 已加入 aocref 名稱對照與來源版本，未知 ID 保留空名稱；CHAT 尚未歸屬玩家。
- 建造、生產、研究都是指令時間，不是完成時間。
- ORDER 不能直接當成攻擊；部分解析可能缺失生產等操作。
- 目前 adapter 共用 spike 解析流程；mgz.model 讀取 metadata 時會再解析一次檔案。
- 未在遊戲內人工核對結果。原始 PLAN.MD 含尚未落實的草案，以現有程式與 README 為準。

Replay、解析大檔和 .venv 留在本機，不納入 Git；樣本可依 replay-sources.json 重新下載。

M1.1 已另以 de-66.6 真實 Replay 驗證玩家 1 的 JSON 時間線。
