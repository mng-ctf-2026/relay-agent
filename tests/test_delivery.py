"""Tests for delivery planning without a transport service."""

from dataclasses import FrozenInstanceError, asdict
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from relay_agent import config
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

    def test_normalizes_decomposed_filenames_to_nfc(self):
        for original, expected in (
            ("cafe\u0301.pdf", "caf\u00e9.pdf"),
            ("\u304b\u3099.pdf", "\u304c.pdf"),
        ):
            with self.subTest(original=original):
                source = self.root / original
                source.write_bytes(b"example")
                item = build_delivery_plan([source]).files[0]
                self.assertEqual(item.name, expected)
                self.assertEqual(item.source, source.resolve())
                self.assertEqual(item.size_bytes, 7)
                self.assertTrue(source.is_file())

    def test_preserves_already_normalized_filenames(self):
        source = self.root / "caf\u00e9.pdf"
        source.touch()
        item = build_delivery_plan([source]).files[0]
        self.assertEqual(item.name, source.name)

    def test_preserves_compatibility_characters(self):
        source = self.root / "\uff21-report.pdf"
        source.touch()
        item = build_delivery_plan([source]).files[0]
        self.assertEqual(item.name, "\uff21-report.pdf")

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

    def test_rejects_an_empty_batch(self):
        with self.assertRaisesRegex(ValueError, "At least one file"):
            build_delivery_plan([])

    def test_rejects_an_empty_iterator(self):
        with self.assertRaisesRegex(ValueError, "At least one file"):
            build_delivery_plan(iter(()))

    def test_rejects_a_single_path_instead_of_a_batch(self):
        for value in ("report.pdf", self.root / "report.pdf"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TypeError, "iterable of paths"):
                    build_delivery_plan(value)

    def test_accepts_a_batch_at_the_limit(self):
        paths = [self.root / f"file-{index}.txt" for index in range(config.MAX_BATCH_FILES)]
        for path in paths:
            path.touch()
        self.assertEqual(len(build_delivery_plan(iter(paths)).files), config.MAX_BATCH_FILES)

    def test_rejects_a_batch_above_the_limit(self):
        paths = [self.root / f"file-{index}.txt" for index in range(config.MAX_BATCH_FILES + 1)]
        for path in paths:
            path.touch()
        with self.assertRaisesRegex(ValueError, "Batch exceeds the limit"):
            build_delivery_plan(iter(paths))

    def test_uses_the_configured_batch_limit(self):
        first = self.root / "first.txt"
        second = self.root / "second.txt"
        first.touch()
        second.touch()
        with patch.object(config, "MAX_BATCH_FILES", 1):
            self.assertEqual(len(build_delivery_plan([first]).files), 1)
            with self.assertRaisesRegex(ValueError, "limit of 1 files"):
                build_delivery_plan([first, second])


if __name__ == "__main__":
    unittest.main()
