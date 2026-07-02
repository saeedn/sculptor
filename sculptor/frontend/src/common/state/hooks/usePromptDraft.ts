import { useAtom } from "jotai";

import {
  draftBranchNameOverrideAtomFamily,
  draftProjectIdAtomFamily,
  draftSourceBranchAtomFamily,
  draftTabNameAtomFamily,
} from "../atoms/promptDrafts";

export const useDraftTabName = (draftId: string): [string | null, (value: string | null) => void] => {
  return useAtom(draftTabNameAtomFamily(draftId));
};

export const useDraftProjectId = (draftId: string): [string | null, (value: string | null) => void] => {
  return useAtom(draftProjectIdAtomFamily(draftId));
};

export const useDraftSourceBranch = (draftId: string): [string | null, (value: string | null) => void] => {
  return useAtom(draftSourceBranchAtomFamily(draftId));
};

export const useDraftBranchNameOverride = (draftId: string): [string | null, (value: string | null) => void] => {
  return useAtom(draftBranchNameOverrideAtomFamily(draftId));
};
