import { Flex } from "@radix-ui/themes";
import { useAtomValue, useSetAtom } from "jotai";
import type { ReactElement } from "react";
import { useCallback, useState } from "react";
import { Outlet } from "react-router-dom";

import { useSyncActiveTabFromRoute } from "../common/hooks/useSyncActiveTabFromRoute.ts";
import { useActiveProjectID } from "../common/NavigateUtils.ts";
import { backendStatusAtom } from "../common/state/atoms/backend.ts";
import {
  deleteErrorToastAtom,
  terminalPromptRejectedToastAtom,
  workspaceDeleteErrorToastAtom,
  workspaceOpenCloseErrorToastAtom,
} from "../common/state/atoms/toasts.ts";
import { useProject } from "../common/state/hooks/useProjects.ts";
import { useUnifiedStream } from "../common/state/hooks/useUnifiedStream";
import { CommandPalette } from "../components/CommandPalette";
import { CommandRegistrations } from "../components/CommandPalette/CommandRegistrations.tsx";
import { DevModeIndicator } from "../components/DevModeIndicator.tsx";
import { KeyboardShortcutsDialog } from "../components/KeyboardShortcutsDialog.tsx";
import { NotificationToasts } from "../components/NotificationToasts.tsx";
import { PanelRegistryProvider } from "../components/panels/PanelRegistryProvider.tsx";
import { RepoPathDialog } from "../components/RepoPathDialog.tsx";
import { Toast } from "../components/Toast.tsx";
import { TopBar } from "../components/TopBar.tsx";
import { VersionPopover } from "../components/VersionPopover.tsx";
import { WarningStatusBanner } from "../components/WarningStatusBanner.tsx";
import { workspaceDefaultLayout, workspacePanels } from "../pages/workspace/panels/workspacePanels.ts";
import { usePageLayoutKeyboardShortcuts } from "./hooks/usePageLayoutKeyboardShortcuts.ts";

export const PageLayout = (): ReactElement => {
  const backendStatus = useAtomValue(backendStatusAtom);
  const deleteErrorToast = useAtomValue(deleteErrorToastAtom);
  const setDeleteErrorToast = useSetAtom(deleteErrorToastAtom);
  const workspaceDeleteErrorToast = useAtomValue(workspaceDeleteErrorToastAtom);
  const setWorkspaceDeleteErrorToast = useSetAtom(workspaceDeleteErrorToastAtom);
  const workspaceOpenCloseErrorToast = useAtomValue(workspaceOpenCloseErrorToastAtom);
  const setWorkspaceOpenCloseErrorToast = useSetAtom(workspaceOpenCloseErrorToastAtom);
  const terminalPromptRejectedToast = useAtomValue(terminalPromptRejectedToastAtom);
  const setTerminalPromptRejectedToast = useSetAtom(terminalPromptRejectedToastAtom);
  const projectID = useActiveProjectID();
  const currentProject = useProject(projectID ?? "");
  const [isRepoPathDialogOpen, setIsRepoPathDialogOpen] = useState(false);

  // Stable callbacks so the memoized <Toast> instances below bail out instead
  // of re-rendering on every unrelated commit while they sit closed. (SCU-1455)
  const handleDeleteErrorOpenChange = useCallback(
    (open: boolean) => {
      if (!open) setDeleteErrorToast(null);
    },
    [setDeleteErrorToast],
  );
  const handleWorkspaceDeleteErrorOpenChange = useCallback(
    (open: boolean) => {
      if (!open) setWorkspaceDeleteErrorToast(null);
    },
    [setWorkspaceDeleteErrorToast],
  );
  const handleWorkspaceOpenCloseErrorOpenChange = useCallback(
    (open: boolean) => {
      if (!open) setWorkspaceOpenCloseErrorToast(null);
    },
    [setWorkspaceOpenCloseErrorToast],
  );
  const handleTerminalPromptRejectedOpenChange = useCallback(
    (open: boolean) => {
      if (!open) setTerminalPromptRejectedToast(null);
    },
    [setTerminalPromptRejectedToast],
  );

  useUnifiedStream();
  usePageLayoutKeyboardShortcuts();
  useSyncActiveTabFromRoute();

  const hasBackendStopped = backendStatus.status === "unresponsive";
  const hasHealthWarningOnBackend = backendStatus.status === "warning";

  const isProjectPathInaccessible = currentProject && currentProject.isPathAccessible === false;

  return (
    <>
      <Flex
        direction="column"
        height="var(--app-height)"
        width="100vw"
        position="relative"
        overflow="hidden"
        style={{ background: "var(--gray-2)" }}
      >
        <TopBar />
        <PanelRegistryProvider panels={workspacePanels} defaultLayout={workspaceDefaultLayout}>
          <Outlet />
        </PanelRegistryProvider>
        <Flex
          align="center"
          px="3"
          py="2"
          flexShrink="0"
          style={{ background: "var(--gray-2)", borderTop: "1px solid var(--gray-a5)" }}
        >
          <Flex flexBasis="0" flexGrow="1" />
          <Flex flexBasis="0" flexGrow="1" justify="center">
            <DevModeIndicator />
          </Flex>
          <Flex flexBasis="0" flexGrow="1" justify="end">
            <VersionPopover />
          </Flex>
        </Flex>
        {isProjectPathInaccessible && (
          <WarningStatusBanner
            message={`Project folder not found: ${currentProject.name}.`}
            linkText="Learn more"
            onLinkClick={() => setIsRepoPathDialogOpen(true)}
          />
        )}
        {(hasBackendStopped || hasHealthWarningOnBackend) && (
          <WarningStatusBanner message={backendStatus.payload.message} />
        )}
      </Flex>
      <CommandRegistrations />
      <CommandPalette />
      <KeyboardShortcutsDialog />
      <RepoPathDialog
        isOpen={isRepoPathDialogOpen}
        project={currentProject}
        onClose={() => setIsRepoPathDialogOpen(false)}
      />
      <NotificationToasts />
      <Toast
        open={deleteErrorToast !== null}
        onOpenChange={handleDeleteErrorOpenChange}
        title={deleteErrorToast?.title}
        description={deleteErrorToast?.description}
        type={deleteErrorToast?.type}
        action={deleteErrorToast?.action ?? undefined}
        duration={10000}
      />
      <Toast
        open={workspaceDeleteErrorToast !== null}
        onOpenChange={handleWorkspaceDeleteErrorOpenChange}
        title={workspaceDeleteErrorToast?.title}
        description={workspaceDeleteErrorToast?.description}
        type={workspaceDeleteErrorToast?.type}
        action={workspaceDeleteErrorToast?.action ?? undefined}
        duration={10000}
      />
      <Toast
        open={workspaceOpenCloseErrorToast !== null}
        onOpenChange={handleWorkspaceOpenCloseErrorOpenChange}
        title={workspaceOpenCloseErrorToast?.title}
        description={workspaceOpenCloseErrorToast?.description}
        type={workspaceOpenCloseErrorToast?.type}
        action={workspaceOpenCloseErrorToast?.action ?? undefined}
        duration={10000}
      />
      <Toast
        open={terminalPromptRejectedToast !== null}
        onOpenChange={handleTerminalPromptRejectedOpenChange}
        title={terminalPromptRejectedToast?.title}
        description={terminalPromptRejectedToast?.description}
      />
    </>
  );
};
