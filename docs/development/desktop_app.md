# Desktop App

Sculptor is packaged as a desktop app using [Electron Forge](https://www.electronforge.io/).

## Backend transport

The renderer is served from the custom `sculptor://app` origin, and all API
requests are same-origin relative (`/api/...`). The Electron main process
intercepts them in the `sculptor://` protocol handler and forwards them to the
local backend over Node's HTTP stack (see `registerAppProtocolHandler` in
`frontend/src/electron/main.ts`). This keeps renderer API traffic out of
Chromium's six-connections-per-host HTTP/1.1 socket pool, which concurrent
bursts of API calls used to exhaust — stalling the UI. WebSockets (the unified
state stream and terminals) are exempt from that limit and connect directly to
`ws://localhost:<backend port>`.

## Commands

```bash
just refresh    # Build prerequisite assets (required first)
just app        # Package as .app and create .dmg installer
just pkg        # Package only (no installer)
```

Skip notarization for local testing:

```bash
SKIP_NOTARIZE_AND_SIGN=1 just app
```

Start with a built-in backend (instead of connecting to an existing one):

```bash
just refresh
START_BACKEND_IN_DEV=1 just start
```

## Passing Arguments to Backend

Prefix backend arguments with `--sculptor=`:

```bash
./frontend/out/sculptor-darwin-arm64/sculptor.app/Contents/MacOS/sculptor --sculptor=--foo --sculptor=--bar
```

With `npm run electron:start`, use two `--` separators:

```bash
cd frontend
npm run electron:start -- -- --sculptor='--foo --bar'
```

## Multiple Instances

Multiple instances are prevented by default (shared database race conditions). For testing, use separate data directories:

```bash
env SCULPTOR_USER_DATA_DIR=$HOME/sculptor-data-1 SCULPTOR_FOLDER=$HOME/sculptor-1 open -n Sculptor.app
```
