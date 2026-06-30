import { useAtomValue } from "jotai";
import type { ReactElement } from "react";
import { memo } from "react";

import { panelsInZoneAtom } from "~/components/panels/atoms.ts";
import { SidebarIcon } from "~/components/panels/SidebarIcon";
import type { PanelId, ZoneId } from "~/components/panels/types.ts";

import styles from "./Sidebar.module.scss";

const SidebarZone = ({ zoneId, panelIds }: { zoneId: ZoneId; panelIds: ReadonlyArray<PanelId> }): ReactElement => (
  <div data-droppable-id={zoneId}>
    {panelIds.map((panelId) => (
      <SidebarIcon key={panelId} panelId={panelId} zoneId={zoneId} />
    ))}
  </div>
);

const RightSidebarInner = (): ReactElement => {
  const topRightPanels = useAtomValue(panelsInZoneAtom("top-right"));
  const bottomRightPanels = useAtomValue(panelsInZoneAtom("bottom-right"));

  const shouldShowDivider = topRightPanels.length > 0 && bottomRightPanels.length > 0;

  return (
    <div className={`${styles.sidebar} ${styles.right}`}>
      <SidebarZone zoneId="top-right" panelIds={topRightPanels} />

      {shouldShowDivider && <div className={styles.divider} />}

      {bottomRightPanels.length > 0 && <SidebarZone zoneId="bottom-right" panelIds={bottomRightPanels} />}

      <div className={styles.spacer} />
    </div>
  );
};

export const RightSidebar = memo(RightSidebarInner);
RightSidebar.displayName = "RightSidebar";
