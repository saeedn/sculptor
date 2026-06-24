import { Flex } from "@radix-ui/themes";
import type { ReactElement } from "react";

import { VersionPopover } from "~/components/VersionPopover.tsx";

export const StatusIndicators = (): ReactElement => {
  return (
    <Flex align="center" gap="2">
      <VersionPopover />
    </Flex>
  );
};
