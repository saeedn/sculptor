export type StaticKeybindingId =
  | "command_palette"
  | "help"
  | "home"
  | "settings"
  | "new_workspace"
  | "open_workspace"
  | "close_workspace"
  | "delete_workspace"
  | "next_tab"
  | "previous_tab"
  | "toggle_theme"
  | "next_agent"
  | "previous_agent"
  | "new_agent"
  | "open_in_app"
  | "find_in_file"
  | "clear_terminal";

export type PanelKeybindingId = `panel_${string}`;

export type KeybindingId = StaticKeybindingId | PanelKeybindingId;

export type KeybindingCategory = "general" | "workspaces" | "navigation" | "panels" | "terminal";

export type KeybindingDefinition = {
  id: KeybindingId;
  name: string;
  description: string;
  category: KeybindingCategory;
  defaultBinding: string | null;
};

export type ResolvedKeybinding = KeybindingDefinition & {
  binding: string | null;
  isDefault: boolean;
};

export const CATEGORY_ORDER = ["workspaces", "navigation", "general", "panels", "terminal"] as const;

export const CATEGORY_DISPLAY_NAMES: Readonly<Record<KeybindingCategory, string>> = {
  general: "General",
  workspaces: "Workspaces",
  navigation: "Navigation",
  panels: "Panels",
  terminal: "Terminal",
};
