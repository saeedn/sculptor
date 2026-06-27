from sculptor.foundation.errors import ExpectedError


class EnvironmentFailure(ExpectedError):
    """Errors related to environments."""


class EnvironmentNotFoundError(EnvironmentFailure):
    """Could not find (or start) an old environment."""


class FileOrDirectoryCouldNotBeDeletedError(EnvironmentFailure, OSError):
    """Error raised when a file or directory could not be deleted."""
