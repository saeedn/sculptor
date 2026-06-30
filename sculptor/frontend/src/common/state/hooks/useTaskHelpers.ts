import { useAtomValue } from "jotai";

import type { CodingAgentTaskView, TaskStatus } from "../../../api";
import { taskAcceptsAutomatedPromptsAtomFamily, taskAtomFamily, taskStatusAtomFamily } from "../atoms/tasks";

export const useTask = (taskId: string): CodingAgentTaskView | null => {
  return useAtomValue(taskAtomFamily(taskId));
};

/** Subscribe to only the task's status field. Re-renders only when status changes. */
export const useTaskStatus = (taskId: string): TaskStatus | undefined => useAtomValue(taskStatusAtomFamily(taskId));

/** Subscribe to only the task's `accepts_automated_prompts` field — true
 * only for registered terminal agents whose registration opted in. */
export const useTaskAcceptsAutomatedPrompts = (taskId: string): boolean | undefined =>
  useAtomValue(taskAcceptsAutomatedPromptsAtomFamily(taskId));
