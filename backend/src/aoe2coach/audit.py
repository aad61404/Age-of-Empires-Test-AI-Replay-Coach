"""Batch replay compatibility audit for a local corpus."""

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from aoe2coach.parser.adapter import parse_replay
from aoe2coach.parser.models import Model, ParsedReplay


class AuditEntry(Model):
    file: str
    sha256: str
    status: Literal["ok", "partial", "failed"]
    parser_name: str
    parser_version: str
    game_version: str | None
    save_version: float | None
    event_count: int
    unknown_event_count: int
    assigned_event_count: int
    warning_count: int
    error_type: str | None
    error_message: str | None


class CorpusAudit(Model):
    schema_version: Literal["aoe2coach.audit.v1"] = "aoe2coach.audit.v1"
    root: str
    recursive: bool
    total: int
    ok: int
    partial: int
    failed: int
    parser_counts: dict[str, int]
    game_version_counts: dict[str, int]
    entries: list[AuditEntry]


def audit_corpus(
    root: Path,
    *,
    recursive: bool = False,
    parser: Callable[[Path], ParsedReplay] = parse_replay,
) -> CorpusAudit:
    """Parse every replay deterministically and summarize compatibility quality."""
    pattern = "**/*.aoe2record" if recursive else "*.aoe2record"
    paths = sorted(root.glob(pattern), key=lambda path: path.as_posix().lower())
    if not paths:
        raise ValueError(f"No .aoe2record files found in {root}")

    entries: list[AuditEntry] = []
    for path in paths:
        replay = parser(path)
        unknown = sum(event.kind == "UNKNOWN" for event in replay.events)
        assigned = sum(event.player_id is not None for event in replay.events)
        entries.append(
            AuditEntry(
                file=path.relative_to(root).as_posix(),
                sha256=replay.source.sha256,
                status=replay.status,
                parser_name=replay.parser.name,
                parser_version=replay.parser.package_version,
                game_version=replay.parser.game_version,
                save_version=replay.parser.save_version,
                event_count=len(replay.events),
                unknown_event_count=unknown,
                assigned_event_count=assigned,
                warning_count=len(replay.warnings),
                error_type=replay.error.type if replay.error is not None else None,
                error_message=replay.error.message if replay.error is not None else None,
            )
        )

    statuses = Counter(entry.status for entry in entries)
    parser_counts = Counter(entry.parser_name for entry in entries)
    game_versions = Counter(entry.game_version or "unknown" for entry in entries)
    return CorpusAudit(
        root=str(root.resolve()),
        recursive=recursive,
        total=len(entries),
        ok=statuses["ok"],
        partial=statuses["partial"],
        failed=statuses["failed"],
        parser_counts=dict(sorted(parser_counts.items())),
        game_version_counts=dict(sorted(game_versions.items())),
        entries=entries,
    )
