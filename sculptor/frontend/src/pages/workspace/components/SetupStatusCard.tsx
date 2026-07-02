import { Anchor as PopoverAnchor } from "@radix-ui/react-popover";
import { IconButton, Popover, Spinner, Tooltip } from "@radix-ui/themes";
import { useAtomValue } from "jotai";
import { Check, Pencil, Play, RotateCcw, Square, TerminalIcon, X } from "lucide-react";
import type { CSSProperties, HTMLAttributes, KeyboardEvent, ReactElement, ReactNode } from "react";
import { forwardRef, useCallback, useEffect, useRef, useState } from "react";

import { ElementIds } from "~/api";
import { resolveWorkspaceSetupCommand } from "~/common/setupDefaults";
import { workspaceSetupOutputAtomFamily } from "~/common/state/atoms/workspaceSetupOutput";
import { workspaceSetupStatusAtomFamily } from "~/common/state/atoms/workspaceSetupStatus";
import { useOpenSettings } from "~/common/state/hooks/useOpenSettings";
import { useProject } from "~/common/state/hooks/useProjects";
import { useWorkspace } from "~/common/state/hooks/useWorkspace";

import { SetupConfigPrompt } from "./SetupConfigPrompt";
import styles from "./SetupStatusCard.module.scss";

type SetupStatusCardProps = {
  workspaceId: string;
};

const SETUP_LABEL = "Setup";
const POPOVER_STYLE: CSSProperties = {
  maxHeight: 380,
  overflow: "hidden",
  padding: 0,
};

const postNoBody = async (path: string): Promise<Response> => fetch(path, { method: "POST" });

/** Format a duration in seconds into a human-readable string (e.g. "3.2s"). */
function formatDuration(seconds: number): string {
  if (Number.isNaN(seconds)) return "0.0s";
  return `${seconds.toFixed(1)}s`;
}

function useElapsedSinceStart(startedAt: number | null, isRunning: boolean): string {
  const [now, setNow] = useState<number>(() => Date.now() / 1000);
  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => {
      setNow(Date.now() / 1000);
    }, 100);
    return (): void => clearInterval(id);
  }, [isRunning]);
  if (startedAt === null) return "0.0s";
  return formatDuration(Math.max(0, now - startedAt));
}

type BadgeState = "executing" | "completed" | "error";

const StatusBadge = ({ state, duration }: { state: BadgeState; duration: string }): ReactElement => {
  if (state === "executing") {
    return (
      <span className={`${styles.badge} ${styles.badgeRunning}`} data-testid="setup-status-badge">
        {duration}
        <span className={styles.badgeIcon}>
          <Spinner size="1" />
        </span>
      </span>
    );
  }

  if (state === "error") {
    return (
      <span className={`${styles.badge} ${styles.badgeError}`} data-testid="setup-status-badge">
        {duration}
        <span className={styles.badgeIcon}>
          <X size={12} />
        </span>
      </span>
    );
  }
  return (
    <span className={`${styles.badge} ${styles.badgeSuccess}`} data-testid="setup-status-badge">
      {duration}
      <span className={styles.badgeIcon}>
        <Check size={12} />
      </span>
    </span>
  );
};

// Render a multiline command on a single line by joining nonblank lines with
// `&&`. Whitespace-only and comment lines are dropped.
function joinCommandForHeader(command: string): string {
  const segments = command
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith("#"));
  if (segments.length === 0) return command.trim();
  return segments.join(" && ");
}

type SetupRowProps = {
  title: ReactNode;
  aside: ReactNode;
  isOpen?: boolean;
  isError?: boolean;
  interactive?: boolean;
  testId?: string;
} & Omit<HTMLAttributes<HTMLDivElement>, "title">;

