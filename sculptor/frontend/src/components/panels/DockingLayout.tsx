import { useAtom, useAtomValue, useSetAtom } from "jotai";
import type { ReactElement, ReactNode } from "react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { ElementIds } from "~/api";
import {
  expandedPanelIdAtom,
  isBottomVisibleAtom,
  isLeftSideVisibleAtom,
  isRightSideVisibleAtom,
  zoneAssignmentsAtom,
  zoneSizesAtom,
  zoneVisibilityAtom,
} from "~/components/panels/atoms.ts";
import {
  CENTER_PANEL_MIN_WIDTH_PX,
  DEFAULT_BOTTOM_PANEL_HEIGHT_PX,
  DEFAULT_SIDE_PANEL_WIDTH_PX,
  PANEL_MIN_PX,
  SIDE_PANEL_MIN_WIDTH_PX,
} from "~/components/panels/constants.ts";
import { usePanelKeyboardShortcuts } from "~/components/panels/hooks.ts";
import { LeftSidebar } from "~/components/panels/LeftSidebar";
import { ResizeHandle } from "~/components/panels/ResizeHandle";
import { RightSidebar } from "~/components/panels/RightSidebar";
import type { ZoneId } from "~/components/panels/types.ts";
import { ZoneContent } from "~/components/panels/ZoneContent";

import styles from "./DockingLayout.module.scss";

type DockingLayoutProps = {
  centerContent?: ReactNode;
};

