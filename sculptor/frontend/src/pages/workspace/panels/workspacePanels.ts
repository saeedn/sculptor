import { FolderOpen, Terminal, Zap } from "lucide-react";

import type { DefaultPanelLayout, PanelDefinition } from "~/components/panels/types.ts";

import { ActionsPanel } from "./ActionsPanel.tsx";
import { FileBrowserPanel } from "./FileBrowserPanel.tsx";
import { TerminalPanelWrapper } from "./TerminalPanel.tsx";

export const workspacePanels: ReadonlyArray<PanelDefinition> = [
  {
    id: "files",
    displayName: "File browser",
    description: "Browse repo files and diffs",
    icon: FolderOpen,
    defaultZone: "top-left",
    defaultShortcut: "",
    component: FileBrowserPanel,
  },
  {
    id: "terminal",
    displayName: "Terminal",
    description: "Open a terminal in the workspace container",
    icon: Terminal,
    defaultZone: "bottom",
    defaultShortcut: "",
    component: TerminalPanelWrapper,
  },
  {
    id: "actions",
    displayName: "Actions",
    description: "Run saved commands against the workspace",
    icon: Zap,
    defaultZone: "top-right",
    defaultShortcut: "",
    component: ActionsPanel,
  },
];

/** Default layout: Files (top-left) and Terminal (bottom) expanded; Actions collapsed. */
export const workspaceDefaultLayout: DefaultPanelLayout = {
  zoneAssignments: {
    files: "top-left",
    actions: "top-right",
    terminal: "bottom",
  },
  activePanelPerZone: {
    "top-left": "files",
    "top-right": "actions",
    bottom: "terminal",
  },
  zoneVisibility: {
    "top-left": true,
    "top-right": false,
    bottom: true,
  },
  zoneOrder: {
    "top-left": ["files"],
    "top-right": ["actions"],
    bottom: ["terminal"],
  },
};
