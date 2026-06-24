import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { ReactElement, ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { DependenciesStatus, DependencyInfo } from "~/api";
import { UserConfigField } from "~/api";
import { dependenciesStatusAtom } from "~/common/state/atoms/dependenciesStatus";
import { useManagedDependency } from "~/common/useManagedDependency";

const makeInfo = (overrides: Partial<DependencyInfo>): DependencyInfo => ({ installed: false, ...overrides });

const makeStatus = (overrides: Partial<DependenciesStatus>): DependenciesStatus => ({
  git: makeInfo({ installed: true }),
  claude: makeInfo({}),
  pi: makeInfo({}),
  ...overrides,
});

describe("useManagedDependency", () => {
  let store: ReturnType<typeof createStore>;
  const onSettingChange = vi.fn().mockResolvedValue(undefined);

  const wrapper = ({ children }: { children: ReactNode }): ReactElement => (
    <Provider store={store}>{children}</Provider>
  );

  beforeEach(() => {
    store = createStore();
    vi.clearAllMocks();
  });

  it("treats an installed, in-range managed binary as up to date and suppresses a stale error", () => {
    store.set(
      dependenciesStatusAtom,
      makeStatus({
        pi: makeInfo({
          installed: true,
          version: "0.78.0",
          mode: "MANAGED",
          isVersionInRange: true,
          installError: "stale error from an earlier attempt",
        }),
      }),
    );

    const { result } = renderHook(() => useManagedDependency({ tool: "PI", onSettingChange }), { wrapper });

    expect(result.current.mode).toBe("MANAGED");
    expect(result.current.displayMode).toBe("MANAGED");
    expect(result.current.isManagedUpToDate).toBe(true);
    expect(result.current.effectiveInstallError).toBeNull();
  });

  it("surfaces the backend install error while the binary is not up to date", () => {
    store.set(
      dependenciesStatusAtom,
      makeStatus({
        claude: makeInfo({
          installed: false,
          mode: "MANAGED",
          isVersionInRange: false,
          installError: "download failed",
        }),
      }),
    );

    const { result } = renderHook(() => useManagedDependency({ tool: "CLAUDE", onSettingChange }), { wrapper });

    expect(result.current.isManagedUpToDate).toBe(false);
    expect(result.current.effectiveInstallError).toBe("download failed");
  });

  it("computes the download progress percent from the install progress bytes", () => {
    store.set(
      dependenciesStatusAtom,
      makeStatus({
        pi: makeInfo({
          installed: false,
          mode: "MANAGED",
          installProgress: { tool: "PI", bytesDownloaded: 50, totalBytes: 200 },
        }),
      }),
    );

    const { result } = renderHook(() => useManagedDependency({ tool: "PI", onSettingChange }), { wrapper });

    expect(result.current.progressPercent).toBe(25);
  });

  it("handleModeChange optimistically switches displayMode and persists the per-tool field", () => {
    store.set(
      dependenciesStatusAtom,
      makeStatus({ pi: makeInfo({ installed: true, mode: "MANAGED", isVersionInRange: true }) }),
    );

    const { result } = renderHook(() => useManagedDependency({ tool: "PI", onSettingChange }), { wrapper });

    act(() => {
      result.current.handleModeChange("CUSTOM");
    });

    expect(result.current.displayMode).toBe("CUSTOM");
    expect(result.current.isModeSettling).toBe(true);
    expect(onSettingChange).toHaveBeenCalledWith(UserConfigField.DEPENDENCY_PATHS, { pi: "CUSTOM" });
  });

  it("handleInstall no longer installs and reports that the user must provide the binary on PATH", async () => {
    store.set(
      dependenciesStatusAtom,
      makeStatus({ claude: makeInfo({ installed: false, mode: "MANAGED", isVersionInRange: false }) }),
    );

    const { result } = renderHook(() => useManagedDependency({ tool: "CLAUDE", onSettingChange }), { wrapper });

    await act(async () => {
      await result.current.handleInstall();
    });

    expect(result.current.isInstalling).toBe(false);
    expect(result.current.effectiveInstallError).toContain("PATH");
  });
});
