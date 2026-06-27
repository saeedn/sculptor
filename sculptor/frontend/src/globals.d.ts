import type { Terminal as XTerm } from "@xterm/xterm";

import type { SculptorElectronAPI } from "./shared/types.ts";

declare global {
  // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
  interface Window {
    sculptor?: SculptorElectronAPI;
    /** The most-recently-focused terminal's xterm, for integration tests.
     * Both the agent terminal and the workspace bottom terminal can be mounted
     * at once, so this tracks whichever the user last interacted with. Prefer
     * the unambiguous per-surface handles below when the test targets one. */
    __xterm?: XTerm;
    /** The agent terminal panel's xterm (terminal-agent PTY), for tests. */
    __terminal_agent_xterm?: XTerm;
    /** The workspace bottom terminal panel's xterm, for tests. */
    __terminal_panel_xterm?: XTerm;
    /** Inlined by the backend's static-HTML serve path when --trace-to is set.
     * The renderer reads this synchronously at boot in common/tracing.ts. */
    __SCULPTOR_TRACING__?: { enabled: boolean };
  }

  declare const API_URL_BASE: string | undefined;
}
