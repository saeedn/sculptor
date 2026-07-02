import { useAtomValue } from "jotai";

import type { AccentColor, GrayColor } from "../atoms/theme";
import {
  themeAccentColorAtom,
  themeAppearanceAtom,
  themeDangerColorAtom,
  themeGrayColorAtom,
  themeSuccessColorAtom,
  themeWarningColorAtom,
} from "../atoms/theme";

export const useThemeDangerColor = (): AccentColor => {
  return useAtomValue(themeDangerColorAtom);
};

export const useThemeSuccessColor = (): AccentColor => {
  return useAtomValue(themeSuccessColorAtom);
};

export const useThemeWarningColor = (): AccentColor => {
  return useAtomValue(themeWarningColorAtom);
};

export const useThemeAccentColor = (): AccentColor => {
  return useAtomValue(themeAccentColorAtom);
};

export const useThemeGrayColor = (): GrayColor => {
  return useAtomValue(themeGrayColorAtom);
};

export const useThemeAppearance = (): "light" | "dark" | "system" => {
  return useAtomValue(themeAppearanceAtom);
};
