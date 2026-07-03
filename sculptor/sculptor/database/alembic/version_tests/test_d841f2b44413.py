import sqlalchemy as sa

from sculptor.database.alembic.migration_test_utils import MigrationTestFixture

PROJECT_ID = "proj-ci-babysitter-paused"
WORKSPACE_ID = "ws-ci-babysitter-paused"


class TestMigrationd841f2b44413(MigrationTestFixture):
    """Adding ci_babysitter_paused backfills existing workspace rows to 0 (not paused).

    The per-workspace CI Babysitter pause flag is newly persisted on the
    workspace; a pre-existing row must come out of the migration as not-paused.
    """

    @property
    def revision(self) -> str:
        return "d841f2b44413"

    @property
    def down_revision(self) -> str:
        return "4ddee12c1e07"

    def seed(self, connection: sa.engine.Connection) -> None:
        connection.execute(
            sa.text("""
                INSERT INTO project (
                    created_at, object_id, organization_reference,
                    name, user_git_repo_url, is_path_accessible, is_deleted
                ) VALUES (
                    '2026-01-01T00:00:00', :project_id, 'org-1',
                    'Test Project', NULL, 1, 0
                )
            """),
            {"project_id": PROJECT_ID},
        )

        connection.execute(
            sa.text("""
                INSERT INTO workspace (
                    created_at, object_id, project_id, organization_reference,
                    description, source_branch, source_git_hash, is_deleted,
                    is_open, setup_status, setup_log_truncated, diff_status
                ) VALUES (
                    '2026-01-01T00:00:00', :ws_id, :project_id, 'org-1',
                    'workspace', NULL, 'abc123', 0,
                    1, 'pending', 0, 'NONE'
                )
            """),
            {"ws_id": WORKSPACE_ID, "project_id": PROJECT_ID},
        )

    def verify(self, connection: sa.engine.Connection) -> None:
        columns = {row[1] for row in connection.execute(sa.text("PRAGMA table_info(workspace)")).fetchall()}
        assert "ci_babysitter_paused" in columns, "Expected ci_babysitter_paused column on workspace"

        result = connection.execute(
            sa.text("SELECT ci_babysitter_paused FROM workspace WHERE object_id = :ws_id"),
            {"ws_id": WORKSPACE_ID},
        )
        row = result.fetchone()
        assert row is not None, f"Expected row in workspace for {WORKSPACE_ID} to survive the migration"
        assert row[0] == 0, f"Expected ci_babysitter_paused to backfill to 0, got {row[0]}"
