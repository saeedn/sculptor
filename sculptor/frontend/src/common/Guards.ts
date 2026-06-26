import type {
  ContextClearedBlock,
  ContextSummaryBlock,
  ErrorBlock,
  FileBlock,
  GetWorkspaceAgentArtifactResponse,
  ResumeResponseBlock,
  TaskListArtifact,
  TextBlock,
  ToolResultBlock,
  ToolUseBlock,
  WarningBlock,
} from "../api";

// Artifact type guards
export const isTaskListArtifact = (response: GetWorkspaceAgentArtifactResponse): response is TaskListArtifact => {
  return response.objectType === "TaskListArtifact";
};

export type BlockUnion =
  | TextBlock
  | ToolUseBlock
  | ToolResultBlock
  | ErrorBlock
  | WarningBlock
  | ContextSummaryBlock
  | ContextClearedBlock
  | ResumeResponseBlock
  | FileBlock;

// Content block type guards
export const isTextBlock = (content: BlockUnion): content is TextBlock => {
  return content.type === "text";
};

export const isToolUseBlock = (content: BlockUnion): content is ToolUseBlock => {
  return content.type === "tool_use";
};
