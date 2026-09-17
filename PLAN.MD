# AoE2 Replay Intelligence Pipeline — V1 Implementation Plan

## 核心定義

```
AoE2 Replay Intelligence Pipeline

Replay
  ↓
Version Detector
  ↓
Parser Adapter
  ↓
Normalized Event Model
  ↓
Deterministic Metrics
  ↓
Strategy Diff
  ↓
LLM Explanation
```

V1 是一個純 Python CLI pipeline。不做 Web、不做 DB。

---

## User Review Required

> [!IMPORTANT]
> **Parser 架構定案**
>
> | 角色 | Parser | 備註 |
> |------|--------|------|
> | **Primary** | `aoc-mgz` (PyPI: `mgz`) | fast/full 雙模式 + Summary/Model 抽象，支援 AoE2 DE |
> | **Backup / Future** | `aoe2rec` | DE-only Rust parser，有 Python binding，適合未來大量處理 |
> | **Reference** | `mgz-fast` | AoEInsights fork，精簡實作，不作為 adapter target |
>
> `ReplayParser` Protocol 存在的理由是**隔離第三方 parser 差異**，而非「它們 API 兼容」。
> 每個 adapter 各自負責轉換成我們的 `ParsedReplay` schema。

> [!WARNING]
> **Replay 檔案限制（架構核心決策）**
>
> `.aoe2record` 存儲的是**玩家操作指令流**，不是完整 Game State。
> - ✅ 可取得：BUILD / TRAIN / RESEARCH / MOVE / ATTACK / RESIGN / CHAT 的 action 和時間戳
> - ✅ 可取得：Player / Civilization / Map / Game Settings
> - ❌ 無法直接取得：任意時間點精確資源量、Unit HP、Fog of War
> - ❌ 自行 reconstruct economy / unit state 會有 drift
>
> **V1 只做 Action-based 分析。此決策不可動搖。**

> [!IMPORTANT]
> **Parser Compatibility 是作品展示重點**
>
> 2026 年 2 月 AoE2 DE 更新曾導致 `aoc-mgz` 因 replay header format 變更而解析失敗。
> 因此 V1 將 parser compatibility 作為正式 architecture feature：
> - Version Detector 識別 replay 版本
> - Parser Adapter 選擇對應 parser
> - Output JSON 包含 parser metadata
> - Graceful degradation：primary 失敗時嘗試 backup

---

## 開發工具（直接確認）

| 工具 | 版本 / 備註 |
|------|------------|
| Python | 3.12+ |
| Package Manager | `uv` |
| Testing | `pytest` + `pytest-cov` |
| Linting | `ruff` |
| Type Check | `mypy` (strict) |
| Data Model | `pydantic` v2 |
| CLI | `typer` |
| Parser | `aoc-mgz` (PyPI: `mgz`) |
| AI Provider | TBD — Protocol interface 先行 |

---

## Milestones

```
Milestone 0 ── Repo + uv + pytest + ruff
     ↓
Milestone 1 ── Real .aoe2record → aoc-mgz → Normalized JSON
     ↓
Milestone 1.1 ── Timeline (Age / Build / Train / Research / Action / Resign)
     ↓
Milestone 1.2 ── Metrics (APM / Age timing / First building / First military / First attack)
     ↓
Milestone 1.3 ── Replay A vs Replay B → Structured Diff
     ↓
Milestone 1.4 ── LLM Explanation
```

### V1 明確不做

| 砍掉 | 原因 |
|------|------|
| PostgreSQL | V2 再加，V1 純 JSON |
| FastAPI | V2 再加，V1 純 CLI |
| Next.js | V2 再加 |
| Playwright | 沒有 Web 就不需要 |
| Tool Calling | AI Provider 未定，Protocol 先行 |
| 高 Elo benchmark dataset | V3 |
| Build-order knowledge base | V3 |
| eAPM | 需先定義 `is_effective_action()`，V1 只做 APM |

