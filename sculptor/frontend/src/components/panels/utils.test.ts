import { describe, expect, it } from "vitest";

import { computeToggleAction } from "~/components/panels/utils.ts";

describe("computeToggleAction", () => {
  const defaultAssignments = {
    info: "top-left" as const,
    cost: "top-left" as const,
    terminal: "bottom" as const,
    changes: "top-right" as const,
  };

  it("should close zone when panel is active and zone is visible", () => {
    const action = computeToggleAction({
      panelId: "info",
      zoneAssignments: defaultAssignments,
      activePanelPerZone: { "top-left": "info" },
      zoneVisibility: { "top-left": true },
    });
    expect(action).toEqual({ type: "close-zone", zone: "top-left" });
  });

  it("should switch panel when different panel is active", () => {
    const action = computeToggleAction({
      panelId: "info",
      zoneAssignments: defaultAssignments,
      activePanelPerZone: { "top-left": "changes" },
      zoneVisibility: { "top-left": true },
    });
    expect(action).toEqual({ type: "switch-panel", zone: "top-left", panelId: "info" });
  });

  it("should open zone when panel is active but zone is closed", () => {
    const action = computeToggleAction({
      panelId: "info",
      zoneAssignments: defaultAssignments,
      activePanelPerZone: { "top-left": "info" },
      zoneVisibility: { "top-left": false },
    });
    expect(action).toEqual({ type: "open-zone", zone: "top-left" });
  });

  it("should open zone when panel is active and zone visibility is undefined", () => {
    const action = computeToggleAction({
      panelId: "info",
      zoneAssignments: defaultAssignments,
      activePanelPerZone: { "top-left": "info" },
      zoneVisibility: {},
    });
    expect(action).toEqual({ type: "open-zone", zone: "top-left" });
  });

  it("should switch and open when switching panels in same zone", () => {
    const assignments = {
      info: "top-left" as const,
      cost: "top-left" as const,
      terminal: "top-left" as const,
      changes: "top-right" as const,
    };
    const action = computeToggleAction({
      panelId: "terminal",
      zoneAssignments: assignments,
      activePanelPerZone: { "top-left": "info" },
      zoneVisibility: { "top-left": true },
    });
    expect(action).toEqual({ type: "switch-panel", zone: "top-left", panelId: "terminal" });
  });
});
