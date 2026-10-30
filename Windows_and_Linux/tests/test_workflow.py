import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.workflow import WorkflowController, WorkflowState


class WorkflowControllerTests(unittest.TestCase):
    def setUp(self):
        self.workflow = WorkflowController()
        self.events = []
        self.workflow.run_started.connect(lambda run: self.events.append(("started", run.serial)))
        self.workflow.run_finished.connect(lambda run: self.events.append(("finished", run.serial)))
        self.workflow.run_failed.connect(lambda run: self.events.append(("failed", run.serial)))
        self.workflow.run_cancelled.connect(
            lambda run: self.events.append(("cancelled", run.serial))
        )

    def test_a_run_moves_from_capture_to_review(self):
        run = self.workflow.begin("Proofread")
        self.assertEqual(self.workflow.state, WorkflowState.CAPTURING)
        self.assertEqual(run.serial, 1)

        self.assertTrue(self.workflow.set_original(run.serial, "their going home"))
        self.assertEqual(self.workflow.state, WorkflowState.RUNNING)

        self.assertTrue(self.workflow.finish(run.serial, "they are going home"))
        self.assertEqual(self.workflow.state, WorkflowState.REVIEWING)
        self.assertEqual(self.workflow.last.revised, "they are going home")
        self.assertIsNone(self.workflow.active)
        self.assertEqual(
            self.events,
            [("started", 1), ("finished", 1)],
        )

    def test_a_stale_response_cannot_finish_the_new_run(self):
        first = self.workflow.begin("Proofread")
        self.workflow.cancel()
        second = self.workflow.begin("Rewrite")

        self.assertFalse(self.workflow.finish(first.serial, "old"))
        self.assertEqual(self.workflow.state, WorkflowState.CAPTURING)
        self.assertTrue(self.workflow.finish(second.serial, "new"))
        self.assertEqual(self.workflow.last.revised, "new")

    def test_a_stale_response_cannot_fail_or_set_the_original(self):
        first = self.workflow.begin("Proofread")
        second = self.workflow.begin("Rewrite")

        self.assertFalse(self.workflow.set_original(first.serial, "old"))
        self.assertFalse(self.workflow.fail(first.serial, "old error"))
        self.assertEqual(self.workflow.state, WorkflowState.CAPTURING)
        self.assertEqual(self.workflow.last.serial, second.serial)
        self.assertEqual(self.workflow.last.error, "")

    def test_every_transition_emits_its_state(self):
        states = []
        self.workflow.state_changed.connect(lambda state, run: states.append(state))
        run = self.workflow.begin("Proofread")
        self.workflow.set_original(run.serial, "their going home")
        self.workflow.finish(run.serial, "they are going home")
        self.workflow.dismiss()

        self.assertEqual(
            states,
            ["capturing", "running", "reviewing", "idle"],
        )

    def test_cancel_without_a_run_is_a_no_op(self):
        self.assertIsNone(self.workflow.cancel())
        self.assertEqual(self.workflow.state, WorkflowState.IDLE)

    def test_reset_drops_both_the_active_and_last_run(self):
        run = self.workflow.begin("Rewrite")
        self.workflow.reset()
        self.assertEqual(self.workflow.state, WorkflowState.IDLE)
        self.assertIsNone(self.workflow.active)
        self.assertIsNone(self.workflow.last)
        self.assertFalse(self.workflow.is_current(run.serial))

    def test_cancel_clears_the_active_run_and_keeps_the_last(self):
        run = self.workflow.begin("Concise")
        cancelled = self.workflow.cancel()

        self.assertIs(cancelled, run)
        self.assertTrue(cancelled.cancelled)
        self.assertEqual(self.workflow.state, WorkflowState.CANCELLED)
        self.assertIsNone(self.workflow.active)
        self.assertIs(self.workflow.last, run)
        self.assertFalse(self.workflow.is_current(run.serial))

    def test_failure_records_the_cause(self):
        run = self.workflow.begin("Summary")
        self.assertTrue(self.workflow.fail(run.serial, "Model not available"))
        self.assertEqual(self.workflow.state, WorkflowState.FAILED)
        self.assertEqual(self.workflow.last.error, "Model not available")
        self.assertIn(("failed", run.serial), self.events)

    def test_dismiss_returns_to_idle_without_dropping_history(self):
        run = self.workflow.begin("Rewrite")
        self.workflow.finish(run.serial, "new")
        self.workflow.dismiss()
        self.assertEqual(self.workflow.state, WorkflowState.IDLE)
        self.assertIs(self.workflow.last, run)

    def test_begin_while_a_run_is_active_supersedes_it(self):
        first = self.workflow.begin("Proofread")
        second = self.workflow.begin("Rewrite")
        self.assertGreater(second.serial, first.serial)
        self.assertFalse(self.workflow.is_current(first.serial))
        self.assertTrue(self.workflow.is_current(second.serial))


if __name__ == "__main__":
    unittest.main()
