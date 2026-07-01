/**
 * Describes what the backend environment supports.
 *
 * Components query individual capability flags so the UI adapts to the
 * environment. The backend always runs on the same host as the app (the
 * remote/custom-command backend was removed), so these are currently constant.
 */

export type BackendCapabilities = {
  /** Can the backend open files/folders on the host OS? */
  canOpenInOS: boolean;
  /** Can Electron show a native directory picker that the backend can access? */
  canSelectLocalDir: boolean;
};

const CAPABILITIES: BackendCapabilities = {
  canOpenInOS: true,
  canSelectLocalDir: true,
} as const satisfies BackendCapabilities;

/** Read the current capabilities. Safe to call from React components or plain utilities. */
export const getBackendCapabilities = (): BackendCapabilities => CAPABILITIES;
