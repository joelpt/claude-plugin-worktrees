# worktrees

Surfaces a repo's **mergeable git worktrees** at session start and offers a
guided, confidence-gated, conflict-aware merge into the default branch.

A worktree is "mergeable" when it has **no live `claude` session** sitting in it.
Everything is **repo-scoped**: although `claude agents --json` lists sessions
across every repo on the machine, this plugin only ever inspects and acts on
worktrees of the repo your current session belongs to — never cross-repo.

## Components

- **SessionStart hook** — on `startup`/`resume`, only when cwd is the repo's
  **main** worktree, silently checks for mergeable worktrees. If any exist, it
  emits a user-facing `systemMessage` banner naming the count and pointing the
  user at `/merge-worktrees` to land them (or `/check-worktrees` to review
  first). The banner is shown to the user only — it is **not** injected into
  the agent's context and never asks the agent to act, so merging stays a
  deliberate, explicit user opt-in (you type the slash command). The hook never
  merges or mutates anything; silent when there's nothing to surface.
- **`/worktrees:check-worktrees`** — renders a table of the repo's linked
  worktrees (dirty state, commits ahead, last commit, live session) and asks
  which to merge (All / None / a paged subset). `--show-all` includes worktrees
  that currently have a session.
- **`/worktrees:merge-worktrees`** — lands the chosen worktrees into the default
  branch from the primary checkout by **rebase + fast-forward** (linear history, no
  merge commits): commits dirty trees (via `commit-commands:commitall`), snapshots a
  restore anchor, determines a land order (escalating advisor → thinking-suite → HITL
  only when confidence is low), lands each via the engine with conflict handling,
  runs the test suite, and on failure rolls back to the exact pre-land state. The
  deterministic git work lives in `worktree_engine.py`; the skill only fills the
  judgement gaps.
- **`/rmws`** (separate personal skill) delegates here: it `ExitWorktree`s the
  current worktree to the primary and calls `/worktrees:merge-worktrees --worktree
  <it>`, re-entering the worktree if the land aborts.

## Scripts

- `scripts/check_worktrees.py` — async, stdlib-only detector/renderer. Shared by
  the hook (`--json`, for the gate) and the skill (table + `--json`).
  `--cwd <path>`, `--show-all`, `--json`.
- `scripts/worktree_engine.py` — deterministic land engine: `land` (preflight +
  rebase + ff-merge; leaves the rebase in progress on conflict), `rebase-continue`,
  `snapshot` / `undo` (exact-state restore), and `teardown` (idempotent, path-gated
  worktree removal + `branch -d`, no `--force`/`-D`).

## Safety

- Linear history only — rebase + ff-merge, never a merge commit.
- Rollback is a **scoped, anchor-protected `git reset --hard`** (engine `undo`): safe
  because everything is committed and snapshotted before any rebase, and `--hard`
  never touches untracked files. Mid-rebase conflicts abort cleanly (no reset).
- Conflict resolution prompts the user only when confidence is low/medium.
- Teardown refuses dirty worktrees and unmerged branches.
- Respects the active project's CLAUDE.md (e.g. SSH-approval gates).

## License

MIT
