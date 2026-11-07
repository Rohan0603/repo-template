#!/usr/bin/env python3
"""Read-only GitHub Projects v2 + Issues governance audit (Python 3.10+).

Example:
    python scripts/validate_governance.py --repo OWNER/REPO --project-id PVT_xxxx

Requires GH_TOKEN/GITHUB_TOKEN or an authenticated `gh auth token` with access to
repository Issues and the selected GitHub Project. Never modifies GitHub data.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

ALLOWED_STATUSES = {"Backlog", "Ready", "In Progress", "Blocked", "In Review", "Done", "Canceled"}
GRAPHQL = """
query($id:ID!, $after:String) {
  node(id:$id) {
    ... on ProjectV2 {
      id
      title
      items(first:100, after:$after) {
        nodes {
          id
          content { ... on Issue { id number repository { nameWithOwner } } }
          fieldValueByName(name:"Status") {
            ... on ProjectV2ItemFieldSingleSelectValue { name }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""


def get_token() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        proc = subprocess.run(["gh", "auth", "token"], check=True, text=True,
                              capture_output=True, timeout=15)
        if proc.stdout.strip():
            return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    raise RuntimeError("Set GH_TOKEN / GITHUB_TOKEN or authenticate using `gh auth login`.")


def request(method: str, path: str, token: str, payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request("https://api.github.com" + path, data=data, method=method,
                                 headers={"Authorization": "Bearer " + token,
                                          "Accept": "application/vnd.github+json",
                                          "Content-Type": "application/json",
                                          "X-GitHub-Api-Version": "2022-11-28",
                                          "User-Agent": "solo-multi-agent-audit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raw = exc.read(1000).decode("utf-8", "replace")
        raise RuntimeError(f"GitHub {method} {path} failed with {exc.code}: {raw}") from exc


def list_issues(repo: str, token: str) -> list[dict]:
    issues = []
    page = 1
    while True:
        batch = request("GET", f"/repos/{repo}/issues?state=all&per_page=100&page={page}", token)
        issues.extend(i for i in batch if "pull_request" not in i)
        if len(batch) < 100:
            break
        page += 1
    return issues


def list_project_items(project_id: str, token: str) -> tuple[str, list[dict]]:
    nodes = []
    cursor = None
    title = ""
    while True:
        data = request("POST", "/graphql", token,
                       {"query": GRAPHQL, "variables": {"id": project_id, "after": cursor}})
        if data.get("errors"):
            raise RuntimeError("GraphQL: " + json.dumps(data["errors"])[:1200])
        project = data.get("data", {}).get("node")
        if not project or not project.get("items"):
            raise RuntimeError("Project node missing or not authorized: " + project_id)
        title = project.get("title") or title
        connection = project["items"]
        nodes.extend(connection["nodes"])
        if not connection["pageInfo"]["hasNextPage"]:
            break
        cursor = connection["pageInfo"]["endCursor"]
        if not cursor:
            raise RuntimeError("Project returned hasNextPage=true without cursor")
    return title, nodes


def audit(repo: str, issues: list[dict], project_items: list[dict]) -> dict:
    errors = []
    issues_by_id = {i["node_id"]: i for i in issues}
    project_index: dict[str, list[str | None]] = {}
    for item in project_items:
        content = item.get("content")
        if not content or content.get("repository", {}).get("nameWithOwner", "").lower() != repo.lower():
            continue
        value = item.get("fieldValueByName") or {}
        project_index.setdefault(content["id"], []).append(value.get("name"))

    def error(issue: dict, kind: str, detail: str):
        errors.append({"issue_number": issue["number"], "issue_url": issue.get("html_url"),
                       "code": kind, "detail": detail})

    for issue in issues:
        labels = {x["name"].lower() for x in issue.get("labels", [])}
        primary = labels & {"chief", "worker"}
        if len(primary) != 1:
            error(issue, "ROUTE_XOR", "Exactly one of chief or worker is required")
        if "human" in labels and "chief" not in labels:
            error(issue, "HUMAN_WITHOUT_CHIEF", "human can only coexist with chief")
        matches = project_index.get(issue["node_id"], [])
        if len(matches) != 1:
            error(issue, "PROJECT_MEMBERSHIP", f"Expected one Project item; found {len(matches)}")
            continue
        status = matches[0]
        if status not in ALLOWED_STATUSES:
            error(issue, "STATUS", f"Missing or unknown Project Status: {status!r}")
            continue
        closed = issue.get("state") == "closed"
        if status in {"Done", "Canceled"} and not closed:
            error(issue, "UNFINISHED_CLOSEOUT", f"Status={status} but issue is open")
        if status not in {"Done", "Canceled"} and closed:
            error(issue, "PREMATURE_CLOSE", f"Status={status} but issue is closed")
        if status == "Ready" and "worker" not in labels:
            error(issue, "READY_ROUTE", "Ready requires worker")
        if status == "In Review" and "chief" not in labels:
            error(issue, "REVIEW_ROUTE", "In Review requires chief")
        if "human" in labels and status != "Blocked":
            error(issue, "HUMAN_NOT_BLOCKED", "human gate must have Status=Blocked")

    return {"repository": repo, "repo_issues_checked": len(issues),
            "project_items_for_repo": sum(len(v) for v in project_index.values()),
            "violation_count": len(errors), "violations": errors,
            "not_checked": ["Definition of Ready content", "Human approval authenticity",
                            "Independent review quality", "Merge SHA/CI evidence",
                            "Cross-issue dependency cycles", "Concurrent lease safety"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="OWNER/REPO")
    parser.add_argument("--project-id", required=True, help="GitHub Projects v2 node ID")
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()
    if "/" not in args.repo or args.repo.startswith("/"):
        parser.error("--repo must be OWNER/REPO")
    try:
        token = get_token()
        issues = list_issues(args.repo, token)
        title, items = list_project_items(args.project_id, token)
        report = audit(args.repo, issues, items)
        report["project_id"] = args.project_id
        report["project_title"] = title
        rendered = json.dumps(report, indent=2)
        print(rendered)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as file:
                file.write(rendered + "\n")
        return 1 if report["violation_count"] else 0
    except Exception as exc:
        print(f"AUDIT INCOMPLETE: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
