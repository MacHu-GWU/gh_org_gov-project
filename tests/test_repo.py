# -*- coding: utf-8 -*-

from gh_org_gov.team_def import TeamDef
from gh_org_gov.repo import plan_sync_repo_permissions


class TestPlanSyncRepoPermissions:
    @staticmethod
    def _make_desired() -> list[TeamDef]:
        return [
            TeamDef(name="Guardians", description="Admin team", repo_role="admin"),
            TeamDef(name="Developers", description="Dev team", repo_role="push"),
            TeamDef(name="No Role Team", description="No repo role"),
        ]

    @staticmethod
    def _make_repos() -> list[str]:
        return ["org/repo-a", "org/repo-b", "org/repo-c"]

    @staticmethod
    def _make_current_perms() -> dict[str, dict[str, str]]:
        return {
            "guardians": {
                "org/repo-a": "admin",
                "org/repo-b": "maintain",  # wrong level
                # repo-c missing
            },
            "developers": {
                "org/repo-a": "push",
                # repo-b, repo-c missing
            },
        }

    def test_add_missing_permissions(self):
        """Repos where team has no permission should be in to_add."""
        desired = self._make_desired()
        all_repos = self._make_repos()
        current = self._make_current_perms()
        result = plan_sync_repo_permissions(desired, all_repos, current)
        # result.pretty_print()  # for debug only

        add_keys = {(ch.team_slug, ch.repo_full_name) for ch in result.to_add}
        assert ("guardians", "org/repo-c") in add_keys
        assert ("developers", "org/repo-b") in add_keys
        assert ("developers", "org/repo-c") in add_keys

    def test_update_wrong_permission(self):
        """Repos where team has wrong permission should be in to_update."""
        desired = self._make_desired()
        all_repos = self._make_repos()
        current = self._make_current_perms()
        result = plan_sync_repo_permissions(desired, all_repos, current)
        # result.pretty_print()  # for debug only

        update_keys = {(ch.team_slug, ch.repo_full_name) for ch in result.to_update}
        assert ("guardians", "org/repo-b") in update_keys
        # Check old/new values
        for ch in result.to_update:
            if ch.team_slug == "guardians" and ch.repo_full_name == "org/repo-b":
                assert ch.old_permission == "maintain"
                assert ch.new_permission == "admin"

    def test_skip_correct_permission(self):
        """Repos with correct permission should not appear in any list."""
        desired = self._make_desired()
        all_repos = self._make_repos()
        current = self._make_current_perms()
        result = plan_sync_repo_permissions(desired, all_repos, current)
        # result.pretty_print()  # for debug only

        all_keys = (
            {(ch.team_slug, ch.repo_full_name) for ch in result.to_add}
            | {(ch.team_slug, ch.repo_full_name) for ch in result.to_update}
            | {(ch.team_slug, ch.repo_full_name) for ch in result.to_remove}
        )
        # guardians/repo-a is already admin, developers/repo-a is already push
        assert ("guardians", "org/repo-a") not in all_keys
        assert ("developers", "org/repo-a") not in all_keys

    def test_ignore_teams_without_repo_role(self):
        """Teams without repo_role should not generate any changes."""
        desired = self._make_desired()
        all_repos = self._make_repos()
        current = self._make_current_perms()
        result = plan_sync_repo_permissions(desired, all_repos, current)
        # result.pretty_print()  # for debug only

        all_slugs = (
            {ch.team_slug for ch in result.to_add}
            | {ch.team_slug for ch in result.to_update}
            | {ch.team_slug for ch in result.to_remove}
        )
        assert "no-role-team" not in all_slugs

    def test_remove_unlisted_false(self):
        """With remove_unlisted=False, no removals even for unknown repos."""
        desired = [TeamDef(name="Guardians", repo_role="admin")]
        current = {"guardians": {"org/deleted-repo": "admin"}}
        result = plan_sync_repo_permissions(
            desired, ["org/repo-a"], current, remove_unlisted=False
        )
        # result.pretty_print()  # for debug only

        assert len(result.to_remove) == 0

    def test_remove_unlisted_true(self):
        """With remove_unlisted=True, repos not in all_repos are removed."""
        desired = [TeamDef(name="Guardians", repo_role="admin")]
        current = {"guardians": {"org/deleted-repo": "admin"}}
        result = plan_sync_repo_permissions(
            desired, ["org/repo-a"], current, remove_unlisted=True
        )
        # result.pretty_print()  # for debug only

        assert len(result.to_remove) == 1
        assert result.to_remove[0].repo_full_name == "org/deleted-repo"
        assert result.to_remove[0].old_permission == "admin"
        assert result.to_remove[0].new_permission is None

    def test_all_in_sync(self):
        """When everything matches, all lists should be empty."""
        desired = [TeamDef(name="Guardians", repo_role="admin")]
        current = {"guardians": {"org/repo-a": "admin"}}
        result = plan_sync_repo_permissions(desired, ["org/repo-a"], current)
        # result.pretty_print()  # for debug only

        assert len(result.to_add) == 0
        assert len(result.to_update) == 0
        assert len(result.to_remove) == 0

    def test_empty_desired(self):
        """No desired teams with repo_role means no changes."""
        desired = [TeamDef(name="Guardians")]
        current = {"guardians": {"org/repo-a": "admin"}}
        result = plan_sync_repo_permissions(desired, ["org/repo-a"], current)
        # result.pretty_print()  # for debug only

        assert len(result.to_add) == 0
        assert len(result.to_update) == 0
        assert len(result.to_remove) == 0

    def test_empty_repos(self):
        """No repos means no changes."""
        desired = [TeamDef(name="Guardians", repo_role="admin")]
        result = plan_sync_repo_permissions(desired, [], {})
        # result.pretty_print()  # for debug only

        assert len(result.to_add) == 0
        assert len(result.to_update) == 0
        assert len(result.to_remove) == 0

    def test_team_not_in_current_perms(self):
        """Team not in current_perms at all should add all repos."""
        desired = [TeamDef(name="New Team", repo_role="pull")]
        all_repos = ["org/repo-a", "org/repo-b"]
        result = plan_sync_repo_permissions(desired, all_repos, {})
        # result.pretty_print()  # for debug only

        assert len(result.to_add) == 2
        assert all(ch.new_permission == "pull" for ch in result.to_add)
        assert all(ch.old_permission is None for ch in result.to_add)


if __name__ == "__main__":
    from gh_org_gov.tests.helper import run_cov_test

    run_cov_test(
        __file__,
        "gh_org_gov.repo",
        preview=False,
    )
