"""Download and catalogue best-effort replays from the official replay endpoint."""

import hashlib
import io
import json
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPLAY_URL = "https://aoe.ms/replay/?gameId={game_id}&profileId={profile_id}"
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024


class CollectionError(RuntimeError):
    """A replay could not be downloaded or safely stored."""


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "aoe2coach/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            declared_size = response.headers.get("Content-Length")
            if declared_size is not None and int(declared_size) > MAX_DOWNLOAD_BYTES:
                raise CollectionError("Replay response exceeds the 100 MiB safety limit.")
            data = bytes(response.read(MAX_DOWNLOAD_BYTES + 1))
    except (OSError, urllib.error.URLError) as exc:
        raise CollectionError(f"Replay download failed: {exc}") from exc
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise CollectionError("Replay response exceeds the 100 MiB safety limit.")
    if not data:
        raise CollectionError("Replay endpoint returned an empty response.")
    return data


def _replay_bytes(download: bytes) -> bytes:
    if not zipfile.is_zipfile(io.BytesIO(download)):
        return download
    try:
        with zipfile.ZipFile(io.BytesIO(download)) as archive:
            candidates = [
                info
                for info in archive.infolist()
                if not info.is_dir() and Path(info.filename).suffix.lower() == ".aoe2record"
            ]
            if len(candidates) != 1:
                raise CollectionError(
                    f"Expected one .aoe2record in archive, found {len(candidates)}."
                )
            if candidates[0].file_size > MAX_DOWNLOAD_BYTES:
                raise CollectionError("Replay file exceeds the 100 MiB safety limit.")
            return archive.read(candidates[0])
    except zipfile.BadZipFile as exc:
        raise CollectionError(f"Invalid replay ZIP: {exc}") from exc


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CollectionError(f"Cannot read manifest {path}: {exc}") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise CollectionError(f"Manifest {path} must contain a JSON array of objects.")
    return value


def collect_replay(
    game_id: int,
    profile_id: int,
    destination: Path,
    *,
    downloader: Any = _download,
) -> dict[str, Any]:
    """Download one replay, store it once, and upsert its manifest entry."""
    destination.mkdir(parents=True, exist_ok=True)
    url = REPLAY_URL.format(game_id=game_id, profile_id=profile_id)
    replay = _replay_bytes(downloader(url))
    digest = hashlib.sha256(replay).hexdigest()
    filename = f"game-{game_id}-profile-{profile_id}-{digest[:12]}.aoe2record"
    output = destination / filename
    if not output.exists():
        output.write_bytes(replay)
    elif output.read_bytes() != replay:
        raise CollectionError(f"Existing file does not match downloaded replay: {output}")

    manifest_path = destination / "manifest.json"
    manifest = _load_manifest(manifest_path)
    entry: dict[str, Any] = {
        "game_id": game_id,
        "profile_id": profile_id,
        "file": filename,
        "url": url,
        "sha256": digest,
        "bytes": len(replay),
        "collected_at": datetime.now(UTC).isoformat(),
    }
    manifest = [
        item
        for item in manifest
        if not (item.get("game_id") == game_id and item.get("profile_id") == profile_id)
    ]
    manifest.append(entry)
    manifest.sort(key=lambda item: (int(item["game_id"]), int(item["profile_id"])))
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(manifest_path)
    return entry
