"""Describe delivery work for a separate transport component."""

from dataclasses import dataclass
from collections.abc import Iterable
from pathlib import Path
import stat


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
    local files may change after planning.
    """
    files = []
    for path in paths:
        source = Path(path).resolve(strict=True)
        metadata = source.stat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"Expected a regular file: {source}")
        files.append(PlannedFile(source, source.name, metadata.st_size))
    return DeliveryPlan(tuple(files))