// Shared `[icon] Setup · [title] [aside]` row shell. forwardRef + props
// passthrough lets the caller attach the popover anchor ref and the
// click/keydown handlers that toggle the popover.
const SetupRow = forwardRef<HTMLDivElement, SetupRowProps>(
  ({ title, aside, isOpen = false, isError = false, interactive = false, testId, className, ...rest }, ref) => {
    const classNames = [styles.row];
    if (isOpen) classNames.push(styles.rowOpen);
    if (isError) classNames.push(styles.rowError);
    if (!interactive) classNames.push(styles.rowNoToggle);
    if (className) classNames.push(className);

    return (
      <div
        ref={ref}
        className={classNames.join(" ")}
        role={interactive ? "button" : undefined}
        aria-haspopup={interactive ? "dialog" : undefined}
        aria-expanded={interactive ? isOpen : undefined}
        tabIndex={interactive ? 0 : undefined}
        data-testid={testId}
        {...rest}
      >
        <span className={styles.rowLeading}>
          <TerminalIcon size={14} className={styles.rowIcon} aria-hidden="true" />
          <span className={styles.rowLabel}>{SETUP_LABEL}</span>
          <span className={styles.rowSeparator} aria-hidden="true">
            ·
          </span>
        </span>
        <span className={styles.rowTitle}>{title}</span>
        <span className={styles.rowAside}>{aside}</span>
      </div>
    );
  },
);
SetupRow.displayName = "SetupRow";

const CommandTitle = ({ command }: { command: string }): ReactElement => (
  <>
    <span className={styles.rowPrompt} aria-hidden="true">
      $
    </span>{" "}
    {command}
  </>
);

/**
 * Pinned status row for the workspace setup command, shown above the agent
 * terminal. Mirrors the backend setup-status state machine: a configure-CTA
 * when nothing is set, a one-click Run row for a not-yet-run command, a live
 * badge while running, and a terminal-state row (with a click-to-open output
 * popover) once the command succeeds or fails.
 */
