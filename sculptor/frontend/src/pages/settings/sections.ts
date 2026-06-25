import {
  CodeIcon,
  CogIcon,
  FolderTreeIcon,
  GitBranchIcon,
  KeyboardIcon,
  PlayIcon,
  ShieldCheckIcon,
  ShieldIcon,
  TerminalIcon,
} from "lucide-react";
import type { ComponentType } from "react";

import { ElementIds } from "../../api";

/**
 * Single source of truth for Settings sections.
 *
 * Both the Settings page sidebar (`SettingsPage.tsx`) and the Cmd+K
 * command palette (`builtinCommands/settings.ts`) consume the
 * `SETTINGS_SECTIONS` array below. Adding, reordering, or renaming a
 * section here propagates to both places automatically — no separate
 * registry to keep in sync.
 *
 * Order in this array IS the rendered order in the sidebar and the
 * palette's "Go to settings..." sub-page.
 */

export const SettingsSection = {
  GENERAL: "GENERAL",
  AGENT: "AGENT",
  KEYBINDINGS: "KEYBINDINGS",
  REPOSITORIES: "REPOSITORIES",
  GIT: "GIT",
  CI: "CI",
  FILE_BROWSER: "FILE_BROWSER",
  PROJECT_ENV_VARS: "PROJECT_ENV_VARS",
  PRIVACY: "PRIVACY",
  ACTIONS: "ACTIONS",
} as const;

export type SettingsSectionId = (typeof SettingsSection)[keyof typeof SettingsSection];

type LucideIconType = ComponentType<{ size?: number | string }>;

export type SettingsSectionDescriptor = {
  id: SettingsSectionId;
  /** Sidebar label and palette row title (without the "Settings: " prefix). */
  displayName: string;
  /** Short hint shown in the palette beneath the row title. */
  paletteSubtitle: string;
  /** Extra fuzzy-search keywords for the palette. "settings" / "preferences" are added automatically. */
  paletteKeywords: ReadonlyArray<string>;
  /** Lucide icon used in the palette row. */
  icon: LucideIconType;
  /** Sidebar test id (also used by the palette row when emitted). */
  testId: string;
};

export const SETTINGS_SECTIONS: ReadonlyArray<SettingsSectionDescriptor> = [
  {
    id: SettingsSection.GENERAL,
    displayName: "General",
    paletteSubtitle: "Theme, updates",
    paletteKeywords: ["theme", "updates"],
    icon: CogIcon,
    testId: ElementIds.SETTINGS_NAV_GENERAL,
  },
  {
    id: SettingsSection.AGENT,
    displayName: "Agent",
    paletteSubtitle: "Default model and effort",
    paletteKeywords: ["model", "llm", "claude"],
    icon: PlayIcon,
    testId: ElementIds.SETTINGS_NAV_AGENT,
  },
  {
    id: SettingsSection.KEYBINDINGS,
    displayName: "Keybindings",
    paletteSubtitle: "Customize keyboard shortcuts",
    paletteKeywords: ["shortcuts", "hotkeys"],
    icon: KeyboardIcon,
    testId: ElementIds.SETTINGS_NAV_KEYBINDINGS,
  },
  {
    id: SettingsSection.REPOSITORIES,
    displayName: "Repositories",
    paletteSubtitle: "Manage repos",
    paletteKeywords: ["repos", "projects"],
    icon: GitBranchIcon,
    testId: ElementIds.SETTINGS_NAV_REPOSITORIES,
  },
  {
    id: SettingsSection.GIT,
    displayName: "Git",
    paletteSubtitle: "Git provider configuration",
    paletteKeywords: ["github", "gitlab"],
    icon: GitBranchIcon,
    testId: ElementIds.SETTINGS_NAV_GIT,
  },
  {
    id: SettingsSection.CI,
    displayName: "CI",
    paletteSubtitle: "CI Babysitter and CI integrations",
    paletteKeywords: ["pipeline", "babysitter", "ci"],
    icon: ShieldIcon,
    testId: ElementIds.SETTINGS_NAV_CI,
  },
  {
    id: SettingsSection.FILE_BROWSER,
    displayName: "File browser",
    paletteSubtitle: "Diff views and tab behavior",
    paletteKeywords: ["diff", "files"],
    icon: FolderTreeIcon,
    testId: ElementIds.SETTINGS_NAV_FILE_BROWSER,
  },
  {
    id: SettingsSection.PROJECT_ENV_VARS,
    displayName: "Environment variables",
    paletteSubtitle: "Per-project env",
    paletteKeywords: ["env", "vars"],
    icon: TerminalIcon,
    testId: ElementIds.SETTINGS_NAV_PROJECT_ENV_VARS,
  },
  {
    id: SettingsSection.PRIVACY,
    displayName: "Privacy",
    paletteSubtitle: "Email and telemetry",
    paletteKeywords: ["account", "profile", "telemetry", "tracking", "data", "opt out"],
    icon: ShieldCheckIcon,
    testId: ElementIds.SETTINGS_NAV_PRIVACY,
  },
  {
    id: SettingsSection.ACTIONS,
    displayName: "Actions",
    paletteSubtitle: "Custom actions",
    paletteKeywords: ["custom"],
    icon: CodeIcon,
    testId: ElementIds.SETTINGS_NAV_ACTIONS,
  },
];
