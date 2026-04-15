# -*- coding: utf-8 -*-

from gh_org_gov.team_def import TeamDef
from gh_org_gov.team_def import TeamPrivacyEnum
from gh_org_gov.team_def import TeamNotificationSettingEnum
from gh_org_gov.team_def import load_team_defs_from_tsv

from pathlib import Path
from gh_org_gov.paths import path_enum

dir_test_data = Path(__file__).absolute().parent / "data"


class TestTeamDef:
    def test_slug(self):
        td = TeamDef(name="Core Architects")
        assert td.slug == "core-architects"

    def test_slug_single_word(self):
        td = TeamDef(name="Guardians")
        assert td.slug == "guardians"

    def test_defaults(self):
        td = TeamDef(name="Test")
        assert td.description == ""
        assert td.privacy == "closed"
        assert td.notification_setting == "notifications_enabled"
        assert td.parent_team_id is None


class TestLoadTeamDefsFromTsv:
    def test_load_minimal(self):
        """Load from the original TSV that only has team_name + description columns.
        Extra columns like description_cn and repo_role should be ignored."""
        path = path_enum.dir_tmp / "team_def.tsv"
        team_defs = load_team_defs_from_tsv(path)
        assert len(team_defs) == 4

        td = team_defs[0]
        assert td.name == "Guardians"
        assert td.slug == "guardians"
        assert "full access" in td.description

        td = team_defs[1]
        assert td.name == "Core Architects"
        assert td.slug == "core-architects"

        td = team_defs[2]
        assert td.name == "Developers"
        assert td.slug == "developers"

        td = team_defs[3]
        assert td.name == "Observers"
        assert td.slug == "observers"

    def test_defaults_when_columns_missing(self):
        """TSV without privacy/notification columns should fall back to defaults."""
        path = path_enum.dir_tmp / "team_def.tsv"
        team_defs = load_team_defs_from_tsv(path)
        for td in team_defs:
            assert td.privacy == TeamPrivacyEnum.closed.value
            assert (
                td.notification_setting
                == TeamNotificationSettingEnum.notifications_enabled.value
            )
            assert td.parent_team_id is None

    def test_load_full(self):
        """Load from the example TSV that has all recognized columns."""
        path = dir_test_data / "team_def.example.tsv"
        team_defs = load_team_defs_from_tsv(path)
        assert len(team_defs) == 4

        # Guardians: closed + enabled
        td = team_defs[0]
        assert td.name == "Guardians"
        assert td.privacy == "closed"
        assert td.notification_setting == "notifications_enabled"
        assert td.parent_team_id is None

        # Observers: secret + disabled
        td = team_defs[3]
        assert td.name == "Observers"
        assert td.privacy == "secret"
        assert td.notification_setting == "notifications_disabled"
        assert td.parent_team_id is None

    def test_extra_columns_ignored(self):
        """Columns not in TEAM_DEF_COL_* constants should be silently ignored."""
        path = path_enum.dir_tmp / "team_def.tsv"
        team_defs = load_team_defs_from_tsv(path)
        # If extra columns caused an error, we wouldn't get here
        assert len(team_defs) == 4
        # Verify no unexpected attributes leaked in
        for td in team_defs:
            assert not hasattr(td, "description_cn")
            assert not hasattr(td, "repo_role")


if __name__ == "__main__":
    from gh_org_gov.tests.helper import run_cov_test

    run_cov_test(
        __file__,
        "gh_org_gov.team_def",
        preview=False,
    )
