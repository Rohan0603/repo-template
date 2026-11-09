"""Offline invariant tests, no network access or GitHub writes."""
import unittest
from validate_governance import audit

REPO = "owner/project"


def issue(n, labels, state="open"):
    return {"node_id": f"ISSUE_{n}", "number": n, "labels": [{"name": v} for v in labels],
            "state": state, "html_url": f"https://github.com/{REPO}/issues/{n}"}


def item(n, status):
    return {"content": {"id": f"ISSUE_{n}", "repository": {"nameWithOwner": REPO}},
            "fieldValueByName": {"name": status}}


class TestAudit(unittest.TestCase):
    def test_valid_handoffs(self):
        a = audit(REPO,
                  [issue(1, ["chief"]), issue(2, ["worker"]),
                   issue(3, ["chief", "human"]), issue(4, ["chief"], "closed")],
                  [item(1, "Backlog"), item(2, "Ready"),
                   item(3, "Blocked"), item(4, "Done")])
        self.assertEqual(a["violation_count"], 0)

    def test_bad_role_and_status(self):
        a = audit(REPO,
                  [issue(1, ["worker", "chief"]), issue(2, ["human", "worker"]),
                   issue(3, ["chief"])],
                  [item(1, "Ready"), item(2, "In Progress")])
        codes = {v["code"] for v in a["violations"]}
        self.assertTrue({"ROUTE_XOR", "HUMAN_WITHOUT_CHIEF", "PROJECT_MEMBERSHIP",
                         "HUMAN_NOT_BLOCKED"}.issubset(codes))

    def test_closeout_invariants(self):
        a = audit(REPO, [issue(1, ["chief"], "open"), issue(2, ["chief"], "closed")],
                  [item(1, "Done"), item(2, "In Review")])
        codes = {v["code"] for v in a["violations"]}
        self.assertTrue({"UNFINISHED_CLOSEOUT", "PREMATURE_CLOSE"}.issubset(codes))


    def test_unprojected_metadata_bootstrap_is_pending_not_ready(self):
        a = audit(REPO,
                  [issue(1, ["worker", "metadata-bootstrap"]),
                   issue(2, ["chief"])],
                  [item(2, "Backlog")])
        self.assertEqual(a["violation_count"], 0)
        self.assertEqual(a["metadata_bootstrap_pending_count"], 1)
        self.assertEqual(a["metadata_bootstrap_pending"][0]["issue_number"], 1)
        self.assertEqual(a["metadata_bootstrap_pending"][0]["project_items"], 0)
        self.assertIsNone(a["metadata_bootstrap_pending"][0]["project_status"])

    def test_bootstrap_with_project_backlog_is_still_pending(self):
        a = audit(REPO, [issue(1, ["worker", "metadata-bootstrap"])],
                  [item(1, "Backlog")])
        self.assertEqual(a["violation_count"], 0)
        self.assertEqual(a["metadata_bootstrap_pending_count"], 1)
        self.assertEqual(a["metadata_bootstrap_pending"][0]["project_status"], "Backlog")

    def test_bootstrap_with_ready_or_invalid_role_is_rejected(self):
        a = audit(REPO,
                  [issue(1, ["worker", "metadata-bootstrap"]),
                   issue(2, ["chief", "metadata-bootstrap"]),
                   issue(3, ["worker", "metadata-bootstrap"], "closed")],
                  [item(1, "Ready"), item(2, "Backlog")])
        codes = {v["code"] for v in a["violations"]}
        self.assertTrue({"BOOTSTRAP_STATUS", "BOOTSTRAP_ROUTE", "BOOTSTRAP_CLOSED"}
                        .issubset(codes))


if __name__ == "__main__":
    unittest.main()
