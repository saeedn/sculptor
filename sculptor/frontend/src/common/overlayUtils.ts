/**
 * Check whether any dismissible overlay (dialog, menu, popover, or select) is
 * currently open. Used to prevent global keyboard handlers from consuming
 * events that should be handled by the topmost overlay.
 *
 * This relies on DOM attributes set by Radix UI, so new Radix-based overlays
 * are detected automatically without code changes here.
 */
export const isDismissibleOverlayOpen = (): boolean => {
  // Radix Dialog / AlertDialog (fixed-position overlays, not popper-based).
  if (document.querySelector('[role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"]')) {
    return true;
  }

  // Radix popper-based overlays (DropdownMenu, ContextMenu, Popover, Select).
  // These are conditionally mounted — the wrapper only exists while open.
  // Check the content child's role to exclude tooltips and hover cards.
  const popperWrappers = document.querySelectorAll("[data-radix-popper-content-wrapper]");
  for (const wrapper of popperWrappers) {
    const content = wrapper.firstElementChild;
    if (content) {
      const role = content.getAttribute("role");
      if (role === "menu" || role === "listbox" || role === "dialog") {
        return true;
      }
    }
  }

  return false;
};
