"""Describe delivery work for a separate transport component."""

from dataclasses import dataclass
from collections.abc import Iterable
from pathlib import Path
import json
import stat
import unicodedata

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
    with at most config.MAX_BATCH_FILES distinct files. Duplicate files are
    skipped, preserving the first occurrence and its position in the batch.
    """
    if isinstance(paths, (str, Path)):
        raise TypeError("Pass an iterable of paths, not a single path")
    files = []
    seen_files: set[tuple[int, int] | Path] = set()
    for path in paths:
        input_path = Path(path)
        try:
            source = input_path.resolve(strict=True)
            metadata = source.stat()
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                exc.errno, "Input file does not exist", str(input_path)
            ) from exc
        except NotADirectoryError as exc:
            raise NotADirectoryError(
                exc.errno, "A parent component of the input path is not a directory",
                str(input_path),
            ) from exc
        except PermissionError as exc:
            raise PermissionError(
                exc.errno, "Permission denied while inspecting input file",
                str(input_path),
            ) from exc
        if stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"Expected a regular file, but input is a directory: {input_path}")
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"Expected a regular file, but input is a special file: {input_path}")
        # File identity also covers hard links; fall back to the resolved path
        # on filesystems that do not provide a usable inode number.
        identity = (metadata.st_dev, metadata.st_ino) if metadata.st_ino else source
        if identity in seen_files:
            continue
        if len(files) >= config.MAX_BATCH_FILES:
            raise ValueError(f"Batch exceeds the limit of {config.MAX_BATCH_FILES} files")
        name = unicodedata.normalize("NFC", source.name)
        files.append(PlannedFile(source, name, metadata.st_size))
        seen_files.add(identity)
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
