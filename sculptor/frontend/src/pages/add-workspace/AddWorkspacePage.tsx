import { Button, Flex, Select, Spinner, Text } from "@radix-ui/themes";
import { useAtomValue, useSetAtom } from "jotai";
import { BotIcon } from "lucide-react";
import type { ReactElement } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import {
  createWorkspaceAgent,
  createWorkspaceV2,
  ElementIds,
  getActiveProjects,
  getMostRecentlyUsedProject,
} from "../../api";
import { HTTPException } from "../../common/Errors.ts";
import { useImbueNavigate } from "../../common/NavigateUtils.ts";
import {
  AGENT_TYPE_LABELS,
  encodeRegisteredAgentType,
  lastUsedAgentTypeAtom,
  parseStoredAgentType,
  type StoredAgentType,
} from "../../common/state/atoms/agentTabs.ts";
import { projectsArrayAtom, updateProjectsAtom } from "../../common/state/atoms/projects.ts";
import { userConfigAtom } from "../../common/state/atoms/userConfig.ts";
import {
  clearDraftCreatingAtom,
  convertNewWorkspaceToTabAtom,
  markDraftCreatingAtom,
} from "../../common/state/atoms/workspaces.ts";
import {
  useDraftBranchNameOverride,
  useDraftProjectId,
  useDraftSourceBranch,
  useDraftTabName,
} from "../../common/state/hooks/usePromptDraft.ts";
import { useRepoInfo } from "../../common/state/hooks/useRepoInfo.ts";
import { useTerminalAgentRegistrations } from "../../common/state/hooks/useTerminalAgentRegistrations.ts";
import { BranchSelector } from "../../components/BranchSelector.tsx";
import { RepoSelector } from "../../components/RepoSelector.tsx";
import { Toast, type ToastContent, ToastType } from "../../components/Toast.tsx";
import styles from "./AddWorkspacePage.module.scss";
import { BranchNameField } from "./components/BranchNameField.tsx";
import { NewWorkspaceForm } from "./components/NewWorkspaceForm.tsx";
import { useBranchNamePreview } from "./hooks/useBranchNamePreview.ts";

