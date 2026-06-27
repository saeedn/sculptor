import { createStore } from "jotai";
import { describe, expect, it } from "vitest";

import type { CodingAgentTaskView } from "../../../api";
import {
  optimisticDeleteTaskAtom,
  rollbackDeleteTaskAtom,
  taskAtomFamily,
  taskIdsAtom,
  tasksArrayAtom,
  updateTasksAtom,
} from "./tasks";

const createMockTask = (overrides: Partial<CodingAgentTaskView> = {}): CodingAgentTaskView =>
  ({
    id: "task-1",
    projectId: "proj-1",
    createdAt: "2024-01-01T00:00:00Z",
    updatedAt: "2024-01-01T00:00:00Z",
    taskStatus: "RUNNING",
    isAutoCompacting: false,
    artifactNames: [],
    initialPrompt: "Test prompt",
    titleOrSomethingLikeIt: "Test task",
    systemPrompt: null,
    model: "CLAUDE_4_SONNET",
    harnessCapabilities: {
      supportsChatInterface: true,
      supportsInteractiveBackchannel: true,
      supportsSkills: true,
      supportsSubAgents: true,
      supportsImageInput: true,
      supportsFastMode: true,
      supportsContextReset: true,
      supportsCompaction: true,
      supportsBackgroundTasks: true,
      supportsSessionResume: true,
      supportsToolUseRendering: true,
      supportsFileAttachments: true,
      supportsInterruption: true,
      supportsFileReferences: true,
    },
    isSmoothStreamingSupported: true,
    isArchived: false,
    isDeleted: false,
    title: "Test task",
    status: "RUNNING",
    goal: "Test goal",
    workspaceId: null,
    ...overrides,
  }) as CodingAgentTaskView;

describe("optimisticDeleteTaskAtom", () => {
  it("returns snapshot and removes task from taskAtomFamily and taskIdsAtom", () => {
    const store = createStore();
    const task = createMockTask({ id: "task-1" });
    store.set(taskAtomFamily("task-1"), task);
    store.set(taskIdsAtom, ["task-1"]);

    const snapshot = store.set(optimisticDeleteTaskAtom, "task-1");

    expect(snapshot).toEqual(task);
    expect(store.get(taskAtomFamily("task-1"))).toBeNull();
    expect(store.get(taskIdsAtom)).toEqual([]);
  });

  it("returns null when task is already deleted", () => {
    const store = createStore();
    store.set(taskIdsAtom, ["task-1"]);

    const snapshot = store.set(optimisticDeleteTaskAtom, "task-1");

    expect(snapshot).toBeNull();
    expect(store.get(taskIdsAtom)).toEqual(["task-1"]);
  });

  it("handles undefined taskIdsAtom gracefully", () => {
    const store = createStore();
    const task = createMockTask({ id: "task-1" });
    store.set(taskAtomFamily("task-1"), task);

    const snapshot = store.set(optimisticDeleteTaskAtom, "task-1");

    expect(snapshot).toEqual(task);
    expect(store.get(taskAtomFamily("task-1"))).toBeNull();
    expect(store.get(taskIdsAtom)).toEqual([]);
  });
});

describe("rollbackDeleteTaskAtom", () => {
  it("restores task to taskAtomFamily and taskIdsAtom after optimistic delete", () => {
    const store = createStore();
    const task = createMockTask({ id: "task-1" });
    store.set(taskAtomFamily("task-1"), task);
    store.set(taskIdsAtom, ["task-1"]);

    const snapshot = store.set(optimisticDeleteTaskAtom, "task-1");
    expect(snapshot).not.toBeNull();

    store.set(rollbackDeleteTaskAtom, { taskId: "task-1", snapshot: snapshot! });

    expect(store.get(taskAtomFamily("task-1"))).toEqual(task);
    expect(store.get(taskIdsAtom)).toContain("task-1");
  });

  it("does not create duplicate entries in taskIdsAtom", () => {
    const store = createStore();
    const task = createMockTask({ id: "task-1" });
    store.set(taskAtomFamily("task-1"), task);
    store.set(taskIdsAtom, ["task-1"]);

    store.set(rollbackDeleteTaskAtom, { taskId: "task-1", snapshot: task });

    const ids = store.get(taskIdsAtom)!;
    expect(ids.filter((id) => id === "task-1")).toHaveLength(1);
  });
});

describe("stream convergence after optimistic delete", () => {
  it("remains correctly deleted when stream confirms deletion", () => {
    const store = createStore();
    const task = createMockTask({ id: "task-1" });
    store.set(taskAtomFamily("task-1"), task);
    store.set(taskIdsAtom, ["task-1"]);

    store.set(optimisticDeleteTaskAtom, "task-1");
    expect(store.get(taskAtomFamily("task-1"))).toBeNull();
    expect(store.get(taskIdsAtom)).toEqual([]);

    store.set(updateTasksAtom, { "task-1": { ...task, isDeleted: true } as CodingAgentTaskView });

    expect(store.get(taskAtomFamily("task-1"))).toBeNull();
    const ids = store.get(taskIdsAtom)!;
    expect(ids).not.toContain("task-1");
    expect(store.get(tasksArrayAtom)).toEqual([]);
  });
});
