from sculptor.config.user_config import BabysitterAgentMRU
from sculptor.config.user_config import BabysitterAgentRegistered
from sculptor.config.user_config import CIBabysitterConfig
from sculptor.config.user_config import UserConfig
from sculptor.config.user_config import UserConfigField


def test_ci_babysitter_defaults() -> None:
    config = UserConfig(
        user_email="test@example.com",
        user_id="user123",
        organization_id="org123",
        instance_id="inst123",
    )
    assert isinstance(config.ci_babysitter, CIBabysitterConfig)
    assert config.ci_babysitter.enabled is False
    assert config.ci_babysitter.retry_cap == 3
    assert config.ci_babysitter.pipeline_failed_prompt.startswith("Investigate the failing pipeline")
    assert config.ci_babysitter.merge_conflict_prompt.startswith("This MR has a merge conflict")
    assert UserConfigField["CI_BABYSITTER"].value == "ciBabysitter"


def test_ci_babysitter_agent_defaults_to_mru() -> None:
    # A fresh config selects the MRU variant.
    config = CIBabysitterConfig()
    assert isinstance(config.agent, BabysitterAgentMRU)


def test_ci_babysitter_config_without_agent_key_is_mru() -> None:
    # Backwards compatibility: configs persisted before this field existed
    # deserialize to the MRU default.
    config = CIBabysitterConfig.model_validate({"enabled": True, "retryCap": 5})
    assert config.enabled is True
    assert config.retry_cap == 5
    assert isinstance(config.agent, BabysitterAgentMRU)


def test_ci_babysitter_agent_variants_round_trip() -> None:
    for variant in (
        BabysitterAgentMRU(),
        BabysitterAgentRegistered(registration_id="claude-code"),
    ):
        config = CIBabysitterConfig(agent=variant)
        restored = CIBabysitterConfig.model_validate(config.model_dump())
        assert type(restored.agent) is type(variant)
        assert restored.agent == variant


def test_ci_babysitter_registered_agent_keeps_registration_id() -> None:
    config = CIBabysitterConfig(agent=BabysitterAgentRegistered(registration_id="my-tui"))
    restored = CIBabysitterConfig.model_validate(config.model_dump())
    assert isinstance(restored.agent, BabysitterAgentRegistered)
    assert restored.agent.registration_id == "my-tui"


def test_ci_babysitter_agent_camel_case_alias_round_trips() -> None:
    config = CIBabysitterConfig(agent=BabysitterAgentRegistered(registration_id="my-tui"))
    dumped = config.model_dump(by_alias=True)
    restored = CIBabysitterConfig.model_validate(dumped)
    assert isinstance(restored.agent, BabysitterAgentRegistered)
    assert restored.agent.registration_id == "my-tui"


def test_user_config_silently_ignores_removed_chat_view_legacy_field() -> None:
    """Regression for the delete-classic-chat removal.

    `chat_view_legacy` was a `UserConfig` field that's been deleted. Older
    clients (and stale on-disk configs) may still send / contain a
    `chatViewLegacy: true` value; the validation must accept the payload
    silently rather than raising. `SerializableModel` validates with
    `extra="allow"` and clears `__pydantic_extra__` in `model_post_init`,
    so the value is dropped on the next persistence write.
    """
    config = UserConfig.model_validate(
        {
            "userEmail": "test@example.com",
            "userId": "user123",
            "organizationId": "org123",
            "instanceId": "inst123",
            "chatViewLegacy": True,
        }
    )
    assert not hasattr(config, "chat_view_legacy")
