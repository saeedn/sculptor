from pathlib import Path

import sculptor.services.user_config.user_config as user_config_module
from sculptor.config.user_config import UserConfig
from sculptor.services.user_config.user_config import save_config


def test_initialize_from_file_round_trips_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(user_config_module, "_CONFIG_PATH", tmp_path / "config.toml")
    config = UserConfig(instance_id="instance_123", env_var_override_enabled=True)
    save_config(config, user_config_module.get_config_path())

    try:
        assert user_config_module.initialize_from_file() is True

        loaded = user_config_module.get_user_config_instance()
        assert loaded is not None
        assert loaded.instance_id == "instance_123"
        assert loaded.env_var_override_enabled is True
    finally:
        user_config_module.set_user_config_instance(None)
