from pathlib import Path

import sculptor


def get_plugins_base_dir() -> Path:
    """The directory containing the bundled plugin directories.

    Resolves to `<repo>/sculptor/` when running from source and to the
    PyInstaller `_internal/` directory in the packaged app. Also exported to
    terminal agents as the `SCULPT_PLUGINS_DIR` env var so registration
    launch commands can reference the bundled plugins without baking in
    per-machine paths (which would rot on app updates and AppImage mounts).
    """
    return Path(sculptor.__file__).parent.parent
