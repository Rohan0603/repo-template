# Bootstrap playbook — GitHub Projects for a solo human + multiple AI agents

**This is a setup guide, not a separate task database.** The configured GitHub Project and linked GitHub Issues are the live task truth.

## 1. Scope and prerequisites

- Copy `AGENTS.md`, `.github/ISSUE_TEMPLATE/agent_task.yml` and `.github/pull_request_template.md` into **a new repository**. Replace `[PROJECT_NAME]`, `[OWNER/REPOSITORY]`, `[PROJECT_URL]` and `[DEFAULT_BRANCH]` before dispatching agents.
- Use account/repo/Project visibility appropriate for the research and assets. A public repository and a public Project may expose issue content, attachments, comments, Discussions and PR logs; treat them separately.
- Install GitHub CLI (`gh`) and authenticate interactively. GitHub Projects has the `project` OAuth scope; `repo` may be needed for private repository operations. Grant *least privilege* appropriate to the actual tasks. Example: `gh auth refresh -s project,repo` (avoid copying tokens into scripts or chat).
- Check authorization: `gh auth status`, `gh api user --jq .login`, `gh project list --owner [OWNER]`.
- Neither GitHub Projects labels nor the `gh` CLI trigger AI agents. The human owner invokes or schedules Chief/Worker directly within Codex, OpenCode, ChatGPT Work, a custom orchestrator, or another chosen runtime. Do not install an agent-dispatching service, provider endpoint or runner credentials for this template.

### Troubleshooting Projects v2 permissions for Chat-mode agents

Repository Issue access and Projects v2 access are separate permission surfaces. A successful issue read, label update, or comment does not prove that an agent can read a Project, its item membership, or its Status and Priority fields. Labels and Project Status are independent: changing `chief`/`worker` never changes Status, and labels never launch a model. The human must invoke each Chief or Worker session separately.

Use a read-only diagnostic, without requesting or pasting a token into chat:

```sh
gh auth status
gh api user --jq .login
gh project list --owner OWNER --limit 100
gh project item-list PROJECT_NUMBER --owner OWNER --limit 1000 --field "Status" --field "Priority" --format json
gh project field-list PROJECT_NUMBER --owner OWNER
```

Interpret the result narrowly:

- **Tool discovery failure:** the runtime exposes no Projects operation. Record Project membership, Status, and Priority as **NOT VERIFIED**; do not guess or make a write.
- **HTTP 401:** authentication is missing or expired. Stop and ask the owner to authenticate through the approved UI/CLI flow; never ask for the credential value in chat.
- **HTTP 403:** the request reached GitHub but this authentication path is not authorized for that Project or operation. Do not infer that the Project or item is absent, and do not retry by broadening permissions blindly.
- **HTTP 200 with no matching item or field:** complete pagination and filtering first. If membership, Status, or Priority still cannot be read back, keep that gate **NOT VERIFIED**.

Personal (user-owned) Projects and organization-owned Projects do not have identical token compatibility. GitHub's [Projects REST items documentation](https://docs.github.com/en/rest/projects/items) notes that adding an item to a user-owned Project does not work with GitHub App user access tokens, GitHub App installation tokens, or fine-grained personal access tokens, while organization-owned Project operations have their own documented fine-grained permission requirements. Check the exact endpoint and authentication method before relying on a permission. For supported authentication paths, `project` (or a read-only `read:project` permission where offered) may be relevant; it does not make every personal-Project operation available. The [Projects API guide](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects) is the authority for the current path and operation.

#### Chief fail-closed handoff

1. Read the issue, all comments, labels, dependencies, and the complete Project item/field result.
2. If Issue APIs work but Project lookup returns a discovery failure, 401, 403, or incomplete membership/field data, record **NOT VERIFIED**, retain `chief`, and do not post a Worker `START` or claim `Ready`.
3. Only after Project authorization is verified may Chief read back the issue's Project membership, Priority, and Status; then change `chief` → `worker` and `Backlog` → `Ready` as separate mutations.
4. Read back each mutation and confirm no conflicting claim before the independently invoked Worker begins. A label-only transition is not evidence of Project `Ready`.

Worker handback follows the same separation: provide the exact PR/head and test evidence, change `worker` → `chief`, and read back the label. Project `In Review` or `Done` still requires its own authorized Project read-back; do not substitute an Issue label.

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

In the repository's **Issues → Labels** create exact lowercase `chief`, `worker`, `human` and non-routing `metadata-bootstrap` (or use `scripts/bootstrap_github.ps1 -Repo OWNER/REPO -Execute`, after a dry-run). The bundled issue form defaults to `chief` and requires Chief to specify **target Project, approved Priority, milestone (or NOT REQUIRED), native dependencies/sub-issues, and missing API operations**. GitHub requires a label to already exist if a form should apply it. Do not add redundant status labels or use `human` alone.

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

## 4. Agent-initiated scheduling, review and human gates

Chief and Worker are **roles** fulfilled by independently invoked AI sessions, not named hosted bots. The owner can start any supported tool manually or schedule its check using that tool's own scheduler. The session must read `AGENTS.md`, query the live Project (all pages), and select eligible Project-linked issues by role and Status.

