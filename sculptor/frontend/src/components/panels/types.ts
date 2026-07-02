import type { LucideIcon } from "lucide-react";
import type { ComponentType } from "react";

export const ZONE_IDS = ["top-left", "bottom", "top-right"] as const;
export type ZoneId = (typeof ZONE_IDS)[number];

// Panel IDs — dynamic string type since panels are registered at runtime
export type PanelId = string;

export type PanelDefinition = {
  id: PanelId;
  displayName: string;
  description: string;
  icon: LucideIcon;
  defaultZone: ZoneId;
  defaultShortcut: string;
  component: ComponentType;
};

// Default layout configuration for first-time initialization
export type DefaultPanelLayout = {
  zoneAssignments: Record<PanelId, ZoneId>;
  activePanelPerZone: Partial<Record<ZoneId, PanelId>>;
  zoneVisibility: Partial<Record<ZoneId, boolean>>;
  zoneOrder: Partial<Record<ZoneId, Array<PanelId>>>;
};
