import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { createStore } from "jotai";
import { Circle } from "lucide-react";
import type { ReactNode } from "react";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { parseShortcut } from "~/common/ShortcutUtils";
import {
  createPanelStore,
  panelsInZoneAtom,
  zoneAssignmentsAtom,
  zoneOrderAtom,
  zoneSizesAtom,
} from "~/components/panels/atoms.ts";
import { DockingLayout } from "~/components/panels/DockingLayout";
import { renderWithProviders } from "~/components/panels/testUtils";
import type { PanelDefinition, PanelId } from "~/components/panels/types.ts";

const TEST_PANEL_CONTENT = {
  info: "TEST_INFO_CONTENT",
  cost: "TEST_COST_CONTENT",
  terminal: "TEST_TERMINAL_CONTENT",
  changes: "TEST_CHANGES_CONTENT",
} as const;

const TEST_PANELS: ReadonlyArray<PanelDefinition> = [
  {
    id: "info",
    displayName: "Info",
    description: "Test panel",
    icon: Circle,
    defaultZone: "top-left",
    defaultShortcut: "Cmd+1",
    component: () => createElement("div", null, TEST_PANEL_CONTENT.info),
  },
  {
    id: "cost",
    displayName: "Cost",
    description: "Test panel",
    icon: Circle,
    defaultZone: "top-left",
    defaultShortcut: "Cmd+4",
    component: () => createElement("div", null, TEST_PANEL_CONTENT.cost),
  },
  {
    id: "terminal",
    displayName: "Terminal",
    description: "Test panel",
    icon: Circle,
    defaultZone: "bottom",
    defaultShortcut: "Cmd+2",
    component: () => createElement("div", null, TEST_PANEL_CONTENT.terminal),
  },
  {
    id: "changes",
    displayName: "Changes",
    description: "Test panel",
    icon: Circle,
    defaultZone: "top-right",
    defaultShortcut: "Cmd+3",
    component: () => createElement("div", null, TEST_PANEL_CONTENT.changes),
  },
];

const createTestStore = (): ReturnType<typeof createStore> => createStore();

const createDefaultTestStore = (): ReturnType<typeof createStore> =>
  createPanelStore(TEST_PANELS, { useDefaultLayout: true });

/** Local helper that always passes TEST_PANELS through PanelRegistryProvider. */
const renderTest = (ui: ReactNode, store: ReturnType<typeof createStore>): ReturnType<typeof renderWithProviders> =>
  renderWithProviders(ui, store, TEST_PANELS);

/** Move keyboard focus into a zone's content container so the focus-then-toggle
 *  dispatch sees the panel as already focused on the next shortcut press. */
const focusZone = (zone: string): void => {
  const el = document.querySelector(`[data-zone-id="${zone}"]`);
  if (el instanceof HTMLElement) el.focus();
};

const fireShortcut = (panelId: PanelId): void => {
  const shortcuts = { info: "Cmd+1", cost: "Cmd+4", terminal: "Cmd+2", changes: "Cmd+3" };
  const parsed = parseShortcut(shortcuts[panelId as keyof typeof shortcuts]);
  // matchesShortcut maps "meta" to ctrlKey on non-macOS (jsdom).
  // Fire the event with the correct platform modifier.
  const isMacOS = window.sculptor?.platform === "darwin";
  fireEvent.keyDown(window, {
    key: parsed.key,
    metaKey: isMacOS ? parsed.meta : false,
    ctrlKey: isMacOS ? parsed.ctrl : parsed.meta || parsed.ctrl,
    altKey: parsed.alt,
    shiftKey: parsed.shift,
  });
};

// atomWithStorage reads from localStorage on init — clear between tests
// so each test starts with fresh default state.
beforeEach(() => localStorage.clear());
afterEach(cleanup);

const getIconElement = (container: HTMLElement, panelId: string): HTMLElement | null =>
  container.querySelector(`[data-panel-icon="${panelId}"]`);

