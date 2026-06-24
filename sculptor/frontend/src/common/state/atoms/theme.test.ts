import { createStore } from "jotai";
import { describe, expect, it } from "vitest";

import {
  DEFAULT_THEME_SETTINGS,
  themeAccentColorAtom,
  themeAppearanceAtom,
  themeCodeThemeAtom,
  themeDangerColorAtom,
  themeGrayColorAtom,
  themeSettingsAtom,
  themeSuccessColorAtom,
  themeWarningColorAtom,
} from "./theme";

describe("DEFAULT_THEME_SETTINGS", () => {
  it("has correct default values", () => {
    expect(DEFAULT_THEME_SETTINGS).toEqual({
      accentColor: "gray",
      appearance: "dark",
      codeTheme: "GitHub",
      dangerColor: "tomato",
      grayColor: "gray",
      successColor: "green",
      warningColor: "amber",
    });
  });
});

describe("themeSettingsAtom", () => {
  it("returns defaults when no value is set", () => {
    const store = createStore();
    expect(store.get(themeSettingsAtom)).toEqual(DEFAULT_THEME_SETTINGS);
  });

  it("can be updated with new settings", () => {
    const store = createStore();
    store.set(themeSettingsAtom, { ...DEFAULT_THEME_SETTINGS, accentColor: "blue" as const });
    expect(store.get(themeSettingsAtom).accentColor).toBe("blue");
  });

  it("preserves other fields on partial update via spread", () => {
    const store = createStore();
    const current = store.get(themeSettingsAtom);
    store.set(themeSettingsAtom, { ...current, dangerColor: "crimson" as const });

    const updated = store.get(themeSettingsAtom);
    expect(updated.dangerColor).toBe("crimson");
    expect(updated.accentColor).toBe("gray");
  });
});

describe("derived atoms", () => {
  it("themeAccentColorAtom returns accentColor from settings", () => {
    const store = createStore();
    expect(store.get(themeAccentColorAtom)).toBe("gray");

    store.set(themeSettingsAtom, { ...DEFAULT_THEME_SETTINGS, accentColor: "blue" as const });
    expect(store.get(themeAccentColorAtom)).toBe("blue");
  });

  it("themeGrayColorAtom returns grayColor from settings", () => {
    const store = createStore();
    expect(store.get(themeGrayColorAtom)).toBe("gray");

    store.set(themeSettingsAtom, { ...DEFAULT_THEME_SETTINGS, grayColor: "sand" as const });
    expect(store.get(themeGrayColorAtom)).toBe("sand");
  });

  it("themeAppearanceAtom returns appearance from settings", () => {
    const store = createStore();
    expect(store.get(themeAppearanceAtom)).toBe("dark");

    store.set(themeSettingsAtom, { ...DEFAULT_THEME_SETTINGS, appearance: "light" as const });
    expect(store.get(themeAppearanceAtom)).toBe("light");
  });

  it("themeDangerColorAtom returns dangerColor from settings", () => {
    const store = createStore();
    expect(store.get(themeDangerColorAtom)).toBe("tomato");

    store.set(themeSettingsAtom, { ...DEFAULT_THEME_SETTINGS, dangerColor: "red" as const });
    expect(store.get(themeDangerColorAtom)).toBe("red");
  });

  it("themeSuccessColorAtom returns successColor from settings", () => {
    const store = createStore();
    expect(store.get(themeSuccessColorAtom)).toBe("green");

    store.set(themeSettingsAtom, { ...DEFAULT_THEME_SETTINGS, successColor: "teal" as const });
    expect(store.get(themeSuccessColorAtom)).toBe("teal");
  });

  it("themeWarningColorAtom returns warningColor from settings", () => {
    const store = createStore();
    expect(store.get(themeWarningColorAtom)).toBe("amber");

    store.set(themeSettingsAtom, { ...DEFAULT_THEME_SETTINGS, warningColor: "orange" as const });
    expect(store.get(themeWarningColorAtom)).toBe("orange");
  });

  it("themeCodeThemeAtom returns codeTheme from settings", () => {
    const store = createStore();
    expect(store.get(themeCodeThemeAtom)).toBe("GitHub");
  });
});
