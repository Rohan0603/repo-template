# Bootstrap playbook — GitHub Projects for a solo human + multiple AI agents

**This is a setup guide, not a separate task database.** The configured GitHub Project and linked GitHub Issues are the live task truth.

## 1. Scope and prerequisites

- Copy `AGENTS.md`, `.github/ISSUE_TEMPLATE/agent_task.yml` and `.github/pull_request_template.md` into **a new repository**. Replace `[PROJECT_NAME]`, `[OWNER/REPOSITORY]`, `[PROJECT_URL]` and `[DEFAULT_BRANCH]` before dispatching agents.
- Use account/repo/Project visibility appropriate for the research and assets. A public repository and a public Project may expose issue content, attachments, comments, Discussions and PR logs; treat them separately.
- Install GitHub CLI (`gh`) and authenticate interactively. GitHub Projects has the `project` OAuth scope; `repo` may be needed for private repository operations. Grant *least privilege* appropriate to the actual tasks. Example: `gh auth refresh -s project,repo` (avoid copying tokens into scripts or chat).
- Check authorization: `gh auth status`, `gh api user --jq .login`, `gh project list --owner [OWNER]`.
- The `gh` command itself does not schedule an AI agent. For unattended routing, integrate a separate authorized GitHub App/dispatcher with notifications or polling.

## 2. Create a live Project (CLI examples)

```sh
# Check existing projects first — do not create duplicates.
gh project list --owner OWNER --limit 100
# Replace OWNER and PRODUCT_NAME with real values.
gh project create --owner OWNER --title "PRODUCT_NAME — Engineering"
# Use the project number returned above.
gh project link PROJECT_NUMBER --owner OWNER --repo OWNER/REPO
# A newly created Project normally includes a built-in Status field. Edit its options in the UI.
gh project field-list PROJECT_NUMBER --owner OWNER
# Additional custom fields; do not duplicate a built-in Status field.
gh project field-create PROJECT_NUMBER --owner OWNER --name Priority --data-type SINGLE_SELECT --single-select-options 'P0 Critical,P1 High,P2 Medium,P3 Low'
gh project field-create PROJECT_NUMBER --owner OWNER --name Risk --data-type SINGLE_SELECT --single-select-options 'Normal,Elevated,Critical'
```

Configure **Status** in the Project settings to: `Backlog`, `Ready`, `In Progress`, `Blocked`, `In Review`, `Done`, `Canceled`. If GitHub initializes three default values, edit the field options directly. Ensure views and built-in workflows refer to these actual options.

Add saved views in the GitHub Projects UI: All/table, Chief queue, Worker ready, Executing, In Review, Human blocked, Blocked, and optionally Roadmap. Apply saved filters such as `label:chief -label:human -status:Done -status:Canceled`, `label:worker status:Ready`, `label:human`, and `status:Blocked` after checking support in the current interface.

## 3. Labels and issue forms

In the repository's **Issues → Labels** create exact lowercase `chief`, `worker`, `human`. The bundled issue form defaults to `chief`; GitHub requires a label to already exist if a form should apply it. Do not add redundant status labels or use `human` alone.

Configure Project built-in **auto-add** to capture newly created/updated issues from the repository. **Backfill existing issues separately**: auto-add does not retroactively include old items.

```sh
# Example manual backfill; repeat for actual existing issue URLs (check membership first).
gh project item-add PROJECT_NUMBER --owner OWNER --url https://github.com/OWNER/REPO/issues/123
# Project field Status must be updated on the item, not by changing a status label.
gh project item-edit PROJECT_NUMBER --owner OWNER --url https://github.com/OWNER/REPO/issues/123 --field Status --value Ready
# Inspect authoritative Project items and values.
gh project item-list PROJECT_NUMBER --owner OWNER --limit 1000 --format json
```

Do not use untracked Project **draft** items as implementation tasks. Convert drafts to repository issues before Worker dispatch. For cross-repository dependencies, use native GitHub blockedBy/blocking relations when available, and link them in issue body as readable context.

## 4. Multi-agent dispatch, review and human gates

Implement **one serialized dispatch coordinator** per Project, not multiple independent workers racing on label events. The agent runner should:

1. Query Project items + current Status + labels, then assign by `chief` or `worker` routing; do not dispatch `human` issues.
2. Require Worker `Ready` + `worker` + certified DoR before starting; require current run/lease read-back on retries.
3. Record transition comment with a unique idempotency marker, replace the issue's role labels with one full-set update, update Project Status, read back all values, and block/reconcile if inconsistent. The comment/Project update cannot be made atomically with the issue labels.
4. Route Worker implementation completion back to Chief for independent assessment; Chief handles human-only blockers and final Done closeout.
5. Run a periodic **read-only governance audit** of every issue in the Project for: missing Project item, invalid route, impossible `human` combination, dependency cycles, stale in-progress leases, review without PR, Done without proof, closed/open vs Project Status drift.

Use a GitHub App or token with actual Projects v2 read/write scope for automation; the repository-scoped `GITHUB_TOKEN` does not necessarily have Projects v2 access. Use explicit `permissions` for GitHub Actions, never assume full access by default.

