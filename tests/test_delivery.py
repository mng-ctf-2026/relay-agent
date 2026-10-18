"""Tests for delivery planning without a transport service."""

from dataclasses import FrozenInstanceError, asdict
from pathlib import Path
import unittest

from relay_agent.delivery import DEFAULT_DESTINATION, DeliveryPlan, PlannedFile


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


if __name__ == "__main__":
    unittest.main()