export const SetupStatusCard = ({ workspaceId }: SetupStatusCardProps): ReactElement | null => {
  const status = useAtomValue(workspaceSetupStatusAtomFamily(workspaceId));
  const output = useAtomValue(workspaceSetupOutputAtomFamily(workspaceId));
  const workspace = useWorkspace(workspaceId);
  const project = useProject(workspace?.projectId ?? "");
  const openSettings = useOpenSettings();
  const popoverOutputRef = useRef<HTMLDivElement | null>(null);
  const rowRef = useRef<HTMLDivElement | null>(null);
  const [isPopoverOpen, setIsPopoverOpen] = useState<boolean>(false);
  const togglePopover = useCallback(() => setIsPopoverOpen((prev) => !prev), []);
  const handleRowKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>): void => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setIsPopoverOpen((prev) => !prev);
    }
  }, []);
  const isRunning = status?.status === "running";
  const startedAt = typeof status?.startedAt === "number" ? status.startedAt : null;
  const finishedAt = typeof status?.finishedAt === "number" ? status.finishedAt : null;
  const isLogTruncated = status?.logTruncated === true;
  const liveElapsed = useElapsedSinceStart(startedAt, isRunning);

  // While the popover is open during a run, autoscroll new chunks into view.
  useEffect(() => {
    if (popoverOutputRef.current && isPopoverOpen && isRunning) {
      popoverOutputRef.current.scrollTop = popoverOutputRef.current.scrollHeight;
    }
  }, [output?.text, isPopoverOpen, isRunning]);

  const handleCancel = useCallback(async () => {
    try {
      await postNoBody(`/api/v1/workspaces/${workspaceId}/setup/cancel`);
    } catch (err) {
      console.error("Failed to cancel setup:", err);
    }
  }, [workspaceId]);

  const handleRerun = useCallback(async () => {
    try {
      await postNoBody(`/api/v1/workspaces/${workspaceId}/setup/rerun`);
    } catch (err) {
      console.error("Failed to rerun setup:", err);
    }
  }, [workspaceId]);

  const handleEdit = useCallback((): void => {
    if (project?.objectId) {
      openSettings("repositories", project.objectId);
    } else {
      openSettings("repositories");
    }
  }, [project?.objectId, openSettings]);

  const editButton = (
    <Tooltip content="Edit command">
      <IconButton
        variant="ghost"
        size="1"
        data-testid={ElementIds.SETUP_EDIT_BUTTON}
        onClick={(e) => {
          e.stopPropagation();
          handleEdit();
        }}
        aria-label="Edit setup command"
      >
        <Pencil size={12} />
      </IconButton>
    </Tooltip>
  );

  // Mirror the backend's tri-state resolution: a null stored value runs the
  // current default, an empty string means the user cleared it, any other
  // string is custom.
  const currentCommand = resolveWorkspaceSetupCommand(project?.workspaceSetupCommand);

  if (status === null) {
    return <SetupConfigPrompt />;
  }

  // The workspace was created before a setup command was configured. If the
  // project now has one, offer a one-click Run; otherwise fall back to the
  // configure-CTA.
  if (status.status === "not_configured") {
    if (currentCommand === null) {
      return <SetupConfigPrompt />;
    }
    const runHeader = joinCommandForHeader(currentCommand);
    return (
      <SetupRow
        testId="setup-status-card"
        title={
          <Tooltip content={currentCommand} side="bottom">
            <span>
              <CommandTitle command={runHeader} />
            </span>
          </Tooltip>
        }
        aside={
          <>
            <Tooltip content="Run setup">
              <IconButton
                variant="soft"
                size="1"
                data-testid="setup-run-button"
                onClick={(e) => {
                  e.stopPropagation();
                  void handleRerun();
                }}
                aria-label="Run setup"
              >
                <Play size={12} />
              </IconButton>
            </Tooltip>
            {editButton}
          </>
        }
      />
    );
  }

  const persistedCommand =
    typeof workspace?.setupCommand === "string" && workspace.setupCommand.length > 0 ? workspace.setupCommand : null;
  const commandRan = persistedCommand ?? currentCommand;
  const commandHeader = commandRan ? joinCommandForHeader(commandRan) : "workspace setup";
  const titleNode = commandRan ? (
    <Tooltip content={commandRan} side="bottom">
      <span>
        <CommandTitle command={commandHeader} />
      </span>
    </Tooltip>
  ) : (
    <span className={styles.rowPlaceholder}>{commandHeader}</span>
  );

  if (status.status === "pending") {
    // The queued card carries the same `setup-status-card` testid as the
    // interactive card it becomes once the run starts, but while pending it
    // renders inert. `aria-disabled` makes that transient gap honest so the
    // framework's actionability contract holds a click until the card turns
    // interactive (SCU-1215).
    return (
      <SetupRow
        testId="setup-status-card"
        aria-disabled
        title={titleNode}
        aside={
          <>
            <span className={`${styles.badge} ${styles.badgeRunning}`} data-testid="setup-status-badge">
              queued
            </span>
            {editButton}
          </>
        }
      />
    );
  }

  let badgeState: BadgeState;
  let badgeDuration: string;
  if (status.status === "running") {
    badgeState = "executing";
    badgeDuration = liveElapsed;
  } else if (status.status === "succeeded") {
    badgeState = "completed";
    badgeDuration = durationBetween(startedAt, finishedAt);
  } else if (status.status === "failed") {
    badgeState = "error";
    badgeDuration = durationBetween(startedAt, finishedAt);
  } else {
    badgeState = "completed";
    badgeDuration = "previous";
  }

  const rawLogText = output?.text ?? "";
  // Prefix the body with "Exit code N\n" on failure, matching how Sculptor's
  // bash tool calls render their popover. Stderr is already merged into the
  // captured stream by the runner.
  const exitCodePrefix =
    status.status === "failed" && typeof status.exitCode === "number" ? `Exit code ${status.exitCode}\n` : "";
  const logText = `${exitCodePrefix}${rawLogText}`;
  const hasLogText = logText.length > 0;
  const hasCommandChanged = persistedCommand !== null && currentCommand !== null && persistedCommand !== currentCommand;
  // Rerun is gated on the project having a command — the backend reads it from
  // `project.workspace_setup_command` and 422s when blank.
  const isRerunVisible = (status.status === "succeeded" || status.status === "failed") && currentCommand !== null;

  const aside = (
    <>
      <StatusBadge state={badgeState} duration={badgeDuration} />
      {isRunning ? (
        <Tooltip content="Cancel setup">
          <IconButton
            variant="ghost"
            size="1"
            data-testid="setup-cancel-button"
            onClick={(e) => {
              e.stopPropagation();
              void handleCancel();
            }}
            aria-label="Cancel setup"
          >
            <Square size={12} />
          </IconButton>
        </Tooltip>
      ) : null}
      {isRerunVisible && (
        <Tooltip content={hasCommandChanged ? "Rerun setup (command has changed)" : "Rerun setup"}>
          <IconButton
            variant={hasCommandChanged ? "soft" : "ghost"}
            color={hasCommandChanged ? "amber" : undefined}
            size="1"
            data-testid="setup-rerun-button"
            data-command-changed={hasCommandChanged ? "true" : "false"}
            onClick={(e) => {
              e.stopPropagation();
              void handleRerun();
            }}
            aria-label={hasCommandChanged ? "Rerun setup (command has changed)" : "Rerun setup"}
          >
            <RotateCcw size={12} />
          </IconButton>
        </Tooltip>
      )}
      {editButton}
    </>
  );

  const isError = status.status === "failed";

  // Use PopoverAnchor + the row's own onClick instead of Popover.Trigger:
  // Trigger composes its toggle via Radix Slot, which is unreliable when
  // action IconButtons are nested in the row. The anchor pattern lets the row
  // own its click; onPointerDownOutside keeps in-row clicks from auto-closing.
  return (
    <Popover.Root open={isPopoverOpen} onOpenChange={setIsPopoverOpen}>
      <PopoverAnchor asChild>
        <SetupRow
          ref={rowRef}
          testId="setup-status-card"
          isOpen={isPopoverOpen}
          isError={isError}
          interactive
          title={titleNode}
          aside={aside}
          onClick={togglePopover}
          onKeyDown={handleRowKeyDown}
        />
      </PopoverAnchor>
      <Popover.Content
        side="bottom"
        sideOffset={4}
        align="start"
        collisionPadding={16}
        className={styles.popoverContent}
        onOpenAutoFocus={(e) => e.preventDefault()}
        onPointerDownOutside={(e) => {
          if (rowRef.current?.contains(e.target as Node)) e.preventDefault();
        }}
        style={POPOVER_STYLE}
      >
        <div className={styles.popover}>
          <div className={styles.popoverSection}>
            <span className={styles.popoverCommand}>
              <span className={styles.prompt}>$</span> {commandRan ?? commandHeader}
              <div className={styles.popoverSummary}>workspace setup command</div>
            </span>
          </div>
          {isLogTruncated && (
            <div className={styles.truncationBanner} data-testid="setup-status-truncation">
              Output was truncated. Showing first and last portions.
            </div>
          )}
          <div className={styles.popoverSection}>
            <div ref={popoverOutputRef} className={styles.popoverBody} data-testid="setup-status-output">
              {hasLogText ? logText : <span className={styles.popoverEmpty}>(no output)</span>}
              {isRunning && <span className={styles.streamCursor} />}
            </div>
          </div>
        </div>
      </Popover.Content>
    </Popover.Root>
  );
};

function durationBetween(startedAt: number | null, finishedAt: number | null): string {
  if (startedAt === null || finishedAt === null) return "";
  return formatDuration(Math.max(0, finishedAt - startedAt));
}
