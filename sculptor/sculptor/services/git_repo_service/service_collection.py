from sculptor.config.settings import SculptorSettings
from sculptor.foundation.concurrency_group import ConcurrencyGroup
from sculptor.services.data_model_service.sql_implementation import SQLDataModelService
from sculptor.services.git_repo_service.data_types import GitRepoServiceCollection
from sculptor.services.git_repo_service.default_implementation import DefaultGitRepoService
from sculptor.services.project_service.default_implementation import DefaultProjectService
from sculptor.services.workspace_service.default_implementation import DefaultWorkspaceService


def get_git_repo_service_collection(
    concurrency_group: ConcurrencyGroup,
    settings: SculptorSettings,
) -> GitRepoServiceCollection:
    """Build the service collection that the git repo service depends on."""
    data_model_service = SQLDataModelService.build_from_settings(
        settings, concurrency_group.make_concurrency_group("data_model_service")
    )
    git_repo_service = DefaultGitRepoService(
        concurrency_group=concurrency_group.make_concurrency_group("git_repo_service")
    )
    project_service = DefaultProjectService(
        concurrency_group=concurrency_group.make_concurrency_group("project_service"),
        data_model_service=data_model_service,
    )
    workspace_service = DefaultWorkspaceService.build(
        concurrency_group=concurrency_group,
        settings=settings,
        data_model_service=data_model_service,
        project_service=project_service,
    )
    return GitRepoServiceCollection(
        settings=settings,
        data_model_service=data_model_service,
        git_repo_service=git_repo_service,
        project_service=project_service,
        workspace_service=workspace_service,
    )
