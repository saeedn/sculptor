import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { ResizeHandle } from "./ResizeHandle";

// jsdom does not implement PointerEvent; fall back to MouseEvent so
// fireEvent.pointerDown's `button`/`clientX`/`clientY` reach the handler.
beforeAll(() => {
  if (typeof window.PointerEvent === "undefined") {
    (window as unknown as { PointerEvent: typeof MouseEvent }).PointerEvent = MouseEvent;
  }
});

afterEach(() => {
  cleanup();
});

// ResizeHandle reflects the active drag via the `data-resize-handle-active`
// attribute (set while a pointer drag is in progress, cleared on pointerup).
describe("ResizeHandle — drag lifecycle", () => {
  const renderHandle = (): HTMLElement => {
    const { getByRole } = render(
      <ResizeHandle axis="x" getSize={() => 200} onResize={vi.fn()} ariaLabel="test handle" />,
    );
    return getByRole("separator");
  };

  it("marks the handle active on pointerdown and clears it on pointerup", () => {
    const handle = renderHandle();
    expect(handle.hasAttribute("data-resize-handle-active")).toBe(false);

    fireEvent.pointerDown(handle, { button: 0, clientX: 100, clientY: 0 });
    expect(handle.hasAttribute("data-resize-handle-active")).toBe(true);

    fireEvent.pointerUp(window, { clientX: 150, clientY: 0 });
    expect(handle.hasAttribute("data-resize-handle-active")).toBe(false);
  });

  it("non-primary buttons do not start a drag", () => {
    const handle = renderHandle();
    fireEvent.pointerDown(handle, { button: 2, clientX: 0, clientY: 0 });
    expect(handle.hasAttribute("data-resize-handle-active")).toBe(false);
  });

  it("reports resize deltas while dragging", () => {
    const onResize = vi.fn();
    const { getByRole } = render(
      <ResizeHandle axis="x" getSize={() => 200} onResize={onResize} ariaLabel="test handle" />,
    );
    const handle = getByRole("separator");

    fireEvent.pointerDown(handle, { button: 0, clientX: 100, clientY: 0 });
    fireEvent.pointerMove(window, { clientX: 150, clientY: 0 });
    expect(onResize).toHaveBeenCalledWith(250);

    fireEvent.pointerUp(window, { clientX: 150, clientY: 0 });
  });
});
