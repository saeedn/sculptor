import { useAtomValue } from "jotai";
import { useCallback, useEffect, useState } from "react";

import type { DependenciesStatus, DependencyInfo, InstallProgress } from "~/api";
import { UserConfigField } from "~/api";
import { dependenciesStatusAtom } from "~/common/state/atoms/dependenciesStatus";

type ManagedDependencyTool = "CLAUDE" | "PI";

// The per-tool mode/path live in a named field of dependency_paths, so a config
// write keys off the lower-case field name while the install/status API keys off
// the upper-case tool.
const DEPENDENCY_CONFIG_KEY = {
  CLAUDE: "claude",
  PI: "pi",
} as const satisfies Record<ManagedDependencyTool, "claude" | "pi">;

// DependenciesStatus has a string index signature (unknown | DependencyInfo), so
// indexing by a dynamic key loses the type. Selecting the named field keeps it.
const selectInfo = (
  status: DependenciesStatus | null | undefined,
  tool: ManagedDependencyTool,
): DependencyInfo | null => {
  if (!status) return null;
  return tool === "CLAUDE" ? status.claude : status.pi;
};

type UseManagedDependencyParams = {
  tool: ManagedDependencyTool;
  onSettingChange: (field: UserConfigField, value: unknown) => Promise<void>;
};

type UseManagedDependencyResult = {
  info: DependencyInfo | null;
  mode: string;
  displayMode: string;
  isModeSettling: boolean;
  handleModeChange: (newMode: string) => void;
  isInstalling: boolean;
  handleInstall: () => Promise<void>;
  installProgress: InstallProgress | null;
  progressPercent: number | null;
  isManagedUpToDate: boolean;
  effectiveInstallError: string | null;
  customPathInput: string;
  setCustomPathInput: (value: string) => void;
  handleApplyCustomPath: () => void;
};

/**
 * Shared install/mode/status lifecycle for a managed dependency (Claude or pi) as
 * surfaced in its Settings section: the optimistic MANAGED/CUSTOM mode switch, the
 * background managed install (with status polling as a WebSocket fallback), the
 * custom-path entry, and the derived install progress/error state. The Claude and pi
 * settings sections are identical apart from which tool they manage, so they share
 * this hook rather than each keeping a copy of the logic.
 */
export const useManagedDependency = ({
  tool,
  onSettingChange,
}: UseManagedDependencyParams): UseManagedDependencyResult => {
  const configKey = DEPENDENCY_CONFIG_KEY[tool];
  const dependenciesStatus = useAtomValue(dependenciesStatusAtom);
  const info = selectInfo(dependenciesStatus, tool);
  const mode = info?.mode ?? "MANAGED";

  // Track the requested mode locally so the Select and conditional sections switch
  // immediately. Cleared once the WebSocket-pushed atom catches up.
  const [pendingMode, setPendingMode] = useState<string | null>(null);
  const displayMode = pendingMode ?? mode;
  const isModeSettling = pendingMode !== null && pendingMode !== mode;

  useEffect(() => {
    if (pendingMode !== null && pendingMode === mode) {
      setPendingMode(null);
    }
  }, [pendingMode, mode]);

  // Safety timeout: clear pendingMode after 10s so the spinner cannot get stuck if
  // the WebSocket update never arrives.
  useEffect(() => {
    if (!isModeSettling) return;
    const timeout = setTimeout(() => setPendingMode(null), 10_000);
    return (): void => clearTimeout(timeout);
  }, [isModeSettling]);

  const handleModeChange = useCallback(
    (newMode: string): void => {
      setPendingMode(newMode);
      onSettingChange(UserConfigField.DEPENDENCY_PATHS, { [configKey]: newMode });
    },
    [onSettingChange, configKey, mode], // eslint-disable-line react-hooks/exhaustive-deps -- mode forces recreation to avoid a stale onSettingChange closure
  );

  const [isInstalling, setIsInstalling] = useState(false);
  const [installError, setInstallError] = useState<string | null>(null);

  // Managed installation has been removed — Sculptor no longer installs or
  // manages binaries; the user provides `claude`/`git` on PATH. The action is
  // kept (settings still render) but reports that installation is unsupported.
  const handleInstall = useCallback(async (): Promise<void> => {
    setInstallError("Sculptor no longer installs binaries — install it yourself and ensure it is on your PATH.");
  }, []);

  // In CUSTOM mode the path field reflects the resolved binary path, so it shows the
  // active path rather than the raw "MANAGED"/"CUSTOM" mode keyword stored in config.
  const path = info?.path ?? "";
  const [customPathInput, setCustomPathInput] = useState(path);

  // Keep the custom path input in sync when the backend value changes (e.g. after
  // applying a new path or switching modes).
  useEffect(() => {
    setCustomPathInput(path);
  }, [path]);

  const handleApplyCustomPath = useCallback((): void => {
    // An empty path reverts to MANAGED rather than persisting a blank custom value
    // that would resolve to nothing.
    onSettingChange(UserConfigField.DEPENDENCY_PATHS, { [configKey]: customPathInput || "MANAGED" });
  }, [onSettingChange, configKey, customPathInput]);

  // Clear stale error/installing state once the atom confirms the binary is healthy
  // (e.g. the backend finished after the frontend timed out or errored).
  useEffect(() => {
    if (info?.installed && info?.isVersionInRange) {
      setInstallError(null);
      setIsInstalling(false);
    }
  }, [info?.installed, info?.isVersionInRange]);

  const installProgress = info?.installProgress ?? null;
  const progressPercent =
    installProgress && installProgress.totalBytes
      ? Math.round((installProgress.bytesDownloaded / installProgress.totalBytes) * 100)
      : null;

  const isManagedUpToDate = Boolean(mode === "MANAGED" && info?.installed && info?.isVersionInRange);

  // Fold the backend status's install error in with the local one, but ignore it once
  // the binary is up to date (the backend error persists for the process lifetime).
  const effectiveInstallError = isManagedUpToDate ? null : (installError ?? info?.installError ?? null);

  return {
    info,
    mode,
    displayMode,
    isModeSettling,
    handleModeChange,
    isInstalling,
    handleInstall,
    installProgress,
    progressPercent,
    isManagedUpToDate,
    effectiveInstallError,
    customPathInput,
    setCustomPathInput,
    handleApplyCustomPath,
  };
};
