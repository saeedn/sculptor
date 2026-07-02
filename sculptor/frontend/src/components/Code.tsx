import { compact } from "lodash";
import type { HTMLProps, PropsWithChildren, ReactElement } from "react";

import { mergeClasses } from "../common/Utils.ts";
import styles from "./Code.module.scss";

export const Code = (
  props: PropsWithChildren & {
    size?: "1" | "2" | "3" | "4" | "5" | "6";
  } & Omit<HTMLProps<HTMLDivElement>, "size">,
): ReactElement => {
  const { className, children, size: maybeSize, style, ...rest } = props;
  const classNames = compact([className, styles.code]);
  const size = maybeSize ?? "2";

  return (
    <span className={mergeClasses(...classNames)} style={{ ...style, fontSize: `var(--font-size-${size})` }} {...rest}>
      {children}
    </span>
  );
};