This template includes a bounded coordinator at `scripts/dispatch_agent.py` and a manual workflow at `.github/workflows/agent-dispatch.yml`. The workflow serializes writes per issue with an Actions concurrency group. The coordinator validates the Project item, enforces `chief` XOR `worker`, stops on `human`, uses a unique handoff marker, replaces governance labels as one full-set update, moves the Project Status to `In Progress`, retries transient API failures three times, and reads the issue and Project back before any provider call. It is a saga with reconciliation, not a false cross-resource transaction.

The workflow requires a separate `GH_PROJECTS_WRITE_TOKEN` secret. It accepts provider and model as required manual inputs and only calls a configured `AGENT_RUNNER_URL` when `execute=true` and both `AGENT_RUNNER_URL` and `AGENT_RUNNER_TOKEN` exist. No provider, model, endpoint, credential or independent review is invented. Without that owner-supplied runner configuration, the safe pilot path is a real coordinator read-back ending in `NOT_DISPATCHED`.

Optional recurring audit: set the GitHub Actions repository variable `GH_PROJECT_NODE_ID` and a dedicated least-privilege secret `GH_PROJECTS_READ_TOKEN`, then rename `.github/workflows/governance-audit.yml.example` to `.github/workflows/governance-audit.yml`. Its read-only scheduled/manual job fails on detected route/status drift and uploads an audit report. Verify secret scope and retention settings before enabling.

**ACID-inspired ≠ ACID database guarantees:** no GitHub API call can atomically change Issue labels, a comment and Project fields together. Durable comments + idempotent retry + read-back + limited single-writer scheduling approximate a recoverable saga. Use `scripts/validate_governance.py` as a read-only, partial invariant check; it does not grant locks or enforce a human approval.

## 5. Git and PR controls

- Pick a protected default branch (`main` recommended) and short-lived `feat/<issue>-slug`, `fix/<issue>-slug`, etc. Each worker gets a separate branch and worktree.
- Require PRs and validated checks (tests, lint, typechecking, security scans as relevant); prohibit force pushes and branch deletion where supported.
- Resolve review threads, revalidate exact final PR head, and deliberately squash-merge one logical change; delete feature branch after merge.
- **Solo-owner caveat:** requiring a second GitHub approving reviewer can deadlock a sole-maintainer account. Independent AI review notes do not satisfy GitHub's native review authorization. Choose a real separate authorized reviewer, or keep zero required native approvals *plus* required CI and an explicit Chief review record for Normal risk, with human approval at Elevated/Critical risk. Document the residual enforcement gap; a comment is not as strong as a trusted required status check.
- Do not configure unattended auto-merge or give ordinary workers branch-protection bypass rights.
- Test protections safely: create a small temporary PR, demonstrate blocked merge on failing CI and lack of direct-push/force-push rights where your account allows it, and record observed evidence. Do not merge a known bad PR to test controls.

## 6. GitHub Discussions for agents

Optional. Enable Discussions for the relevant repository. Suggested categories: `Research/RFC` (open-ended), `Architecture` (open-ended), `Questions` (Q&A), `Retrospectives` (open-ended). It is an asynchronous discussion forum, not a reliable agent event bus. GitHub's GraphQL API supports `createDiscussion` and `addDiscussionComment`; each writer still needs authorization and a dispatcher/poller to deliver new replies to actual agent sessions.

When exploration yields an actionable conclusion, Chief creates/updates the **Project-linked Issue**, summarizes decision, sources, rationale and exact next steps, and adds dependencies/acceptance. The Worker should not need to read an unbounded Discussion thread to discover its instructions. PR inline comments remain the right channel for code-level feedback.

## 7. Verification before declaring rollout done

- [ ] Root `AGENTS.md` is automatically discovered and read in full by the chosen agent runtime (test with a fresh session).
- [ ] All actionable issues appear in the Project, including backfilled legacy work; draft work converted to issues.
- [ ] All issues have `chief` XOR `worker`; if `human`, also `chief`.
- [ ] Every queue view matches a direct, paginated Project API query; reconcile differences.
- [ ] Real Worker DoR/START/implementation/review/closeout cycle passes end-to-end.
- [ ] Worker-to-Chief escalation and Chief-to-Worker handoff record correct comments, role labels and Project Status with read-back.
- [ ] Human-only gate is handled by Chief; owner need not edit labels.
- [ ] PR protections and CI gates are demonstrated, not merely described.
- [ ] API secondary rate limits, permissions and outages produce a **Blocked/recoverable** outcome rather than duplicate comments or missing tasks.

## References

- [GitHub CLI Projects](https://cli.github.com/manual/gh_project)
- [GitHub Projects API](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects)
- [GitHub Projects auto-add limitation](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/adding-items-automatically)
- [GitHub Issue forms syntax](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)
- [GitHub issue dependencies](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-issue-dependencies)
- [GitHub branch rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
- [GitHub Discussions GraphQL](https://docs.github.com/en/graphql/guides/using-the-graphql-api-for-discussions)
