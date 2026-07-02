import { Flex } from "@radix-ui/themes";
import type { ReactElement } from "react";

import { getTitleBarLeftPadding, TITLEBAR_HEIGHT } from "../electron/utils.ts";
import styles from "./TitleBar.module.scss";

export const TitleBar = (): ReactElement => {
  return (
    <Flex
      position="absolute"
      top="0"
      left="0"
      width="100%"
      pl={getTitleBarLeftPadding()}
      height={`${TITLEBAR_HEIGHT}px`}
      align="center"
      justify="end"
      pr="10px"
      className={styles.draggable}
    />
  );
};
