import { ContextMenu } from "@radix-ui/themes";
import type { ReactElement, ReactNode } from "react";

import { usePanelById } from "~/components/panels/hooks.ts";
import type { PanelId, ZoneId } from "~/components/panels/types.ts";

type PanelContextMenuProps = {
  panelId: PanelId;
  zoneId: ZoneId;
  children: ReactNode;
  onOpenChange?: (open: boolean) => void;
};

export const PanelContextMenu = ({ panelId, children, onOpenChange }: PanelContextMenuProps): ReactElement => {
  const panelDef = usePanelById(panelId);

  return (
    <ContextMenu.Root onOpenChange={onOpenChange}>
      <ContextMenu.Trigger>{children}</ContextMenu.Trigger>
      <ContextMenu.Content size="1">
        <ContextMenu.Label>{panelDef?.displayName ?? panelId}</ContextMenu.Label>
      </ContextMenu.Content>
    </ContextMenu.Root>
  );
};
