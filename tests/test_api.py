# -*- coding: utf-8 -*-

from gh_org_gov import api


def test():
    _ = api
    _ = api.RepositoryRoleEnum
    _ = api.TeamDefTsvColEnum
    _ = api.get_github
    _ = api.graphql_request
    _ = api.TeamPrivacyEnum
    _ = api.TeamNotificationSettingEnum
    _ = api.TeamDef
    _ = api.ExistingTeamDef
    _ = api.load_team_defs_from_tsv
    _ = api.TeamSyncResult
    _ = api.plan_sync
    _ = api.fetch_existing_team_defs
    _ = api.sync_teams
    _ = api.RepoPermChange
    _ = api.RepoPermSyncResult
    _ = api.fetch_repo_team_permissions
    _ = api.plan_sync_repo_permissions
    _ = api.sync_repo_permissions


if __name__ == "__main__":
    from gh_org_gov.tests import run_cov_test

    run_cov_test(
        __file__,
        "gh_org_gov.api",
        preview=False,
    )
