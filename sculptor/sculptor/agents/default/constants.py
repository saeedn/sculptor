from typing import Final

from sculptor.interfaces.agents.tool_names import AgentToolName

DEFAULT_WAIT_TIMEOUT: Final[float] = 30.0
REMOVED_MESSAGE_IDS_STATE_FILE: Final[str] = "removed_message_ids"


FILE_CHANGE_TOOL_NAMES: Final[tuple[AgentToolName, ...]] = (
    AgentToolName.EDIT,
    AgentToolName.WRITE,
    AgentToolName.MULTI_EDIT,
)


ENTITY_MENTIONS_SYSTEM_PROMPT: Final[str] = """
<Entity mentions>
When a user message contains text of the form %[type:id|display_name], it refers
to a Sculptor entity:
- type is one of: repository, workspace, agent
- id is the opaque backend identifier for that entity
- display_name is the human-readable name

The id can be used directly with sculpt CLI commands. For example:
  sculpt workspace show <id>
  sculpt agent list --workspace <id>
  sculpt agent show <id>

Do not assume the display_name is a valid argument to sculpt commands — always
use the id.
</Entity mentions>
"""

# Mode-specific system prompt content
WORKTREE_MODE_PROMPT: Final[str] = """
<Environment mode>
You are working in a git worktree of the user's local repository (worktree mode).

The checkout is a real git worktree, so the `.git` directory is shared with the user's repository on disk. Commits you make on this branch are immediately visible in the user's working copy — there is no separate sync step.

Because the `.git` is shared, the remotes you see (e.g. `origin`) are the user's real remotes, and there is no `local` remote. Your commits and branch are written straight into the user's `.git`, so they show up in the user's repo automatically.

You can push changes normally with `git push`, but NEVER do so without explicit permission from the user.
</Environment mode>
"""