---

## Proposed Changes

---

### Milestone 0：Repository Foundation

#### [NEW] 目錄結構

```
Age-of-Empires-Test-AI-Replay-Coach/
├── .github/
│   └── workflows/
│       └── ci.yml
├── backend/
│   ├── pyproject.toml
│   ├── src/
│   │   └── aoe2coach/
│   │       ├── __init__.py
│   │       ├── parser/
│   │       │   ├── __init__.py
│   │       │   ├── protocol.py        # ReplayParser Protocol
│   │       │   ├── models.py          # Pydantic data models
│   │       │   ├── version_detector.py # Replay version detection
│   │       │   └── adapters/
│   │       │       ├── __init__.py
│   │       │       └── aoc_mgz.py     # aoc-mgz adapter
│   │       ├── analyzer/
│   │       │   ├── __init__.py
│   │       │   ├── timeline.py        # M1.1: Timeline extraction
│   │       │   ├── metrics.py         # M1.2: Deterministic metrics
│   │       │   └── diff.py            # M1.3: Strategy Diff
│   │       ├── ai/
│   │       │   ├── __init__.py
│   │       │   ├── protocol.py        # CoachProvider Protocol
│   │       │   └── coach.py           # M1.4: LLM Coach
│   │       └── cli/
│   │           ├── __init__.py
│   │           └── main.py
│   └── tests/
│       ├── conftest.py
│       ├── fixtures/
│       ├── test_parser.py
│       ├── test_timeline.py
│       ├── test_metrics.py
│       ├── test_diff.py
│       └── test_cli.py
├── replays/                            # .gitignored, real replays
│   └── .gitkeep
├── .gitignore
├── .env.example
├── Makefile
└── README.md
```

#### [NEW] [pyproject.toml](file:///c:/Work/Age-of-Empires-Test-AI-Replay-Coach/backend/pyproject.toml)

```toml
[project]
name = "aoe2coach"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "mgz>=1.8",
    "pydantic>=2.0",
    "typer>=0.12",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.5",
    "mypy>=1.10",
]
ai = [
    # AI provider SDKs — added when provider is chosen
]

[project.scripts]
aoe2coach = "aoe2coach.cli.main:app"
```

#### [NEW] [Makefile](file:///c:/Work/Age-of-Empires-Test-AI-Replay-Coach/Makefile)

```makefile
install:
	cd backend && uv sync --all-extras

test:
	cd backend && uv run pytest -v --cov=aoe2coach

lint:
	cd backend && uv run ruff check src/ tests/
	cd backend && uv run ruff format --check src/ tests/

typecheck:
	cd backend && uv run mypy src/

parse:
	cd backend && uv run aoe2coach parse $(REPLAY)
```

---

### Milestone 1：Replay Parser → Normalized JSON

**Deliverable：一個真實 .aoe2record → Python CLI → JSON**

#### [NEW] [models.py](file:///c:/Work/Age-of-Empires-Test-AI-Replay-Coach/backend/src/aoe2coach/parser/models.py)

```python
from enum import Enum
from pydantic import BaseModel

class EventType(str, Enum):
    BUILD    = "BUILD"
    TRAIN    = "TRAIN"
    RESEARCH = "RESEARCH"
    MOVE     = "MOVE"
    ATTACK   = "ATTACK"
    AGE_UP   = "AGE_UP"
    RESIGN   = "RESIGN"
    CHAT     = "CHAT"

class GameEvent(BaseModel):
    time: int              # Game time in seconds
    player_id: int
    type: EventType
    entity: str            # Human-readable: "Barracks", "Feudal Age", "Knight"
    details: dict = {}

class PlayerInfo(BaseModel):
    player_id: int
    name: str
    civilization: str
    team: int | None = None
    winner: bool | None = None
    color_id: int | None = None

class MatchInfo(BaseModel):
    map_name: str
    duration: int          # Total game time in seconds
    game_speed: str
    map_size: str | None = None
    game_type: str | None = None

class ParserMeta(BaseModel):
    """Parser 和 Replay 的 metadata，用於 compatibility tracking。"""
    parser_name: str       # e.g. "aoc-mgz"
    parser_version: str    # e.g. "1.8.2"
    game_version: str      # e.g. "DE"
    save_version: float | None = None  # e.g. 68.0

class ParsedReplay(BaseModel):
    parser: ParserMeta
    match: MatchInfo
    players: list[PlayerInfo]
    events: list[GameEvent]
```

