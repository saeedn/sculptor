import type { PrimitiveAtom } from "jotai";
import { atom } from "jotai";
import { atomFamily } from "jotai/utils";

export const debugViewAtomFamily = atomFamily<string, PrimitiveAtom<boolean>>(() => atom<boolean>(false));
