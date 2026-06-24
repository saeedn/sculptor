import { ArrowDownIcon, MessageSquareIcon, SearchIcon } from "lucide-react";

import type { CommandRuntime } from "../runtime.ts";
import type { Command } from "../types.ts";

export const buildChatCommands = (runtime: CommandRuntime): Array<Command> => [
  {
    id: "chat.focus_input",
    title: "Focus chat input",
    subtitle: "Move keyboard focus to the chat box",
    keywords: ["compose", "type"],
    group: "chat",
    icon: MessageSquareIcon,
    shortcut: "focus_input",
    // Only show on surfaces where there's actually a chat input to
    // focus. The `focus_input` keybinding (in
    // usePageLayoutKeyboardShortcuts) covers the AddWorkspace name
    // input as a separate, keyboard-only fallback — but the palette
    // row's title says "Focus chat input", so it must not surface
    // anywhere a chat input doesn't exist.
    when: (ctx) => ctx.hasChatPanel,
    perform: () => runtime.ui.focusChatInput(),
  },
  {
    id: "chat.search",
    title: "Search within chat",
    subtitle: "Find a message in this conversation",
    keywords: ["find", "query"],
    group: "chat",
    icon: SearchIcon,
    shortcut: "chat_search",
    when: (ctx) => ctx.hasChatPanel,
    perform: () => runtime.ui.showChatSearch(),
  },
  {
    id: "chat.jump_bottom",
    title: "Jump to bottom",
    subtitle: "Scroll to the latest message",
    keywords: ["scroll", "tail"],
    group: "chat",
    icon: ArrowDownIcon,
    when: (ctx) => ctx.hasChatPanel,
    perform: () => runtime.ui.jumpChatToBottom(),
  },
];
