"""Run with: cd backend && uv run python ../scripts/build_demo.py REPLAY."""
import sys
from pathlib import Path

from aoe2coach.parser.adapter import AocMgzAdapter

root = Path(__file__).resolve().parents[1]
replay = AocMgzAdapter().parse(Path(sys.argv[1]))
if replay.match is None:
    raise SystemExit("Replay metadata unavailable")
(root / "demo" / "replay.json").write_text(replay.model_dump_json(), encoding="utf-8")
print(f"Demo data ready: {replay.status}, {len(replay.events)} events")
