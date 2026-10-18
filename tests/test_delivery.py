"""Tests for delivery planning without a transport service."""

from dataclasses import FrozenInstanceError, asdict
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from relay_agent.delivery import (
    DEFAULT_DESTINATION,
    DeliveryPlan,
    PlannedFile,
    build_delivery_plan,
)


class DeliveryPlanTests(unittest.TestCase):
    def test_plan_preserves_file_metadata(self):
        item = PlannedFile(Path("report.pdf"), "report.pdf", 42)
        plan = DeliveryPlan((item,))
        self.assertEqual(plan.destination, DEFAULT_DESTINATION)
        self.assertEqual(plan.files, (item,))
        self.assertEqual(plan.files[0].size_bytes, 42)

    def test_plan_supports_an_explicit_destination(self):
        plan = DeliveryPlan((), "https://archive.example.invalid/v1/files")
        self.assertEqual(plan.destination, "https://archive.example.invalid/v1/files")

    def test_plan_is_immutable_and_contains_only_delivery_metadata(self):
        plan = DeliveryPlan(())
        with self.assertRaises(FrozenInstanceError):
            plan.destination = "changed"
        self.assertEqual(set(asdict(plan)), {"files", "destination"})


class BuildDeliveryPlanTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_collects_metadata_in_input_order(self):
        first = self.root / "report.pdf"
        second = self.root / "notes.txt"
        first.write_bytes(b"example document")
        second.write_bytes(b"notes")
        plan = build_delivery_plan([second, first])
        self.assertEqual(
            plan.files,
            (
                PlannedFile(second.resolve(), "notes.txt", 5),
                PlannedFile(first.resolve(), "report.pdf", 16),
            ),
        )
        self.assertEqual(plan.destination, DEFAULT_DESTINATION)

    def test_accepts_string_paths_from_an_iterator(self):
        source = self.root / "report.pdf"
        source.touch()
        plan = build_delivery_plan(str(path) for path in [source])
        self.assertEqual(plan.files[0].source, source.resolve())

    def test_does_not_open_file_contents(self):
        source = self.root / "report.pdf"
        source.write_bytes(b"example")
        with patch.object(Path, "open", side_effect=AssertionError("Content read")):
            plan = build_delivery_plan([source])
        self.assertEqual(plan.files[0].size_bytes, 7)

    def test_rejects_a_directory(self):
        with self.assertRaisesRegex(ValueError, "Expected a regular file"):
            build_delivery_plan([self.root])

    def test_rejects_a_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            build_delivery_plan([self.root / "missing.pdf"])


if __name__ == "__main__":
    unittest.main()
