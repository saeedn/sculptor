import type { CodingAgentTaskView } from "~/api";
import { useWorkspacePageParams } from "~/common/NavigateUtils.ts";
import { useTask } from "~/common/state/hooks/useTaskHelpers";

export type WorkspacePanelData = {
  task: CodingAgentTaskView | null;
};

export const useWorkspacePanelData = (): WorkspacePanelData => {
  const { agentID } = useWorkspacePageParams();
  const task = useTask(agentID ?? "");
  return { task };
};
