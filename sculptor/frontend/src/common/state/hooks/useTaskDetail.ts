import { useAtomValue } from "jotai";

import { getEmptyTaskDetailState, taskDetailAtomFamily, type TaskDetailState } from "../atoms/taskDetails";

export const useTaskDetail = (taskId: string): TaskDetailState | null => {
  return useAtomValue(taskDetailAtomFamily(taskId));
};

export const useTaskDetailWithDefaults = (taskId: string): TaskDetailState => {
  const detail = useTaskDetail(taskId);
  return detail || getEmptyTaskDetailState();
};