const getClickableIcon = (container: HTMLElement, panelId: string): HTMLElement | null =>
  getIconElement(container, panelId)?.querySelector("[role='button'], [class*='icon']") ??
  getIconElement(container, panelId);

const getSidebarZone = (container: HTMLElement, zoneId: string): HTMLElement | null =>
  container.querySelector(`[data-sidebar-zone-id="${zoneId}"]`);

const getIconsInZone = (container: HTMLElement, zoneId: string): Array<string> => {
  const zone = getSidebarZone(container, zoneId);
  if (!zone) return [];
  return Array.from(zone.querySelectorAll("[data-panel-icon]")).map((el) => (el as HTMLElement).dataset.panelIcon!);
};

const getZoneContent = (container: HTMLElement, zoneId: string): HTMLElement | null =>
  container.querySelector(`[data-zone-id="${zoneId}"]`);

describe("DockingLayout", () => {
  describe("default layout rendering", () => {
    it("renders Info and Cost icons in the top-left zone", () => {
      const store = createDefaultTestStore();
      const { container } = renderTest(<DockingLayout />, store);
      const topLeftIcons = getIconsInZone(container, "top-left");
      expect(topLeftIcons).toContain("info");
      expect(topLeftIcons).toContain("cost");
    });

    it("renders Terminal icon in the bottom zone", () => {
      const store = createDefaultTestStore();
      const { container } = renderTest(<DockingLayout />, store);
      const bottomIcons = getIconsInZone(container, "bottom");
      expect(bottomIcons).toContain("terminal");
    });

    it("renders Changes icon in the top-right zone", () => {
      const store = createDefaultTestStore();
      const { container } = renderTest(<DockingLayout />, store);
      const topRightIcons = getIconsInZone(container, "top-right");
      expect(topRightIcons).toContain("changes");
    });

    it("renders Info panel content in top-left zone", () => {
      const store = createDefaultTestStore();
      const { container } = renderTest(<DockingLayout />, store);
      const zoneEl = getZoneContent(container, "top-left")!;
      expect(zoneEl).not.toBeNull();
      expect(within(zoneEl).getByText(TEST_PANEL_CONTENT.info)).toBeInTheDocument();
    });

    it("renders Terminal panel content in bottom zone", () => {
      const store = createDefaultTestStore();
      const { container } = renderTest(<DockingLayout />, store);
      const zoneEl = getZoneContent(container, "bottom")!;
      expect(zoneEl).not.toBeNull();
      expect(within(zoneEl).getByText(TEST_PANEL_CONTENT.terminal)).toBeInTheDocument();
    });

    it("renders Changes panel content in top-right zone", () => {
      const store = createDefaultTestStore();
      const { container } = renderTest(<DockingLayout />, store);
      const zoneEl = getZoneContent(container, "top-right")!;
      expect(zoneEl).not.toBeNull();
      expect(within(zoneEl).getByText(TEST_PANEL_CONTENT.changes)).toBeInTheDocument();
    });

    it("renders center content when provided", () => {
      const store = createDefaultTestStore();
      renderTest(<DockingLayout centerContent={<div>My Editor</div>} />, store);
      expect(screen.getByText("My Editor")).toBeInTheDocument();
    });

    it("renders default center content when none provided", () => {
      const store = createDefaultTestStore();
      renderTest(<DockingLayout />, store);
      expect(screen.getByText("Center Content")).toBeInTheDocument();
    });

    it("does not render Cost panel content (not the active panel in top-left)", () => {
      const store = createDefaultTestStore();
      renderTest(<DockingLayout />, store);
      expect(screen.queryByText(TEST_PANEL_CONTENT.cost)).not.toBeInTheDocument();
    });

    it("renders no icons for a zone with no registered panels", () => {
      const panelsWithoutTopRight = TEST_PANELS.filter((p) => p.defaultZone !== "top-right");
      const store = createPanelStore(panelsWithoutTopRight, { useDefaultLayout: true });
      const { container } = renderWithProviders(<DockingLayout />, store, panelsWithoutTopRight);

      expect(getIconsInZone(container, "top-right")).toHaveLength(0);
      expect(getIconsInZone(container, "top-left")).toContain("info");
    });
  });

  describe("icon toggle", () => {
    it("clicking active icon hides zone content", () => {
      const store = createDefaultTestStore();
      const { container } = renderTest(<DockingLayout />, store);

      // Info panel content is initially visible
      expect(screen.getByText(TEST_PANEL_CONTENT.info)).toBeInTheDocument();

      // Click the Info icon to close the zone
      const infoIcon = getClickableIcon(container, "info");
      expect(infoIcon).not.toBeNull();
      fireEvent.click(infoIcon!);

      expect(screen.queryByText(TEST_PANEL_CONTENT.info)).not.toBeInTheDocument();
    });

    it("clicking icon again reopens zone", () => {
      const store = createDefaultTestStore();
      const { container } = renderTest(<DockingLayout />, store);

      const infoIcon = getClickableIcon(container, "info");
      fireEvent.click(infoIcon!);
      expect(screen.queryByText(TEST_PANEL_CONTENT.info)).not.toBeInTheDocument();

      fireEvent.click(infoIcon!);
      expect(screen.getByText(TEST_PANEL_CONTENT.info)).toBeInTheDocument();
    });

    it("clicking a different icon in the same zone switches the panel", () => {
      const store = createDefaultTestStore();
      const { container } = renderTest(<DockingLayout />, store);

      // Initially Info is active
      expect(screen.getByText(TEST_PANEL_CONTENT.info)).toBeInTheDocument();

      // Click Cost icon
      const costIcon = getClickableIcon(container, "cost");
      fireEvent.click(costIcon!);

      // Cost content visible, Info content gone
      expect(screen.getByText(TEST_PANEL_CONTENT.cost)).toBeInTheDocument();
      expect(screen.queryByText(TEST_PANEL_CONTENT.info)).not.toBeInTheDocument();
    });

    it("active icon has the active class after switching", () => {
      const store = createDefaultTestStore();
      const { container } = renderTest(<DockingLayout />, store);

      // Click Cost to make it active
      const costIcon = getClickableIcon(container, "cost");
      fireEvent.click(costIcon!);

      // The Cost icon's inner element should have "active" class
      const costIconEl = getIconElement(container, "cost");
      const costInner = costIconEl?.querySelector("[class*='icon']");
      expect(costInner).toBeTruthy();
      expect(costInner!.className).toContain("active");

      // Info icon should NOT have active class
      const infoIconEl = getIconElement(container, "info");
      const infoInner = infoIconEl?.querySelector("[class*='icon']");
      expect(infoInner).toBeTruthy();
      expect(infoInner!.className).not.toContain("active");
    });

    it("toggling the only panel in a zone hides zone content", () => {
      const store = createDefaultTestStore();
      const { container } = renderTest(<DockingLayout />, store);

      // Changes is the sole panel in top-right
      expect(screen.getByText(TEST_PANEL_CONTENT.changes)).toBeInTheDocument();

      const changesIcon = getClickableIcon(container, "changes");
      fireEvent.click(changesIcon!);

      expect(screen.queryByText(TEST_PANEL_CONTENT.changes)).not.toBeInTheDocument();
    });

    it("clicking non-active icon in closed zone opens it with that panel", () => {
      const store = createDefaultTestStore();
      const { container } = renderTest(<DockingLayout />, store);

      // Close top-left zone by clicking Info (active panel)
      const infoIcon = getClickableIcon(container, "info");
      fireEvent.click(infoIcon!);
      expect(screen.queryByText(TEST_PANEL_CONTENT.info)).not.toBeInTheDocument();
      expect(screen.queryByText(TEST_PANEL_CONTENT.cost)).not.toBeInTheDocument();

      // Click Cost — should reopen zone with Cost
      const costIcon = getClickableIcon(container, "cost");
      fireEvent.click(costIcon!);
      expect(screen.getByText(TEST_PANEL_CONTENT.cost)).toBeInTheDocument();
    });
  });

  describe("reorder within zone", () => {
    it("renders icons in the order specified by zoneOrderAtom", () => {
      const store = createDefaultTestStore();
      store.set(zoneOrderAtom, { "top-left": ["cost", "info"] });

      const { container } = renderTest(<DockingLayout />, store);

      const iconsInTopLeft = getIconsInZone(container, "top-left");
      expect(iconsInTopLeft).toEqual(["cost", "info"]);
    });

    it("renders icons in default order when no zoneOrderAtom is set", () => {
      const store = createDefaultTestStore();

      const { container } = renderTest(<DockingLayout />, store);

      const iconsInTopLeft = getIconsInZone(container, "top-left");
      expect(iconsInTopLeft).toContain("info");
      expect(iconsInTopLeft).toContain("cost");
    });

    it("reordering does not change zone assignments", () => {
      const store = createDefaultTestStore();
      const assignmentsBefore = store.get(zoneAssignmentsAtom);

      store.set(zoneOrderAtom, { "top-left": ["cost", "info"] });
      renderTest(<DockingLayout />, store);

      const assignmentsAfter = store.get(zoneAssignmentsAtom);
      expect(assignmentsAfter).toEqual(assignmentsBefore);
    });
  });

  describe("keyboard shortcuts", () => {
    it("Cmd+1 hides the Info panel when it already has focus", () => {
      const store = createDefaultTestStore();
      renderTest(<DockingLayout />, store);

      // Info content is initially visible
      expect(screen.getByText(TEST_PANEL_CONTENT.info)).toBeInTheDocument();

      // Simulate the user having focused the panel — without focus, the first
      // press just moves focus and does not hide.
      focusZone("top-left");
      fireShortcut("info");
      expect(screen.queryByText(TEST_PANEL_CONTENT.info)).not.toBeInTheDocument();
    });

    it("Cmd+1 reopens the Info panel after it was hidden", () => {
      const store = createDefaultTestStore();
      renderTest(<DockingLayout />, store);

      focusZone("top-left");
      fireShortcut("info");
      expect(screen.queryByText(TEST_PANEL_CONTENT.info)).not.toBeInTheDocument();

      fireShortcut("info");
      expect(screen.getByText(TEST_PANEL_CONTENT.info)).toBeInTheDocument();
    });

    it("Cmd+2 toggles the Terminal panel via focus-then-hide", () => {
      const store = createDefaultTestStore();
      renderTest(<DockingLayout />, store);

      expect(screen.getByText(TEST_PANEL_CONTENT.terminal)).toBeInTheDocument();

      focusZone("bottom");
      fireShortcut("terminal");
      expect(screen.queryByText(TEST_PANEL_CONTENT.terminal)).not.toBeInTheDocument();

      fireShortcut("terminal");
      expect(screen.getByText(TEST_PANEL_CONTENT.terminal)).toBeInTheDocument();
    });

    it("Cmd+3 hides the Changes panel when it already has focus", () => {
      const store = createDefaultTestStore();
      renderTest(<DockingLayout />, store);

      expect(screen.getByText(TEST_PANEL_CONTENT.changes)).toBeInTheDocument();

      focusZone("top-right");
      fireShortcut("changes");
      expect(screen.queryByText(TEST_PANEL_CONTENT.changes)).not.toBeInTheDocument();
    });

    it("Cmd+4 switches to Cost panel in top-left zone", () => {
      const store = createDefaultTestStore();
      renderTest(<DockingLayout />, store);

      // Info is initially active in top-left
      expect(screen.getByText(TEST_PANEL_CONTENT.info)).toBeInTheDocument();

      fireShortcut("cost");
      expect(screen.getByText(TEST_PANEL_CONTENT.cost)).toBeInTheDocument();
      expect(screen.queryByText(TEST_PANEL_CONTENT.info)).not.toBeInTheDocument();
    });
  });

  describe("zone order consistency", () => {
    it("panelsInZoneAtom returns deterministic order without explicit zoneOrder", () => {
      const store = createDefaultTestStore();
      const panels = store.get(panelsInZoneAtom("top-left"));
      // Default: info and cost both in top-left, ordered by Object.entries position
      expect(panels).toEqual(["info", "cost"]);
    });

    it("moved panel position depends on Object.entries order without explicit zoneOrder", () => {
      const store = createTestStore();

      // Move info from top-left to top-right (where changes already is)
      store.set(zoneAssignmentsAtom, {
        info: "top-right",
        cost: "top-left",
        terminal: "bottom",
        changes: "top-right",
      });

      const topRightPanels = store.get(panelsInZoneAtom("top-right"));
      // "info" appears BEFORE "changes" because it is defined earlier in the
      // assignments object.  Without an explicit zoneOrder, Object.entries
      // insertion order determines panel position.  A user who moved info to
      // top-right would typically expect it AFTER the existing changes panel.
      expect(topRightPanels).toEqual(["info", "changes"]);
    });

    it("explicit zoneOrder places moved panel at intended position", () => {
      const store = createTestStore();

      store.set(zoneAssignmentsAtom, {
        info: "top-right",
        cost: "top-left",
        terminal: "bottom",
        changes: "top-right",
      });
      // Explicit order: changes first, then info (appended at end as user expects)
      store.set(zoneOrderAtom, { "top-right": ["changes", "info"] });

      const topRightPanels = store.get(panelsInZoneAtom("top-right"));
      expect(topRightPanels).toEqual(["changes", "info"]);
    });

    it("source zone preserves order minus the moved panel", () => {
      const store = createTestStore();
      store.set(zoneOrderAtom, { "top-left": ["cost", "info"] });

      // Move info out of top-left
      store.set(zoneAssignmentsAtom, {
        info: "top-right",
        cost: "top-left",
        terminal: "bottom",
        changes: "top-right",
      });

      const topLeftPanels = store.get(panelsInZoneAtom("top-left"));
      expect(topLeftPanels).toEqual(["cost"]);
    });
  });

  describe("zone size persistence", () => {
    it("preserves zone sizes in localStorage across store instances", () => {
      const store1 = createDefaultTestStore();
      store1.set(zoneSizesAtom, { "top-left": 25, "top-right": 15, bottom: 35 });

      const { unmount } = renderTest(<DockingLayout />, store1);
      unmount();

      // Flush debounced localStorage writes before creating a new store
      window.dispatchEvent(new Event("beforeunload"));

      // Create a new store (simulates page navigation and return)
      const store2 = createDefaultTestStore();
      renderTest(<DockingLayout />, store2);

      // Zone sizes should persist via localStorage
      const sizes = store2.get(zoneSizesAtom);
      expect(sizes).toEqual({ "top-left": 25, "top-right": 15, bottom: 35 });
    });

    it("renders correctly after unmount/remount with persisted zone sizes", () => {
      const store1 = createDefaultTestStore();
      store1.set(zoneSizesAtom, { "top-left": 25, "top-right": 15, bottom: 35 });

      // First render
      const { unmount } = renderTest(<DockingLayout />, store1);

      // Verify panels render
      expect(screen.getByText(TEST_PANEL_CONTENT.info)).toBeInTheDocument();
      expect(screen.getByText(TEST_PANEL_CONTENT.terminal)).toBeInTheDocument();
      expect(screen.getByText(TEST_PANEL_CONTENT.changes)).toBeInTheDocument();

      // Unmount (simulates navigating to home page)
      unmount();

      // Flush debounced localStorage writes before creating a new store
      window.dispatchEvent(new Event("beforeunload"));

      // Remount with a fresh store (simulates navigating back to workspace)
      const store2 = createDefaultTestStore();
      renderTest(<DockingLayout />, store2);

      // All panels should still render correctly
      expect(screen.getByText(TEST_PANEL_CONTENT.info)).toBeInTheDocument();
      expect(screen.getByText(TEST_PANEL_CONTENT.terminal)).toBeInTheDocument();
      expect(screen.getByText(TEST_PANEL_CONTENT.changes)).toBeInTheDocument();

      // Zone sizes should be preserved in the new store
      expect(store2.get(zoneSizesAtom)).toEqual({ "top-left": 25, "top-right": 15, bottom: 35 });
    });

    it("uses default sizes when no sizes are persisted", () => {
      const store = createDefaultTestStore();

      // No sizes set — should be empty object (defaults used by DockingLayout)
      expect(store.get(zoneSizesAtom)).toEqual({});

      // Should still render without error
      renderTest(<DockingLayout />, store);
      expect(screen.getByText(TEST_PANEL_CONTENT.info)).toBeInTheDocument();
    });

    it("preserves zone sizes independently of zone assignments", () => {
      const store1 = createDefaultTestStore();
      store1.set(zoneSizesAtom, { "top-left": 30, "top-right": 10, bottom: 40 });

      // Render to trigger localStorage sync, then unmount
      const { unmount } = renderTest(<DockingLayout />, store1);
      unmount();

      // Flush debounced localStorage writes before creating a new store
      window.dispatchEvent(new Event("beforeunload"));

      // Create a new store with default layout — createPanelStore does NOT
      // override zoneSizesAtom, so sizes survive via localStorage
      const store2 = createDefaultTestStore();
      renderTest(<DockingLayout />, store2);

      expect(store2.get(zoneSizesAtom)).toEqual({ "top-left": 30, "top-right": 10, bottom: 40 });

      // But zone assignments are the defaults (set by createPanelStore)
      const assignments = store2.get(zoneAssignmentsAtom);
      expect(assignments.info).toBe("top-left");
      expect(assignments.terminal).toBe("bottom");
      expect(assignments.changes).toBe("top-right");
    });

    it("persists partial zone sizes (only some zones resized)", () => {
      const store1 = createDefaultTestStore();
      store1.set(zoneSizesAtom, { bottom: 40 });

      // Render to trigger localStorage sync, then unmount
      const { unmount } = renderTest(<DockingLayout />, store1);
      unmount();

      // Flush debounced localStorage writes before creating a new store
      window.dispatchEvent(new Event("beforeunload"));

      const store2 = createDefaultTestStore();
      renderTest(<DockingLayout />, store2);
      const sizes = store2.get(zoneSizesAtom);

      expect(sizes).toEqual({ bottom: 40 });
      // Other zones should be undefined (DockingLayout falls back to defaults)
      expect(sizes["top-left"]).toBeUndefined();
      expect(sizes["top-right"]).toBeUndefined();
    });

    it("renders all zones after multiple mount/unmount cycles", () => {
      // Cycle 1: render and set sizes
      const store1 = createDefaultTestStore();
      store1.set(zoneSizesAtom, { "top-left": 25, "top-right": 15, bottom: 35 });
      const { unmount: unmount1 } = renderTest(<DockingLayout />, store1);
      unmount1();

      // Flush debounced localStorage writes before creating new stores
      window.dispatchEvent(new Event("beforeunload"));

      // Cycle 2: remount with new store
      const store2 = createDefaultTestStore();
      const { unmount: unmount2 } = renderTest(<DockingLayout />, store2);
      expect(screen.getByText(TEST_PANEL_CONTENT.info)).toBeInTheDocument();
      expect(store2.get(zoneSizesAtom)).toEqual({ "top-left": 25, "top-right": 15, bottom: 35 });
      unmount2();

      // Cycle 3: remount again — sizes still preserved
      const store3 = createDefaultTestStore();
      renderTest(<DockingLayout />, store3);
      expect(screen.getByText(TEST_PANEL_CONTENT.info)).toBeInTheDocument();
      expect(store3.get(zoneSizesAtom)).toEqual({ "top-left": 25, "top-right": 15, bottom: 35 });
    });
  });
});
