import { KeyboardIcon } from "lucide-react";

import type { CommandRuntime } from "../runtime.ts";
import type { Command } from "../types.ts";

export const buildHelpCommands = (runtime: CommandRuntime): Array<Command> => [
  {
    id: "help.shortcuts",
    title: "Show keyboard shortcuts",
    subtitle: "Open the shortcut reference",
    keywords: ["hotkeys", "bindings", "help", "docs"],
    group: "help",
    icon: KeyboardIcon,
    shortcut: "help",
    perform: () => runtime.ui.toggleHelpDialog(),
  },
];
