// NOTE: you cannot import electron things here because this file is imported both in electron flavor JS and in browser flavor JS.

/**
 * Check if the app is running in Electron environment
 * This checks for the presence of the sculptor API exposed via contextBridge
 */
export const isElectron = (): boolean => {
  return typeof window !== "undefined" && window.sculptor !== undefined;
};

/**
 * Open a native directory selection dialog
 * @returns The selected directory path or null if cancelled
 * @throws Error if not in Electron environment
 */
export const selectProjectDirectory = async (): Promise<string | null> => {
  if (isElectron() && window.sculptor?.selectProjectDirectory) {
    return await window.sculptor.selectProjectDirectory();
  }
  throw Error("selectProjectDirectory is only available in Electron environment");
};

// Titlebar constants
export const TITLEBAR_HEIGHT = 40;
const TITLEBAR_MAC_LEFT_PADDING = 80;
// On macOS the traffic-light buttons are drawn by the OS at a fixed device-pixel
// size and position, but the rest of the page is zoomed via CSS `zoom` on
// document.body. To keep the reserved gutter width matching the native buttons
// regardless of zoom level, divide our base px values by --app-zoom.
const macZoomPaddingCss = (px: number): string => `calc(${px}px / var(--app-zoom))`;
export const getTitleBarLeftPadding = (): string => {
  // On macOS, the titlebar traffic light buttons are on the left, so we need to add padding
  if (!isMac()) {
    return "12px";
  }
  return macZoomPaddingCss(TITLEBAR_MAC_LEFT_PADDING);
};

export const isMac = (): boolean => {
  return window.sculptor?.platform === "darwin" || navigator.platform.startsWith("Mac");
};

export const getMetaKey = (): string => {
  return isMac() ? "⌘" : "Ctrl";
};

export const isModifierPressed = (e: KeyboardEvent | React.KeyboardEvent): boolean => {
  return isMac() ? e.metaKey : e.ctrlKey;
};
