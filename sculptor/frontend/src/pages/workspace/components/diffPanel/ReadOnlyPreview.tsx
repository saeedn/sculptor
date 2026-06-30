import type { FileOptions, SupportedLanguages } from "@pierre/diffs";
import { File as PierreFile } from "@pierre/diffs/react";
import { Flex, Text } from "@radix-ui/themes";
import { useAtomValue } from "jotai";
import type { ReactElement } from "react";
import { useLayoutEffect, useMemo, useRef } from "react";

import { ElementIds } from "~/api";
import { themeCodeThemeAtom } from "~/common/state/atoms/theme.ts";
import { appThemeAtom, fileBrowserLineWrappingAtom } from "~/common/state/atoms/userConfig.ts";
import { useWorkspaceFileContent } from "~/common/state/hooks/useWorkspaceFileContent.ts";
import { getShikiThemes } from "~/common/theme/shikiThemes.ts";

import styles from "./ReadOnlyPreview.module.scss";
import { StickyHorizontalScrollbar } from "./StickyHorizontalScrollbar.tsx";

/**
 * Override Pierre's shadow DOM background and hide the native horizontal
 * scrollbar (replaced by StickyHorizontalScrollbar at the panel bottom).
 */
const bgOverrideSheet = new CSSStyleSheet();
bgOverrideSheet.replaceSync(
  [
    "[data-diffs], [data-diffs-header], [data-error-wrapper] {",
    "  --diffs-light-bg: var(--color-panel-solid) !important;",
    "  --diffs-dark-bg: var(--color-background) !important;",
    "  --diffs-bg: light-dark(var(--color-panel-solid), var(--color-background)) !important;",
    "}",
    // Hide Pierre's native horizontal scrollbar — replaced by StickyHorizontalScrollbar.
    "[data-code] { scrollbar-width: none; }",
    "[data-code]::-webkit-scrollbar { display: none; }",
  ].join("\n"),
);

const EXTENSION_LANGUAGE_MAP: Record<string, SupportedLanguages> = {
  ts: "typescript",
  tsx: "tsx",
  js: "javascript",
  jsx: "jsx",
  py: "python",
  rb: "ruby",
  rs: "rust",
  go: "go",
  java: "java",
  c: "c",
  cpp: "cpp",
  h: "c",
  hpp: "cpp",
  cs: "csharp",
  swift: "swift",
  kt: "kotlin",
  scala: "scala",
  sh: "bash",
  bash: "bash",
  zsh: "bash",
  json: "json",
  yaml: "yaml",
  yml: "yaml",
  toml: "toml",
  xml: "xml",
  html: "html",
  css: "css",
  scss: "scss",
  less: "less",
  md: "markdown",
  sql: "sql",
  graphql: "graphql",
  dockerfile: "dockerfile",
  makefile: "makefile",
  lua: "lua",
  php: "php",
  r: "r",
  dart: "dart",
  vue: "vue",
  svelte: "svelte",
};

const getLanguageFromPath = (filePath: string): SupportedLanguages | undefined => {
  const ext = filePath.split(".").pop()?.toLowerCase();
  if (!ext) return undefined;
  return EXTENSION_LANGUAGE_MAP[ext];
};

type ReadOnlyPreviewProps = {
  workspaceId: string;
  filePath: string;
};

export const ReadOnlyPreview = ({ workspaceId, filePath }: ReadOnlyPreviewProps): ReactElement => {
  const { data: content, isPending, isError: hasError } = useWorkspaceFileContent(workspaceId, filePath, null);
  const overflow = useAtomValue(fileBrowserLineWrappingAtom);
  const appTheme = useAtomValue(appThemeAtom);
  const codeTheme = useAtomValue(themeCodeThemeAtom);
  const shikiThemes = getShikiThemes(codeTheme);
  const pierreRef = useRef<HTMLDivElement>(null);

  /**
   * Inject our override stylesheet into Pierre's shadow DOM.
   *
   * `useLayoutEffect` so the sheet is adopted between React's commit and the
   * browser's next paint — without this, Pierre's first paint shows the
   * Shiki theme background (passed inline on the `<pre>`) until our override
   * lands, which flashes in dark mode against the surrounding `#111`.
   * Pierre's web component upgrades synchronously on element creation, so
   * the shadow root is already attached by the time this effect runs.
   */
  const hasContent = content != null;
  useLayoutEffect(() => {
    const el = pierreRef.current;
    if (!el || !hasContent) return;
    const shadowRoot = el.querySelector("diffs-container")?.shadowRoot;
    if (!shadowRoot) return;
    if (!shadowRoot.adoptedStyleSheets.includes(bgOverrideSheet)) {
      shadowRoot.adoptedStyleSheets = [...shadowRoot.adoptedStyleSheets, bgOverrideSheet];
    }
  }, [hasContent, overflow]);

  const fileName = useMemo(() => filePath.split("/").pop() ?? filePath, [filePath]);
  const lang = useMemo(() => getLanguageFromPath(filePath), [filePath]);

  const fileOptions = useMemo(
    (): FileOptions<undefined> => ({
      overflow,
      themeType: appTheme,
      theme: shikiThemes,
      disableFileHeader: true,
    }),
    [overflow, appTheme, shikiThemes],
  );

  const fileContents = useMemo(() => {
    if (content == null) return null;
    return { name: fileName, contents: content, lang };
  }, [content, fileName, lang]);

  if (isPending) {
    return (
      <Flex align="center" justify="center" flexGrow="1">
        <Text size="2" color="gray">
          Loading file...
        </Text>
      </Flex>
    );
  }

  if (hasError || fileContents == null) {
    return (
      <Flex align="center" justify="center" flexGrow="1">
        <Text size="2" color="gray">
          Could not load file content
        </Text>
      </Flex>
    );
  }

  return (
    <div className={styles.wrapper} data-testid={ElementIds.READ_ONLY_PREVIEW}>
      <div className={styles.container}>
        <div ref={pierreRef}>
          <PierreFile file={fileContents} options={fileOptions} />
        </div>
      </div>
      {overflow === "scroll" && <StickyHorizontalScrollbar containerRef={pierreRef} />}
    </div>
  );
};