> [!NOTE]
> **`ParserMeta` 是 V1 的作品展示重點之一**。每次 output 都帶 parser 版本和 replay 版本資訊，
> 讓下游消費者知道資料來源和可靠性。當 AoE2 patch 導致 parser 失效時，這個 metadata 可以用來
> 判斷哪些已解析的資料需要重新處理。

#### [NEW] [protocol.py](file:///c:/Work/Age-of-Empires-Test-AI-Replay-Coach/backend/src/aoe2coach/parser/protocol.py) — Parser Protocol

```python
from typing import Protocol
from pathlib import Path

class ReplayParser(Protocol):
    """Protocol for replay parsers.
    
    存在理由：隔離第三方 parser 差異。
    每個 adapter 各自負責將 parser-specific output 轉換為 ParsedReplay schema。
    
    AoE2 patch 可能隨時改變 replay format，導致某個 parser 暫時失效。
    透過 Protocol + 多個 adapter，系統可以 graceful degradation。
    """
    def parse(self, file_path: Path) -> ParsedReplay: ...
    def can_parse(self, file_path: Path) -> bool: ...
```

#### [NEW] [version_detector.py](file:///c:/Work/Age-of-Empires-Test-AI-Replay-Coach/backend/src/aoe2coach/parser/version_detector.py)

```python
class ReplayVersion(BaseModel):
    game_version: str         # "DE", "HD", "Conquerors"
    save_version: float | None
    file_extension: str       # ".aoe2record", ".mgz", ".mgx"

class VersionDetector:
    """Detect replay file version before selecting parser adapter.
    
    Pipeline:
        Replay → VersionDetector → Parser Adapter → Normalization
    """
    def detect(self, file_path: Path) -> ReplayVersion: ...
```

#### [NEW] [aoc_mgz.py](file:///c:/Work/Age-of-Empires-Test-AI-Replay-Coach/backend/src/aoe2coach/parser/adapters/aoc_mgz.py) — Primary Adapter

使用 `mgz` 的兩層策略：
1. `mgz.fast.header.parse()` → metadata（Players, Map, Civ, Settings）
2. `mgz.fast.operation()` → 迭代 body operations，過濾 action types
3. Fallback：fast 失敗時嘗試 `mgz.model.parse_match()`

```python
class AocMgzAdapter:
    """aoc-mgz adapter — Primary parser.
    
    Implements ReplayParser protocol.
    Converts mgz-specific data structures to our ParsedReplay schema.
    """
    PARSER_NAME = "aoc-mgz"
    
    def parse(self, file_path: Path) -> ParsedReplay:
        with open(file_path, 'rb') as f:
            eof = os.fstat(f.fileno()).st_size
            header = parse_header(f)
            meta(f)
            
            events = []
            current_time = 0
            
            while f.tell() < eof:
                try:
                    op_type, payload = operation(f)
                    if op_type == Operation.SYNC:
                        current_time += payload
                    elif op_type == Operation.ACTION:
                        event = self._convert_action(current_time, payload)
                        if event:
                            events.append(event)
                except Exception:
                    break
            
            return ParsedReplay(
                parser=ParserMeta(
                    parser_name=self.PARSER_NAME,
                    parser_version=mgz.__version__,
                    game_version=self._detect_game_version(header),
                    save_version=header.get('save_version'),
                ),
                match=self._extract_match(header),
                players=self._extract_players(header),
                events=sorted(events, key=lambda e: e.time),
            )
```

