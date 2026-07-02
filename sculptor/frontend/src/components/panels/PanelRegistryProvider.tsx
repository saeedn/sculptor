import { useAtomValue, useSetAtom } from "jotai";
import { useHydrateAtoms } from "jotai/utils";
import type { ReactElement, ReactNode } from "react";
import { useEffect, useRef } from "react";

import {
  activePanelPerZoneAtom,
  panelRegistryAtom,
  zoneAssignmentsAtom,
  zoneOrderAtom,
  zoneVisibilityAtom,
} from "~/components/panels/atoms.ts";
import type { DefaultPanelLayout, PanelDefinition, PanelId, ZoneId } from "~/components/panels/types.ts";

type PanelRegistryProviderProps = {
  panels: ReadonlyArray<PanelDefinition>;
  defaultLayout?: DefaultPanelLayout;
  children: ReactNode;
};

/**
 * Hydrates the panel registry atom with the given panels on first render.
 * Optionally applies a default layout when no persisted layout exists in localStorage.
 */
export const PanelRegistryProvider = ({
  panels,
  defaultLayout,
  children,
}: PanelRegistryProviderProps): ReactElement => {
  useHydrateAtoms([[panelRegistryAtom, panels]]);

  const zoneAssignments = useAtomValue(zoneAssignmentsAtom);
  const zoneOrder = useAtomValue(zoneOrderAtom);
  const setZoneAssignments = useSetAtom(zoneAssignmentsAtom);
  const setActivePanelPerZone = useSetAtom(activePanelPerZoneAtom);
  const setZoneVisibility = useSetAtom(zoneVisibilityAtom);
  const setZoneOrder = useSetAtom(zoneOrderAtom);
  const setPanelRegistry = useSetAtom(panelRegistryAtom);
  const hasInitialized = useRef(false);

  // useHydrateAtoms only fires on the first render. Keep the registry in sync
  // when the panels prop changes.
  useEffect(() => {
    setPanelRegistry(panels);
  }, [panels, setPanelRegistry]);

  // One-time bootstrap: apply the full defaultLayout when no persisted layout
  // exists. Only runs on first render; later changes are handled by the
  // reconciliation effect below so dynamic panel toggling works.
  useEffect(() => {
    if (!defaultLayout || hasInitialized.current) return;
    hasInitialized.current = true;

    if (Object.keys(zoneAssignments).length === 0) {
      setZoneAssignments(defaultLayout.zoneAssignments);
      setActivePanelPerZone(defaultLayout.activePanelPerZone);
      setZoneVisibility(defaultLayout.zoneVisibility);
      setZoneOrder(defaultLayout.zoneOrder);
    }
  }, [defaultLayout, zoneAssignments, setZoneAssignments, setActivePanelPerZone, setZoneVisibility, setZoneOrder]);

  // Reconcile the persisted layout against the currently-registered panels.
  // Runs whenever the panels prop changes, so newly-added panels get a zone
  // and removed panels are cleaned up.
  useEffect(() => {
    if (Object.keys(zoneAssignments).length === 0) return;

    const registeredIds = new Set(panels.map((p) => p.id));
    const missingPanels = panels.filter((p) => !(p.id in zoneAssignments));
    const stalePanelIds = Object.keys(zoneAssignments).filter((id) => !registeredIds.has(id as PanelId));

    // Panels are fixed-position: a persisted zone that differs from the
    // panel's fixed zone (a drag-to-dock-era layout, or an unknown zone id)
    // would strand the panel in a slot the UI no longer manages, so snap it
    // back.
    const fixedZoneFor = (panel: PanelDefinition): ZoneId =>
      defaultLayout?.zoneAssignments[panel.id] ?? panel.defaultZone;
    const panelsWithInvalidZone = panels.filter(
      (p) => p.id in zoneAssignments && zoneAssignments[p.id] !== fixedZoneFor(p),
    );

    if (missingPanels.length === 0 && stalePanelIds.length === 0 && panelsWithInvalidZone.length === 0) return;

    const newAssignments = { ...zoneAssignments };
    const newOrder = { ...zoneOrder };

    // Remove panels that are no longer registered (e.g. deleted features).
    // Clean them from active-panel and zone-order so zones don't render empty.
    if (stalePanelIds.length > 0) {
      const staleSet = new Set(stalePanelIds);
      for (const id of stalePanelIds) {
        delete newAssignments[id as PanelId];
      }

      for (const [zone, order] of Object.entries(newOrder)) {
        if (order) {
          newOrder[zone as ZoneId] = order.filter((id) => !staleSet.has(id));
        }
      }
      setActivePanelPerZone((prev) => {
        const cleaned = { ...prev };
        for (const [zone, panelId] of Object.entries(cleaned)) {
          if (panelId && staleSet.has(panelId)) {
            const remaining = (newOrder[zone as ZoneId] ?? []).filter((id) => !staleSet.has(id));
            cleaned[zone as ZoneId] = remaining[0] as PanelId | undefined;
          }
        }
        return cleaned;
      });
    }

    // Snap panels back to their fixed zone, moving them out of the stored one.
    for (const panel of panelsWithInvalidZone) {
      const zone = fixedZoneFor(panel);
      newAssignments[panel.id] = zone;
      for (const [zoneId, order] of Object.entries(newOrder)) {
        if (zoneId !== zone && order) {
          newOrder[zoneId as ZoneId] = order.filter((id) => id !== panel.id);
        }
      }
      const order = newOrder[zone] ?? [];
      if (!order.includes(panel.id)) {
        newOrder[zone] = [...order, panel.id];
      }
    }

    // Add panels that were registered after the user last saved (e.g. a new
    // panel shipped in a release).
    for (const panel of missingPanels) {
      const zone = defaultLayout?.zoneAssignments[panel.id] ?? panel.defaultZone;
      newAssignments[panel.id] = zone;
      const order = newOrder[zone] ?? [];
      newOrder[zone] = [...order, panel.id];
    }

    // A snapped-back panel may still be the stored active panel of the zone
    // it was moved out of; repoint such zones at a panel they actually hold.
    if (panelsWithInvalidZone.length > 0) {
      setActivePanelPerZone((prev) => {
        const cleaned = { ...prev };
        for (const [zone, panelId] of Object.entries(cleaned)) {
          if (panelId && newAssignments[panelId] !== zone) {
            cleaned[zone as ZoneId] = newOrder[zone as ZoneId]?.[0];
          }
        }
        return cleaned;
      });
    }

    setZoneAssignments(newAssignments);
    setZoneOrder(newOrder);
  }, [defaultLayout, panels, zoneAssignments, zoneOrder, setZoneAssignments, setActivePanelPerZone, setZoneOrder]);

  return <>{children}</>;
};