- **Single-issue:** specify exactly one GitHub issue and role. Normal implementation must verify live labels, Project membership, `Ready`, dependencies and active claim. An issue explicitly labeled `worker + metadata-bootstrap` is a **separate metadata-only bootstrap** task that may start from its repository Issue URL before Project membership exists; implementation is forbidden until Chief subsequently certifies DoR.
- **Queue:** specify a role and issue-count limit. Normal implementation enumerates the Project's paginated `worker + Ready` items **excluding `metadata-bootstrap`**. A separately requested **metadata-bootstrap queue** may search only repository issues with both `worker` and `metadata-bootstrap` and perform metadata-only writes. Never merge those two queues or process a conflicting claim.
- **Safe claim:** inspect all comments for active/ambiguous claims, comment `START` with a unique run ID and UTC expiry, then read back and re-check competing claims **before** changing Project Status or doing work. On a conflict, stop without relabeling or changing Status. After an evidenced handoff or stop, write and verify the matching `<!-- claim-end:ISSUE-N:RUN-ID -->` `CLAIM RELEASED` comment. Missing release or expired claims require Chief reconciliation; labels/comments are not distributed locks.
- **Handoffs:** first Chief → Worker handoff ALWAYS contains the `GITHUB METADATA SETUP` checklist (`Project`, `Status`, `Priority`, milestone, native relations, assignee/required fields; VERIFIED / TO SET / NOT REQUIRED / NOT VERIFIED). If Chief cannot update/verify required metadata, the exception is a **`METADATA BOOTSTRAP HANDOFF`** with `worker + metadata-bootstrap` and **no Project `Ready` assertion**. Worker completes only approved metadata, reads back, and routes to Chief; Chief alone certifies DoR before normal implementation handoff. For ordinary handoffs, update `chief` XOR `worker` and Project Status, and read back all mutations. `human` only coexists with Chief, who clears it after the human-only gate is verified.
- **Governance CI:** keep read-only audit of labels, Project membership and statuses. Do not let GitHub Actions automatically dispatch AI sessions.

There are **no** `AGENT_RUNNER_URL`, `AGENT_RUNNER_TOKEN`, provider/model deployment, or agent-triggering workflows required for this approach. Token credentials used for optional read-only auditing remain separate from the agents' own authorized GitHub access.

### First-handoff metadata bootstrap — for a Chief lacking Projects/Milestones API

This is **not** a substitute for Project `Ready`; it is a bounded owner-authorized **metadata-only** exception. Before the first Worker implementation handoff, Chief records exact target values and missing operations in the issue. The values must be selected by Chief or explicitly approved by owner; missing decisions are a blocker, not Worker discretion.

| Metadata | Chief supplies | Worker, if Chief API is blocked |
|---|---|---|
| GitHub Project | canonical URL, owner, project number | Verify current membership, add if missing, read back |
| Project fields | selected Priority, Backlog during bootstrap, required custom fields | Set only approved values; read back per field |
| Milestone | exact existing title/number, or explicitly NOT REQUIRED | Assign existing milestone; create only if separately approved with an exact title and scope |
| Native dependencies / sub-issues | exact blocking/parent issue URLs and relationship | Apply and read back supported native relations; escalate if unavailable |
| Other issue fields | exact assignee or other approved values | Apply and independently verify |

1. Chief posts `METADATA BOOTSTRAP HANDOFF`, stating **IMPLEMENTATION NOT AUTHORIZED**, with the checklist, sources, permission gaps and a unique handoff ID. Set **`worker` + `metadata-bootstrap`** and read back the issue labels. The Project may not yet contain the issue.
2. The human invokes a Worker in **single-issue** or explicitly requested **metadata-bootstrap queue** mode. The Worker reads the entire issue and all claims, posts/reads a unique START, then checks conflicts and permission before making any metadata write. Do not branch or implement code.
3. Worker adds the item to the correct Project if necessary, fills approved metadata and reads back Project item/fields and milestone/dependency relationships. Where supported, `gh project item-list PROJECT_NUMBER --owner OWNER --limit 1000 --format json --field "Status" --field "Priority"` can assist read-back; check pagination and values. Do not paste tokens in chat or create a milestone speculatively.
4. Worker posts `METADATA VERIFIED` or `METADATA BLOCKED` with per-field evidence/errors, removes `metadata-bootstrap`, changes `worker` → `chief` and verifies labels, then releases the START claim. If incomplete, Chief retains and resolves the blocker.
5. Chief independently verifies all metadata, issues the **separate** implementation `CHIEF RESPONSE/HANDOFF` only after full DoR, and sets `worker + Ready` with Project read-back. If Chief still cannot access Projects, it requests an authorized verifier and does not claim `Ready`.

**No automatic agents:** label changes, Project events, Actions and comments must not invoke Codex/Claude Code/OpenCode/ChatGPT. A human invokes or schedules sessions in those tools. See `AGENTS.md` §4 and `docs/WORKFLOW_EXAMPLES.md` §0 for the canonical policy and copy-ready comment templates.

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
- [ ] Bootstrap cases carry `worker + metadata-bootstrap` only during metadata setup, and end with `chief` plus independent project/field read-back before code authorization.
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
