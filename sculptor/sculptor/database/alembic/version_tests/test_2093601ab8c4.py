import sqlalchemy as sa

from sculptor.database.alembic.migration_test_utils import MigrationTestFixture


class TestMigration2093601ab8c4(MigrationTestFixture):
    """Test fixture for migration 2093601ab8c4 (drop workspace.initialization_strategy).

    Seeds a workspace row carrying the soon-to-be-dropped column, then verifies the
    row survives the migration and the column is gone.
    """

    @property
    def revision(self) -> str:
        return "2093601ab8c4"

    @property
    def down_revision(self) -> str:
        return "154dd95dbcca"

    def seed(self, connection: sa.engine.Connection) -> None:
        connection.execute(
            sa.text(
                """
                INSERT INTO workspace (
                    created_at, object_id, project_id, organization_reference,
                    description, initialization_strategy, is_deleted, is_open,
                    setup_status, setup_log_truncated, diff_status
                ) VALUES (
                    '2026-01-01 00:00:00', 'workspace-1', 'project-1', 'org-1',
                    'a workspace', 'WORKTREE', 0, 1, 'pending', 0, 'clean'
                )
                """
            )
        )

    def verify(self, connection: sa.engine.Connection) -> None:
        columns = {row[1] for row in connection.execute(sa.text("PRAGMA table_info(workspace)"))}
        assert "initialization_strategy" not in columns, "initialization_strategy column should be dropped"
        result = connection.execute(
            sa.text("SELECT object_id, setup_status FROM workspace WHERE object_id = 'workspace-1'")
        ).one()
        assert result[0] == "workspace-1"
        assert result[1] == "pending"
