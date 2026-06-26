export const DIFF_TOOLS = ["Edit", "MultiEdit", "Write"] as const;
type DiffTool = (typeof DIFF_TOOLS)[number];

export const isDiffTool = (toolName: string): toolName is DiffTool => {
  return DIFF_TOOLS.includes(toolName as DiffTool);
};
