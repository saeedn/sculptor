import type { PrimitiveAtom } from "jotai";
import { atom } from "jotai";
import { atomFamily } from "jotai/utils";
import isEqual from "lodash/isEqual";

import type { ArtifactType, ChatMessage } from "../../../api";
import type { ArtifactsMap } from "../../../pages/workspace/Types";

/**
 * Complete state for a single task's detail view.
 * This is accumulated from incremental TaskUpdate messages.
 */
export type TaskDetailState = {
  // The agent's current in-flight message; read by useActiveFileOperation to
  // highlight the file the agent is editing. (Terminal agents drive this via
  // the stream; the older chat-message accumulation was removed.)
  inProgressChatMessage: ChatMessage | null;
  artifacts: ArtifactsMap;
  error?: string;
};

export const taskDetailAtomFamily = atomFamily<string, PrimitiveAtom<TaskDetailState | null>>(() =>
  atom<TaskDetailState | null>(null),
);

export const getEmptyTaskDetailState = (): TaskDetailState => {
  return {
    inProgressChatMessage: null,
    artifacts: {},
  };
};

export const updateTaskDetailAtom = atom(
  null,
  (getAtom, setAtom, update: { taskId: string; updater: (prev: TaskDetailState | null) => TaskDetailState }) => {
    const currentState = getAtom(taskDetailAtomFamily(update.taskId));
    const newState = update.updater(currentState);
    if (!isEqual(currentState, newState)) {
      setAtom(taskDetailAtomFamily(update.taskId), newState);
    }
  },
);

export const taskUpdatedArtifactsAtomFamily = atomFamily<string, PrimitiveAtom<Array<ArtifactType>>>(() =>
  atom<Array<ArtifactType>>([]),
);

export const updateTaskUpdatedArtifactsAtom = atom(
  null,
  (getAtom, setAtom, update: { taskId: string; artifactTypes: Array<ArtifactType> }) => {
    const existing = getAtom(taskUpdatedArtifactsAtomFamily(update.taskId));
    if (existing.length === 0) {
      setAtom(taskUpdatedArtifactsAtomFamily(update.taskId), Array.from(new Set(update.artifactTypes)));
      return;
    }

    const mergedTypes = Array.from(new Set([...existing, ...update.artifactTypes]));
    setAtom(taskUpdatedArtifactsAtomFamily(update.taskId), mergedTypes);
  },
);

export const clearTaskUpdatedArtifactsAtom = atom(
  null,
  (getAtom, setAtom, update: { taskId: string; artifactTypes: Array<ArtifactType> }) => {
    const existing = getAtom(taskUpdatedArtifactsAtomFamily(update.taskId));
    if (existing.length === 0) {
      return;
    }

    const artifactsToClear = new Set(update.artifactTypes);
    const remaining = existing.filter((artifactType) => !artifactsToClear.has(artifactType));

    if (remaining.length !== existing.length) {
      setAtom(taskUpdatedArtifactsAtomFamily(update.taskId), remaining);
    }
  },
);
