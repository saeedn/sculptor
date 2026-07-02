// Browser-harness Vite build. Sculptor is a desktop-only application; this
// build exists solely for the browser-mode integration tests, which run the
// frontend in headless Chromium served statically by the backend (see
// `just test-integration`). Only the web-specific knobs live here — the
// dev/prod branch, proxy, env loading, and shared plugin pipeline come from
// `defineFrontendConfig` in vite.base.config.ts. Web specifics: a build-start
// hook that regenerates the API types.
import { execSync } from "node:child_process";

import { defineFrontendConfig } from "./vite.base.config.ts";

/* eslint-disable-next-line import/no-default-export */
export default defineFrontendConfig({
  root: __dirname,
  defaultFrontendPort: 5174,
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
