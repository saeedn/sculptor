import { Circle } from "lucide-react";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import type { UserConfig } from "~/api";
import { userConfigAtom } from "~/common/state/atoms/userConfig.ts";
import {
  createPanelStore,
  isZoneVisibleAtom,
  panelEnabledAtom,
  panelShortcutsAtom,
  panelsInZoneAtom,
} from "~/components/panels/atoms.ts";
import type { PanelDefinition } from "~/components/panels/types.ts";

const TEST_PANELS: ReadonlyArray<PanelDefinition> = [
  {
    id: "info",
    displayName: "Info",
    description: "Test panel",
    icon: Circle,
    defaultZone: "top-left",
    defaultShortcut: "",
    component: () => createElement("div"),
  },
  {
    id: "terminal",
    displayName: "Terminal",
    description: "Test panel",
    icon: Circle,
    defaultZone: "bottom",
    defaultShortcut: "",
    component: () => createElement("div"),
  },
  {
    id: "changes",
    displayName: "Changes",
    description: "Test panel",
    icon: Circle,
    defaultZone: "top-right",
    defaultShortcut: "",
    component: () => createElement("div"),
  },
];

beforeEach(() => localStorage.clear());
afterEach(() => localStorage.clear());

describe("panel enabled state", () => {
  it("disabling a non-builtin panel removes it from panelsInZoneAtom", () => {
    const store = createPanelStore(TEST_PANELS, { useDefaultLayout: true });
    expect(store.get(panelsInZoneAtom("top-left"))).toEqual(["info"]);
    store.set(panelEnabledAtom, { info: false });
    expect(store.get(panelsInZoneAtom("top-left"))).toEqual([]);
  });

  it("disabling the only panel in a zone hides the zone", () => {
    const store = createPanelStore(TEST_PANELS, { useDefaultLayout: true });
    expect(store.get(isZoneVisibleAtom("top-left"))).toBe(true);
    store.set(panelEnabledAtom, { info: false });
    expect(store.get(isZoneVisibleAtom("top-left"))).toBe(false);
  });

  it("re-enabling restores the panel in its previously assigned zone", () => {
    const store = createPanelStore(TEST_PANELS, { useDefaultLayout: true });
    store.set(panelEnabledAtom, { info: false });
    expect(store.get(panelsInZoneAtom("top-left"))).toEqual([]);
    store.set(panelEnabledAtom, { info: true });
    expect(store.get(panelsInZoneAtom("top-left"))).toEqual(["info"]);
  });

  it("ignores stored disabled state for builtin panels", () => {
    const builtinPanels: ReadonlyArray<PanelDefinition> = TEST_PANELS.map((p) =>
      p.id === "info" ? { ...p, isBuiltin: true } : p,
    );
    const store = createPanelStore(builtinPanels, { useDefaultLayout: true });
    store.set(panelEnabledAtom, { info: false });
    expect(store.get(panelsInZoneAtom("top-left"))).toEqual(["info"]);
  });

  it("excludes disabled panels from panelShortcutsAtom", () => {
    const panelsWithShortcut: ReadonlyArray<PanelDefinition> = TEST_PANELS.map((p) =>
      p.id === "info" ? { ...p, defaultShortcut: "Cmd+1" } : p,
    );
    const store = createPanelStore(panelsWithShortcut, { useDefaultLayout: true });
    expect(store.get(panelShortcutsAtom).info).toBe("Cmd+1");
    store.set(panelEnabledAtom, { info: false });
    expect(store.get(panelShortcutsAtom).info).toBeUndefined();
  });
});

describe("panelShortcutsAtom round-trip via userConfig.keybindings", () => {
  it("returns an empty map when every panel has an empty defaultShortcut and no overrides", () => {
    const store = createPanelStore(TEST_PANELS, { useDefaultLayout: true });
    expect(store.get(panelShortcutsAtom)).toEqual({});
  });

  it("flows a userConfig override into the result map", () => {
    const store = createPanelStore(TEST_PANELS, { useDefaultLayout: true });
    store.set(userConfigAtom, { keybindings: { panel_info: "Meta+E" } } as unknown as UserConfig);
    expect(store.get(panelShortcutsAtom).info).toBe("Meta+E");
  });

  it("treats an explicit null override as no shortcut (entry absent)", () => {
    const panelsWithDefault: ReadonlyArray<PanelDefinition> = TEST_PANELS.map((p) =>
      p.id === "info" ? { ...p, defaultShortcut: "Cmd+1" } : p,
    );
    const store = createPanelStore(panelsWithDefault, { useDefaultLayout: true });
    expect(store.get(panelShortcutsAtom).info).toBe("Cmd+1");
    store.set(userConfigAtom, { keybindings: { panel_info: null } } as unknown as UserConfig);
    expect(store.get(panelShortcutsAtom).info).toBeUndefined();
  });
});
