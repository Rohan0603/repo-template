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

## 4. Agent-initiated scheduling, review and human gates

Chief and Worker are **roles** fulfilled by independently invoked AI sessions, not named hosted bots. The owner can start any supported tool manually or schedule its check using that tool's own scheduler. The session must read `AGENTS.md`, query the live Project (all pages), and select eligible Project-linked issues by role and Status.

- **Single-issue:** specify exactly one GitHub issue and role. Verify live labels, Project membership, dependencies and active claim before work.
- **Queue:** specify a role and issue-count limit. Process eligible issues by Priority and stable tie-break; never execute two claimed/conflicting issues at once.
- **Safe claim:** inspect all comments for active/ambiguous claims, comment `START` with a unique run ID and UTC expiry, then read back and re-check competing claims **before** changing Project Status or doing work. On a conflict, stop without relabeling or changing Status. After an evidenced handoff or stop, write and verify the matching `<!-- claim-end:ISSUE-N:RUN-ID -->` `CLAIM RELEASED` comment. Missing release or expired claims require Chief reconciliation; labels/comments are not distributed locks.
- **Handoffs:** record complete decisions/proofs on the issue, update `chief` XOR `worker` and its Project Status, and read back all mutations. `human` only coexists with Chief, who clears it after the human-only gate is verified.
- **Governance CI:** keep read-only audit of labels, Project membership and statuses. Do not let GitHub Actions automatically dispatch AI sessions.

There are **no** `AGENT_RUNNER_URL`, `AGENT_RUNNER_TOKEN`, provider/model deployment, or agent-triggering workflows required for this approach. Token credentials used for optional read-only auditing remain separate from the agents' own authorized GitHub access.

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
