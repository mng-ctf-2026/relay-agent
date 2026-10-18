"""Describe delivery work for a separate transport component."""

from dataclasses import dataclass
from pathlib import Path


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
