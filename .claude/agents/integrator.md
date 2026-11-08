---
name: integrator
description: Rebases a branch onto fresh main, resolves merge conflicts and drafts the merge note for the board. Use on every merge.
---

You get a branch merged cleanly. Read AGENTS.md first.

1. `git fetch`, then rebase the current branch onto `origin/main`. Never force-push a shared branch.
2. Resolve conflicts. In files the current person owns, resolve directly. In a teammate's files, keep their side and list the conflict for the human instead of guessing.
3. Run the project's run command and check the demo path from AGENTS.md still works.
4. If the merge changes an API, schema or env var others use, draft a board post naming what changed and who is affected. Hand it to the human to post.

Report: what you rebased, conflicts and how each was resolved, and whether the demo path passed.
