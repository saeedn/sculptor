import type { Editor as TipTapEditor } from "@tiptap/react";
import { describe, expect, it } from "vitest";

import { parsePseudoSkillCommand } from "./pseudoSkills";

type FakeMentionNode = {
  type: { name: "mention" };
  attrs: { id: string; mentionSuggestionChar: string };
};
type FakeTextNode = { type: { name: "text" }; text: string };
type FakeChild = FakeMentionNode | FakeTextNode;

function fakeEditor(children: Array<FakeChild>): TipTapEditor {
  const paragraph = {
    childCount: children.length,
    child: (index: number): FakeChild => children[index],
  };
  const doc = {
    childCount: children.length === 0 ? 0 : 1,
    child: (_: number): typeof paragraph => paragraph,
  };
  return { state: { doc } } as unknown as TipTapEditor;
}

const emptyEditor = (): TipTapEditor => fakeEditor([]);

describe("parsePseudoSkillCommand", () => {
  describe("plain-text argless commands", () => {
    it("matches /clear exactly", () => {
      expect(parsePseudoSkillCommand(emptyEditor(), "/clear")).toEqual({ name: "clear", args: "" });
    });

    it("trims surrounding whitespace on /clear", () => {
      expect(parsePseudoSkillCommand(emptyEditor(), "   /clear   ")).toEqual({ name: "clear", args: "" });
    });

    it("matches /copy exactly", () => {
      expect(parsePseudoSkillCommand(emptyEditor(), "/copy")).toEqual({ name: "copy", args: "" });
    });

    it("rejects /clear followed by extra text", () => {
      expect(parsePseudoSkillCommand(emptyEditor(), "/clear the cache")).toBeNull();
    });

    it("rejects commands not at the start", () => {
      expect(parsePseudoSkillCommand(emptyEditor(), "please /clear")).toBeNull();
    });

    it("returns null for regular text", () => {
      expect(parsePseudoSkillCommand(emptyEditor(), "hello world")).toBeNull();
    });

    it("returns null for empty input", () => {
      expect(parsePseudoSkillCommand(emptyEditor(), "")).toBeNull();
    });
  });

  describe("TipTap mention-node path", () => {
    it("accepts argless /clear with the trailing space TipTap autocomplete inserts", () => {
      // Selecting `/clear` from the slash-menu autocomplete adds a trailing
      // space after the mention node.
      const editor = fakeEditor([
        { type: { name: "mention" }, attrs: { id: "/clear", mentionSuggestionChar: "/" } },
        { type: { name: "text" }, text: " " },
      ]);
      expect(parsePseudoSkillCommand(editor, "/clear ")).toEqual({ name: "clear", args: "" });
    });

    it("falls through to plain-text when argless /clear has extra non-whitespace trailing", () => {
      // Mixed input like "/clear the cache" should be sent as a regular
      // message — the mention-only path can't claim it, and the plain-text
      // path has no exact match for argless skills.
      const editor = fakeEditor([
        { type: { name: "mention" }, attrs: { id: "/clear", mentionSuggestionChar: "/" } },
        { type: { name: "text" }, text: " the cache" },
      ]);
      expect(parsePseudoSkillCommand(editor, "/clear the cache")).toBeNull();
    });

    it("matches bare /copy mention", () => {
      const editor = fakeEditor([{ type: { name: "mention" }, attrs: { id: "/copy", mentionSuggestionChar: "/" } }]);
      expect(parsePseudoSkillCommand(editor, "")).toEqual({ name: "copy", args: "" });
    });

    it("returns null for an unknown mention", () => {
      const editor = fakeEditor([{ type: { name: "mention" }, attrs: { id: "/unknown", mentionSuggestionChar: "/" } }]);
      expect(parsePseudoSkillCommand(editor, "")).toBeNull();
    });

    it("falls through to plain-text when first child is not a mention", () => {
      const editor = fakeEditor([{ type: { name: "text" }, text: "hello" }]);
      expect(parsePseudoSkillCommand(editor, "hello")).toBeNull();
    });
  });

  describe("case sensitivity", () => {
    it("rejects mixed-case /Clear", () => {
      expect(parsePseudoSkillCommand(emptyEditor(), "/Clear")).toBeNull();
    });
  });
});
