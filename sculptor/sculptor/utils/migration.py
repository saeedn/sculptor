from sculptor.utils import build as build_utils


def ensure_sculptor_folder_ready() -> None:
    """Ensure the Sculptor data folder has the expected structure.

    Idempotent: creates the data folder and its ``internal``/``workspaces``
    subdirectories if they are missing, and is a no-op once they exist.
    """
    sculptor_path = build_utils.get_sculptor_folder()
    (sculptor_path / "internal").mkdir(parents=True, exist_ok=True)
    (sculptor_path / "workspaces").mkdir(parents=True, exist_ok=True)
