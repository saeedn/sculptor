import { useWorkspacePageParams } from "~/common/NavigateUtils.ts";
import { useWorkspace } from "~/common/state/hooks/useWorkspace.ts";

/**
 * Returns the absolute path of the code directory for a workspace.
 *
 * Worktree workspaces own their own checkout at `${environmentId}/code`.
 * Returns null if the information is not yet available.
 *
 * When called without arguments, uses the workspace ID from the current URL.
 * Pass an explicit `workspaceId` to look up a specific workspace.
 *
 * TODO: The backend should expose the code path directly on the workspace
 * object so the frontend doesn't need to re-derive it from environmentId.
 */
export const useWorkspaceCodePath = (workspaceId?: string): string | null => {
  const { workspaceID: workspaceIdFromParams } = useWorkspacePageParams();
  const resolvedWorkspaceId = workspaceId ?? workspaceIdFromParams;
  const workspace = useWorkspace(resolvedWorkspaceId);

  if (!workspace) {
    return null;
  }

  return workspace.environmentId ? `${workspace.environmentId}/code` : null;
};
