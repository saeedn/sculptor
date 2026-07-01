import { act, fireEvent, render } from "@testing-library/react";
import type { createStore } from "jotai";
import { Provider } from "jotai";
import { Circle } from "lucide-react";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { activePanelPerZoneAtom, createPanelStore, zoneVisibilityAtom } from "~/components/panels/atoms.ts";
import { usePanelKeyboardShortcuts } from "~/components/panels/hooks.ts";
import { PanelRegistryProvider } from "~/components/panels/PanelRegistryProvider";
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
    id: "cost",
    displayName: "Cost",
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

const Stub = (): null => {
  usePanelKeyboardShortcuts();
  return null;
};

const mountDispatch = (
  store: ReturnType<typeof createStore>,
  panels: ReadonlyArray<PanelDefinition>,
): {
  unmount: () => void;
  zones: Record<string, HTMLElement>;
} => {
  const zones: Record<string, HTMLElement> = {};
  for (const zone of ["top-left", "bottom", "top-right"] as const) {
    const el = document.createElement("div");
    el.setAttribute("data-zone-id", zone);
    el.tabIndex = -1;
    document.body.appendChild(el);
    zones[zone] = el;
  }
  const { unmount } = render(
    <Provider store={store}>
      <PanelRegistryProvider panels={panels}>
        <Stub />
      </PanelRegistryProvider>
    </Provider>,
  );
  return {
    unmount: (): void => {
      unmount();
      for (const el of Object.values(zones)) el.remove();
    },
    zones,
  };
};

const isMacOS = (): boolean =>
  (typeof window !== "undefined" && window.sculptor?.platform === "darwin") || navigator.platform.startsWith("Mac");

const fireMetaE = (): void => {
  const isMac = isMacOS();
  fireEvent.keyDown(window, {
    key: "e",
    metaKey: isMac,
    ctrlKey: !isMac,
  });
};

describe("usePanelKeyboardShortcuts focus-then-toggle dispatch", () => {
  it("press 1 on a hidden panel shows + activates it", () => {
    const panels: ReadonlyArray<PanelDefinition> = TEST_PANELS.map((p) =>
      p.id === "info" ? { ...p, defaultShortcut: "Meta+e" } : p,
    );
    const store = createPanelStore(panels, { useDefaultLayout: true });
    store.set(zoneVisibilityAtom, (prev) => ({ ...prev, "top-left": false }));

    const { unmount } = mountDispatch(store, panels);
    act(() => fireMetaE());

    expect(store.get(zoneVisibilityAtom)["top-left"]).toBe(true);
    expect(store.get(activePanelPerZoneAtom)["top-left"]).toBe("info");
    unmount();
  });

  it("press on a visible+focused panel hides the zone", () => {
    const panels: ReadonlyArray<PanelDefinition> = TEST_PANELS.map((p) =>
      p.id === "info" ? { ...p, defaultShortcut: "Meta+e" } : p,
    );
    const store = createPanelStore(panels, { useDefaultLayout: true });

    const { unmount, zones } = mountDispatch(store, panels);
    zones["top-left"].focus();
    expect(document.activeElement).toBe(zones["top-left"]);

    act(() => fireMetaE());

    expect(store.get(zoneVisibilityAtom)["top-left"]).toBe(false);
    unmount();
  });

  it("press on a visible-but-not-focused panel does not hide the zone", () => {
    const panels: ReadonlyArray<PanelDefinition> = TEST_PANELS.map((p) =>
      p.id === "info" ? { ...p, defaultShortcut: "Meta+e" } : p,
    );
    const store = createPanelStore(panels, { useDefaultLayout: true });

    const { unmount } = mountDispatch(store, panels);
    // Body has focus by default — the panel is visible but not focused.
    expect(document.activeElement).toBe(document.body);

    act(() => fireMetaE());

    expect(store.get(zoneVisibilityAtom)["top-left"]).toBe(true);
    unmount();
  });

  it("press on a panel that is not the active tab makes it active", () => {
    const panels: ReadonlyArray<PanelDefinition> = TEST_PANELS.map((p) =>
      p.id === "cost" ? { ...p, defaultShortcut: "Meta+e", defaultZone: "top-left" } : p,
    );
    const store = createPanelStore(panels, { useDefaultLayout: true });
    // Make both info and cost share top-left, with info active.
    store.set(activePanelPerZoneAtom, (prev) => ({ ...prev, "top-left": "info" }));

    const { unmount } = mountDispatch(store, panels);
    act(() => fireMetaE());

    expect(store.get(activePanelPerZoneAtom)["top-left"]).toBe("cost");
    expect(store.get(zoneVisibilityAtom)["top-left"]).toBe(true);
    unmount();
  });
});
