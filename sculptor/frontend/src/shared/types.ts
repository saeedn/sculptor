type BaseBackendStatusPayload = { message: string };

export type BackendStatusPayloads = {
  loading: BaseBackendStatusPayload;
  running: BaseBackendStatusPayload;
  warning: BaseBackendStatusPayload;
  error: BaseBackendStatusPayload & { message: string; stack: string };
  exited: BaseBackendStatusPayload & { code: number | null; signal: NodeJS.Signals | null; stderr: string };
  unresponsive: BaseBackendStatusPayload;
  shutting_down: BaseBackendStatusPayload;
};

export type BackendStatus<T extends keyof BackendStatusPayloads = keyof BackendStatusPayloads> = {
  status: T;
  payload: BackendStatusPayloads[T];
};

export type AnyBackendStatus = BackendStatus<keyof BackendStatusPayloads>;

// Dev-mode metadata exposed by the Electron main process via the
// GET_DEV_INFO IPC channel. Resolves to null in packaged builds. The
// `iconDataUrl` is the same NativeImage used for the dock icon serialized
// at full resolution — the renderer scales it via CSS.
export type SculptorDevInfo = {
  label: string;
  workspaceId: string | null;
  iconDataUrl: string | null;
};

// Type definitions for Electron IPC exposed to the renderer
export type SculptorElectronAPI = {
  selectProjectDirectory: () => Promise<string | null>;
  platform: string;
  getCurrentBackendStatus: () => Promise<AnyBackendStatus>;
  onBackendStatusChange: (callback: (state: AnyBackendStatus) => void) => void;
  removeBackendStatusListener: () => void;
  getSessionToken: () => Promise<string>;
  getBackendPort: () => Promise<number>;
  // File storage operations
  saveFile: (fileData: ArrayBuffer, filename: string) => Promise<string>;
  getFileData: (filePath: string) => Promise<string>;
  getBackendUrl: () => Promise<string | null>;
  getAppVersion: () => Promise<string>;
  // Dev-mode metadata: resolves to null in packaged builds.
  getDevInfo: () => Promise<SculptorDevInfo | null>;
  // Zoom commands forwarded from the main process (View menu / accelerators
  // / SCULPTOR_ZOOM_FACTOR). The renderer is the source of truth for the
  // zoom level — it persists the level and applies setZoomFactor itself so
  // the CSS variable update and the Chromium repaint stay in sync.
  onZoomCommand: (callback: (command: ZoomCommand) => void) => (...args: Array<unknown>) => void;
  removeZoomCommandListener: (wrappedCallback: (...args: Array<unknown>) => void) => void;
  setZoomFactor: (factor: number) => void;
};

export type ZoomCommand = { kind: "in" } | { kind: "out" } | { kind: "reset" } | { kind: "setFactor"; factor: number };
