import { contextBridge, ipcRenderer, webFrame } from "electron";

import type { ZoomCommand } from "./electron/constants.ts";
import {
  BACKEND_PORT_CHANNEL_NAME,
  BACKEND_STATUS_CHANGE_CHANNEL_NAME,
  GET_APP_VERSION_CHANNEL_NAME,
  GET_CURRENT_BACKEND_STATUS_CHANNEL_NAME,
  GET_DEV_INFO_CHANNEL_NAME,
  GET_FILE_DATA_CHANNEL_NAME,
  SAVE_FILE_CHANNEL_NAME,
  SELECT_PROJECT_DIRECTORY_CHANNEL_NAME,
  ZOOM_COMMAND_CHANNEL_NAME,
} from "./electron/constants.ts";
import type { AnyBackendStatus, SculptorDevInfo } from "./shared/types.ts";

contextBridge.exposeInMainWorld("sculptor", {
  platform: process.platform,
  // Select a project directory using native file dialog
  selectProjectDirectory: () => ipcRenderer.invoke(SELECT_PROJECT_DIRECTORY_CHANNEL_NAME),
  // Get current backend process state
  getCurrentBackendStatus: () => ipcRenderer.invoke(GET_CURRENT_BACKEND_STATUS_CHANNEL_NAME),
  // Register callback for backend process state updates
  onBackendStatusChange: (callback: (state: AnyBackendStatus) => void) =>
    ipcRenderer.on(BACKEND_STATUS_CHANGE_CHANNEL_NAME, (_event, state) => callback(state)),
  // Remove backend state listener
  removeBackendStatusListener: () => ipcRenderer.removeAllListeners(BACKEND_STATUS_CHANGE_CHANNEL_NAME),
  getSessionToken: () => ipcRenderer.invoke("get-session-token"),
  getBackendPort: () => ipcRenderer.invoke(BACKEND_PORT_CHANNEL_NAME),
  // File storage operations
  saveFile: (fileData: ArrayBuffer, filename: string): Promise<string> =>
    ipcRenderer.invoke(SAVE_FILE_CHANNEL_NAME, fileData, filename),
  getFileData: (filePath: string): Promise<string> => ipcRenderer.invoke(GET_FILE_DATA_CHANNEL_NAME, filePath),
  getBackendUrl: (): Promise<string | null> => ipcRenderer.invoke("get-backend-url"),
  getAppVersion: (): Promise<string> => ipcRenderer.invoke(GET_APP_VERSION_CHANNEL_NAME),
  // Dev-mode metadata: resolves to null in packaged builds.
  getDevInfo: (): Promise<SculptorDevInfo | null> => ipcRenderer.invoke(GET_DEV_INFO_CHANNEL_NAME),
  // Zoom commands dispatched from the View menu / accelerators (or the
  // SCULPTOR_ZOOM_FACTOR override at startup).
  onZoomCommand: (callback: (command: ZoomCommand) => void): ((...args: Array<unknown>) => void) => {
    const wrappedCallback = (_event: unknown, command: ZoomCommand): void => callback(command);
    ipcRenderer.on(ZOOM_COMMAND_CHANNEL_NAME, wrappedCallback);
    return wrappedCallback as (...args: Array<unknown>) => void;
  },
  removeZoomCommandListener: (wrappedCallback: (...args: Array<unknown>) => void): void => {
    ipcRenderer.off(ZOOM_COMMAND_CHANNEL_NAME, wrappedCallback);
  },
  // Apply a page zoom factor synchronously from the renderer. Pairs with the
  // CSS variable update in useAppZoom so the page repaint and the gutter
  // recompute happen in the same frame (no jitter).
  setZoomFactor: (factor: number): void => {
    webFrame.setZoomFactor(factor);
  },
});
