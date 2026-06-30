import { PuzzleIcon } from "lucide-react";

import type { Command } from "../types.ts";

// Individual panel toggles (Files, Actions, Terminal, …) live on the
// `view.panels` sub-page so the root list isn't dominated by "Toggle X" rows.
// The page title intentionally matches what users search for ("Toggle panel
// visibility...") so typing it surfaces the page that actually lists panels.
export const buildPanelCommands = (): Array<Command> => [
  {
    id: "view.toggle_panels",
    title: "Toggle panel visibility...",
    subtitle: "Show or hide individual panels (Files, Actions, Terminal, …)",
    keywords: ["panel", "visibility", "show", "hide", "view", "tool"],
    group: "view",
    icon: PuzzleIcon,
    pageId: "view.panels",
    primary: true,
    order: 110,
    when: (ctx) => ctx.route.isWorkspace,
    perform: (): void => {
      // Page push handled by the runner.
    },
  },
];
