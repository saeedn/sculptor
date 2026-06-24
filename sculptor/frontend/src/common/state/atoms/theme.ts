import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";

import type { AppearanceMode } from "~/common/theme/appearanceModes.ts";
import type { ShikiThemePairName } from "~/common/theme/shikiThemes.ts";
import { DEFAULT_SHIKI_THEME } from "~/common/theme/shikiThemes.ts";

/**
 * Radix UI accent color name (the `color` prop accepted by Radix Theme and
 * Radix components). The full picker has been removed, but the color names
 * still flow through to components (e.g. destructive action buttons, status
 * pills) and the terminal palette, so the type and the fixed defaults survive.
 */
export type AccentColor =
  | "gray"
  | "gold"
  | "bronze"
  | "brown"
  | "yellow"
  | "amber"
  | "orange"
  | "tomato"
  | "red"
  | "ruby"
  | "crimson"
  | "pink"
  | "plum"
  | "purple"
  | "violet"
  | "iris"
  | "indigo"
  | "blue"
  | "cyan"
  | "teal"
  | "jade"
  | "green"
  | "grass"
  | "lime"
  | "mint"
  | "sky";

export type GrayColor = "auto" | "gray" | "mauve" | "slate" | "sage" | "olive" | "sand";

/**
 * Slimmed theme settings. Only the fields the app still reads survive: the
 * light/dark/system appearance toggle, the (now fixed) Radix color names that
 * components and the terminal palette derive from, and the code-block theme.
 */
export type ThemeSettings = {
  accentColor: AccentColor;
  appearance: AppearanceMode;
  codeTheme: ShikiThemePairName;
  dangerColor: AccentColor;
  grayColor: GrayColor;
  successColor: AccentColor;
  warningColor: AccentColor;
};

export const DEFAULT_THEME_SETTINGS: ThemeSettings = {
  accentColor: "gray",
  appearance: "dark",
  codeTheme: DEFAULT_SHIKI_THEME,
  dangerColor: "tomato",
  grayColor: "gray",
  successColor: "green",
  warningColor: "amber",
};

/**
 * PRIMARY ATOM: Theme Settings
 *
 * Persisted to localStorage via atomWithStorage so the appearance preference
 * survives across sessions without requiring backend API changes.
 */
export const themeSettingsAtom = atomWithStorage<ThemeSettings>("sculptor-theme", DEFAULT_THEME_SETTINGS);

// Derived atoms for individual settings.

export const themeAccentColorAtom = atom<AccentColor>((get) => get(themeSettingsAtom).accentColor);

export const themeGrayColorAtom = atom<GrayColor>((get) => get(themeSettingsAtom).grayColor);

export const themeAppearanceAtom = atom<AppearanceMode>((get) => get(themeSettingsAtom).appearance);

export const themeDangerColorAtom = atom<AccentColor>((get) => get(themeSettingsAtom).dangerColor);

export const themeSuccessColorAtom = atom<AccentColor>((get) => get(themeSettingsAtom).successColor);

export const themeWarningColorAtom = atom<AccentColor>((get) => get(themeSettingsAtom).warningColor);

export const themeCodeThemeAtom = atom<ShikiThemePairName>(
  (get) => get(themeSettingsAtom).codeTheme ?? DEFAULT_SHIKI_THEME,
);
