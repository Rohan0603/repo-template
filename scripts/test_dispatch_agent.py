import unittest

from dispatch_agent import (
    build_full_label_set,
    decide_dispatch,
    retry_call,
    transition_marker,
)


class TestDispatchAgent(unittest.TestCase):
    def test_worker_ready_is_dispatchable(self):
        decision = decide_dispatch(["worker"], "Ready", "open")
        self.assertEqual(decision, (True, "worker"))

    def test_human_gate_is_not_dispatchable(self):
        decision = decide_dispatch(["chief", "human"], "Blocked", "open")
        self.assertEqual(decision, (False, "human-gate"))

    def test_invalid_route_is_rejected(self):
        decision = decide_dispatch(["chief", "worker"], "Ready", "open")
        self.assertEqual(decision, (False, "invalid-route"))

    def test_label_transition_replaces_only_governance_labels(self):
        labels = build_full_label_set(["bug", "chief", "human"], "worker")
        self.assertEqual(labels, ["bug", "worker"])

    def test_retry_stops_at_success(self):
        attempts = []

        def operation():
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("temporary")
            return "ok"

        self.assertEqual(retry_call(operation, attempts=3, delay_seconds=0), "ok")
        self.assertEqual(len(attempts), 3)

    def test_transition_marker_is_stable(self):
        self.assertEqual(transition_marker(42, "run-7"), "<!-- dispatch:issue-42:run-7 -->")


if __name__ == "__main__":
    unittest.main()
