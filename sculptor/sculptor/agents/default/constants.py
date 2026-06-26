from typing import Final

# Mode-specific system prompt content
WORKTREE_MODE_PROMPT: Final[str] = """
<Environment mode>
You are working in a git worktree of the user's local repository (worktree mode).

The checkout is a real git worktree, so the `.git` directory is shared with the user's repository on disk. Commits you make on this branch are immediately visible in the user's working copy — there is no separate sync step.

Because the `.git` is shared, the remotes you see (e.g. `origin`) are the user's real remotes, and there is no `local` remote. Your commits and branch are written straight into the user's `.git`, so they show up in the user's repo automatically.

You can push changes normally with `git push`, but NEVER do so without explicit permission from the user.
</Environment mode>
"""
