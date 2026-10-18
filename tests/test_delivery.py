"""Tests for delivery planning without a transport service."""

from dataclasses import FrozenInstanceError, asdict
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import errno
import os
import stat
import unittest
from unittest.mock import patch

from relay_agent import config
from relay_agent.delivery import (
    DEFAULT_DESTINATION,
    DeliveryPlan,
    PlannedFile,
    build_delivery_plan,
    delivery_plan_to_json,
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


class DeliveryPlanJsonTests(unittest.TestCase):
    def test_serializes_metadata_and_preserves_file_order(self):
        first = PlannedFile(Path("reports") / "report.pdf", "report.pdf", 42)
        second = PlannedFile(Path("notes.txt"), "notes.txt", 0)
        plan = DeliveryPlan((first, second))
        before = asdict(plan)
        payload = json.loads(delivery_plan_to_json(plan))
        self.assertEqual(payload, {
            "destination": DEFAULT_DESTINATION,
            "files": [
                {"source": str(first.source), "name": "report.pdf", "size_bytes": 42},
                {"source": str(second.source), "name": "notes.txt", "size_bytes": 0},
            ],
        })
        self.assertEqual(asdict(plan), before)

    def test_keeps_unicode_filenames_readable(self):
        name = "\u5831\u544a-caf\u00e9.pdf"
        plan = DeliveryPlan((PlannedFile(Path(name), name, 7),))
        output = delivery_plan_to_json(plan)
        self.assertIn(name, output)
        self.assertEqual(json.loads(output)["files"][0]["name"], name)

    def test_escapes_special_characters(self):
        name = 'report"\\\n.txt'
        plan = DeliveryPlan((PlannedFile(Path("report.txt"), name, 1),))
        self.assertEqual(json.loads(delivery_plan_to_json(plan))["files"][0]["name"], name)

    def test_supports_an_empty_plan_and_custom_destination(self):
        destination = "https://archive.example.invalid/v1/files"
        plan = DeliveryPlan((), destination)
        self.assertEqual(json.loads(delivery_plan_to_json(plan)), {
            "destination": destination,
            "files": [],
        })

    def test_does_not_include_adapter_credentials(self):
        plan = DeliveryPlan((PlannedFile(Path("report.pdf"), "report.pdf", 42),))
        with patch.object(config, "DELIVERY_ACCESS_KEY", "adapter-test-secret"):
            output = delivery_plan_to_json(plan)
        self.assertNotIn("adapter-test-secret", output)
        self.assertEqual(set(json.loads(output)), {"destination", "files"})


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
        with self.assertRaisesRegex(ValueError, "Expected a regular file") as caught:
            build_delivery_plan([self.root])
        self.assertIn("input is a directory", str(caught.exception))
        self.assertIn(str(self.root), str(caught.exception))

    def test_rejects_a_missing_file(self):
        source = self.root / "missing.pdf"
        with self.assertRaisesRegex(FileNotFoundError, "Input file does not exist") as caught:
            build_delivery_plan([source])
        self.assertEqual(caught.exception.filename, str(source))
        self.assertEqual(caught.exception.errno, errno.ENOENT)
        self.assertIsInstance(caught.exception.__cause__, FileNotFoundError)

    def test_explains_permission_errors_during_resolution_or_stat(self):
        source = self.root / "restricted.pdf"
        source.touch()
        for operation in ("resolve", "stat"):
            with self.subTest(operation=operation):
                error = PermissionError(errno.EACCES, "Access denied")
                with patch.object(Path, operation, side_effect=error):
                    with self.assertRaisesRegex(PermissionError, "Permission denied while inspecting") as caught:
                        build_delivery_plan([source])
                self.assertEqual(caught.exception.filename, str(source))
                self.assertEqual(caught.exception.errno, errno.EACCES)
                self.assertIs(caught.exception.__cause__, error)

    def test_explains_a_non_directory_parent(self):
        source = self.root / "report.pdf" / "child.txt"
        error = NotADirectoryError(errno.ENOTDIR, "Not a directory")
        with patch.object(Path, "resolve", side_effect=error):
            with self.assertRaisesRegex(NotADirectoryError, "parent component.*not a directory") as caught:
                build_delivery_plan([source])
        self.assertEqual(caught.exception.filename, str(source))
        self.assertEqual(caught.exception.errno, errno.ENOTDIR)
        self.assertIs(caught.exception.__cause__, error)

    def test_explains_special_file_rejection(self):
        source = self.root / "input.pipe"
        metadata = os.stat_result((stat.S_IFIFO, 0, 0, 1, 0, 0, 0, 0, 0, 0))
        with patch.object(Path, "resolve", return_value=source):
            with patch.object(Path, "stat", return_value=metadata):
                with self.assertRaisesRegex(ValueError, "input is a special file") as caught:
                    build_delivery_plan([source])
        self.assertIn(str(source), str(caught.exception))

    def test_explains_a_file_disappearing_after_resolution(self):
        source = self.root / "removed.pdf"
        error = FileNotFoundError(errno.ENOENT, "No such file")
        with patch.object(Path, "resolve", return_value=source):
            with patch.object(Path, "stat", side_effect=error):
                with self.assertRaisesRegex(FileNotFoundError, "Input file does not exist") as caught:
                    build_delivery_plan([source])
        self.assertEqual(caught.exception.filename, str(source))
        self.assertIs(caught.exception.__cause__, error)

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
