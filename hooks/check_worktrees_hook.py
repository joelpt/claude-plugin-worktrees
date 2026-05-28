#!/usr/bin/env python3
"""SessionStart hook: surface this repo's mergeable worktrees.

Gate-then-inject. Fires only for startup/resume (enforced by hooks.json
matchers; re-checked defensively here). Stays completely silent unless:
  - cwd is inside a git repo, AND
  - cwd is the repo's MAIN worktree (never a linked worktree — the review
    skill must not run from inside a worktree), AND
  - the repo has >=1 linked worktree with NO live claude session.

When all hold, it prints (plain stdout → injected as SessionStart context)
a forceful, mandatory-framed directive instructing the agent to run the
/worktrees:check-worktrees skill and AskUserQuestion gate before any other
work this turn. SessionStart hooks cannot force a tool call (exit 2 does not
block here, and hooks "cannot trigger / commands or tool calls") — injected
stdout is passive context the agent may ignore, so the wording is pushed to
its imperative ceiling to maximise compliance. This hook itself never merges
or mutates anything; the skill drives the human-gated flow.

Repo-scoped by construction: the detector only inspects worktrees of this
repo. Exit code is always 0 — a failing SessionStart hook would degrade the
user's session for no benefit.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ALLOWED_SOURCES = {"startup", "resume"}


def read_stdin() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def is_main_worktree(cwd: str) -> bool:
    """True iff cwd is the main (non-linked) worktree of its git repo."""
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--git-dir", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return False
    if proc.returncode != 0:
        return False
    lines = proc.stdout.strip().splitlines()
    if len(lines) != 2:
        return False
    git_dir, common_dir = lines
    # Linked worktrees have a distinct per-worktree git dir; main does not.
    return os.path.realpath(git_dir) == os.path.realpath(common_dir)


def detector_path() -> Path:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if root:
        return Path(root) / "scripts" / "check_worktrees.py"
    return Path(__file__).resolve().parent.parent / "scripts" / "check_worktrees.py"


def count_orphans(cwd: str) -> int:
    """Run the detector in --json mode; return the orphan count (0 on error)."""
    try:
        proc = subprocess.run(
            [sys.executable, str(detector_path()), "--cwd", cwd, "--json"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception:
        return 0
    try:
        data = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return 0
    return len(data) if isinstance(data, list) else 0


def main() -> int:
    payload = read_stdin()
    source = payload.get("source", "")
    if source and source not in ALLOWED_SOURCES:
        return 0
    cwd = payload.get("cwd") or os.getcwd()

    if not is_main_worktree(cwd):
        return 0

    n = count_orphans(cwd)
    if n <= 0:
        return 0

    plural = "worktree" if n == 1 else "worktrees"
    pronoun = "it" if n == 1 else "they"
    verb = "is" if n == 1 else "are"
    print(
        f"🚨 MANDATORY — {n} mergeable {plural} detected 🚨\n\n"
        f"This repo has {n} linked git {plural} with no live `claude` session, "
        f"so {pronoun} {verb} likely ready to merge into the default branch.\n\n"
        f"BEFORE answering the user's query or taking ANY other action this turn, "
        f"you MUST:\n"
        f"1. Invoke the `/worktrees:check-worktrees` skill now and show its table "
        f"output to the user.\n"
        f"2. Then IMMEDIATELY use `AskUserQuestion` to ask whether they want to "
        f"merge the pending {plural} via `/worktrees:merge-worktrees` before "
        f"continuing.\n\n"
        f"DEFER the user's actual question / request / command until AFTER that "
        f"`AskUserQuestion` — and any resulting `/worktrees:merge-worktrees` run — "
        f"has fully concluded. MANDATORY, NO EXCEPTIONS, REQUIRED BEHAVIOR. "
        f"Failure to do this violates the user's explicit wishes. 🚨\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
