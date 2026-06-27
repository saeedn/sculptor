// Panel size defaults (pixels). The layout is pixel-native; flexbox handles
// "fill the remaining space" for the center panel.
export const DEFAULT_SIDE_PANEL_WIDTH_PX = 300;
export const DEFAULT_BOTTOM_PANEL_HEIGHT_PX = 300;
export const DEFAULT_INNER_BOTTOM_HEIGHT_PX = 200;
export const SIDE_PANEL_MIN_WIDTH_PX = 245;
// Minimum usable width for the chat interface. When the window is too narrow
// to fit both side panels and this, side panels auto-collapse (right first).
export const CENTER_PANEL_MIN_WIDTH_PX = 400;
// Hard floor for any panel so it can always be grabbed and dragged back out.
export const PANEL_MIN_PX = 60;
