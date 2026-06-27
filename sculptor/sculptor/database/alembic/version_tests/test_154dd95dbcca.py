import sqlalchemy as sa

from sculptor.database.alembic.migration_test_utils import MigrationTestFixture


class TestMigration154dd95dbcca(MigrationTestFixture):
    """Test fixture for migration 154dd95dbcca (drop task.max_seconds).

    Seeds a project + task row carrying the soon-to-be-dropped column, then verifies
    the task row survives the migration and the column is gone.
    """

    @property
    def revision(self) -> str:
        return "154dd95dbcca"

    @property
    def down_revision(self) -> str:
        return "e90178677d91"

    def seed(self, connection: sa.engine.Connection) -> None:
        connection.execute(
            sa.text(
                """
                INSERT INTO project (
                    created_at, object_id, organization_reference, name,
                    is_path_accessible, is_deleted
                ) VALUES (
                    '2026-01-01 00:00:00', 'project-1', 'org-1', 'a project', 1, 0
                )
                """
            )
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO task (
                    created_at, object_id, organization_reference, user_reference,
                    project_id, input_data, max_seconds, outcome, is_deleted, is_deleting
                ) VALUES (
                    '2026-01-01 00:00:00', 'task-1', 'org-1', 'user-1',
                    'project-1', '{}', 30.0, 'QUEUED', 0, 0
                )
                """
            )
        )

    def verify(self, connection: sa.engine.Connection) -> None:
        columns = {row[1] for row in connection.execute(sa.text("PRAGMA table_info(task)"))}
        assert "max_seconds" not in columns, "max_seconds column should be dropped"
        result = connection.execute(sa.text("SELECT object_id, outcome FROM task WHERE object_id = 'task-1'")).one()
        assert result[0] == "task-1"
        assert result[1] == "QUEUED"
