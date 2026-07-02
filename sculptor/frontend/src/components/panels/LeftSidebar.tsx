import { useAtomValue } from "jotai";
import type { ReactElement } from "react";
import { memo } from "react";

import { panelsInZoneAtom } from "~/components/panels/atoms.ts";
import { SidebarIcon } from "~/components/panels/SidebarIcon";
import type { PanelId, ZoneId } from "~/components/panels/types.ts";

import styles from "./Sidebar.module.scss";

// `data-sidebar-zone-id` (not `data-zone-id`) — that attribute locates zone
// *content* (ZoneContent, keyboard-shortcut focus in hooks.ts) and the icon
// strip must not shadow it in querySelector order.
const SidebarZone = ({ zoneId, panelIds }: { zoneId: ZoneId; panelIds: ReadonlyArray<PanelId> }): ReactElement => (
  <div data-sidebar-zone-id={zoneId}>
    {panelIds.map((panelId) => (
      <SidebarIcon key={panelId} panelId={panelId} />
    ))}
  </div>
);

const LeftSidebarInner = (): ReactElement => {
  const topLeftPanels = useAtomValue(panelsInZoneAtom("top-left"));
  const bottomPanels = useAtomValue(panelsInZoneAtom("bottom"));

  return (
    <div className={`${styles.sidebar} ${styles.left}`}>
      <SidebarZone zoneId="top-left" panelIds={topLeftPanels} />

      <div className={styles.spacer} />

      <SidebarZone zoneId="bottom" panelIds={bottomPanels} />
    </div>
  );
};

export const LeftSidebar = memo(LeftSidebarInner);
LeftSidebar.displayName = "LeftSidebar";