export const AddWorkspacePage = (): ReactElement => {
  const { draftId } = useParams<{ draftId: string }>();
  if (!draftId) {
    throw new Error("AddWorkspacePage requires a draftId route parameter");
  }
  const { navigateToAgent } = useImbueNavigate();
  const convertNewWorkspaceToTab = useSetAtom(convertNewWorkspaceToTabAtom);
  const markDraftCreating = useSetAtom(markDraftCreatingAtom);
  const clearDraftCreating = useSetAtom(clearDraftCreatingAtom);
  const nameInputRef = useRef<HTMLInputElement>(null);

  // Project state — read from global atom so AddRepoDialog updates are reflected immediately
  const projects = useAtomValue(projectsArrayAtom);
  const updateProjects = useSetAtom(updateProjectsAtom);
  // Repo/branch selections are persisted per draftId (like the workspace name)
  // so they survive the unmount/remount that happens when the user switches to
  // another tab and back. See SCU-1427.
  const [selectedProjectId, setSelectedProjectId] = useDraftProjectId(draftId);
  // Latest selection, read inside the one-shot project-load effect without
  // making it a dependency (which would re-fetch projects on every change).
  const selectedProjectIdRef = useRef(selectedProjectId);
  selectedProjectIdRef.current = selectedProjectId;
  const [isLoadingProjects, setIsLoadingProjects] = useState(true);

  // The type of the workspace's first agent (agent type is per-agent, not
  // per-workspace). Registered terminal agents select as `registered:<id>`.
  // The form opens preset to the shared last-used type (the same MRU the tab
  // bar's + button reads) — a deliberate mount-time snapshot the user can
  // change freely; the MRU is written back only when a workspace is actually
  // created.
  const lastUsedAgentType = useAtomValue(lastUsedAgentTypeAtom);
  const setUserConfig = useSetAtom(userConfigAtom);
  // Optimistically reflect the chosen harness in the shared config (the same
  // value the tab bar's + button reads). The backend persists it as the
  // most-recently-used harness when the agent is created (record-on-create).
  const setLastUsedAgentType = useCallback(
    (stored: StoredAgentType): void => {
      setUserConfig((prev) => (prev ? { ...prev, lastUsedAgentType: stored } : prev));
    },
    [setUserConfig],
  );
  const [agentTypeValue, setAgentTypeValue] = useState<string>(lastUsedAgentType);
  const { registrations, refetch: refreshRegistrations } = useTerminalAgentRegistrations();
  const { agentType, registrationId } = parseStoredAgentType(agentTypeValue as StoredAgentType);
  const [workspaceNameDraft, setWorkspaceNameDraft] = useDraftTabName(draftId);
  const workspaceName = workspaceNameDraft ?? "";
  const setWorkspaceName = useCallback(
    (value: string) => setWorkspaceNameDraft(value || null),
    [setWorkspaceNameDraft],
  );
  const [userSelectedBranch, setUserSelectedBranch] = useDraftSourceBranch(draftId);
  const [isPending, setIsPending] = useState(false);
  const [toast, setToast] = useState<ToastContent | null>(null);
  // `null` means "use the auto-filled preview"; any string means the user has
  // taken over and we render their override. Both the value and the manual flag
  // collapse into one piece of state so they can never disagree.
  const [branchNameOverride, setBranchNameOverride] = useDraftBranchNameOverride(draftId);
  const isBranchNameManuallyEdited = branchNameOverride !== null;

  const handleProjectChange = useCallback(
    (nextProjectId: string | null): void => {
      setSelectedProjectId(nextProjectId);
      // Switching repos invalidates branch choices made against the old repo.
      setBranchNameOverride(null);
      setUserSelectedBranch(null);
    },
    [setSelectedProjectId, setBranchNameOverride, setUserSelectedBranch],
  );

  // Single source of truth for the branch-name field. The hook owns preview
  // fetching and the debounced collision check; the parent owns the override.
  const {
    preview: branchNamePreview,
    displayedValue: effectiveBranchName,
    isLoading: isBranchNamePreviewLoading,
    status: branchNameStatus,
  } = useBranchNamePreview({
    projectId: selectedProjectId,
    workspaceName,
    override: branchNameOverride,
  });

  // Repo info for the selected project
  const { repoInfo, fetchRepoInfo, fetchCurrentBranch } = useRepoInfo(selectedProjectId ?? "");

  const sourceBranch = useMemo(() => {
    if (userSelectedBranch) {
      return userSelectedBranch;
    }
    return repoInfo?.currentBranch;
  }, [userSelectedBranch, repoInfo]);

  // Load projects on mount into global atom
  useEffect(() => {
    let isCancelled = false;

    const loadProjects = async (): Promise<void> => {
      try {
        const [projectsResponse, mruResponse] = await Promise.all([
          getActiveProjects({ meta: { skipWsAck: true } }),
          getMostRecentlyUsedProject({ meta: { skipWsAck: true } }),
        ]);

        if (isCancelled) return;

        const activeProjects = projectsResponse.data ?? [];
        updateProjects(activeProjects);

        // Keep a persisted selection (restored from a previous visit to this
        // draft tab) when it still points at an existing project. Only fall back
        // to the MRU project — then the first project — when there is no valid
        // selection yet, so navigating away and back doesn't reset the repo.
        const restoredProjectId = selectedProjectIdRef.current;
        const hasValidSelection =
          restoredProjectId !== null && activeProjects.some((p) => p.objectId === restoredProjectId);
        if (!hasValidSelection) {
          const mruProjectId = mruResponse.data;
          if (mruProjectId && activeProjects.some((p) => p.objectId === mruProjectId)) {
            setSelectedProjectId(mruProjectId);
          } else if (activeProjects.length > 0) {
            setSelectedProjectId(activeProjects[0].objectId);
          }
        }
      } catch (error) {
        console.error("Failed to load projects:", error);
        if (!isCancelled) {
          setToast({ title: "Failed to load repositories", type: ToastType.ERROR });
        }
      } finally {
        if (!isCancelled) {
          setIsLoadingProjects(false);
        }
      }
    };

    void loadProjects();
    return (): void => {
      isCancelled = true;
    };
  }, [updateProjects, setSelectedProjectId]);

  // Auto-select newly added projects
  const prevProjectIdsRef = useRef(new Set(projects.map((p) => p.objectId)));
  useEffect(() => {
    const currentIds = new Set(projects.map((p) => p.objectId));
    const newIds = projects.filter((p) => !prevProjectIdsRef.current.has(p.objectId));
    prevProjectIdsRef.current = currentIds;

    if (newIds.length > 0) {
      setSelectedProjectId(newIds[newIds.length - 1].objectId);
      // A freshly added repo replaces the selection, so a branch picked against
      // the previous repo no longer applies.
      setUserSelectedBranch(null);
    }
  }, [projects, setSelectedProjectId, setUserSelectedBranch]);

  // Refresh branch info when the project changes. The source-branch reset lives
  // in handleProjectChange / the new-project effect (i.e. on a real user-driven
  // change) rather than here, so restoring a persisted project on remount does
  // not wipe the persisted source branch.
  useEffect(() => {
    if (!selectedProjectId) return;
    fetchCurrentBranch();
    fetchRepoInfo();
  }, [selectedProjectId, fetchCurrentBranch, fetchRepoInfo]);

  const handleSubmit = useCallback(async (): Promise<void> => {
    if (isPending || !selectedProjectId) return;

    const trimmedBranch = effectiveBranchName.trim();
    if (!trimmedBranch) {
      setToast({
        title: "Branch name is required",
        type: ToastType.ERROR,
      });
      return;
    }

    setIsPending(true);
    try {
      // Signal that this pseudo-tab is creating a workspace so the WebSocket
      // handler (updateWorkspacesAtom) won't auto-open the new workspace as
      // a duplicate tab.  The flag is cleared by convertNewWorkspaceToTab.
      markDraftCreating(draftId);

      const wsResponse = await createWorkspaceV2({
        body: {
          projectId: selectedProjectId,
          sourceBranch,
          description: workspaceName.trim() || "Untitled workspace",
          requestedBranchName: trimmedBranch,
        },
      });

      if (!wsResponse.data) {
        throw new Error("Failed to create workspace — no response data");
      }

      const workspaceId = wsResponse.data.objectId;

      // The API call waits for WebSocket confirmation (via request tracker),
      // so the workspace is already in workspaceIdsAtom.  Replace the
      // pseudo-tab with the real workspace tab in its same position.
      convertNewWorkspaceToTab({ draftId, workspaceId });
      // The draft has become a real workspace — drop all of its persisted
      // form state so the (now-defunct) draftId doesn't leave stale entries
      // behind in localStorage.
      setWorkspaceNameDraft(null);
      setSelectedProjectId(null);
      setUserSelectedBranch(null);
      setBranchNameOverride(null);

      // If the remembered registered agent's registration is no longer present
      // (deleted since it was picked), fall back to a plain terminal rather
      // than leaving the just-created workspace with a failed, agentless
      // first-agent create.
      const isMissingRegistration =
        agentType === "registered" && !registrations.some((r) => r.registrationId === registrationId);
      const effectiveAgentType = isMissingRegistration ? "terminal" : agentType;
      const effectiveRegistrationId = isMissingRegistration ? undefined : registrationId;
      const effectiveAgentTypeValue: StoredAgentType = isMissingRegistration
        ? "terminal"
        : (agentTypeValue as StoredAgentType);

      // Create first agent (no prompt in the simplified form). The built-in
      // terminal/registered agents have no creation-time model concept, so no
      // model is sent.
      const agentResponse = await createWorkspaceAgent({
        path: { workspace_id: workspaceId },
        body: {
          agentType: effectiveAgentType,
          registrationId: effectiveRegistrationId,
        },
      });

      if (!agentResponse.data) {
        throw new Error("Failed to create agent — no response data");
      }

      // The agent was actually created with this type — record it as the
      // shared MRU so the tab bar's plain + click creates the same type.
      setLastUsedAgentType(effectiveAgentTypeValue);

      navigateToAgent(workspaceId, agentResponse.data.id);
    } catch (error) {
      // Clear the pending-creation flag so auto-open resumes normally.
      clearDraftCreating(draftId);
      console.error("Failed to create workspace:", error);
      if (error instanceof HTTPException && error.status === 409) {
        setToast({
          title: `Branch '${trimmedBranch}' already exists`,
          type: ToastType.ERROR,
        });
      } else {
        setToast({
          title: "",
          description: (
            <div>
              <b>Failed to create workspace</b>
              <br />
              <pre>{"" + error}</pre>
            </div>
          ),
          type: ToastType.ERROR,
        });
      }
    } finally {
      setIsPending(false);
    }
  }, [
    isPending,
    selectedProjectId,
    draftId,
    agentType,
    registrationId,
    registrations,
    agentTypeValue,
    setLastUsedAgentType,
    sourceBranch,
    workspaceName,
    effectiveBranchName,
    navigateToAgent,
    setWorkspaceNameDraft,
    setSelectedProjectId,
    setUserSelectedBranch,
    setBranchNameOverride,
    convertNewWorkspaceToTab,
    markDraftCreating,
    clearDraftCreating,
  ]);

  // When nothing on the page has meaningful focus, arrow keys should move
  // focus to the workspace name input so the user can start navigating.
  useEffect(() => {
    const handleArrowKey = (e: KeyboardEvent): void => {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;

      // Only intercept when focus is on the document body (i.e. nothing
      // interactive is focused). Other elements like inputs and the
      // recent workspaces area have their own arrow key handlers.
      if (document.activeElement !== document.body) return;

      e.preventDefault();
      nameInputRef.current?.focus();
    };

    document.addEventListener("keydown", handleArrowKey);
    return (): void => document.removeEventListener("keydown", handleArrowKey);
  }, []);

  if (isLoadingProjects) {
    return (
      <Flex align="center" justify="center" height="var(--app-height)">
        <Spinner size="3" />
      </Flex>
    );
  }

  return (
    <>
      <Flex direction="column" align="center" justify="center" className={styles.container}>
        <Flex direction="column" align="center" gap="5" className={styles.content}>
          <Text className={styles.headerTitle}>Name your workspace</Text>

          <NewWorkspaceForm
            workspaceName={workspaceName}
            onWorkspaceNameChange={setWorkspaceName}
            nameInputRef={nameInputRef}
            repoInfo={repoInfo}
            isPending={isPending}
            isSubmitDisabled={effectiveBranchName.trim() === "" || isBranchNamePreviewLoading}
            onSubmit={handleSubmit}
            autoFocus
            branchField={
              <BranchNameField
                value={effectiveBranchName}
                isManuallyEdited={isBranchNameManuallyEdited}
                isLoading={isBranchNamePreviewLoading}
                status={branchNameStatus}
                preview={branchNamePreview}
                onUserEdit={(value): void => setBranchNameOverride(value)}
                onReset={(): void => setBranchNameOverride(null)}
                disabled={isPending}
              />
            }
          >
            <RepoSelector
              projects={projects}
              selectedProjectId={selectedProjectId}
              onProjectChange={handleProjectChange}
              className={styles.compactSelector}
            />

            {repoInfo ? (
              <BranchSelector
                fetchRepoInfo={fetchRepoInfo}
                repoInfo={repoInfo}
                setUserSelectedBranch={setUserSelectedBranch}
                sourceBranch={sourceBranch}
              />
            ) : (
              <Button disabled={true} className={styles.loadingButton}>
                <Flex align="center" gap="1">
                  <Spinner />
                  <Text size="1">Loading ...</Text>
                </Flex>
              </Button>
            )}

            {/* First-agent type selector — the same per-agent choice as the
                tab bar's + menu: a plain Terminal agent or any registered
                terminal agent. */}
            <Select.Root
              size="1"
              value={agentTypeValue}
              onValueChange={setAgentTypeValue}
              onOpenChange={(open) => {
                // Re-read the registrations directory on every open so the
                // options track the filesystem without a restart.
                if (open) refreshRegistrations();
              }}
            >
              <Select.Trigger
                variant="ghost"
                className={styles.compactSelector}
                data-testid={ElementIds.ADD_WORKSPACE_AGENT_TYPE_SELECT}
              >
                <Flex align="center" gap="1">
                  <BotIcon size={12} />
                  <Text className={styles.selectorLabel}>agent</Text>
                  {agentType === "registered"
                    ? (registrations.find((r) => r.registrationId === registrationId)?.displayName ?? "Registered")
                    : AGENT_TYPE_LABELS[agentType]}
                </Flex>
              </Select.Trigger>
              <Select.Content position="popper" side="bottom" sideOffset={5}>
                <Select.Item value="terminal" data-testid={ElementIds.AGENT_TYPE_OPTION_TERMINAL}>
                  {AGENT_TYPE_LABELS.terminal}
                </Select.Item>
                {registrations.map((registration) => (
                  <Select.Item
                    key={registration.registrationId}
                    value={encodeRegisteredAgentType(registration.registrationId)}
                    data-testid={ElementIds.AGENT_TYPE_OPTION_REGISTERED}
                    data-registration-id={registration.registrationId}
                  >
                    {registration.displayName}
                  </Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
          </NewWorkspaceForm>
        </Flex>
      </Flex>
      <Toast
        open={!!toast}
        onOpenChange={(open) => !open && setToast(null)}
        description={toast?.description}
        duration={5000}
        title={toast?.title}
        type={toast?.type}
      />
    </>
  );
};
