import { atom } from "jotai";

import type { CiBabysitterConfig, CustomActionsConfig, UserConfig } from "../../../api";
import { themeAppearanceAtom } from "./theme";

/**
 * PRIMARY ATOM: Global UserConfig State
 *
 * This atom serves as the single source of truth for all user configuration.
 * It mirrors the backend UserConfig model.
 *
 * Lifecycle:
 * 1. Initialized as null on app startup
 * 2. Populated during app initialization via GET /api/v1/config
 * 3. Updated whenever settings are changed via PUT /api/v1/config
 * 4. Eventually will be updated via WebSocket streams when we migrate to database storage
 */
export const userConfigAtom = atom<UserConfig | null>(null);

/**
 * DERIVED ATOMS: Semantic Setting Accessors
 *
 * These atoms provide clean, typed access to specific settings while automatically
 * reacting to changes in the primary userConfig atom. This pattern eliminates the
 * need for manual subscription management and ensures consistent behavior.
 */

// Theme setting — derives from the persisted theme settings (localStorage) so
// that the Radix <Theme> appearance and all consumers (e.g. diff panel
// CodeMirror) stay in sync. The server-side userConfig.appTheme field is no
// longer used.
export const appThemeAtom = atom<"light" | "dark" | "system">((get) => {
  return get(themeAppearanceAtom);
});

// Custom actions
const EMPTY_CUSTOM_ACTIONS: CustomActionsConfig = { actions: [], groups: [] };

export const customActionsAtom = atom<CustomActionsConfig>((get) => {
  const config = get(userConfigAtom);
  const raw = config?.customActions as Record<string, unknown> | null | undefined;
  if (raw == null || typeof raw !== "object" || !Array.isArray(raw.actions) || !Array.isArray(raw.groups)) {
    return EMPTY_CUSTOM_ACTIONS;
  }
  return raw as CustomActionsConfig;
});

// PR creation settings
const DEFAULT_PR_CREATION_PROMPT =
  "Push my changes to origin and create a pull request. Check whether the repo uses GitHub (gh) or GitLab (glab) and use the appropriate tool. Write a clear description summarizing the changes.";

export const prCreationPromptAtom = atom<string>(
  (get) => get(userConfigAtom)?.prCreationPrompt ?? DEFAULT_PR_CREATION_PROMPT,
);

export const isPrPollingEnabledAtom = atom<boolean>((get) => get(userConfigAtom)?.prPollingEnabled ?? true);

export const prPollIntervalAtom = atom<number>((get) => get(userConfigAtom)?.prPollIntervalSeconds ?? 30);

export const prPollClosedMultiplierAtom = atom<number>((get) => get(userConfigAtom)?.prPollClosedMultiplier ?? 6);

export const prDefaultTargetBranchAtom = atom<string>(
  (get) => get(userConfigAtom)?.prDefaultTargetBranch ?? "origin/main",
);

// CI Babysitter settings (experimental). The full nested config lives under
// userConfig.ciBabysitter on the backend; individual atoms below derive from
// that object with sensible per-field defaults for when the config hasn't
// been loaded yet.
const DEFAULT_CI_BABYSITTER_PIPELINE_PROMPT =
  "Investigate the failing pipeline for this MR, identify the root cause, fix the code, commit, and push.";
const DEFAULT_CI_BABYSITTER_MERGE_CONFLICT_PROMPT =
  "This MR has a merge conflict with its base branch. Fetch the latest, then rebase against the base branch, resolve all conflicts, and force-push the result.";

export const ciBabysitterConfigAtom = atom<CiBabysitterConfig | null>(
  (get) => get(userConfigAtom)?.ciBabysitter ?? null,
);

export const isCiBabysitterEnabledAtom = atom<boolean>((get) => get(ciBabysitterConfigAtom)?.enabled ?? false);

export const ciBabysitterRetryCapAtom = atom<number>((get) => get(ciBabysitterConfigAtom)?.retryCap ?? 3);

export const ciBabysitterPipelineFailedPromptAtom = atom<string>(
  (get) => get(ciBabysitterConfigAtom)?.pipelineFailedPrompt ?? DEFAULT_CI_BABYSITTER_PIPELINE_PROMPT,
);

export const ciBabysitterMergeConflictPromptAtom = atom<string>(
  (get) => get(ciBabysitterConfigAtom)?.mergeConflictPrompt ?? DEFAULT_CI_BABYSITTER_MERGE_CONFLICT_PROMPT,
);

// Which agent the babysitter drives: the discriminated union from the backend
// (MRU | Registered{registrationId}); null until config loads.
export const ciBabysitterAgentAtom = atom<NonNullable<CiBabysitterConfig["agent"]> | null>(
  (get) => get(ciBabysitterConfigAtom)?.agent ?? null,
);

// File browser settings
export const fileBrowserSplitRatioAtom = atom<number>((get) => get(userConfigAtom)?.fileBrowserDefaultSplitRatio ?? 50);

export const fileBrowserTabCloseBehaviorAtom = atom<"mru" | "adjacent">(
  (get) => (get(userConfigAtom)?.fileBrowserTabCloseBehavior as "mru" | "adjacent") ?? "mru",
);

export const fileBrowserLineWrappingAtom = atom<"wrap" | "scroll">(
  (get) => (get(userConfigAtom)?.fileBrowserLineWrapping as "wrap" | "scroll") ?? "wrap",
);

export const fileBrowserDiffViewTypeAtom = atom<"unified" | "split">(
  (get) => (get(userConfigAtom)?.fileBrowserDiffViewType as "unified" | "split") ?? "unified",
);

// Commit button settings
export const DEFAULT_COMMIT_PROMPT =
  "Stage every changed and untracked file, then commit with a comprehensive commit message. Do not leave any files unstaged.";

export const commitPromptAtom = atom<string>((get) => get(userConfigAtom)?.commitPrompt ?? DEFAULT_COMMIT_PROMPT);

// Project environment variable settings
export const envVarOverrideEnabledAtom = atom<boolean>((get) => get(userConfigAtom)?.envVarOverrideEnabled ?? false);

// Default branch-naming pattern (user-global default)
export const defaultWorkspaceBranchNamingPatternAtom = atom<string>(
  (get) => get(userConfigAtom)?.defaultWorkspaceBranchNamingPattern ?? "<user>/<slug>",
);

// Branch deletion policy (tri-state)
export const workspaceBranchDeletionPolicyAtom = atom<"never" | "delete_if_safe" | "always">(
  (get) =>
    (get(userConfigAtom)?.workspaceBranchDeletionPolicy as "never" | "delete_if_safe" | "always" | undefined) ??
    "delete_if_safe",
);
