import { render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { Circle } from "lucide-react";
import type { ReactElement } from "react";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  activePanelPerZoneAtom,
  panelRegistryAtom,
  zoneAssignmentsAtom,
  zoneOrderAtom,
  zoneVisibilityAtom,
} from "~/components/panels/atoms.ts";
import { PanelRegistryProvider } from "~/components/panels/PanelRegistryProvider";
import type { DefaultPanelLayout, PanelDefinition } from "~/components/panels/types.ts";

const INFO_PANEL: PanelDefinition = {
  id: "info",
  displayName: "Info",
  description: "Test info panel",
  icon: Circle,
  defaultZone: "top-left",
  defaultShortcut: "",
  component: () => createElement("div"),
};

const TERMINAL_PANEL: PanelDefinition = {
  id: "terminal",
  displayName: "Terminal",
  description: "Test terminal panel",
  icon: Circle,
  defaultZone: "bottom",
  defaultShortcut: "",
  component: () => createElement("div"),
};

const CHANGES_PANEL: PanelDefinition = {
  id: "changes",
  displayName: "Changes",
  description: "Test changes panel",
  icon: Circle,
  defaultZone: "top-right",
  defaultShortcut: "",
  component: () => createElement("div"),
};

// A panel registered after first load, whose defaultZone ("top-right") has no
// prior zoneOrder entry in TEST_DEFAULT_LAYOUT — this lets the reconciliation
// tests exercise the "create a zoneOrder entry for a fresh zone" path.
const NOTES_PANEL: PanelDefinition = {
  id: "notes",
  displayName: "Notes",
  description: "Test notes panel",
  icon: Circle,
  defaultZone: "top-right",
  defaultShortcut: "",
  component: () => createElement("div"),
};

const TEST_PANELS: ReadonlyArray<PanelDefinition> = [INFO_PANEL, TERMINAL_PANEL, CHANGES_PANEL];

const EXTENDED_PANELS: ReadonlyArray<PanelDefinition> = [...TEST_PANELS, NOTES_PANEL];

const TEST_DEFAULT_LAYOUT: DefaultPanelLayout = {
  zoneAssignments: {
    info: "top-left",
    terminal: "bottom",
    changes: "top-right",
  },
  activePanelPerZone: {
    "top-left": "info",
    bottom: "terminal",
    "top-right": "changes",
  },
  zoneVisibility: {
    "top-left": true,
    bottom: true,
    "top-right": true,
  },
  zoneOrder: {
    "top-left": ["info"],
    bottom: ["terminal"],
  },
};

type RenderProviderArgs = {
  store: ReturnType<typeof createStore>;
  panels: ReadonlyArray<PanelDefinition>;
  defaultLayout?: DefaultPanelLayout;
};

const buildTree = ({ store, panels, defaultLayout }: RenderProviderArgs): ReactElement => (
  <Provider store={store}>
    <PanelRegistryProvider panels={panels} defaultLayout={defaultLayout}>
      <div data-testid="child" />
    </PanelRegistryProvider>
  </Provider>
);

const renderProvider = (
  args: RenderProviderArgs,
): {
  rerender: (next: RenderProviderArgs) => void;
  unmount: () => void;
} => {
  const result = render(buildTree(args));
  return {
    rerender: (next: RenderProviderArgs): void => result.rerender(buildTree(next)),
    unmount: (): void => result.unmount(),
  };
};

beforeEach(() => localStorage.clear());
afterEach(() => localStorage.clear());

