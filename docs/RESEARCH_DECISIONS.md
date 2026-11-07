# Design review — solo developer, multiple AI models, GitHub-only task management

**Research checkpoint:** 7 November 2026. This is a reusable recommendation, not a modification to any of the user's existing repositories. Recheck platform features and plan limits on adoption.

## Existing Daemon Reborn governance examined

- [`daemon-reborn/AGENTS.md`](https://github.com/Rohan0603/daemon-reborn/blob/main/AGENTS.md): Linear authority; issue-before-code; `START`/`PROGRESS`/`BLOCKED`/`REVIEW HANDOFF`/`CLOSEOUT`; real tests and read-back; independent review; no hidden TODO work.
- [`daemon-reborn/.github/pull_request_template.md`](https://github.com/Rohan0603/daemon-reborn/blob/main/.github/pull_request_template.md): exact tests/results, PR evidence, risk/privacy/rollback.
- [ORC-229](https://linear.app/agtorchestrator/issue/ORC-229): workflow v3.1; strict Definition of Ready, source-based Chief research, one executor per actionable issue, separate independent review, normal versus elevated/critical risk merge gates, human approval for elevated/critical, no unattended auto-merge.
- [ORC-234](https://linear.app/agtorchestrator/issue/ORC-234): GitHub protection read-back and safe ruleset demonstration, no bypass of reviewer authority.
- [ORC-236](https://linear.app/agtorchestrator/issue/ORC-236): standing audit of issue inventory, dependencies, DoR, stale states, evidence drift, status and deliverable integrity. This was a Linear rule; the new template adapts it to GitHub Projects and Issues.

The new template retains **the rigor** while replacing `ChatGPT` → `chief`, `Coding Agent` → `worker`, and `Work/Human Only` → a **Chief-managed `human` flag** where truly required. It deliberately removes Linear as task authority for new projects.

## Research-backed decisions and rationale

| Decision | Why | Source |
|---|---|---|
| Use **one root `AGENTS.md`** as both canonical contract and agent entrypoint | Codex and multiple agents auto-discover **AGENTS.md**, so a separate singular-filename policy adds needless indirection and possible drift | [AGENTS.md](https://agents.md/), [OpenAI Codex instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md) |
| GitHub Projects **Status** is authoritative workflow state; GitHub Issue is authoritative task content | Projects has custom fields, views and built-in automations, but they must be configured; issue state open/closed alone is not a rich lifecycle | [Projects built-in workflows](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-built-in-automations) |
| New issues auto-add and historical issues backfill | GitHub's auto-add does **not** add already-existing issues | [Project auto-add docs](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/adding-items-automatically) |
| Use `chief` XOR `worker`; `human` iff `chief` is responsible for human-only gate | Eliminates ambiguous routing and avoids requiring the owner to manipulate labels; must be **actively validated** | Project governance design choice; adapted from daemon-reborn one executor rule |
| Stage comment, update labels, update Project field, then read back | GitHub API has per-resource mutations; no multi-resource ACID transaction; a compensating/repairable saga is realistic | [Projects GraphQL API](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects), [Projects mutations](https://docs.github.com/en/graphql/reference/projects) |
| Issue form creates a Chief-owned specification | GitHub forms can initialize labels and require sections; agents should still verify Project membership and DoR | [Issue forms](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms) |
| Use native issue dependencies and sub-issues instead of text-only `blockedBy` | GitHub supports blocking relationships and CLI inspection; helps visible scheduling | [Issue dependencies](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-issue-dependencies) |
| Short-lived issue branches, deliberate squash merges, required CI | Keeps independent changes reviewable and the mainline compact; no long-lived development branch by default for one maintainer | [Squash merge tradeoffs](https://docs.github.com/en/pull-requests/reference/pull-request-merges), [Branch protections](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) |
| Independent AI review ≠ GitHub authorized approver | Native protected branches require a real authorized review identity. A sole-owner repository can become unmergeable if 1 approval is required and no legitimate reviewer exists | [Protected branch approval constraints](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) |
| Discussions for RFC/Q&A, not work dispatch | Threaded, asynchronous, durable exploration; actionable work belongs in Issues with Project membership; GraphQL supports discussion comments | [Discussions best practices](https://docs.github.com/en/discussions/guides/best-practices-for-community-conversations-on-github), [GraphQL Discussions](https://docs.github.com/en/graphql/guides/using-the-graphql-api-for-discussions) |
| Verify Projects privileges separately and avoid all-scopes tokens | Projects v2 may require explicit GraphQL access; GitHub Actions default token is scoped and settings can restrict it | [GitHub CLI Projects scope](https://cli.github.com/manual/gh_project), [Workflow permissions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) |

## Important limitations

1. **No full ACID** across GitHub Issues, Projects, PRs and Discussions. The template implements a **recoverable state transition protocol**. A true serializable dispatcher needs an external single-writer/lock or a transactional database; GitHub comments/labels alone cannot provide strong isolation.
2. **No automatic AI dispatch** from label change alone. A runner must poll or receive webhook events and have the right Project/Issues permissions. Configure idempotency, race resolution and rate limits.
3. **No automatic independent approval** merely by using a superior AI. If the same GitHub account posts both Worker and Chief comments, the application cannot claim that GitHub's native independent review requirement is satisfied.
4. **No faithful status guarantee from the built-in Issue closed→Done workflow** without extra verification. Closing an issue is only a projection of accepted delivery; action workflows may need guards.
5. **Discussion content can be stale or unsafe to publish.** Always distill decisions back to issue/ADR scope and verify repository/Project visibility.
6. **Not a mandatory merge policy** until GitHub rulesets and an actual end-to-end enforcement trial demonstrate the chosen checks. Risk-tier approvals and evidence gates are process rules unless supported by a trusted enforcement integration.

## Revisit after a pilot

Run one small issue through Chief specification, Worker implementation, worker→chief escalation, Chief review, a simulated human gate, and a protected merge. Measure token/context load, duplicated API calls, queue lag, dispatch failures, conflict frequency and review findings. Refine only from observed data, not from theoretical simplicity.
