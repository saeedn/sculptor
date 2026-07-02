import type { PanelId, ZoneId } from "~/components/panels/types.ts";

export type ToggleAction =
  | { type: "close-zone"; zone: ZoneId }
  | { type: "switch-panel"; zone: ZoneId; panelId: PanelId }
  | { type: "open-zone"; zone: ZoneId };

/** Determines the toggle action for a panel click or keyboard shortcut. */
export const computeToggleAction = (inputs: {
  panelId: PanelId;
  zoneAssignments: Record<PanelId, ZoneId>;
  activePanelPerZone: Partial<Record<ZoneId, PanelId>>;
  zoneVisibility: Partial<Record<ZoneId, boolean>>;
}): ToggleAction => {
  const zone = inputs.zoneAssignments[inputs.panelId];
  const activePanel = inputs.activePanelPerZone[zone];
  const isZoneVisible = inputs.zoneVisibility[zone] ?? false;

  if (activePanel === inputs.panelId && isZoneVisible) {
    return { type: "close-zone", zone };
  }

  if (activePanel !== inputs.panelId) {
    return { type: "switch-panel", zone, panelId: inputs.panelId };
  }

  return { type: "open-zone", zone };
};