export const DockingLayout = ({ centerContent }: DockingLayoutProps): ReactElement => {
  const isLeftVisibleBase = useAtomValue(isLeftSideVisibleAtom);
  const isRightVisibleBase = useAtomValue(isRightSideVisibleAtom);
  const isBottomVisibleBase = useAtomValue(isBottomVisibleAtom);
  const zoneSizes = useAtomValue(zoneSizesAtom);
  const setZoneSizes = useSetAtom(zoneSizesAtom);
  const zoneAssignments = useAtomValue(zoneAssignmentsAtom);
  const [expandedPanelId, setExpandedPanelId] = useAtom(expandedPanelIdAtom);

  // In expand mode, only the zone containing the expanded panel is visible.
  // The only panel that ever expands is "files" (top-left), so expand mode
  // shows the left side and hides everything else.
  const expandedZone = expandedPanelId ? (zoneAssignments[expandedPanelId] as ZoneId | undefined) : undefined;
  const isExpanded = expandedPanelId != null;

  const isLeftVisible = isExpanded ? expandedZone === "top-left" : isLeftVisibleBase;
  const isRightVisible = isExpanded ? false : isRightVisibleBase;
  const isBottomVisible = isExpanded ? false : isBottomVisibleBase;

  usePanelKeyboardShortcuts();

  // Escape key exits expand mode (only when no dialog is open)
  useEffect((): (() => void) | void => {
    if (!isExpanded) return;
    const handleKeyDown = (e: KeyboardEvent): void => {
      if (e.key !== "Escape") return;
      // Don't exit expand mode if a Radix dialog is open
      if (document.querySelector("[data-radix-dialog-overlay]")) return;
      e.stopPropagation();
      setExpandedPanelId(null);
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isExpanded, setExpandedPanelId]);

  // Track the PanelGroup's size so we can (a) detect when the window can't
  // fit both sides alongside the center at their minimum widths, and
  // (b) seed sensible percentage-derived defaults on first launch.
  const panelGroupRef = useRef<HTMLDivElement>(null);
  const [panelGroupSize, setPanelGroupSize] = useState({ width: 0, height: 0 });
  const { width: panelGroupWidth, height: panelGroupHeight } = panelGroupSize;

  useLayoutEffect(() => {
    const el = panelGroupRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (rect.width > 0 || rect.height > 0) {
      setPanelGroupSize({ width: rect.width, height: rect.height });
    }
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      setPanelGroupSize({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    observer.observe(el);
    return (): void => observer.disconnect();
  }, []);

  // Freeze the first non-zero measurement so percentage-derived defaults are
  // stable even if the user later resizes the window. We do NOT write these
  // defaults to zoneSizesAtom — that caused downstream re-renders that
  // destabilised other tests (e.g. clipboard/toast flows). The atom only
  // holds values the user has explicitly dragged to.
  const [initialGroupSize, setInitialGroupSize] = useState<{ width: number; height: number } | null>(null);
  useLayoutEffect(() => {
    if (initialGroupSize !== null) return;
    if (panelGroupWidth <= 0 || panelGroupHeight <= 0) return;
    setInitialGroupSize({ width: panelGroupWidth, height: panelGroupHeight });
  }, [panelGroupWidth, panelGroupHeight, initialGroupSize]);

  // ── Zone sizes (pixels) ──────────────────────────────────────────────
  // Every persisted zone size is a pixel value. The layout keeps side panels
  // at their stored widths and collapses them (right first, then left) when
  // the window is too narrow to fit them alongside the center panel's
  // minimum — rather than squishing them below a usable size.
  const defaultSideWidthPx = initialGroupSize ? Math.round(initialGroupSize.width * 0.2) : DEFAULT_SIDE_PANEL_WIDTH_PX;
  const defaultBottomHeightPx = initialGroupSize
    ? Math.round(initialGroupSize.height * 0.3)
    : DEFAULT_BOTTOM_PANEL_HEIGHT_PX;
  const topLeftPx = zoneSizes["top-left"] ?? defaultSideWidthPx;
  const topRightPx = zoneSizes["top-right"] ?? defaultSideWidthPx;
  const bottomPx = zoneSizes["bottom"] ?? defaultBottomHeightPx;

  // When the window can't fit the minimum layout, hide zones — right side
  // first, then left. This is a one-way change (not restored when the
  // window grows back); the user reopens via the sidebar icons.
  const setZoneVisibility = useSetAtom(zoneVisibilityAtom);
  useEffect(() => {
    if (panelGroupWidth <= 0) return;
    if (isExpanded) return;
    const leftMin = isLeftVisible ? SIDE_PANEL_MIN_WIDTH_PX : 0;
    const rightMin = isRightVisible ? SIDE_PANEL_MIN_WIDTH_PX : 0;
    if (leftMin + CENTER_PANEL_MIN_WIDTH_PX + rightMin <= panelGroupWidth) return;
    if (isRightVisible) {
      setZoneVisibility((v) => ({ ...v, "top-right": false }));
      return;
    }

    if (isLeftVisible) {
      setZoneVisibility((v) => ({ ...v, "top-left": false }));
    }
  }, [panelGroupWidth, isLeftVisible, isRightVisible, isExpanded, setZoneVisibility]);

  // Refs keep the latest values accessible from within the resize-handle
  // callbacks without re-creating them on every pixel of drag.
  const sizesRef = useRef(zoneSizes);
  sizesRef.current = zoneSizes;
  const defaultSideWidthRef = useRef(defaultSideWidthPx);
  defaultSideWidthRef.current = defaultSideWidthPx;
  const defaultBottomHeightRef = useRef(defaultBottomHeightPx);
  defaultBottomHeightRef.current = defaultBottomHeightPx;

  const readSize = useCallback((key: ZoneId, fallback: number): number => sizesRef.current[key] ?? fallback, []);

  const writeSize = useCallback(
    (key: ZoneId, nextPx: number, minPx: number): void => {
      const clamped = Math.max(minPx, Math.round(nextPx));
      setZoneSizes((prev) => (prev[key] === clamped ? prev : { ...prev, [key]: clamped }));
    },
    [setZoneSizes],
  );

  const getTopLeft = useCallback(() => readSize("top-left", defaultSideWidthRef.current), [readSize]);
  const setTopLeft = useCallback((px: number) => writeSize("top-left", px, SIDE_PANEL_MIN_WIDTH_PX), [writeSize]);

  const getTopRight = useCallback(() => readSize("top-right", defaultSideWidthRef.current), [readSize]);
  const setTopRight = useCallback((px: number) => writeSize("top-right", px, SIDE_PANEL_MIN_WIDTH_PX), [writeSize]);

  const getBottom = useCallback(() => readSize("bottom", defaultBottomHeightRef.current), [readSize]);
  const setBottom = useCallback((px: number) => writeSize("bottom", px, PANEL_MIN_PX), [writeSize]);

  return (
    <div className={styles.container}>
      {!isExpanded && <LeftSidebar />}

      <div ref={panelGroupRef} className={styles.panelGroup}>
        <div className={styles.outerVertical}>
          <div className={styles.topRow}>
            {isLeftVisible && (
              <>
                <div className={styles.sidePanel} style={{ width: topLeftPx, minWidth: SIDE_PANEL_MIN_WIDTH_PX }}>
                  <div className={styles.innerTop}>
                    <ZoneContent zoneId="top-left" />
                  </div>
                </div>
                <ResizeHandle axis="x" getSize={getTopLeft} onResize={setTopLeft} ariaLabel="Resize left panel" />
              </>
            )}

            <div className={styles.centerPanel}>
              <div className={styles.centerWrapper}>
                <div className={styles.centerInner}>
                  {centerContent ?? <div className={styles.centerContent}>Center Content</div>}
                </div>
              </div>
            </div>

            {isRightVisible && (
              <>
                <ResizeHandle
                  axis="x"
                  getSize={getTopRight}
                  onResize={setTopRight}
                  direction={-1}
                  ariaLabel="Resize right panel"
                />
                <div
                  className={styles.sidePanel}
                  style={{ width: topRightPx, minWidth: SIDE_PANEL_MIN_WIDTH_PX }}
                  data-testid={ElementIds.PANEL_RIGHT_AREA}
                >
                  <div className={styles.innerTop} data-testid={ElementIds.PANEL_TOP_RIGHT}>
                    <ZoneContent zoneId="top-right" />
                  </div>
                </div>
              </>
            )}
          </div>

          {isBottomVisible && (
            <>
              <ResizeHandle
                axis="y"
                getSize={getBottom}
                onResize={setBottom}
                direction={-1}
                ariaLabel="Resize bottom panel"
              />
              <div className={styles.bottomPanel} style={{ height: bottomPx }}>
                <ZoneContent zoneId="bottom" />
              </div>
            </>
          )}
        </div>
      </div>

      {!isExpanded && <RightSidebar />}
    </div>
  );
};
