import { useEffect, useRef, useState } from "react";

import { previewBranchName, validateNewBranchName } from "~/api";

/**
 * Status of the displayed branch name, from the debounced backend check:
 * - `unknown`: not checked yet (empty name or in flight)
 * - `invalid`: not a legal git ref name
 * - `exists`: legal, but already a branch in the repo
 * - `available`: legal and free to use
 */
export type BranchNameStatus = "unknown" | "invalid" | "exists" | "available";

type BranchNamePreviewState = {
  /** The auto-filled value sourced from the backend `preview-branch-name` endpoint. */
  preview: string;
  /** The value the user actually sees: `override` if set, otherwise `preview`. */
  displayedValue: string;
  /** True while the preview fetch is in flight in auto mode. */
  isLoading: boolean;
  /** Result of the debounced `validate-new-branch-name` check on `displayedValue`. */
  status: BranchNameStatus;
};

type UseBranchNamePreviewArgs = {
  projectId: string | null;
  workspaceName: string;
  /** The user's manual override; null means "use the auto-filled preview". */
  override: string | null;
};

const PREVIEW_DEBOUNCE_MS = 250;
const VALIDATION_DEBOUNCE_MS = 300;

export function useBranchNamePreview({
  projectId,
  workspaceName,
  override,
}: UseBranchNamePreviewArgs): BranchNamePreviewState {
  const [preview, setPreview] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [status, setStatus] = useState<BranchNameStatus>("unknown");

  const previewRequestId = useRef<number>(0);
  const validationRequestId = useRef<number>(0);

  const isManuallyEdited = override !== null;
  const displayedValue = override ?? preview;

  useEffect(() => {
    if (!projectId || isManuallyEdited) {
      setIsLoading(false);
      return;
    }
    const myId = ++previewRequestId.current;
    setIsLoading(true);
    const timer = window.setTimeout(() => {
      void (async (): Promise<void> => {
        try {
          const result = await previewBranchName({
            query: { project_id: projectId, workspace_name: workspaceName },
          });
          if (myId === previewRequestId.current && result.data) {
            setPreview(result.data.branchName);
          }
        } catch {
          // keep previous preview
        } finally {
          if (myId === previewRequestId.current) {
            setIsLoading(false);
          }
        }
      })();
    }, PREVIEW_DEBOUNCE_MS);
    return (): void => {
      window.clearTimeout(timer);
    };
  }, [projectId, workspaceName, isManuallyEdited]);

  useEffect(() => {
    if (!projectId) {
      setStatus("unknown");
      return;
    }
    const trimmed = displayedValue.trim();
    if (!trimmed) {
      setStatus("unknown");
      return;
    }
    const myId = ++validationRequestId.current;
    const timer = window.setTimeout(() => {
      void (async (): Promise<void> => {
        try {
          const result = await validateNewBranchName({
            path: { project_id: projectId },
            query: { name: trimmed },
          });
          if (myId === validationRequestId.current && result.data) {
            const { isValid } = result.data;
            setStatus(!isValid ? "invalid" : result.data.alreadyExists ? "exists" : "available");
          }
        } catch {
          if (myId === validationRequestId.current) {
            setStatus("unknown");
          }
        }
      })();
    }, VALIDATION_DEBOUNCE_MS);
    return (): void => {
      window.clearTimeout(timer);
    };
  }, [projectId, displayedValue]);

  return { preview, displayedValue, isLoading, status };
}