> [!WARNING]
> **Game Time 計算**：SYNC operation 推進遊戲時鐘。時間單位需根據 game speed 轉換。
> AoE2 DE "Normal" = 1.0x, "Fast" = 1.5x, "Very Fast" = 2.0x。
> V1 先以遊戲內顯示時間為準，不做 real-time 轉換。

#### [NEW] [main.py](file:///c:/Work/Age-of-Empires-Test-AI-Replay-Coach/backend/src/aoe2coach/cli/main.py) — CLI

```bash
# Milestone 1: Parse
aoe2coach parse replays/test_game.aoe2record
aoe2coach parse replays/test_game.aoe2record --output pretty
aoe2coach parse replays/test_game.aoe2record -o output.json

# Milestone 1.1: Timeline
aoe2coach timeline replays/test_game.aoe2record --player 1

# Milestone 1.2: Metrics
aoe2coach metrics replays/test_game.aoe2record --player 1

# Milestone 1.3: Diff
aoe2coach diff replay_a.aoe2record replay_b.aoe2record --player 1

# Milestone 1.4: Coach
aoe2coach coach replay_a.aoe2record --vs replay_b.aoe2record --player 1
```

**Milestone 1 output 範例（含 parser metadata）：**

```json
{
  "parser": {
    "parser_name": "aoc-mgz",
    "parser_version": "1.8.2",
    "game_version": "DE",
    "save_version": 68.0
  },
  "match": {
    "map_name": "Arabia",
    "duration": 1520,
    "game_speed": "Normal"
  },
  "players": [
    {"player_id": 1, "name": "Player1", "civilization": "Franks", "winner": true},
    {"player_id": 2, "name": "Player2", "civilization": "Britons", "winner": false}
  ],
  "events": [
    {"time": 430, "player_id": 1, "type": "BUILD",    "entity": "Barracks",      "details": {}},
    {"time": 522, "player_id": 1, "type": "RESEARCH",  "entity": "Feudal Age",    "details": {}},
    {"time": 645, "player_id": 1, "type": "BUILD",    "entity": "Stable",        "details": {}},
    {"time": 710, "player_id": 1, "type": "TRAIN",    "entity": "Scout Cavalry", "details": {"count": 1}}
  ]
}
```

---

### Milestone 1.1：Timeline

#### [NEW] [timeline.py](file:///c:/Work/Age-of-Empires-Test-AI-Replay-Coach/backend/src/aoe2coach/analyzer/timeline.py)

從 `ParsedReplay` 中按 player 和 event type 組織時間線。

```python
class PlayerTimeline(BaseModel):
    player_id: int
    player_name: str
    civilization: str
    age_ups: list[GameEvent]       # Feudal / Castle / Imperial
    buildings: list[GameEvent]     # All BUILD events, sorted by time
    researches: list[GameEvent]    # All RESEARCH events
    military_production: list[GameEvent]  # All TRAIN events (military)
    actions: list[GameEvent]       # All MOVE / ATTACK events
    resign: GameEvent | None

class TimelineExtractor:
    def extract(self, replay: ParsedReplay, player_id: int) -> PlayerTimeline: ...
    def extract_all(self, replay: ParsedReplay) -> list[PlayerTimeline]: ...
```

---

### Milestone 1.2：Deterministic Metrics

#### [NEW] [metrics.py](file:///c:/Work/Age-of-Empires-Test-AI-Replay-Coach/backend/src/aoe2coach/analyzer/metrics.py)

從 `PlayerTimeline` 計算確定性指標。