describe("PanelRegistryProvider — bootstrap", () => {
  it("applies defaultLayout on first mount when no persisted layout exists", () => {
    const store = createStore();
    renderProvider({ store, panels: TEST_PANELS, defaultLayout: TEST_DEFAULT_LAYOUT });

    expect(store.get(zoneAssignmentsAtom)).toEqual(TEST_DEFAULT_LAYOUT.zoneAssignments);
    expect(store.get(activePanelPerZoneAtom)).toEqual(TEST_DEFAULT_LAYOUT.activePanelPerZone);
    expect(store.get(zoneVisibilityAtom)).toEqual(TEST_DEFAULT_LAYOUT.zoneVisibility);
    expect(store.get(zoneOrderAtom)).toEqual(TEST_DEFAULT_LAYOUT.zoneOrder);
  });

  it("leaves layout atoms empty when no defaultLayout is provided", () => {
    const store = createStore();
    renderProvider({ store, panels: TEST_PANELS });

    expect(store.get(zoneAssignmentsAtom)).toEqual({});
    expect(store.get(activePanelPerZoneAtom)).toEqual({});
    expect(store.get(zoneVisibilityAtom)).toEqual({});
    expect(store.get(zoneOrderAtom)).toEqual({});
  });

  it("does not re-apply the bootstrap-only atoms when zoneAssignments is already populated", () => {
    const store = createStore();
    store.set(zoneAssignmentsAtom, { info: "top-left", terminal: "bottom", changes: "top-right" });

    renderProvider({ store, panels: TEST_PANELS, defaultLayout: TEST_DEFAULT_LAYOUT });

    // activePanelPerZone and zoneVisibility are bootstrap-only atoms — they
    // must remain untouched when zoneAssignments is already populated.
    expect(store.get(activePanelPerZoneAtom)).toEqual({});
    expect(store.get(zoneVisibilityAtom)).toEqual({});
  });
});

describe("PanelRegistryProvider — registry sync", () => {
  it("hydrates panelRegistryAtom with initial panels on mount", () => {
    const store = createStore();
    renderProvider({ store, panels: TEST_PANELS, defaultLayout: TEST_DEFAULT_LAYOUT });

    expect(store.get(panelRegistryAtom)).toEqual(TEST_PANELS);
  });

  it("updates panelRegistryAtom when the panels prop changes", () => {
    const store = createStore();
    const { rerender } = renderProvider({
      store,
      panels: TEST_PANELS,
      defaultLayout: TEST_DEFAULT_LAYOUT,
    });

    expect(store.get(panelRegistryAtom)).toEqual(TEST_PANELS);

    rerender({ store, panels: EXTENDED_PANELS, defaultLayout: TEST_DEFAULT_LAYOUT });

    expect(store.get(panelRegistryAtom)).toEqual(EXTENDED_PANELS);
  });
});

describe("PanelRegistryProvider — reconciliation (adding panels)", () => {
  it("adds a newly-registered panel to zoneAssignments at its defaultZone", () => {
    const store = createStore();
    const { rerender } = renderProvider({
      store,
      panels: TEST_PANELS,
      defaultLayout: TEST_DEFAULT_LAYOUT,
    });

    rerender({ store, panels: EXTENDED_PANELS, defaultLayout: TEST_DEFAULT_LAYOUT });

    expect(store.get(zoneAssignmentsAtom)[NOTES_PANEL.id]).toBe("top-right");
  });

  it("appends a newly-registered panel to zoneOrder for its zone", () => {
    const store = createStore();
    const { rerender } = renderProvider({
      store,
      panels: TEST_PANELS,
      defaultLayout: TEST_DEFAULT_LAYOUT,
    });

    rerender({ store, panels: EXTENDED_PANELS, defaultLayout: TEST_DEFAULT_LAYOUT });

    const topRightOrder = store.get(zoneOrderAtom)["top-right"];
    expect(topRightOrder).toBeDefined();
    expect(topRightOrder!).toContain(NOTES_PANEL.id);
    expect(topRightOrder![topRightOrder!.length - 1]).toBe(NOTES_PANEL.id);
  });

  it("creates a zoneOrder entry for a zone that had no prior entry in defaultLayout", () => {
    // The default layout does not include "top-right" in zoneOrder. Adding
    // a panel whose defaultZone is top-right must create the entry.
    const store = createStore();
    const { rerender } = renderProvider({
      store,
      panels: TEST_PANELS,
      defaultLayout: TEST_DEFAULT_LAYOUT,
    });

    expect(store.get(zoneOrderAtom)["top-right"]).toBeUndefined();

    rerender({ store, panels: EXTENDED_PANELS, defaultLayout: TEST_DEFAULT_LAYOUT });

    expect(store.get(zoneOrderAtom)["top-right"]).toEqual([NOTES_PANEL.id]);
    expect(store.get(zoneAssignmentsAtom)[NOTES_PANEL.id]).toBe("top-right");
  });
});

