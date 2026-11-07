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


if __name__ == "__main__":
    unittest.main()