| 指標 | 計算方式 | 備註 |
|------|---------|------|
| `apm` | 總 action 數 / 遊戲時長（分鐘） | **不是 eAPM**，V1 不過濾 effective |
| `feudal_time` | `RESEARCH "Feudal Age"` 的 `time` | |
| `castle_time` | `RESEARCH "Castle Age"` 的 `time` | |
| `imperial_time` | `RESEARCH "Imperial Age"` 的 `time` | |
| `dark_age_duration` | `feudal_time - 0` | |
| `first_barracks` | 第一個 `BUILD "Barracks"` 的 `time` | |
| `first_stable` | 第一個 `BUILD "Stable"` 的 `time` | |
| `first_archery_range` | 第一個 `BUILD "Archery Range"` 的 `time` | |
| `first_military_unit` | 第一個 `TRAIN` 軍事單位的 `time` | 需定義 military unit list |
| `first_attack` | 第一個 `ATTACK` 的 `time` | |
| `resign_time` | `RESIGN` 的 `time` | |

```python
class PlayerMetrics(BaseModel):
    player_id: int
    apm: float                          # Actions Per Minute（不是 eAPM）
    feudal_time: int | None
    castle_time: int | None
    imperial_time: int | None
    dark_age_duration: int | None
    first_barracks: int | None
    first_stable: int | None
    first_archery_range: int | None
    first_military_unit: int | None
    first_attack: int | None
    resign_time: int | None

class MetricsCalculator:
    def calculate(self, timeline: PlayerTimeline) -> PlayerMetrics: ...
```

> [!IMPORTANT]
> **APM vs eAPM**
>
> V1 的 `apm` = `total_actions / game_minutes`。這是純粹的 APM。
>
> eAPM（Effective APM）需要先定義 `is_effective_action(action)` 過濾規則：
> - 排除 selection spam
> - 排除重複 rapid duplicate commands
> - 排除無效 move
>
> 等我們對 action stream 有足夠理解後，V2 再加 eAPM。

---

### Milestone 1.3：Strategy Diff

#### [NEW] [diff.py](file:///c:/Work/Age-of-Empires-Test-AI-Replay-Coach/backend/src/aoe2coach/analyzer/diff.py)

```python
class MetricDelta(BaseModel):
    metric: str
    value_a: int | float | None
    value_b: int | float | None
    delta: int | float | None      # value_a - value_b
    unit: str                       # "seconds" | "apm"

class DiffResult(BaseModel):
    player_a: str
    player_b: str
    deltas: list[MetricDelta]
    earliest_significant_deviation: str | None
    downstream_differences: list[str]

class StrategyDiff:
    SIGNIFICANCE_THRESHOLD: int = 30  # seconds
    
    def diff(self, metrics_a: PlayerMetrics, metrics_b: PlayerMetrics) -> DiffResult:
        """Compare two player metrics.
        
        NOT causal inference.
        
        Output:
        - deltas: 每個指標的差異
        - earliest_significant_deviation: 時間最早且差異超過 threshold 的指標
        - downstream_differences: 時間晚於 earliest_significant_deviation 且也有差異的指標
        
        LLM 可以建議「值得檢查是否源自較晚的 Feudal transition」，
        但系統不直接斷言因果關係。
        """
```

> [!IMPORTANT]
> **Correlation ≠ Causality**
>
> V1 的 Diff Engine 只輸出：
> - `earliest_significant_deviation`：時間最早的顯著偏差
> - `downstream_differences`：時間晚於偏差起點且也有差異的指標
>
> **不做因果推論**。不會說「Feudal 慢導致 Stable 慢」。
>
> LLM 可以在解釋時說「後續 Stable / Scout timing 也出現延遲，值得檢查是否源自較晚的 Feudal transition」，
> 但措辭是建議性的，不是斷言性的。

**Diff output 範例：**

