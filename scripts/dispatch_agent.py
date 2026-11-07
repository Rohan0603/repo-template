#!/usr/bin/env python3
"""Fail-closed, single-writer Chief/Worker dispatcher for GitHub Projects v2.

The coordinator owns only the handoff saga. A separately configured runner owns
model execution. No provider or credential is inferred by this script.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Callable

PRIMARY = {"chief", "worker"}
HUMAN = "human"
DISPATCHABLE = {"Backlog", "Ready", "In Progress", "In Review"}
STATUS_OPTIONS = {"Backlog", "Ready", "In Progress", "Blocked", "In Review", "Done", "Canceled"}


def retry_call(operation: Callable[[], Any], attempts: int = 3, delay_seconds: float = 1.0) -> Any:
    last_error: Exception | None = None
    for index in range(attempts):
        try:
            return operation()
        except Exception as exc:  # bounded retry for transient GitHub/runner failures
            last_error = exc
            if index + 1 < attempts and delay_seconds:
                time.sleep(delay_seconds * (index + 1))
    assert last_error is not None
    raise last_error


def transition_marker(issue_number: int, run_id: str) -> str:
    return f"<!-- dispatch:issue-{issue_number}:{run_id} -->"


def build_full_label_set(existing: list[str], target_role: str) -> list[str]:
    if target_role not in PRIMARY:
        raise ValueError("target_role must be chief or worker")
    preserved = {name for name in existing if name.lower() not in PRIMARY | {HUMAN}}
    preserved.add(target_role)
    if target_role == "chief" and any(name.lower() == HUMAN for name in existing):
        preserved.add(HUMAN)
    return sorted(preserved, key=str.casefold)


def decide_dispatch(labels: list[str], status: str | None, issue_state: str) -> tuple[bool, str]:
    normalized = {label.casefold() for label in labels}
    routes = normalized & PRIMARY
    if len(routes) != 1 or (HUMAN in normalized and "chief" not in normalized):
        return False, "invalid-route"
    if HUMAN in normalized:
        return False, "human-gate"
    if issue_state == "closed" or status not in DISPATCHABLE:
        return False, "status-gate"
    return True, next(iter(routes))


class GitHub:
    def __init__(self, token: str):
        self.token = token

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            "https://api.github.com" + path,
            data=data,
            method=method,
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "repo-template-agent-dispatch/1.0",
            },
        )

        def send() -> Any:
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    if response.status == 204:
                        return None
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                detail = exc.read(1000).decode("utf-8", "replace")
                if exc.code in {408, 409, 429} or exc.code >= 500:
                    raise RuntimeError(f"transient GitHub {method} {path}: HTTP {exc.code}") from exc
                raise RuntimeError(f"GitHub {method} {path}: HTTP {exc.code}: {detail}") from exc

        return retry_call(send)

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        result = self.request("POST", "/graphql", {"query": query, "variables": variables})
        if result.get("errors"):
            raise RuntimeError("GraphQL error: " + json.dumps(result["errors"])[:1200])
        return result["data"]


PROJECT_QUERY = """
query($project:ID!, $after:String) {
  node(id:$project) { ... on ProjectV2 {
    id title
    fields(first:100) { nodes { ... on ProjectV2SingleSelectField { id name options { id name } } } }
    items(first:100, after:$after) { nodes { id content { ... on Issue { id number state repository { nameWithOwner } } }
      fieldValueByName(name:"Status") { ... on ProjectV2ItemFieldSingleSelectValue { name optionId } }
    } pageInfo { hasNextPage endCursor } }
  } }
}
"""


def project_item(github: GitHub, project_id: str, repo: str, issue_id: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    cursor = None
    project: dict[str, Any] | None = None
    while True:
        data = github.graphql(PROJECT_QUERY, {"project": project_id, "after": cursor})
        project = data.get("node")
        if not project:
            raise RuntimeError("Project node missing or not authorized")
        for item in project["items"]["nodes"]:
            content = item.get("content") or {}
            if content.get("id") == issue_id and content.get("repository", {}).get("nameWithOwner", "").casefold() == repo.casefold():
                return item, project
        page = project["items"]["pageInfo"]
        if not page["hasNextPage"]:
            return None, project
        cursor = page["endCursor"]


def status_field(project: dict[str, Any], status: str) -> tuple[str, str]:
    for field in project.get("fields", {}).get("nodes", []):
        if field.get("name") != "Status":
            continue
        for option in field.get("options", []):
            if option.get("name") == status:
                return field["id"], option["id"]
    raise RuntimeError(f"Project Status option is not configured: {status}")


def update_project_status(github: GitHub, project_id: str, item_id: str, project: dict[str, Any], status: str) -> None:
    field_id, option_id = status_field(project, status)
    mutation = """
    mutation($project:ID!, $item:ID!, $field:ID!, $option:String!) {
      updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:{singleSelectOptionId:$option}}) { projectV2Item { id } }
    }
    """
    github.graphql(mutation, {"project": project_id, "item": item_id, "field": field_id, "option": option_id})


def add_project_item(github: GitHub, project_id: str, issue_id: str) -> str:
    mutation = """
    mutation($project:ID!, $content:ID!) {
      addProjectV2ItemById(input:{projectId:$project,contentId:$content}) { item { id } }
    }
    """
    return github.graphql(mutation, {"project": project_id, "content": issue_id})["addProjectV2ItemById"]["item"]["id"]


def comments(github: GitHub, repo: str, issue_number: int) -> list[dict[str, Any]]:
    return github.request("GET", f"/repos/{repo}/issues/{issue_number}/comments?per_page=100")


def token_from_environment() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    return subprocess.run(["gh", "auth", "token"], check=True, text=True, capture_output=True, timeout=15).stdout.strip()


def run(args: argparse.Namespace) -> int:
    if not args.provider or not args.model:
        raise RuntimeError("provider and model are required; no model/provider is inferred")
    token = token_from_environment()
    github = GitHub(token)
    issue_path = f"/repos/{args.repo}/issues/{args.issue_number}"
    issue = github.request("GET", issue_path)
    issue_id = issue["node_id"]
    labels = [label["name"] for label in issue.get("labels", [])]
    project_id = args.project_id or os.environ.get("GH_PROJECT_NODE_ID")
    if not project_id:
        raise RuntimeError("GH_PROJECT_NODE_ID/project_id is required")
    item, project = project_item(github, project_id, args.repo, issue_id)
    if item is None:
        item_id = add_project_item(github, project_id, issue_id)
        def read_added_item() -> tuple[dict[str, Any] | None, dict[str, Any]]:
            found, current_project = project_item(github, project_id, args.repo, issue_id)
            if found is None:
                raise RuntimeError("Project item add is not visible yet")
            return found, current_project

        item, project = retry_call(read_added_item, attempts=5, delay_seconds=1)
        if item is None:
            raise RuntimeError(f"Project item add did not read back: {item_id}")
    current_status = ((item.get("fieldValueByName") or {}).get("name"))
    allowed, route = decide_dispatch(labels, current_status, issue.get("state", "open"))
    result = {"repo": args.repo, "issue": args.issue_number, "status": current_status, "route": route, "run_id": args.run_id}
    if not allowed:
        result["outcome"] = "NOT_DISPATCHED"
        print(json.dumps(result, indent=2))
        return 0

    marker = transition_marker(args.issue_number, args.run_id)
    existing_comments = comments(github, args.repo, args.issue_number)
    if not any(marker in (comment.get("body") or "") for comment in existing_comments):
        github.request("POST", issue_path + "/comments", {"body": marker + "\nPREPARE HANDOFF\n" +
            f"Dispatch route: `{route}`\nProvider: `{args.provider}`\nModel: `{args.model}`\n" +
            "This coordinator will not invoke a provider unless an explicit runner is configured."})
        github.request("PUT", issue_path + "/labels", {"labels": build_full_label_set(labels, route)})
        update_project_status(github, project_id, item["id"], project, "In Progress")

    refreshed = github.request("GET", issue_path)
    refreshed_item, _ = project_item(github, project_id, args.repo, refreshed["node_id"])
    refreshed_labels = {label["name"].casefold() for label in refreshed.get("labels", [])}
    refreshed_status = ((refreshed_item or {}).get("fieldValueByName") or {}).get("name")
    if route not in refreshed_labels or "chief" in refreshed_labels and "worker" in refreshed_labels or refreshed_status != "In Progress":
        github.request("POST", issue_path + "/comments", {"body": marker + "\nRECONCILIATION REQUIRED\nDispatcher read-back did not match the prepared handoff; no provider call was made."})
        result["outcome"] = "BLOCKED_RECONCILIATION"
        print(json.dumps(result, indent=2))
        return 2

    runner_url = os.environ.get("AGENT_RUNNER_URL")
    runner_token = os.environ.get("AGENT_RUNNER_TOKEN")
    if not args.execute or not runner_url or not runner_token:
        result["outcome"] = "NOT_DISPATCHED"
        result["reason"] = "explicit runner URL/token not configured or execute=false"
        print(json.dumps(result, indent=2))
        return 0

    request = urllib.request.Request(
        runner_url,
        data=json.dumps({"repo": args.repo, "issue_number": args.issue_number, "route": route,
                         "provider": args.provider, "model": args.model, "run_id": args.run_id}).encode("utf-8"),
        method="POST",
        headers={"Authorization": "Bearer " + runner_token, "Content-Type": "application/json",
                 "User-Agent": "repo-template-agent-dispatch/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        if response.status >= 300:
            raise RuntimeError(f"runner rejected dispatch: HTTP {response.status}")
    github.request("POST", issue_path + "/comments", {"body": marker + "\nDISPATCH ACCEPTED\nRunner accepted the explicit provider/model request; follow-up evidence must be recorded on this issue."})
    result["outcome"] = "DISPATCH_ACCEPTED"
    print(json.dumps(result, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--project-id")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local-run"))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as exc:
        print(f"DISPATCH INCOMPLETE: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
