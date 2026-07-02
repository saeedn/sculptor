import { atom } from "jotai";

export type ChatActions = {
  appendText: ((text: string) => void) | null;
  sendMessage: ((message: string) => Promise<void>) | null;
  isDisabled: boolean;
};

export const chatActionsAtom = atom<ChatActions>({
  appendText: null,
  sendMessage: null,
  isDisabled: true,
});