describe("PanelRegistryProvider — reconciliation (fixed zones)", () => {
  it("snaps a panel persisted in a foreign zone back to its fixed zone", () => {
    const store = createStore();
    // A drag-to-dock-era persisted layout: "changes" was dragged to "top-left".
    store.set(zoneAssignmentsAtom, { info: "top-left", terminal: "bottom", changes: "top-left" });
    store.set(zoneOrderAtom, { "top-left": ["info", "changes"], bottom: ["terminal"] });
    store.set(activePanelPerZoneAtom, { "top-left": "changes", bottom: "terminal" });

    renderProvider({ store, panels: TEST_PANELS, defaultLayout: TEST_DEFAULT_LAYOUT });

    expect(store.get(zoneAssignmentsAtom).changes).toBe("top-right");
    expect(store.get(zoneOrderAtom)["top-left"]).toEqual(["info"]);
    expect(store.get(zoneOrderAtom)["top-right"]).toEqual(["changes"]);
    // The vacated zone's active panel must be repointed at a panel it holds.
    expect(store.get(activePanelPerZoneAtom)["top-left"]).toBe("info");
  });

  it("snaps a panel persisted in an unknown zone back to its fixed zone", () => {
    const store = createStore();
    store.set(zoneAssignmentsAtom, {
      info: "top-left",
      terminal: "bottom",
      // @ts-expect-error -- deliberately corrupt persisted data
      changes: "no-such-zone",
    });
    store.set(zoneOrderAtom, { "top-left": ["info"], bottom: ["terminal"] });

    renderProvider({ store, panels: TEST_PANELS, defaultLayout: TEST_DEFAULT_LAYOUT });

    expect(store.get(zoneAssignmentsAtom).changes).toBe("top-right");
    expect(store.get(zoneOrderAtom)["top-right"]).toEqual(["changes"]);
  });
});

describe("PanelRegistryProvider — reconciliation (removing panels)", () => {
  it("removes stale panels from zoneAssignments when they disappear from props", () => {
    const store = createStore();
    const extendedDefaultLayout: DefaultPanelLayout = {
      zoneAssignments: { ...TEST_DEFAULT_LAYOUT.zoneAssignments, notes: "top-right" },
      activePanelPerZone: { ...TEST_DEFAULT_LAYOUT.activePanelPerZone, "top-right": "notes" },
      zoneVisibility: { ...TEST_DEFAULT_LAYOUT.zoneVisibility, "top-right": true },
      zoneOrder: { ...TEST_DEFAULT_LAYOUT.zoneOrder, "top-right": ["notes"] },
    };

    const { rerender } = renderProvider({
      store,
      panels: EXTENDED_PANELS,
      defaultLayout: extendedDefaultLayout,
    });

    expect(store.get(zoneAssignmentsAtom)[NOTES_PANEL.id]).toBe("top-right");

    rerender({ store, panels: TEST_PANELS, defaultLayout: extendedDefaultLayout });

    expect(store.get(zoneAssignmentsAtom)[NOTES_PANEL.id]).toBeUndefined();
  });

  it("removes stale panels from zoneOrder for every zone", () => {
    const store = createStore();
    const extendedDefaultLayout: DefaultPanelLayout = {
      zoneAssignments: { ...TEST_DEFAULT_LAYOUT.zoneAssignments, notes: "top-right" },
      activePanelPerZone: { ...TEST_DEFAULT_LAYOUT.activePanelPerZone, "top-right": "notes" },
      zoneVisibility: { ...TEST_DEFAULT_LAYOUT.zoneVisibility, "top-right": true },
      zoneOrder: { ...TEST_DEFAULT_LAYOUT.zoneOrder, "top-right": ["notes"] },
    };

    const { rerender } = renderProvider({
      store,
      panels: EXTENDED_PANELS,
      defaultLayout: extendedDefaultLayout,
    });

    rerender({ store, panels: TEST_PANELS, defaultLayout: extendedDefaultLayout });

    const order = store.get(zoneOrderAtom);
    for (const zoneId of Object.keys(order)) {
      const zoneOrder = order[zoneId as keyof typeof order];
      if (zoneOrder) {
        expect(zoneOrder).not.toContain(NOTES_PANEL.id);
      }
    }
  });

  it("falls back to the next remaining panel in the zone when the active panel is removed", () => {
    const store = createStore();
    // Seed a zone with two panels, panelA active.
    const panelA: PanelDefinition = { ...INFO_PANEL, id: "panelA", defaultZone: "top-left" };
    const panelB: PanelDefinition = { ...INFO_PANEL, id: "panelB", defaultZone: "top-left" };

    const seededLayout: DefaultPanelLayout = {
      zoneAssignments: { panelA: "top-left", panelB: "top-left" },
      activePanelPerZone: { "top-left": "panelA" },
      zoneVisibility: { "top-left": true },
      zoneOrder: { "top-left": ["panelA", "panelB"] },
    };

    const { rerender } = renderProvider({
      store,
      panels: [panelA, panelB],
      defaultLayout: seededLayout,
    });

    expect(store.get(activePanelPerZoneAtom)["top-left"]).toBe("panelA");

    // Remove panelA — active should fall back to panelB.
    rerender({ store, panels: [panelB], defaultLayout: seededLayout });
    expect(store.get(activePanelPerZoneAtom)["top-left"]).toBe("panelB");

    // Remove panelB — zone becomes empty, active becomes undefined.
    rerender({ store, panels: [], defaultLayout: seededLayout });
    expect(store.get(activePanelPerZoneAtom)["top-left"]).toBeUndefined();
  });
});

