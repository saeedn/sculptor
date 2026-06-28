import pytest

from sculptor.version import pep_440_to_semver


@pytest.mark.parametrize(
    ["our_version", "expected"],
    [
        ("1.2.3", "1.2.3"),
        ("1.2.3rc1", "1.2.3-rc.1"),
        ("0.10.0.dev0", "0.10.0-dev.0"),
        ("0.10.0.dev20260303001234", "0.10.0-dev.20260303001234"),
        ("1.0.0.dev1", "1.0.0-dev.1"),
        ("1.0.0rc1.dev2", ValueError),
        ("1.2.3.post1", ValueError),
    ],
)
def test_pep_440_to_semver(our_version, expected) -> None:
    """Test that the current version can be converted to semver."""
    if isinstance(expected, str):
        assert pep_440_to_semver(our_version) == expected
    else:
        with pytest.raises(expected):
            pep_440_to_semver(our_version)
