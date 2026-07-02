// Web (and OpenHost) Vite build. Only the web-specific knobs live here — the
// dev/prod branch, proxy, env loading, and shared plugin pipeline come from
// `defineFrontendConfig` in vite.base.config.ts. Web specifics: a same-origin
// API_URL_BASE and a build-start hook that regenerates the API types.
import { execSync } from "node:child_process";

import { defineFrontendConfig } from "./vite.base.config.ts";

/* eslint-disable-next-line import/no-default-export */
export default defineFrontendConfig({
  root: __dirname,
  defaultFrontendPort: 5174,
  apiUrlBase: (env): string => JSON.stringify(env.SCULPTOR_API_BASE_URL || ""),
  extraPlugins: [
    {
      name: "generate-types",
      buildStart(): void {
        console.log("Generating dynamic types...");
        execSync("npm run generate-api", { stdio: "inherit" });
      },
    },
  ],
});
