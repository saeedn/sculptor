import type { Atom, PrimitiveAtom } from "jotai";
import { atom } from "jotai";
import { atomFamily } from "jotai/utils";
import { isEqual } from "lodash";

import type { CodingAgentTaskView, TaskStatus } from "../../../api";

export const taskAtomFamily = atomFamily<string, PrimitiveAtom<CodingAgentTaskView | null>>(() =>
  atom<CodingAgentTaskView | null>(null),
);

export const taskIdsAtom = atom<ReadonlyArray<string> | undefined>(undefined);

export const tasksArrayAtom = atom<ReadonlyArray<CodingAgentTaskView> | undefined>((get) => {
  const taskIds = get(taskIdsAtom);
  if (taskIds === undefined) {
    return undefined;
  }
  return taskIds
    .map((id) => get(taskAtomFamily(id)))
    .filter((task): task is CodingAgentTaskView => task !== null && !task.isDeleted);
});

export const updateTasksAtom = atom(null, (get, set, updates: Record<string, CodingAgentTaskView>) => {
  const seenIds = new Set(get(taskIdsAtom));
  let didIdsChange = false;

  Object.entries(updates).forEach(([id, task]) => {
    if (task.isDeleted) {
      if (seenIds.has(id)) {
        seenIds.delete(id);
        didIdsChange = true;
      }
      set(taskAtomFamily(id), null);
      return;
    }

    // Skip atom update when the task data hasn't changed to avoid unnecessary re-renders.
    const current = get(taskAtomFamily(id));
    if (!isEqual(current, task)) {
      set(taskAtomFamily(id), task);
    }

    if (!seenIds.has(id)) {
      seenIds.add(id);
      didIdsChange = true;
    }
  });

  if (didIdsChange) {
    set(taskIdsAtom, Array.from(seenIds));
  }
});

export const optimisticDeleteTaskAtom = atom(null, (get, set, taskId: string): CodingAgentTaskView | null => {
  const task = get(taskAtomFamily(taskId));
  if (task === null) {
    return null;
  }
  const snapshot = task;
  set(taskAtomFamily(taskId), null);
  const currentIds = get(taskIdsAtom) ?? [];
  set(
    taskIdsAtom,
    currentIds.filter((id) => id !== taskId),
  );
  return snapshot;
});

export const rollbackDeleteTaskAtom = atom(
  null,
  (get, set, { taskId, snapshot }: { taskId: string; snapshot: CodingAgentTaskView }): void => {
    set(taskAtomFamily(taskId), snapshot);
    const currentIds = get(taskIdsAtom) ?? [];
    if (!currentIds.includes(taskId)) {
      set(taskIdsAtom, [...currentIds, taskId]);
    }
  },
);

// Holds optimistic agent titles by agent id while a rename is in flight (and for a
// short trailing window after, to mask stale WebSocket pushes — see the comment in
// AgentTabs.tsx where this is set). AgentTabs reads from this atom so the tab label
// updates immediately instead of waiting for the rename round-trip to update
// taskAtomFamily.
export const pendingAgentTitlesAtom = atom<Readonly<Record<string, string>>>({});

// Fine-grained derived atoms for commonly-read task fields.
// Components subscribing to these only re-render when the specific field changes.
// Jotai uses Object.is for primitive comparisons, so string/boolean fields that
// stay the same across a task object update will not notify subscribers.

export const taskStatusAtomFamily = atomFamily<string, Atom<TaskStatus | undefined>>((taskId) =>
  atom((get) => get(taskAtomFamily(taskId))?.status),
);

export const taskAcceptsAutomatedPromptsAtomFamily = atomFamily<string, Atom<boolean | undefined>>((taskId) =>
  atom((get) => get(taskAtomFamily(taskId))?.acceptsAutomatedPrompts),
);
