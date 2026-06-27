from pathlib import Path

from sculptor.database.core import IN_MEMORY_SQLITE

_SQLITE_URL_PREFIX = "sqlite:///"


def maybe_get_db_path(database_url: str) -> Path | None:
    """Return the on-disk path for a file-backed sqlite URL, or None for in-memory URLs."""
    if (
        not database_url.startswith(_SQLITE_URL_PREFIX)
        or database_url == IN_MEMORY_SQLITE
        or "mode=memory" in database_url
    ):
        return None
    path_without_prefix = database_url.removeprefix(_SQLITE_URL_PREFIX)
    path_without_options = path_without_prefix.split("?", 1)[0]
    return Path(path_without_options)
