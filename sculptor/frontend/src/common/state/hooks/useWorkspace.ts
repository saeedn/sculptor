import { useAtomValue } from "jotai";

import type { Workspace } from "../../../api";
import { workspaceAtomFamily } from "../atoms/workspaces";

/**
 * Hook to access workspace data by ID.
 * Returns null if workspace is not loaded or workspaceId is null/undefined.
 */
export const useWorkspace = (workspaceId: string | null | undefined): Workspace | null => {
  // Handle null/undefined workspaceId gracefully
  const workspace = useAtomValue(workspaceAtomFamily(workspaceId ?? ""));

  if (!workspaceId) {
    return null;
  }

  return workspace;
};
