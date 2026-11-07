# Reusable GitHub Agent Governance Starter Kit

**Purpose:** New solo-developer projects executed by multiple AI models with one GitHub Project as the task/status source of truth.

Copy the single root `AGENTS.md` (full policy and standard auto-discovery filename) to each new repository. Read `docs/SETUP_GITHUB_PROJECTS.md`, create your Project and role labels, then install the optional issue and PR templates.

The human owner **manually invokes or schedules** AI sessions in Codex, OpenCode, ChatGPT Work, custom orchestrators, or other tools. Each session queries the live GitHub Project and issues, applies advisory issue claims, performs the designated role and writes evidence/handoffs back. **GitHub never launches AI agents.**

The default routing is **chief** (research/architecture/decisions/review) or **worker** (implementation) as mutually exclusive labels; **human** is a Chief-managed extra flag for human-only gates. Every actionable issue must live in the correct Project and have one primary role. Labels never launch agents, and no central dispatcher or external runner service is needed. A scheduled agent session independently discovers its eligible issues through the GitHub Project.

## Files

- `AGENTS.md` — **only** canonical operating contract and auto-discovered instructions (edit placeholders).
- `.github/ISSUE_TEMPLATE/agent_task.yml` — form for full work context, starts with `chief`.
- `.github/pull_request_template.md` — exact evidence and review gate template.
- `docs/SETUP_GITHUB_PROJECTS.md` — setup commands, views, branch governance and pilot tests.
- `docs/RESEARCH_DECISIONS.md` — sources, rationale and limitations.
- `docs/WORKFLOW_EXAMPLES.md` — complete Chief/Worker/Human transition examples.
- `scripts/validate_governance.py` — optional **read-only** role/Project/status audit; does not grant or enforce permissions.
- `.github/workflows/governance-audit.yml.example` — optional daily/manual read-only Project audit; rename only after setting up secrets/variables.

The starter kit does not introduce GitHub-triggered model execution. The scheduled governance audit remains read-only. Github Project creation and CLI authorization are separate actions to perform for each **new** repository. Never paste access tokens in chat or commit them to this package.

## Automated governance checks and repository bootstrap

The template includes an **active** GitHub Actions workflow in `.github/workflows/governance.yml`:

- Pull requests and pushes to `main` run the offline governance-validator unit tests with no secrets.
- Scheduled/manual Projects audits run **only** when the repository variable `GH_PROJECT_NODE_ID` is set. They also require the repository secret `GH_PROJECTS_READ_TOKEN` with **read-only** access to the target Project. A missing secret fails the configured audit; it never silently reports a pass.
- The workflow checks route/status consistency only; it does not automatically dispatch agents or enforce branch protection.

On Windows after creating a new repository from this template:

```powershell
# Preview without any writes
pwsh -File scripts/bootstrap_github.ps1 -Repo OWNER/REPO
# Apply labels and repository PR/Discussion settings with owner/admin permission
pwsh -File scripts/bootstrap_github.ps1 -Repo OWNER/REPO -Execute
```

The bootstrap script creates `chief`, `worker`, `human` labels and opts into Discussions and squash-only merges with merged-branch cleanup. These **repository settings are not copied** from the template into new repositories. Its dry-run mode is the default; it does not delete repositories or alter access controls.

Complete the GitHub Projects v2 creation, Status options/views, auto-add/backfill, required checks, and default-branch protection in `docs/SETUP_GITHUB_PROJECTS.md`. Private-repository protections may require an eligible plan. Never represent an unconfigured Project or unenforced branch rule as active.
