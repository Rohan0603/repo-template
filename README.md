# Reusable GitHub Agent Governance Starter Kit

**Purpose:** New solo-developer projects executed by multiple AI models with one GitHub Project as the task/status source of truth.

Copy the single root `AGENTS.md` (full policy and standard auto-discovery filename) to each new repository. Read `docs/SETUP_GITHUB_PROJECTS.md`, create your Project and role labels, then install the optional issue and PR templates.

The default routing is **chief** (research/architecture/decisions/review) or **worker** (implementation) as mutually exclusive labels; **human** is a Chief-managed extra flag for human-only gates. Every actionable issue must live in the correct Project and have one primary role. Don't assume the labels launch agents; a separate dispatcher or manual agent invocation is required.

## Files

- `AGENTS.md` — **only** canonical operating contract and auto-discovered instructions (edit placeholders).
- `.github/ISSUE_TEMPLATE/agent_task.yml` — form for full work context, starts with `chief`.
- `.github/pull_request_template.md` — exact evidence and review gate template.
- `docs/SETUP_GITHUB_PROJECTS.md` — setup commands, views, branch governance and pilot tests.
- `docs/RESEARCH_DECISIONS.md` — sources, rationale and limitations.
- `docs/WORKFLOW_EXAMPLES.md` — complete Chief/Worker/Human transition examples.
- `scripts/validate_governance.py` — optional **read-only** role/Project/status audit; does not grant or enforce permissions.
- `.github/workflows/governance-audit.yml.example` — optional daily/manual read-only Project audit; rename only after setting up secrets/variables.

No existing GitHub or Linear repository is modified by this starter kit. Github Project creation and CLI authorization are separate actions to perform for each **new** repository. Never paste access tokens in chat or commit them to this package.
