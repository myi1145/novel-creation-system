import unittest

from tests.run_stage_acceptance import build_execution_plan


class StageAcceptanceEntryTest(unittest.TestCase):
    def test_core_plan_should_only_include_core_suite(self):
        plan = build_execution_plan("core")
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0][0], "core")
        self.assertGreaterEqual(len(plan[0][1]), 1)

    def test_all_plan_should_keep_layered_suite_order(self):
        plan = build_execution_plan("all")
        self.assertEqual([item[0] for item in plan], ["core", "real-smoke", "real-acceptance"])
        self.assertGreaterEqual(len(plan[0][1]), 1)
        self.assertGreaterEqual(len(plan[1][1]), 1)
        self.assertGreaterEqual(len(plan[2][1]), 1)


if __name__ == "__main__":
    unittest.main()
