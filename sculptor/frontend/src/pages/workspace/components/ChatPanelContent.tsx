import { type ReactElement } from "react";

import { useWorkspacePageParams } from "~/common/NavigateUtils.ts";

import { AgentTerminalPanel } from "./AgentTerminalPanel.tsx";
import styles from "./ChatPanelContent.module.scss";
import { SetupStatusCard } from "./SetupStatusCard.tsx";

/**
 * The main panel for an agent: a pinned workspace setup-status row above a
 * full-pane terminal. Every agent is a terminal agent, so the panel always
 * renders `AgentTerminalPanel`; the setup card surfaces the workspace's
 * setup-command status (or the configure-CTA) independently of the agent.
 */
export const ChatPanelContent = (): ReactElement => {
  const { workspaceID, agentID: taskID } = useWorkspacePageParams();

  return (
    <div className={styles.panel}>
      {workspaceID && (
        <div className={styles.setupRow}>
          <SetupStatusCard workspaceId={workspaceID} />
        </div>
      )}
      {/* Keyed by task id: a direct terminal->terminal tab switch must remount
          the panel so each agent gets its own xterm instance. Without the key,
          React reuses the component and the previous agent's scrollback stays
          in the (single) xterm buffer when the WebSocket reconnects to the new
          agent's PTY — leaking one tab's content into another. */}
      <AgentTerminalPanel key={taskID} taskId={taskID ?? ""} />
    </div>
  );
};
