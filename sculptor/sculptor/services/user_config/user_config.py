import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import tomlkit
from loguru import logger
from pydantic import ValidationError

from sculptor.config.user_config import UserConfig
from sculptor.utils.build import get_internal_folder


class InvalidConfigError(Exception):
    """Exception raised when the configuration is invalid."""

    def __init__(self, error: Exception) -> None:
        """Wrap the underlying error in a user-facing config-load message."""
        self.message = f"Unhandled error loading your config file:\n{error}"
        super().__init__(self.message)


_CONFIG_INSTANCE: UserConfig | None = None


def get_user_config_instance() -> UserConfig:
    """Get the global config instance if one exists."""
    return _CONFIG_INSTANCE or get_default_user_config_instance()


def get_user_config_instance_if_set() -> UserConfig | None:
    """Return the loaded config instance, or None if none has been set.

    Unlike ``get_user_config_instance`` (which falls back to a default
    placeholder), this distinguishes "no real config yet" — onboarding, or
    tests that never set one — so callers can avoid persisting derived state
    (e.g. the most-recently-used harness) onto a throwaway default config.
    """
    return _CONFIG_INSTANCE


def set_user_config_instance(config: UserConfig | None) -> None:
    """Set the global config instance."""
    logger.debug("Setting global user config instance (is_set={})", config is not None)
    global _CONFIG_INSTANCE
    _CONFIG_INSTANCE = config


def _generate_default_config_path() -> Path:
    return get_internal_folder() / "config.toml"


_CONFIG_PATH = _generate_default_config_path()


def get_config_path() -> Path:
    """Get the path to the config file."""
    return _CONFIG_PATH


def load_config(config_path: Path) -> UserConfig:
    """Load and validate a UserConfig from the given TOML file."""
    assert config_path.exists(), f"Config file does not exist at {config_path}"

    try:
        with open(config_path, "rb") as f:
            config_data = tomllib.load(f)

            config_dict = dict(config_data)

            config = UserConfig(**config_dict)
            return config
    except ValidationError as e:
        raise InvalidConfigError(e) from e


def _sanitize_for_toml(data: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively convert None values to empty strings for TOML compatibility.

    model_dump(exclude_none=True) only excludes top-level None fields,
    not None values inside dict-typed fields. TOML cannot represent None,
    so we convert them to empty strings to preserve the "explicitly cleared" state.
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            result[key] = ""
        elif isinstance(value, dict):
            # pyrefly: ignore [unsupported-operation]
            result[key] = _sanitize_for_toml(value)
        else:
            result[key] = value
    return result


def save_config(config: UserConfig, config_path: Path) -> None:
    """Writes the given config out to disk.

    Beware: Does not update the local configuration instance!"""
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # atomically write the config file
    with open(config_path.with_suffix(".tmp"), "w") as f:
        tomlkit.dump(_sanitize_for_toml(config.model_dump(exclude_none=True)), f)
    config_path.with_suffix(".tmp").rename(config_path)


def _generate_default_user_config_instance() -> UserConfig:
    """Generates a default user config instance."""
    return UserConfig()


_DEFAULT_CONFIG_INSTANCE: UserConfig = _generate_default_user_config_instance()


def get_default_user_config_instance() -> UserConfig:
    """Return the process-wide default (anonymized) user config instance."""
    return _DEFAULT_CONFIG_INSTANCE


def initialize_from_file() -> bool:
    """Initializes the global singleton UserConfig instance from the default file location.

    Returns:
        True if we were able to successfully load from that file.
        If False, it indicates that onboarding is required due to a missing or corrupted file
    """
    config_path = get_config_path()
    if config_path.exists():
        try:
            config = load_config(config_path)
            set_user_config_instance(config)
            return True
        except (ValidationError, InvalidConfigError) as e:
            logger.info("Failed to load config, will require onboarding: {}", e)
            return False
    else:
        logger.info("No config file found at {}, will require onboarding", config_path)
        return False
