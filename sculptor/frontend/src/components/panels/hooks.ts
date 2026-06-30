import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { useCallback, useEffect, useMemo } from "react";
import { flushSync } from "react-dom";

import { isDismissibleOverlayOpen, shouldHandleKeybinding } from "~/common/ShortcutUtils";
import {
  activePanelPerZoneAtom,
  panelRegistryAtom,
  panelShortcutsAtom,
  panelsInZoneAtom,
  zoneAssignmentsAtom,
  zoneOrderAtom,
  zoneVisibilityAtom,
} from "~/components/panels/atoms.ts";
import type { PanelDefinition, PanelId, ZoneId } from "~/components/panels/types.ts";
import { ZONE_IDS } from "~/components/panels/types.ts";
import { computeToggleAction } from "~/components/panels/utils.ts";

/** Look up a single panel definition from the registry by ID. */
export const usePanelById = (id: PanelId | null): PanelDefinition | undefined => {
  const registry = useAtomValue(panelRegistryAtom);
  if (!id) return undefined;
  return registry.find((p) => p.id === id);
};

/** Per-zone enabled-panel lists. Use this for any guard or layout logic that
 *  must respect `panelEnabledAtom` — disabled panels are filtered out. */
export const usePanelsByZone = (): Partial<Record<ZoneId, ReadonlyArray<PanelId>>> => {
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const zonePanelArrays = ZONE_IDS.map((zoneId) => useAtomValue(panelsInZoneAtom(zoneId)));
  return useMemo(() => {
    const result: Partial<Record<ZoneId, ReadonlyArray<PanelId>>> = {};
    ZONE_IDS.forEach((zoneId, i) => {
      result[zoneId] = zonePanelArrays[i];
    });
    return result;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, zonePanelArrays);
};

type UsePanelActionsResult = {
  movePanel: (panelId: PanelId, targetZone: ZoneId, insertIndex?: number) => void;
  togglePanel: (panelId: PanelId) => void;
};

/** Hook providing intent-based panel mutation operations. */
export const usePanelActions = (): UsePanelActionsResult => {
  const zoneAssignments = useAtomValue(zoneAssignmentsAtom);
  const panelsByZone = usePanelsByZone();
  const [activePanelPerZone, setActivePanelPerZone] = useAtom(activePanelPerZoneAtom);
  const [zoneVisibility, setZoneVisibility] = useAtom(zoneVisibilityAtom);
  const setZoneAssignments = useSetAtom(zoneAssignmentsAtom);
  const setZoneOrder = useSetAtom(zoneOrderAtom);

  const movePanel = useCallback(
    (panelId: PanelId, targetZone: ZoneId, insertIndex?: number): void => {
      const sourceZone = zoneAssignments[panelId];

      if (sourceZone !== targetZone) {
        // Pre-compute remaining panels in the source zone before any state updates
        // so the downstream setters don't depend on a stale zoneAssignments closure.
        const remainingInSource = (Object.entries(zoneAssignments) as Array<[PanelId, ZoneId]>).filter(
          ([pid, zone]) => zone === sourceZone && pid !== panelId,
        );

        setZoneAssignments((prev) => ({ ...prev, [panelId]: targetZone }));

        setActivePanelPerZone((prev) => {
          const next = { ...prev, [targetZone]: panelId };
          if (prev[sourceZone] === panelId) {
            if (remainingInSource.length > 0) {
              next[sourceZone] = remainingInSource[0][0];
            } else {
              delete next[sourceZone];
            }
          }
          return next;
        });

        setZoneVisibility((prev) => {
          const next = { ...prev, [targetZone]: true };
          if (remainingInSource.length === 0) {
            next[sourceZone] = false;
          }
          return next;
        });
      }

      // Update zone order (handles both cross-zone moves and same-zone reorders)
      setZoneOrder((prev) => {
        const getDefaultOrder = (zone: ZoneId): Array<PanelId> =>
          (Object.entries(zoneAssignments) as Array<[PanelId, ZoneId]>)
            .filter(([, z]) => z === zone)
            .map(([pid]) => pid);

        const targetOrder = (prev[targetZone] ?? getDefaultOrder(targetZone)).filter((id) => id !== panelId);
        if (insertIndex !== undefined) {
          const clampedIndex = Math.min(insertIndex, targetOrder.length);
          targetOrder.splice(clampedIndex, 0, panelId);
        } else {
          targetOrder.push(panelId);
        }

        const sourceZone = zoneAssignments[panelId];
        if (sourceZone === targetZone) {
          return { ...prev, [targetZone]: targetOrder };
        }
        const sourceOrder = (prev[sourceZone] ?? getDefaultOrder(sourceZone)).filter((id) => id !== panelId);
        return { ...prev, [sourceZone]: sourceOrder, [targetZone]: targetOrder };
      });

      // Invariant: bottom-{side} cannot hold panels while top-{side} is empty.
      // If this move vacated a top zone whose bottom sibling still has panels,
      // promote the bottom panels up to the top so the side stays consolidated.
      // The empty check uses enabled-filtered panels (panelsByZone): a zone with
      // only disabled panels is visually empty and must trigger promotion.
      const siblingSide: "left" | "right" | null =
        sourceZone === "top-left" ? "left" : sourceZone === "top-right" ? "right" : null;
      if (siblingSide !== null && sourceZone !== targetZone) {
        const topZone: ZoneId = siblingSide === "left" ? "top-left" : "top-right";
        const bottomZone: ZoneId = siblingSide === "left" ? "bottom-left" : "bottom-right";
        const isTopNowEmpty = !(panelsByZone[topZone] ?? []).some((pid) => pid !== panelId);
        if (isTopNowEmpty) {
          const bottomPanels = (Object.entries(zoneAssignments) as Array<[PanelId, ZoneId]>)
            .filter(([, z]) => z === bottomZone)
            .map(([p]) => p);
          if (bottomPanels.length > 0) {
            setZoneAssignments((prev) => {
              const next = { ...prev };
              for (const p of bottomPanels) {
                next[p] = topZone;
              }
              return next;
            });
            setActivePanelPerZone((prev) => {
              const next = { ...prev };
              if (prev[bottomZone] !== undefined) {
                next[topZone] = prev[bottomZone];
                delete next[bottomZone];
              }
              return next;
            });
            setZoneVisibility((prev) => ({
              ...prev,
              [topZone]: true,
              [bottomZone]: false,
            }));
            setZoneOrder((prev) => {
              const next = { ...prev };
              next[topZone] = prev[bottomZone] ?? bottomPanels;
              next[bottomZone] = [];
              return next;
            });
          }
        }
      }
    },
    [zoneAssignments, panelsByZone, setZoneAssignments, setActivePanelPerZone, setZoneVisibility, setZoneOrder],
  );

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

  return { movePanel, togglePanel };
};

/**
 * PyCharm/VS Code-style focus-then-toggle dispatch. Disabled panels are
 * already absent from `panelShortcutsAtom`, so they never fire here.
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
    const focusPanel = (panel: PanelDefinition, zone: ZoneId): void => {
      const customTarget = panel.getFocusTarget?.() ?? null;
      if (customTarget instanceof HTMLElement) {
        customTarget.focus();
        return;
      }
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
          focusPanel(panel, zone);
        } else if (!isActiveTab) {
          flushSync(() => {
            setActivePanelPerZone((prev) => ({ ...prev, [zone]: panelId as PanelId }));
          });
          focusPanel(panel, zone);
        } else if (!hasFocus) {
          focusPanel(panel, zone);
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
