import { cleanup, render } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { ReactElement, ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_THEME_SETTINGS } from "~/common/state/atoms/theme.ts";

import { ImbueTheme } from "./ThemeProvider";

// Mock useResolvedTheme to avoid matchMedia dependency in tests
vi.mock("~/common/Utils.ts", () => ({
  useResolvedTheme: (): "light" | "dark" => "light",
}));

type Store = ReturnType<typeof createStore>;

const createWrapper =
  (store: Store) =>
  ({ children }: { children: ReactNode }): ReactElement => <Provider store={store}>{children}</Provider>;

beforeEach(() => localStorage.clear());
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ImbueTheme", () => {
  it("renders children", () => {
    const store = createStore();
    const { getByText } = render(
      <ImbueTheme>
        <span>test content</span>
      </ImbueTheme>,
      { wrapper: createWrapper(store) },
    );

    expect(getByText("test content")).toBeInTheDocument();
  });

  it("applies default theme settings to the Radix Theme element", () => {
    const store = createStore();
    const { container } = render(
      <ImbueTheme>
        <span>child</span>
      </ImbueTheme>,
      { wrapper: createWrapper(store) },
    );

    // Radix Theme renders a div with a class containing the theme configuration.
    // The .radix-themes element carries data attributes for the configured options.
    const themeRoot = container.querySelector(".radix-themes");
    expect(themeRoot).toBeInTheDocument();
    expect(themeRoot).toHaveAttribute("data-accent-color", DEFAULT_THEME_SETTINGS.accentColor);
    expect(themeRoot).toHaveAttribute("data-gray-color", DEFAULT_THEME_SETTINGS.grayColor);
  });

  it("resolves the light appearance from the resolved theme", () => {
    const store = createStore();
    const { container } = render(
      <ImbueTheme>
        <span>child</span>
      </ImbueTheme>,
      { wrapper: createWrapper(store) },
    );

    // useResolvedTheme is mocked to "light", so the Radix root carries the
    // light appearance class.
    const themeRoot = container.querySelector(".radix-themes");
    expect(themeRoot).toHaveClass("light");
  });
});
