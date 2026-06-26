import sqlalchemy as sa

from sculptor.database.alembic.migration_test_utils import MigrationTestFixture

EXPECTED_TABLES = {
    "project",
    "task",
    "workspace",
    "user_settings",
    "notification",
    "saved_agent_message",
}


class TestInitialMigration(MigrationTestFixture):
    """Test fixture for the squashed initial migration that creates all tables."""

    @property
    def revision(self) -> str:
        return "c8985360b2ca"

    @property
    def down_revision(self) -> None:
        return None

    def verify(self, connection: sa.engine.Connection) -> None:
        result = connection.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = {row[0] for row in result}
        for expected in EXPECTED_TABLES:
            assert expected in tables, f"Expected table '{expected}' not found"
