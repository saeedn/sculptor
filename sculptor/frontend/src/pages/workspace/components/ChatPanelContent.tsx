import { type ReactElement } from "react";

import { useWorkspacePageParams } from "~/common/NavigateUtils.ts";

import { AgentTerminalPanel } from "./AgentTerminalPanel.tsx";

/**
 * The main panel for an agent: a full-pane terminal. Every agent is a
 * terminal agent, so the panel always renders `AgentTerminalPanel`.
 */
export const ChatPanelContent = (): ReactElement => {
  const { agentID: taskID } = useWorkspacePageParams();

  // Keyed by task id: a direct terminal->terminal tab switch must remount
  // the panel so each agent gets its own xterm instance. Without the key,
  // React reuses the component and the previous agent's scrollback stays
  // in the (single) xterm buffer when the WebSocket reconnects to the new
  // agent's PTY — leaking one tab's content into another.
  return <AgentTerminalPanel key={taskID} taskId={taskID ?? ""} />;
};
