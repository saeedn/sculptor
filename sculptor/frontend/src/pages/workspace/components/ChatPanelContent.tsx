import type { Editor as TipTapEditor } from "@tiptap/react";
import { useAtomValue, useSetAtom } from "jotai";
import { type ReactElement, useEffect } from "react";

import { useWorkspacePageParams } from "~/common/NavigateUtils.ts";
import { debugViewAtomFamily } from "~/common/state/atoms/alphaScroll.ts";
import type { InsertSkillArg } from "~/common/state/atoms/chatActions.ts";
import { useTaskSupportsChatInterface } from "~/common/state/hooks/useTaskHelpers.ts";
import { chatPanelMountedAtom } from "~/components/panels/atoms.ts";

import { AgentTerminalPanel } from "./AgentTerminalPanel.tsx";
import { AlphaChatInterface } from "./chat-alpha/AlphaChatInterface.tsx";
import { DebugChatView } from "./chat-alpha/DebugChatView.tsx";
import { useChatData } from "./useChatData.ts";

type ChatPanelContentProps = {
  appendTextRef?: React.MutableRefObject<((text: string) => void) | null>;
  insertSkillRef?: React.MutableRefObject<((skill: InsertSkillArg) => void) | null>;
  editorRef?: React.MutableRefObject<TipTapEditor | null>;
};

/**
 * The main-panel switch: terminal agents get a full-pane terminal in the
 * space the chat interface occupies for chat agents, driven by the
 * `supports_chat_interface` capability.
 *
 * The switch lives outside `ChatPanelInner` because `useChatData` must not
 * run for terminal agents — it registers `chatActionsAtom` closures, which
 * is exactly what keeps Commit / Create PR / custom actions disabled for
 * them (the load-bearing gate).
 */
export const ChatPanelContent = ({
  appendTextRef,
  insertSkillRef,
  editorRef,
}: ChatPanelContentProps): ReactElement | null => {
  const { agentID: taskID } = useWorkspacePageParams();
  const isChatInterfaceSupported = useTaskSupportsChatInterface(taskID ?? "");

  if (isChatInterfaceSupported === false) {
    // Keyed by task id: a direct terminal->terminal tab switch must remount
    // the panel so each agent gets its own xterm instance. Without the key,
    // React reuses the component and the previous agent's scrollback stays
    // in the (single) xterm buffer when the WebSocket reconnects to the new
    // agent's PTY — leaking one tab's content into another.
    return <AgentTerminalPanel key={taskID} taskId={taskID ?? ""} />;
  }

  // While capabilities are loading, render nothing rather than the chat —
  // mounting useChatData for a terminal agent would register chat actions,
  // and a chat→terminal swap flashes. This deliberately differs from
  // useCapabilityGate's `?? true` affordance default.
  if (isChatInterfaceSupported === undefined) {
    return null;
  }
  return <ChatPanelInner appendTextRef={appendTextRef} insertSkillRef={insertSkillRef} editorRef={editorRef} />;
};

const ChatPanelInner = ({ appendTextRef, insertSkillRef, editorRef }: ChatPanelContentProps): ReactElement => {
  const { workspaceID, agentID: taskID } = useWorkspacePageParams();
  const isDebugView = useAtomValue(debugViewAtomFamily(taskID ?? ""));
  const setChatPanelMounted = useSetAtom(chatPanelMountedAtom);

  const chatData = useChatData({ taskID: taskID ?? "", workspaceID, appendTextRef, insertSkillRef });

  // Reactive signal for "is the chat panel currently rendered?" — read by the
  // command palette (via `chatPanelMountedAtom`) instead of poking the DOM.
  // The debug view replaces the chat panel and so doesn't count.
  const isChatPanelRendered = !isDebugView;
  useEffect(() => {
    if (!isChatPanelRendered) return;
    setChatPanelMounted(true);
    return (): void => {
      setChatPanelMounted(false);
    };
  }, [isChatPanelRendered, setChatPanelMounted]);

  if (isDebugView) {
    return <DebugChatView messages={chatData.chatMessages} />;
  }

  return (
    <AlphaChatInterface
      {...chatData}
      appendTextRef={appendTextRef}
      insertSkillRef={insertSkillRef}
      editorRef={editorRef}
    />
  );
};
