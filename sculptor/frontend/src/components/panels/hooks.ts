import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { useCallback, useEffect } from "react";
import { flushSync } from "react-dom";

import { isDismissibleOverlayOpen, shouldHandleKeybinding } from "~/common/ShortcutUtils";
import {
  activePanelPerZoneAtom,
  panelRegistryAtom,
  panelShortcutsAtom,
  zoneAssignmentsAtom,
  zoneVisibilityAtom,
} from "~/components/panels/atoms.ts";
import type { PanelDefinition, PanelId, ZoneId } from "~/components/panels/types.ts";
import { computeToggleAction } from "~/components/panels/utils.ts";

/** Look up a single panel definition from the registry by ID. */
export const usePanelById = (id: PanelId | null): PanelDefinition | undefined => {
  const registry = useAtomValue(panelRegistryAtom);
  if (!id) return undefined;
  return registry.find((p) => p.id === id);
};

type UsePanelActionsResult = {
  togglePanel: (panelId: PanelId) => void;
};

/** Hook providing intent-based panel mutation operations. */
export const usePanelActions = (): UsePanelActionsResult => {
  const zoneAssignments = useAtomValue(zoneAssignmentsAtom);
  const [activePanelPerZone, setActivePanelPerZone] = useAtom(activePanelPerZoneAtom);
  const [zoneVisibility, setZoneVisibility] = useAtom(zoneVisibilityAtom);

  const togglePanel = useCallback(
    (panelId: PanelId): void => {
      const action = computeToggleAction({
        panelId,
        zoneAssignments,
        activePanelPerZone,
        zoneVisibility,
      });

      switch (action.type) {
        case "close-zone":
          setZoneVisibility((prev) => ({ ...prev, [action.zone]: false }));
          break;
        case "switch-panel":
          setActivePanelPerZone((prev) => ({ ...prev, [action.zone]: action.panelId }));
          setZoneVisibility((prev) => ({ ...prev, [action.zone]: true }));
          break;
        case "open-zone":
          setZoneVisibility((prev) => ({ ...prev, [action.zone]: true }));
          break;
      }
    },
    [zoneAssignments, activePanelPerZone, zoneVisibility, setActivePanelPerZone, setZoneVisibility],
  );

  return { togglePanel };
};

/**
 * PyCharm/VS Code-style focus-then-toggle dispatch.
 */
export const usePanelKeyboardShortcuts = (): void => {
  const shortcuts = useAtomValue(panelShortcutsAtom);
  const registry = useAtomValue(panelRegistryAtom);
  const zoneAssignments = useAtomValue(zoneAssignmentsAtom);
  const zoneVisibility = useAtomValue(zoneVisibilityAtom);
  const activePanelPerZone = useAtomValue(activePanelPerZoneAtom);
  const setZoneVisibility = useSetAtom(zoneVisibilityAtom);
  const setActivePanelPerZone = useSetAtom(activePanelPerZoneAtom);

  useEffect(() => {
    const focusPanel = (zone: ZoneId): void => {
      const fallback = document.querySelector(`[data-zone-id="${zone}"]`);
      if (fallback instanceof HTMLElement) fallback.focus();
    };

    const handleKeyDown = (e: KeyboardEvent): void => {
      if (isDismissibleOverlayOpen()) return;
      for (const [panelId, shortcutString] of Object.entries(shortcuts)) {
        if (!shouldHandleKeybinding(e, shortcutString)) continue;
        const panel = registry.find((p) => p.id === panelId);
        if (!panel) return;
        const zone = zoneAssignments[panelId];
        if (!zone) return;

        e.preventDefault();

        const isVisible = zoneVisibility[zone] ?? false;
        const isActiveTab = activePanelPerZone[zone] === panelId;
        const zoneEl = document.querySelector(`[data-zone-id="${zone}"]`);
        const hasFocus = zoneEl?.contains(document.activeElement) ?? false;

        if (!isVisible) {
          // flushSync forces React to commit the visibility/active-panel
          // changes before we try to focus the (now-mounted) zone element.
          flushSync(() => {
            setZoneVisibility((prev) => ({ ...prev, [zone]: true }));
            setActivePanelPerZone((prev) => ({ ...prev, [zone]: panelId as PanelId }));
          });
          focusPanel(zone);
        } else if (!isActiveTab) {
          flushSync(() => {
            setActivePanelPerZone((prev) => ({ ...prev, [zone]: panelId as PanelId }));
          });
          focusPanel(zone);
        } else if (!hasFocus) {
          focusPanel(zone);
        } else {
          setZoneVisibility((prev) => ({ ...prev, [zone]: false }));
        }
        return;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return (): void => window.removeEventListener("keydown", handleKeyDown);
  }, [
    shortcuts,
    registry,
    zoneAssignments,
    zoneVisibility,
    activePanelPerZone,
    setZoneVisibility,
    setActivePanelPerZone,
  ]);
};