```json
{
  "player_a": "Player1 (Franks)",
  "player_b": "Benchmark (Franks)",
  "deltas": [
    {"metric": "feudal_time",   "value_a": 645, "value_b": 592, "delta": 53,  "unit": "seconds"},
    {"metric": "first_stable",  "value_a": 695, "value_b": 630, "delta": 65,  "unit": "seconds"},
    {"metric": "first_military_unit", "value_a": 730, "value_b": 660, "delta": 70, "unit": "seconds"},
    {"metric": "apm",           "value_a": 32,  "value_b": 45,  "delta": -13, "unit": "apm"}
  ],
  "earliest_significant_deviation": "feudal_time",
  "downstream_differences": ["first_stable", "first_military_unit"]
}
```

---

### Milestone 1.4：LLM Explanation

#### [NEW] [ai/protocol.py](file:///c:/Work/Age-of-Empires-Test-AI-Replay-Coach/backend/src/aoe2coach/ai/protocol.py)

```python
class CoachProvider(Protocol):
    """Protocol for AI coach providers.
    
    AI Provider 未定，先用 Protocol 隔離。
    等 Diff Engine 穩定後再選定 provider 和 SDK。
    """
    async def explain(self, diff: DiffResult, context: MatchContext) -> CoachingReport: ...
```

#### [NEW] [ai/coach.py](file:///c:/Work/Age-of-Empires-Test-AI-Replay-Coach/backend/src/aoe2coach/ai/coach.py)

**三層 input 結構（不在 prompt 裡硬塞 domain knowledge）：**

```python
class MatchContext(BaseModel):
    """LLM 接收的結構化 context，三層分離。"""
    
    # Layer 1: Replay Facts — 從 replay 直接提取的確定性事實
    replay_facts: dict  # PlayerMetrics, Timeline, Match info
    
    # Layer 2: Benchmark Facts — 外部參考數據（V1 可以是另一場 replay）
    benchmark_facts: dict | None  # 對照組的 metrics
    
    # Layer 3: Diff — 計算出的結構化差異
    diff: DiffResult | None

class CoachingReport(BaseModel):
    summary: str                        # 一句話總結
    key_observations: list[str]         # 主要觀察
    suggested_improvements: list[str]   # 優先改善項目
    reasoning: str                      # LLM 的推理過程
```

> [!IMPORTANT]
> **LLM 只做最後解釋**
>
> ```
> Replay Facts  ─┐
>                 ├──→ LLM ──→ Explanation
> Benchmark Facts ┤
>                 │
> Diff Result    ─┘
> ```
>
> LLM 不硬塞「各文明特色」「常見 build order」「timing benchmark」。
> 這些要嘛從外部 benchmark 資料帶入（Layer 2），要嘛讓 LLM 用自身知識補充，
> 但系統必須清楚標示哪些是 replay fact、哪些是 benchmark、哪些是 LLM reasoning。

---

## Architecture Diagram

```mermaid
graph TB
    subgraph "Input"
        A[".aoe2record"]
    end
    
    subgraph "Version Detection"
        VD["VersionDetector"]
    end
    
    subgraph "Parser Layer"
        P["ReplayParser Protocol"]
        PA["AocMgzAdapter (Primary)"]
        PB["Aoe2RecAdapter (Future)"]
        P --> PA
        P --> PB
    end
    
    subgraph "Data Models"
        PM["ParserMeta"]
        MI["MatchInfo"]
        PI["PlayerInfo[]"]
        GE["GameEvent[]"]
        PR["ParsedReplay"]
        PR --> PM
        PR --> MI
        PR --> PI
        PR --> GE
    end
    
    subgraph "Analysis Pipeline"
        TL["TimelineExtractor (M1.1)"]
        MC["MetricsCalculator (M1.2)"]
        SD["StrategyDiff (M1.3)"]
    end
    
    subgraph "AI Layer"
        CP["CoachProvider Protocol"]
        AC["AICoach (M1.4)"]
        CP --> AC
    end
    
    subgraph "CLI"
        CLI["typer CLI"]
    end
    
    A --> VD
    VD --> P
    PA --> PR
    PR --> TL
    TL --> MC
    MC --> SD
    SD --> AC
    CLI --> VD
```

