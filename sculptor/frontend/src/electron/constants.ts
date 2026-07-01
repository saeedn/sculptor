export const BACKEND_PORT_CHANNEL_NAME = "BACKEND_PORT";
export const BACKEND_STATUS_CHANGE_CHANNEL_NAME = "BACKEND_STATUS_CHANGE";
export const SELECT_PROJECT_DIRECTORY_CHANNEL_NAME = "SELECT_PROJECT_DIRECTORY";
export const GET_CURRENT_BACKEND_STATUS_CHANNEL_NAME = "GET_CURRENT_BACKEND_STATUS";
export const GET_DEV_INFO_CHANNEL_NAME = "GET_DEV_INFO";
// Sent from main → renderer when the user invokes a zoom action (View menu /
// accelerators) or when an explicit factor is pushed at startup
// (SCULPTOR_ZOOM_FACTOR). The renderer is the source of truth for the page
// zoom factor: it owns the level, calls webFrame.setZoomFactor, and updates
// the --app-zoom CSS custom property — all in one synchronous task so the
// page and the title-bar gutter repaint together (no jitter).
export const ZOOM_COMMAND_CHANNEL_NAME = "ZOOM_COMMAND";

export type ZoomCommand = { kind: "in" } | { kind: "out" } | { kind: "reset" } | { kind: "setFactor"; factor: number };
