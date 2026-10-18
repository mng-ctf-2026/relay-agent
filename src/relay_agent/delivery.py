"""Describe delivery work for a separate transport component."""

from dataclasses import dataclass
from collections.abc import Iterable
from pathlib import Path
import json
import stat
import unicodedata

from relay_agent import config


DEFAULT_DESTINATION = "https://drop-storage-gw-ctf.t-tlab.com/"


@dataclass(frozen=True)
class PlannedFile:
    """Local source and metadata needed by a delivery adapter."""

    source: Path
    name: str
    size_bytes: int


@dataclass(frozen=True)
class DeliveryPlan:
    """An ordered batch of files, without transport credentials."""

    files: tuple[PlannedFile, ...]
    destination: str = DEFAULT_DESTINATION


def build_delivery_plan(paths: Iterable[str | Path]) -> DeliveryPlan:
    """Collect a snapshot of file metadata without reading file contents.

    A delivery adapter must recheck files before using this snapshot because
    local files may change after planning. Inputs must be a nonempty iterable
    with at most config.MAX_BATCH_FILES entries.
    """
    if isinstance(paths, (str, Path)):
        raise TypeError("Pass an iterable of paths, not a single path")
    files = []
    for path in paths:
        if len(files) >= config.MAX_BATCH_FILES:
            raise ValueError(f"Batch exceeds the limit of {config.MAX_BATCH_FILES} files")
        source = Path(path).resolve(strict=True)
        metadata = source.stat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"Expected a regular file: {source}")
        name = unicodedata.normalize("NFC", source.name)
        files.append(PlannedFile(source, name, metadata.st_size))
    if not files:
        raise ValueError("At least one file is required")
    return DeliveryPlan(tuple(files))


def delivery_plan_to_json(plan: DeliveryPlan) -> str:
    """Serialize delivery metadata as JSON, preserving Unicode filenames.

    Source paths use the local platform's spelling. This only returns a string;
    it does not access files or contact the destination.
    """
    payload = {
        "destination": plan.destination,
        "files": [
            {
                "source": str(item.source),
                "name": item.name,
                "size_bytes": item.size_bytes,
            }
            for item in plan.files
        ],
    }
    return json.dumps(payload, ensure_ascii=False)