---

## Verification Plan

### Automated Tests

```bash
# Milestone 0
make install       # uv sync works
make lint          # ruff passes
make typecheck     # mypy passes

# Milestone 1
pytest tests/test_parser.py -v
aoe2coach parse replays/test_game.aoe2record     # Smoke test real file

# Milestone 1.1
pytest tests/test_timeline.py -v

# Milestone 1.2
pytest tests/test_metrics.py -v
aoe2coach metrics replays/test_game.aoe2record --player 1

# Milestone 1.3
pytest tests/test_diff.py -v
aoe2coach diff replays/game_a.aoe2record replays/game_b.aoe2record --player 1

# Milestone 1.4
pytest tests/test_cli.py -v     # End-to-end
```

### Manual Verification

1. **最優先**：拿 2～5 個真實 `.aoe2record` 跑 parser，驗證到底能穩定 extract 哪些 event
2. **Parser output**：比對 JSON 中的 Player / Map / Civ 是否與遊戲內結果一致
3. **Timeline**：檢查 Age-up timing 是否與遊戲內統計畫面吻合
4. **Diff**：手動比較兩場 Replay 的 diff output 是否合理
5. **AI Coach**：閱讀 LLM 建議，確認是否基於正確的 replay facts 且措辭非斷言式

### 關鍵驗證（Milestone 1 前必須完成）

> [!IMPORTANT]
> 目前最該做的不是寫 code，而是拿 **2～5 個真實 `.aoe2record`**，驗證 `aoc-mgz` 到底能穩定
> extract 哪些 event type。那一步做完，V1 schema 才真正能定稿。
>
> 建議流程：
> 1. 準備 2～5 個真實 replay 檔（自己打 AI 對戰 + 從公開來源下載）
> 2. 寫一個 spike script 用 `mgz` 解析，dump 所有 operation 和 action
> 3. 確認哪些 event type 可以穩定取得，哪些有缺失
> 4. 根據結果回來修 `EventType` enum 和 `models.py`

---

## Implementation Order

| Step | Milestone | 內容 | Deliverable |
|------|-----------|------|------------|
| 1 | M0 | Repo + pyproject.toml + .gitignore + Makefile + CI | `make install && make lint` 通過 |
| 2 | M1-prep | **Spike script**：用真實 replay 驗證 mgz 能 extract 哪些 event | 確認 schema 可行性 |
| 3 | M1a | Pydantic models + Parser Protocol + VersionDetector | 資料模型定義 |
| 4 | M1b | AocMgzAdapter 實作 | 可解析真實 replay |
| 5 | M1c | CLI `parse` 指令 | **M1 達成：CLI → JSON** |
| 6 | M1d | Parser unit tests | 測試覆蓋 |
| 7 | M1.1 | TimelineExtractor + CLI `timeline` | Timeline 可用 |
| 8 | M1.2 | MetricsCalculator + CLI `metrics` | Metrics 可用 |
| 9 | M1.3 | StrategyDiff + CLI `diff` | **Diff 可用** |
| 10 | M1.4 | CoachProvider Protocol + AICoach + CLI `coach` | **LLM 解釋可用** |

---

## 後續版本路線

```
V1.x ─── 本 Plan（Parser + CLI + Metrics + Diff + LLM）
V2.0 ─── FastAPI Backend + Next.js Frontend + PostgreSQL
V2.1 ─── Build Order Detection + Strategy Classification
V2.2 ─── eAPM（定義 is_effective_action 後）
V3.0 ─── 高 Elo Benchmark Dataset + 同文明/地圖比較
V4.0 ─── Economic Reconstruction + Advanced Timeline
V5.0 ─── AI Personal Coach（追蹤 20 場 + recurring mistakes）
```
