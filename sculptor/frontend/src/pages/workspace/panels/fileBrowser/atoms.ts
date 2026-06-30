import { atom } from "jotai";
import { atomFamily, atomWithStorage } from "jotai/utils";

import { getCachedWorkspaceDiff } from "~/common/state/hooks/useWorkspaceDiff.ts";
import { parseDiff } from "~/components/DiffUtils.ts";
import type { DiffScope } from "~/pages/workspace/components/diffPanel/types.ts";

import type { FileBrowserState, FileStatus, ViewMode } from "./types.ts";
import { determineFileStatus } from "./utils.ts";

type FolderStateKey = "expandedFolders" | "changesExpandedFolders";

const DEFAULT_FILE_BROWSER_STATE: FileBrowserState = {
  expandedFolders: [],
  changesExpandedFolders: [],
  viewMode: "tree",
  searchQuery: "",
  searchOpen: false,
  scrollPosition: 0,
};

export const fileBrowserStateAtomFamily = atomFamily((workspaceId: string) =>
  atomWithStorage<FileBrowserState>(`fileBrowser-state-${workspaceId}`, DEFAULT_FILE_BROWSER_STATE),
);

/**
 * Build a path → FileStatus map from the cached uncommittedDiff for a
 * workspace. Used by the `openFileFromUiEvent` write atom for `--mode auto`
 * resolution (a one-shot read that doesn't need Jotai subscription).
 *
 * Returns an empty map if the diff hasn't been fetched yet — `--mode auto`
 * then falls back to file-view, which is the documented behavior.
 */
export const getUncommittedFileStatusMap = (
  workspaceId: string,
  targetBranch: string | null,
): Map<string, FileStatus> => {
  const diff = getCachedWorkspaceDiff(workspaceId, targetBranch);
  const map = new Map<string, FileStatus>();
  const diffString = diff?.uncommittedDiff;
  if (!diffString) {
    return map;
  }
  const parsed = parseDiff(diffString);
  for (const fileChange of parsed.fileChanges) {
    const { referenceFileName } = fileChange.fileNames;
    map.set(referenceFileName, determineFileStatus(fileChange));
  }
  return map;
};

/** Per-workspace scope for the Changes tab. Resets on page refresh. */
export const changesScopeAtomFamily = atomFamily((_workspaceId: string) => atom<DiffScope>("vs-target-branch"));

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
const createToggleFolderAtom = (key: FolderStateKey) =>
  atom(null, (get, set, { workspaceId, folderPath }: { workspaceId: string; folderPath: string }) => {
    const stateAtom = fileBrowserStateAtomFamily(workspaceId);
    const state = get(stateAtom);
    const folders = new Set(state[key]);
    if (folders.has(folderPath)) {
      folders.delete(folderPath);
    } else {
      folders.add(folderPath);
    }
    set(stateAtom, { ...state, [key]: Array.from(folders) });
  });

// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
const createExpandFoldersAtom = (key: FolderStateKey) =>
  atom(null, (get, set, { workspaceId, paths }: { workspaceId: string; paths: Array<string> }) => {
    const stateAtom = fileBrowserStateAtomFamily(workspaceId);
    const state = get(stateAtom);
    const folders = new Set(state[key]);
    for (const path of paths) {
      folders.add(path);
    }
    set(stateAtom, { ...state, [key]: Array.from(folders) });
  });

export const toggleFolderAtom = createToggleFolderAtom("expandedFolders");
export const expandFoldersAtom = createExpandFoldersAtom("expandedFolders");

export const toggleChangesFolderAtom = createToggleFolderAtom("changesExpandedFolders");
export const expandChangesFoldersAtom = createExpandFoldersAtom("changesExpandedFolders");

export const collapseAllFoldersAtom = atom(null, (get, set, { workspaceId }: { workspaceId: string }) => {
  const stateAtom = fileBrowserStateAtomFamily(workspaceId);
  const state = get(stateAtom);
  set(stateAtom, { ...state, expandedFolders: [] });
});

export const collapseAllChangesFoldersAtom = atom(null, (get, set, { workspaceId }: { workspaceId: string }) => {
  const stateAtom = fileBrowserStateAtomFamily(workspaceId);
  const state = get(stateAtom);
  set(stateAtom, { ...state, changesExpandedFolders: [] });
});

export const toggleViewModeAtom = atom(null, (get, set, { workspaceId }: { workspaceId: string }) => {
  const stateAtom = fileBrowserStateAtomFamily(workspaceId);
  const state = get(stateAtom);
  const viewMode: ViewMode = state.viewMode === "tree" ? "flat" : "tree";
  set(stateAtom, { ...state, viewMode });
});

export const setSearchAtom = atom(
  null,
  (get, set, { workspaceId, query, open }: { workspaceId: string; query: string; open: boolean }) => {
    const stateAtom = fileBrowserStateAtomFamily(workspaceId);
    const state = get(stateAtom);
    set(stateAtom, { ...state, searchQuery: query, searchOpen: open });
  },
);
