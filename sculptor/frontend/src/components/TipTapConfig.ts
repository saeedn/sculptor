import { wrappingInputRule } from "@tiptap/core";
import BulletList from "@tiptap/extension-bullet-list";
import Paragraph from "@tiptap/extension-paragraph";
import Placeholder from "@tiptap/extension-placeholder";
import { Markdown } from "@tiptap/markdown";
import { Extension } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { common, createLowlight } from "lowlight";
import { Marked, type marked as MarkedInstance, type Tokens } from "marked";

import { CustomCodeBlockLowlight } from "./CodeBlockExtension";
import styles from "./Editor.module.scss";

/**
 * The default Paragraph extension serializes empty paragraphs as the HTML entity
 * string "&nbsp;". The marked tokenizer misparses this inside list items, causing
 * the literal text "&nbsp;" to appear after a round-trip.
 *
 * We serialize empty paragraphs as a zero-width space (\u200B) instead. Unlike
 * \u00A0 (NBSP), \u200B does not match /^\s/, so the ordered list tokenizer's
 * INDENTED_LINE_REGEX won't treat it as indented continuation content — which
 * previously caused text after a list to be swallowed. And unlike an empty string,
 * \u200B is real content, so the paragraph survives a round-trip through the
 * markdown parser without collapsing.
 */
const CustomParagraph = Paragraph.extend({
  renderMarkdown: (node, h) => {
    if (!node) {
      return "";
    }
    const content = Array.isArray(node.content) ? node.content : [];
    if (content.length === 0) {
      return "\u200B";
    }
    return h.renderChildren(content);
  },
});

/**
 * Drop `+` from the bullet-list input rule. The default rule wraps the line
 * in a list when the user types `*`, `-`, or `+` followed by a space \u2014 but
 * `+` is also the trigger for our mention prefilter popover, so users who
 * pick a `+` mention and then type a space would unintentionally start a
 * list. `*` and `-` are still honored.
 */
const CustomBulletList = BulletList.extend({
  addInputRules() {
    return [
      wrappingInputRule({
        find: /^\s*([-*])\s$/,
        type: this.type,
      }),
    ];
  },
});

/**
 * Regex that matches a complete `<span data-sculptor-node>…</span>` element,
 * including any additional data-* attributes (e.g. `data-skill-description`,
 * `data-skill-type`) that carry skill chip metadata.  These spans are emitted
 * by the Mention extension's `renderMarkdown` when serialising mentions to
 * the draft string stored in localStorage.  We need to allow them through
 * marked so the MarkdownManager's `parseHTMLToken` path can convert them
 * back into Mention nodes via the `parseHTML` rule added below.
 */
const SCULPTOR_NODE_SPAN_RE = /^<span\s+data-sculptor-node(?:\s+[^>]*)?>([\s\S]*?)<\/span>/;

/**
 * Custom marked instance that does not treat angle-bracket text (e.g.
 * `<skill-name>`, `<Component />`) as HTML.  Without this, marked's
 * tokenizer interprets any `<word>` as an HTML tag and the
 * MarkdownManager's parseHTMLToken silently drops it.
 *
 * Returning `undefined` tells marked "no match" so the text falls through
 * to the `inlineText` rule and is preserved verbatim.
 *
 * Exception: `<span data-sculptor-node>` tags produced by the Mention
 * extension's `renderMarkdown` are explicitly allowed through so that
 * draft @-mentions survive the round-trip through localStorage.
 */
const sculptorMarked = new Marked({
  tokenizer: {
    html(_src: string): Tokens.HTML | undefined {
      return undefined;
    },
    tag(src: string): Tokens.Tag | undefined {
      // Allow sculptor mention spans through so they reach parseHTMLToken.
      const match = SCULPTOR_NODE_SPAN_RE.exec(src);
      if (match) {
        return {
          type: "html",
          raw: match[0],
          inLink: false,
          inRawBlock: false,
          text: match[0],
          block: false,
        };
      }
      return undefined;
    },
  },
});

const lowlight = createLowlight(common);

type TipTapConfigOptions = {
  placeholder?: string;
  editable?: boolean;
};

/**
 * Creates the shared TipTap extensions configuration used by the Editor.
 */
export const createTipTapExtensions = ({ placeholder, editable = true }: TipTapConfigOptions): Array<Extension> => {
  const extensions = [
    StarterKit.configure({
      codeBlock: false,
      link: false,
      paragraph: false,
      bulletList: false,
    }),
    CustomParagraph as Extension<unknown, unknown>,
    CustomBulletList as Extension<unknown, unknown>,
    // `indentation.size: 4` overrides @tiptap/markdown's 2-space default so
    // nested list items in the output of `getMarkdown()` are indented far
    // enough to nest under any list marker, including double-digit ordered
    // markers like `10. `. CommonMark — and therefore remark-gfm, which
    // renders chat messages downstream — only treats content as nested under
    // a `1. ` item when it's indented to column ≥ 3; the previous 2-space
    // default collapsed nested ordered lists into a single flat list once
    // the message was sent and re-rendered.
    Markdown.configure({
      marked: sculptorMarked as unknown as typeof MarkedInstance,
      indentation: { style: "space", size: 4 },
    }),
    CustomCodeBlockLowlight.configure({ lowlight }) as Extension<unknown, unknown>,
    Extension.create({
      name: "PreventEnter",
      addKeyboardShortcuts() {
        return {
          "Mod-Enter": (): boolean => true, // Return true and do nothing else
        };
      },
    }),
  ];

  // Only add placeholder for editable mode
  if (editable && placeholder) {
    extensions.push(
      Placeholder.configure({
        // Only show the placeholder when the entire editor is empty — not on
        // individual empty paragraphs within multi-paragraph content.  Without
        // this, pressing Enter at the start of text creates an empty first
        // paragraph that incorrectly displays the placeholder.
        placeholder: ({ editor }) => (editor.isEmpty ? placeholder : ""),
        emptyNodeClass: styles.placeholder,
        showOnlyCurrent: false,
      }),
    );
  }

  return extensions;
};
