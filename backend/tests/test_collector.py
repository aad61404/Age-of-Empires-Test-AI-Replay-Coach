"""Validate replay collection, ZIP handling, deduplication, and failures."""

import io
import json
import zipfile
from pathlib import Path

import pytest

from aoe2coach.collector import CollectionError, collect_replay


def zipped_replay(data: bytes, *, name: str = "match.aoe2record") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, data)
    return buffer.getvalue()


def test_collects_zipped_replay_and_writes_manifest(tmp_path: Path) -> None:
    entry = collect_replay(123, 456, tmp_path, downloader=lambda _: zipped_replay(b"replay"))
    replay = tmp_path / entry["file"]
    assert replay.read_bytes() == b"replay"
    assert entry["game_id"] == 123
    assert entry["profile_id"] == 456
    assert entry["url"].endswith("gameId=123&profileId=456")
    assert json.loads((tmp_path / "manifest.json").read_text()) == [entry]


def test_recollect_upserts_instead_of_duplicating(tmp_path: Path) -> None:
    collect_replay(123, 456, tmp_path, downloader=lambda _: b"replay")
    collect_replay(123, 456, tmp_path, downloader=lambda _: b"replay")
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert len(manifest) == 1
    assert len(list(tmp_path.glob("*.aoe2record"))) == 1


def test_rejects_archive_without_exactly_one_replay(tmp_path: Path) -> None:
    with pytest.raises(CollectionError, match="found 0"):
        collect_replay(123, 456, tmp_path, downloader=lambda _: zipped_replay(b"x", name="x.txt"))


def test_rejects_invalid_manifest(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text("{}")
    with pytest.raises(CollectionError, match="JSON array"):
        collect_replay(123, 456, tmp_path, downloader=lambda _: b"replay")