describe("PanelRegistryProvider — idempotency", () => {
  it("rerendering with the same panels reference does not change state", () => {
    const store = createStore();
    const { rerender } = renderProvider({
      store,
      panels: TEST_PANELS,
      defaultLayout: TEST_DEFAULT_LAYOUT,
    });

    const assignmentsBefore = store.get(zoneAssignmentsAtom);
    const orderBefore = store.get(zoneOrderAtom);
    const activeBefore = store.get(activePanelPerZoneAtom);
    const visibilityBefore = store.get(zoneVisibilityAtom);

    rerender({ store, panels: TEST_PANELS, defaultLayout: TEST_DEFAULT_LAYOUT });

    expect(store.get(zoneAssignmentsAtom)).toEqual(assignmentsBefore);
    expect(store.get(zoneOrderAtom)).toEqual(orderBefore);
    expect(store.get(activePanelPerZoneAtom)).toEqual(activeBefore);
    expect(store.get(zoneVisibilityAtom)).toEqual(visibilityBefore);
  });

  it("rerendering with a fresh array of the same contents does not change state", () => {
    const store = createStore();
    const { rerender } = renderProvider({
      store,
      panels: TEST_PANELS,
      defaultLayout: TEST_DEFAULT_LAYOUT,
    });

    const assignmentsBefore = store.get(zoneAssignmentsAtom);
    const orderBefore = store.get(zoneOrderAtom);

    rerender({ store, panels: [...TEST_PANELS], defaultLayout: TEST_DEFAULT_LAYOUT });

    expect(store.get(zoneAssignmentsAtom)).toEqual(assignmentsBefore);
    expect(store.get(zoneOrderAtom)).toEqual(orderBefore);
  });

  it("toggling a panel off then on again yields the original assignment", () => {
    const store = createStore();
    const extendedDefaultLayout: DefaultPanelLayout = {
      zoneAssignments: { ...TEST_DEFAULT_LAYOUT.zoneAssignments, notes: "top-right" },
      activePanelPerZone: { ...TEST_DEFAULT_LAYOUT.activePanelPerZone, "top-right": "notes" },
      zoneVisibility: { ...TEST_DEFAULT_LAYOUT.zoneVisibility, "top-right": true },
      zoneOrder: { ...TEST_DEFAULT_LAYOUT.zoneOrder, "top-right": ["notes"] },
    };

    const { rerender } = renderProvider({
      store,
      panels: EXTENDED_PANELS,
      defaultLayout: extendedDefaultLayout,
    });

    expect(store.get(zoneAssignmentsAtom)[NOTES_PANEL.id]).toBe("top-right");

    rerender({ store, panels: TEST_PANELS, defaultLayout: extendedDefaultLayout });
    expect(store.get(zoneAssignmentsAtom)[NOTES_PANEL.id]).toBeUndefined();

    rerender({ store, panels: EXTENDED_PANELS, defaultLayout: extendedDefaultLayout });
    expect(store.get(zoneAssignmentsAtom)[NOTES_PANEL.id]).toBe("top-right");
    expect(store.get(zoneOrderAtom)["top-right"]).toContain(NOTES_PANEL.id);
  });
});
