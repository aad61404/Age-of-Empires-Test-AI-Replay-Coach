"""Exploratory parser report; deliberately retains raw operation semantics."""

import hashlib
from collections import Counter
from enum import Enum
from importlib.metadata import version
from pathlib import Path
from typing import Any

from mgz import fast  # type: ignore[import-untyped]
from mgz.fast.header import parse as parse_header  # type: ignore[import-untyped]
from mgz.model import get_dataset, parse_match  # type: ignore[import-untyped]


def json_value(value: Any) -> Any:
    """Preserve unknown byte payloads losslessly in exploratory JSON."""
    if isinstance(value, bytes):
        return {"hex": value.hex()}
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    return value


def inspect_replay(path: Path, *, include_all_operations: bool = True) -> dict[str, Any]:
    """Dump operations, reporting parse failures instead of hiding partial data."""
    report: dict[str, Any] = {
        "schema": "aoe2coach.spike.v1",
        "source": {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
        "parser": {"name": "mgz", "package_version": version("mgz")},
        "status": "failed",
        "operations": [],
        "warnings": [
            "Action timestamps describe commands, not completion of training/research/building.",
            "Reaching the file boundary does not prove the recorded match finished.",
        ],
    }
    counts: Counter[str] = Counter()
    actions: Counter[str] = Counter()
    time_ms = 0
    with path.open("rb") as handle:
        try:
            header = parse_header(handle)
            report["parser"].update(
                {
                    k: json_value(header[k])
                    for k in ("version", "game_version", "save_version", "log_version")
                }
            )
            dataset = None
            try:
                dataset_id, dataset = get_dataset(header["version"], header["mod"])
                report["parser"]["dataset_id"] = dataset_id
                report["parser"]["reference_version"] = version("aocref")
            except Exception as exc:
                report["warnings"].append(f"Entity names unavailable: {exc}")
            time_ms = header["map"]["restore_time"]
            fast.meta(handle)
            size = path.stat().st_size
            while handle.tell() < size:
                offset = handle.tell()
                op, payload = fast.operation(handle)
                if op == fast.Operation.SYNC:
                    time_ms += payload[0]
                row = {
                    "offset": offset,
                    "time_ms": time_ms,
                    "operation": op.name,
                    "payload": json_value(payload),
                }
                counts[op.name] += 1
                if op == fast.Operation.ACTION:
                    actions[payload[0].name] += 1
                    if dataset is not None:
                        fields = payload[1]
                        for key, table in (
                            ("building_id", "objects"),
                            ("unit_id", "objects"),
                            ("technology_id", "technologies"),
                        ):
                            if key in fields:
                                row["entity_name"] = dataset[table].get(str(fields[key]))
                                break
                if include_all_operations or op in (fast.Operation.ACTION, fast.Operation.CHAT):
                    report["operations"].append(row)
            report["status"] = "ok"
        except Exception as exc:
            report["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "offset": handle.tell(),
            }
    report["operation_counts"] = dict(counts)
    report["action_counts"] = dict(actions)
    if actions["ERROR"]:
        report["warnings"].append(f"{actions['ERROR']} actions could not be decoded by mgz.")
        if report["status"] == "ok":
            report["status"] = "partial"
    report["last_time_ms"] = time_ms
    if report["status"] in ("ok", "partial"):
        try:
            with path.open("rb") as handle:
                match = parse_match(handle)
            report["match"] = {
                "map": match.map.name,
                "speed": match.speed,
                "duration_seconds": match.duration.total_seconds(),
                "players": [
                    {"id": p.number, "name": p.name, "civilization": p.civilization}
                    for p in match.players
                ],
            }
        except Exception as exc:
            report["status"] = "partial"
            report["metadata_error"] = {"type": type(exc).__name__, "message": str(exc)}
    return report
