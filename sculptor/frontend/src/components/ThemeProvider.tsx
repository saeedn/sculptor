import { Theme as RadixTheme } from "@radix-ui/themes";
import type { PropsWithChildren, ReactElement } from "react";
import { useLayoutEffect, useRef } from "react";

import { useThemeAccentColor, useThemeGrayColor } from "~/common/state/hooks/useTheme.ts";
import { useResolvedTheme } from "~/common/Utils.ts";

export const ImbueTheme = ({ children }: PropsWithChildren): ReactElement => {
  const appearance = useResolvedTheme();
  const accentColor = useThemeAccentColor();
  const grayColor = useThemeGrayColor();

  // Track whether this is the initial mount (no theme switch yet).
  const prevAppearanceRef = useRef(appearance);

  // Work around two issues that cause a visible flash on theme toggle:
  //
  // 1. Radix Theme's internal useEffect-based appearance sync — it copies
  //    the `appearance` prop into local state via useEffect, so the CSS
  //    class ("light"/"dark") updates one frame late. We eagerly apply the
  //    correct class here before the browser paints.
  //
  // 2. CSS transitions on background-color / color (used by tabs, buttons,
  //    etc.) cause old theme colors to *animate* to new values instead of
  //    snapping instantly. We suppress all transitions for one frame during
  //    the switch, then re-enable them.
  useLayoutEffect(() => {
    const isThemeSwitch = prevAppearanceRef.current !== appearance;
    prevAppearanceRef.current = appearance;
    if (!isThemeSwitch) return;

    // Fix the Radix Theme root class immediately.
    const el = document.querySelector<HTMLElement>('.radix-themes[data-is-root-theme="true"]');
    if (el) {
      const stale = appearance === "light" ? "dark" : "light";
      if (el.classList.contains(stale)) {
        el.classList.remove(stale);
        el.classList.add(appearance);
      }
    }

    // Suppress CSS transitions so colors snap to the new theme instantly.
    document.documentElement.classList.add("theme-switching");
    requestAnimationFrame(() => {
      document.documentElement.classList.remove("theme-switching");
    });
  }, [appearance]);

  return (
    <RadixTheme accentColor={accentColor} appearance={appearance} grayColor={grayColor}>
      {children}
    </RadixTheme>
  );
};

export const ThemeProvider = ({ children }: PropsWithChildren): ReactElement => {
  return <ImbueTheme>{children}</ImbueTheme>;
};
