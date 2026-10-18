"""Describe delivery work for a separate transport component."""

from dataclasses import dataclass
from collections.abc import Iterable
from pathlib import Path
import stat

from relay_agent import config


DEFAULT_DESTINATION = "https://ingest.corp-relay.example/v1/files"


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
        files.append(PlannedFile(source, source.name, metadata.st_size))
    if not files:
        raise ValueError("At least one file is required")
    return DeliveryPlan(tuple(files))
