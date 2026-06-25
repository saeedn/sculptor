"""This module contains checks that we want to run on startup in sculptor.

This allows us to detect conditions where sculptor might not safely run, and ask the user to fix this.

The design is decoupled: check execution is separate from result presentation, allowing
for flexible handling (CLI errors now, web modals in the future).
"""

import tempfile

from loguru import logger

from sculptor.utils import build as build_utils


def check_sculptor_directory_writable() -> bool:
    """Check that the Sculptor data directory is writable.

    This verifies that Sculptor can create and write files in its data directory,
    which is required for normal operation (storing state, artifacts, workspaces, etc.).

    Returns:
        True if the directory is writable, False otherwise.
    """
    sculptor_folder = build_utils.get_sculptor_folder()
    try:
        with tempfile.NamedTemporaryFile(dir=sculptor_folder, delete=True) as tmp:
            tmp.write(b"test")
            tmp.flush()
        return True
    except OSError as e:
        logger.error(
            "Sculptor data directory is not writable: {}. Please check permissions for: {}",
            e,
            sculptor_folder,
        )
        return False
