import type { Editor as TipTapEditor } from "@tiptap/react";
import { EditorContent, useEditor } from "@tiptap/react";
import type React from "react";
import type { ReactElement } from "react";
import { useEffect, useMemo, useRef } from "react";

import { mergeClasses, optional } from "../common/Utils.ts";
import styles from "./Editor.module.scss";
import { processAndValidateFiles, saveFiles } from "./FileUploadUtils";
import { createTipTapExtensions } from "./TipTapConfig";

/**
 * CustomParagraph serializes empty paragraphs as "\u200B" (zero-width space).
 * When getMarkdown() returns only "\u200B", the editor is logically empty.
 * Normalize this to "" so it doesn't leak into React state and cause
 * round-trip issues when the editor is recreated via the markdown parser.
 */
const normalizeMarkdown = (md: string): string => (md === "\u200B" ? "" : md);

const isFileValidType = (item: DataTransferItem): boolean => {
  return item.kind === "file" && item.type.startsWith("image/");
};

const extractFilesFromClipboard = (items: DataTransferItemList): Array<File> => {
  const files: Array<File> = [];
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    if (isFileValidType(item)) {
      const file = item.getAsFile();
      if (file) {
        files.push(file);
      }
    }
  }
  return files;
};

const handlePastedFiles = async (
  files: Array<File>,
  onFilesChange: (files: Array<string>) => void,
  onError: (error: { title: string; description?: string }) => void,
): Promise<void> => {
  try {
    const { validFiles, errors } = await processAndValidateFiles(files);

    if (errors.length > 0) {
      onError({
        title: "Paste Error",
        description: errors.join("\n"),
      });
    }

    if (validFiles.length > 0) {
      const savedFilePaths = await saveFiles(validFiles);
      if (savedFilePaths.length > 0) {
        onFilesChange(savedFilePaths);
      } else {
        onError({ title: "Failed to save pasted files" });
      }
    }
  } catch (error) {
    console.error("Error processing pasted files:", error);
    onError({ title: "Failed to process pasted files" });
  }
};

type EditorProps = {
  tagName: string;
  placeholder: string;
  value: string;
  onChange: React.Dispatch<string>;
  onKeyDown?: (event: KeyboardEvent) => boolean | void;
  wrapperClassName?: string;
  // Composed onto the scroll area's class list. Lets a host that mounts
  // the Editor in a height-constrained flex column (e.g. the Notes panel)
  // opt out of the default `max-height: 500px` cap meant for the chat
  // input, where the editor grows with content.
  scrollAreaClassName?: string;
  disabled?: boolean;
  autoFocus?: boolean;
  footer?: ReactElement | undefined;
  onFilesChange?: (files: Array<string>) => void;
  onError?: (error: { title: string; description?: string }) => void;
  editorRef?: React.MutableRefObject<TipTapEditor | null>;
};

export const Editor = ({
  tagName,
  placeholder,
  value,
  onChange,
  onKeyDown,
  wrapperClassName,
  scrollAreaClassName,
  autoFocus = true,
  disabled = false,
  footer,
  onFilesChange,
  onError,
  editorRef,
}: EditorProps): ReactElement => {
  const onKeyDownRef = useRef<((event: KeyboardEvent) => boolean | void) | undefined>(onKeyDown);
  const onFilesChangeRef = useRef(onFilesChange);
  const onErrorRef = useRef(onError);
  // The editor is recreated only when `extensions` changes (see useEditor deps
  // below), so the `onUpdate` callback closes over whichever `onChange` was in
  // scope at editor creation. Route subsequent updates through a ref so a
  // parent that swaps in a new closure (e.g. one that captures other state)
  // doesn't end up calling a stale handler.
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    onKeyDownRef.current = onKeyDown;
  }, [onKeyDown]);

  useEffect(() => {
    onFilesChangeRef.current = onFilesChange;
  }, [onFilesChange]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  const extensions = useMemo(() => createTipTapExtensions({ placeholder, editable: true }), [placeholder]);

  const editor = useEditor(
    {
      extensions,
      editorProps: {
        attributes: {
          class: styles.editor,
          ["data-testid"]: tagName,
          spellcheck: "true",
        },
        handleKeyDown: (_, event) => {
          return onKeyDownRef.current?.(event) ?? false;
        },
        handlePaste: (view, event) => {
          // Only handle paste when the attach handlers are present. ChatInput
          // omits `onFilesChange` for a harness that can't accept file
          // attachments, so the paste-to-attach path is inert there. Every
          // harness that accepts attachments today (Claude and pi) also accepts
          // image input, so routing pasted images here is correct for all of
          // them. Were a future harness to accept attachments but not image
          // input, paste would still route images here while the +menu/toolbar
          // gate them — re-gate this on supportsImageInput at that point.
          if (!onFilesChangeRef.current || !onErrorRef.current) {
            return false;
          }

          const items = event.clipboardData?.items;
          if (!items) {
            return false;
          }

          const pastedFiles = extractFilesFromClipboard(items);

          if (pastedFiles.length > 0) {
            event.preventDefault();
            handlePastedFiles(pastedFiles, onFilesChangeRef.current, onErrorRef.current).catch((error) => {
              console.error("Unexpected error in handlePastedFiles:", error);
            });

            // Prevent default paste behavior
            return true;
          }

          // Let TipTap handle non-file pastes
          return false;
        },
      },
      // When value is empty, omit contentType so TipTap creates a default
      // document with an empty paragraph. The @tiptap/markdown parser produces
      // a document with zero nodes for "", which prevents the placeholder from
      // rendering until the editor gains focus.
      content: value || undefined,
      ...(value ? { contentType: "markdown" as const } : {}),
      onUpdate: ({ editor }) => {
        onChangeRef.current(normalizeMarkdown(editor.getMarkdown()));
      },
    },
    // `extensions` is memoized on the same deps that would invalidate the
    // editor, so recreating only when it changes keeps both in lockstep
    // without duplicating the dependency list.
    [extensions],
  );

  // Expose the TipTap editor instance to parent components via ref. Null the
  // ref on unmount so a parent that outlives this component doesn't keep a
  // handle to a destroyed TipTap editor.
  useEffect(() => {
    if (!editorRef) return;
    editorRef.current = editor;
    return (): void => {
      editorRef.current = null;
    };
  }, [editor, editorRef]);

  // Handle autoFocus
  useEffect(() => {
    if (autoFocus && editor) {
      editor.commands.focus("end");
    }
  }, [autoFocus, editor]);

  useEffect(() => {
    if (editor) {
      const currentMarkdown = normalizeMarkdown(editor.getMarkdown());

      // Only update if the content is different from the incoming value
      if (value !== currentMarkdown) {
        if (value) {
          editor.commands.setContent(value, { contentType: "markdown" });
        } else {
          editor.commands.clearContent();
        }
      }
    }
  }, [value, editor]);

  // Set initial editable state and update when disabled changes
  useEffect(() => {
    if (editor && editor.isEditable !== !disabled) {
      editor.setEditable(!disabled);
    }
  }, [disabled, editor]);

  return (
    <div
      className={
        wrapperClassName ? wrapperClassName : mergeClasses(optional(disabled, styles.disabled), styles.editorWrapper)
      }
    >
      <div className={mergeClasses(styles.scrollArea, scrollAreaClassName)}>
        <EditorContent editor={editor} />
      </div>
      {footer && <div className={styles.footer}>{footer}</div>}
    </div>
  );
};
