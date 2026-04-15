# -*- coding: utf-8 -*-

import pytest

from gh_org_gov.team_def import TeamDef
from gh_org_gov.team import plan_sync


class TestPlanSync:
    def _make_existing(self) -> list[TeamDef]:
        return [
            TeamDef(name="Guardians", description="Admin team"),
            TeamDef(name="Developers", description="Dev team"),
            TeamDef(name="Legacy Team", description="Old team"),
        ]

    def test_create(self):
        """Teams in desired but not existing should be created."""
        desired = [
            TeamDef(name="Guardians", description="Admin team"),
            TeamDef(name="New Team", description="Brand new"),
        ]
        existing = self._make_existing()
        result = plan_sync(desired, existing)
        # result.pretty_print()  # for debug only

        assert len(result.to_create) == 1
        assert result.to_create[0].name == "New Team"

    def test_update(self):
        """Teams with changed fields should be updated."""
        desired = [
            TeamDef(name="Guardians", description="Updated description"),
        ]
        existing = self._make_existing()
        result = plan_sync(desired, existing)
        # result.pretty_print()  # for debug only

        assert len(result.to_update) == 1
        td, changes = result.to_update[0]
        assert td.name == "Guardians"
        assert "description" in changes
        assert changes["description"] == ("Admin team", "Updated description")

    def test_no_change(self):
        """Teams that match exactly should not appear in any list."""
        desired = [
            TeamDef(name="Guardians", description="Admin team"),
        ]
        existing = self._make_existing()
        result = plan_sync(desired, existing)
        # result.pretty_print()  # for debug only

        assert len(result.to_create) == 0
        assert len(result.to_update) == 0
        assert len(result.to_delete) == 0

    def test_delete_orphans_false(self):
        """With delete_orphans=False, orphan teams should NOT be deleted."""
        desired = [
            TeamDef(name="Guardians", description="Admin team"),
        ]
        existing = self._make_existing()
        result = plan_sync(desired, existing, delete_orphans=False)
        # result.pretty_print()  # for debug only

        assert len(result.to_delete) == 0

    def test_delete_orphans_true(self):
        """With delete_orphans=True, teams in existing but not desired should be deleted."""
        desired = [
            TeamDef(name="Guardians", description="Admin team"),
        ]
        existing = self._make_existing()
        result = plan_sync(desired, existing, delete_orphans=True)
        # result.pretty_print()  # for debug only

        assert set(result.to_delete) == {"developers", "legacy-team"}

    def test_update_privacy(self):
        """Changing privacy should be detected."""
        desired = [
            TeamDef(name="Guardians", description="Admin team", privacy="secret"),
        ]
        existing = self._make_existing()
        result = plan_sync(desired, existing)
        # result.pretty_print()  # for debug only

        assert len(result.to_update) == 1
        _, changes = result.to_update[0]
        assert "privacy" in changes
        assert changes["privacy"] == ("closed", "secret")

    def test_update_notification_setting(self):
        """Changing notification_setting should be detected."""
        desired = [
            TeamDef(
                name="Guardians",
                description="Admin team",
                notification_setting="notifications_disabled",
            ),
        ]
        existing = self._make_existing()
        result = plan_sync(desired, existing)
        # result.pretty_print()  # for debug only

        assert len(result.to_update) == 1
        _, changes = result.to_update[0]
        assert "notification_setting" in changes

    def test_combined(self):
        """Test create + update + delete in one sync."""
        desired = [
            TeamDef(name="Guardians", description="New desc"),
            TeamDef(name="Brand New Team", description="Hello"),
        ]
        existing = self._make_existing()
        result = plan_sync(desired, existing, delete_orphans=True)
        # result.pretty_print()  # for debug only

        assert len(result.to_create) == 1
        assert result.to_create[0].name == "Brand New Team"

        assert len(result.to_update) == 1
        assert result.to_update[0][0].name == "Guardians"

        assert set(result.to_delete) == {"developers", "legacy-team"}

    def test_empty_desired(self):
        """Empty desired with delete_orphans=True should delete all existing."""
        existing = self._make_existing()
        result = plan_sync([], existing, delete_orphans=True)
        # result.pretty_print()  # for debug only

        assert len(result.to_create) == 0
        assert len(result.to_update) == 0
        assert len(result.to_delete) == 3

    def test_empty_existing(self):
        """Empty existing should create all desired."""
        desired = [TeamDef(name="A"), TeamDef(name="B")]
        result = plan_sync(desired, [], delete_orphans=True)
        # result.pretty_print()  # for debug only
        assert len(result.to_create) == 2
        assert len(result.to_update) == 0
        assert len(result.to_delete) == 0


if __name__ == "__main__":
    from gh_org_gov.tests.helper import run_cov_test

    run_cov_test(
        __file__,
        "gh_org_gov.team",
        preview=False,
    )
