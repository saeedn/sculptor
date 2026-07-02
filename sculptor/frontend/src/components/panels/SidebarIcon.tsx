import { Tooltip } from "@radix-ui/themes";
import { useAtomValue } from "jotai";
import type { ReactElement } from "react";

import { ElementIds } from "~/api";
import { activePanelPerZoneAtom, zoneAssignmentsAtom, zoneVisibilityAtom } from "~/components/panels/atoms.ts";
import { usePanelActions, usePanelById } from "~/components/panels/hooks.ts";
import type { PanelId } from "~/components/panels/types.ts";

import styles from "./SidebarIcon.module.scss";

const PANEL_ICON_TEST_IDS: Partial<Record<PanelId, ElementIds>> = {
  files: ElementIds.PANEL_ICON_FILES,
  actions: ElementIds.PANEL_ICON_ACTIONS,
  terminal: ElementIds.PANEL_ICON_TERMINAL,
};

type SidebarIconProps = {
  panelId: PanelId;
};

export const SidebarIcon = ({ panelId }: SidebarIconProps): ReactElement | null => {
  const panelDef = usePanelById(panelId);
  const zoneAssignments = useAtomValue(zoneAssignmentsAtom);
  const activePanelPerZone = useAtomValue(activePanelPerZoneAtom);
  const zoneVisibility = useAtomValue(zoneVisibilityAtom);
  const { togglePanel } = usePanelActions();

  if (!panelDef) return null;

  const zone = zoneAssignments[panelId];
  const isActive = activePanelPerZone[zone] === panelId && (zoneVisibility[zone] ?? false);
  const Icon = panelDef.icon;

  const handleClick = (): void => {
    togglePanel(panelId);
  };

  const iconClassName = [styles.icon, isActive ? styles.active : ""].filter(Boolean).join(" ");

  return (
    <div data-panel-icon={panelId} data-testid={PANEL_ICON_TEST_IDS[panelId]}>
      <Tooltip content={panelDef.displayName} side="right">
        <div role="button" className={iconClassName} onClick={handleClick}>
          <Icon size={18} />
        </div>
      </Tooltip>
    </div>
  );
};
