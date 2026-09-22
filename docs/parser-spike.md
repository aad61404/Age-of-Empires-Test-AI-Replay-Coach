# Parser spike 驗證報告

環境：macOS arm64、Python 3.12.9、mgz 1.8.51。
來源：[aoc-mgz 官方測試資料](https://github.com/happyleavesaoc/aoc-mgz/tree/9c1e9cc93998887a56f336dc4489555f4ad5577a/tests/recs)。
下載 URL、SHA-256 見 replay-sources.json；完整統計見 spike-results.json。
原始錄影與 operation dump 留在本機 replays/，不提交 Git。

| 樣本 | 地圖 | 遊戲秒數 | Action 數 | 結果 |
|---|---|---:|---:|---|
| de-63.0 | Arena | 1408.873 | 2337 | partial：223 個 ERROR actions |
| de-66.3 | Arabia | 2875.892 | 9695 | ok |
| de-66.6 | Arena | 2220.129 | 3333 | ok |

三份均成功取得玩家、文明、地圖與版本；ok 表示 parser 掃描至檔案邊界且沒有回報解碼錯誤，
不代表每個操作語意已驗證，也不代表比賽一定完整。尚未在遊戲內比對時間，亦未驗證最新遊戲版本。

## 已確認與模型修訂方向

- SYNC payload[0] 是毫秒增量；使用遊戲時間，無須再套用 speed 倍率。
- BUILD、RESEARCH、MOVE、RESIGN 均有樣本；保留 player_id、entity ID 和原始 payload。
- 生產在 66.3/66.6 樣本為 DE_QUEUE（710 / 309 次），代表排隊指令，不代表單位完成。
- 63.0 沒有成功解碼的 queue 操作，且有 223 個 ERROR；不可推論玩家沒有生產。
- ORDER 為一般目標指令，不能一律轉成 ATTACK；DE_ATTACK_MOVE 也只是移動攻擊指令。
- CHAT 是獨立 operation，不能只從 ACTION 中取聊天。
- RESEARCH 是研究指令時間，不能直接宣稱為升級完成時間或用來計算黑暗時代持續時間。
- 保留未知與 ERROR 操作，輸出 partial 狀態；禁止靜默截斷後宣告成功。
- mgz.model 也使用 fast parser，不能把它當成獨立 parser 備援；此處僅用於取得可讀 metadata。

## 下一步

以 command-based schema 定義 BUILD_COMMAND、QUEUE_COMMAND、RESEARCH_COMMAND 等事件，
保留原始 action 類型、毫秒與 ID，加入資料完整度欄位。先做正式 parse CLI，再做 timeline。
APM 分母、計數範圍與缺失資料政策需要明確定義；first_attack 暫不根據 ORDER 推算。
