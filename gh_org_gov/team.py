# -*- coding: utf-8 -*-

"""
GitHub Team Sync Module

This module provides functionality to sync GitHub organization teams
using a declarative approach. It compares desired team definitions
against the actual GitHub state and executes the delta.

Key classes:

- :class:`TeamSyncResult`: Delta between desired and existing team states

Key functions:

- :func:`plan_sync`: Compute the delta between desired and existing teams
- :func:`sync_teams`: Execute the sync against GitHub API

Ref:

- Create a team: https://docs.github.com/en/rest/teams/teams?apiVersion=2022-11-28#create-a-team
- Update a team: https://docs.github.com/en/rest/teams/teams?apiVersion=2022-11-28#update-a-team
- Delete a team: https://docs.github.com/en/rest/teams/teams?apiVersion=2022-11-28#delete-a-team
- List teams: https://docs.github.com/en/rest/teams/teams?apiVersion=2022-11-28#list-teams
"""

import typing as T
import time
import dataclasses

from .team_def import TeamDef
from .team_def import ExistingTeamDef
from .team_def import TeamPrivacyEnum
from .team_def import TeamNotificationSettingEnum

# Fields to compare when detecting changes between desired and existing teams
_SYNC_FIELDS = [
    "name",
    "description",
    "privacy",
    "notification_setting",
    "parent_team_id",
]


@dataclasses.dataclass
class TeamSyncResult:
    """
    Result of comparing desired team definitions with existing teams.

    :param to_create: teams that need to be created
    :param to_update: teams that need to be updated, each as
        ``(desired_def, {field: (old_value, new_value)})``
    :param to_delete: slugs of teams that should be deleted
    """

    to_create: list[TeamDef] = dataclasses.field(default_factory=list)
    to_update: list[tuple[TeamDef, ExistingTeamDef, dict]] = dataclasses.field(default_factory=list)
    to_delete: list[ExistingTeamDef] = dataclasses.field(default_factory=list)

    def pretty_print(self):
        """
        Pretty print the sync execution plan.
        """
        print(
            f"Summary: "
            f"🟢 Create {len(self.to_create)} | "
            f"🟡 Update {len(self.to_update)} | "
            f"🔴 Delete {len(self.to_delete)}"
        )

        if not self.to_create and not self.to_update and not self.to_delete:
            print("Already in sync, nothing to do.")
            return

        if self.to_create:
            print(f"🟢 Create ({len(self.to_create)}) ---")
            for td in self.to_create:
                print(f"  🟢 {td.name} (slug={td.slug!r})")
                if td.description:
                    print(f"    description: {td.description}")
                if td.privacy != TeamPrivacyEnum.closed.value:
                    print(f"    privacy: {td.privacy}")
                if td.notification_setting != TeamNotificationSettingEnum.notifications_enabled.value:
                    print(f"    notification_setting: {td.notification_setting}")
                if td.parent_team_id is not None:
                    print(f"    parent_team_id: {td.parent_team_id}")

        if self.to_update:
            print(f"🟡 Update ({len(self.to_update)}) ---")
            for td, existing, changes in self.to_update:
                print(f"  🟡 {td.name} (slug={td.slug!r}, id={existing.team_id})")
                for field, (old, new) in changes.items():
                    print(f"    {field}: {old!r} -> {new!r}")

        if self.to_delete:
            print(f"🔴 Delete ({len(self.to_delete)}) ---")
            for etd in self.to_delete:
                print(f"  🔴 {etd.name} (slug={etd.slug!r}, id={etd.team_id})")

    def execute(
        self,
        org,  # github.Organization.Organization
        delay: float = 0.1,
    ):
        """
        Execute the sync plan against the GitHub API.

        Uses ``team_id`` from :class:`ExistingTeamDef` to get Team objects
        via ``org.get_team(id)`` for update and delete operations.

        :param org: PyGithub ``Organization`` object
        :param delay: seconds to wait between API calls to avoid rate limiting
        """
        for td in self.to_create:
            _execute_create(org, td)
            time.sleep(delay)

        for td, existing, changes in self.to_update:
            team = org.get_team(existing.team_id)
            _execute_update(team, td, changes)
            time.sleep(delay)

        for etd in self.to_delete:
            team = org.get_team(etd.team_id)
            _execute_delete(team)
            time.sleep(delay)


def _execute_create(
    org,  # github.Organization.Organization
    td: TeamDef,
):
    """
    Create a single team in the GitHub org.

    :param org: PyGithub ``Organization`` object
    :param td: the team definition to create
    """
    kwargs: dict[str, T.Any] = dict(
        name=td.name,
        description=td.description,
        privacy=td.privacy,
        notification_setting=td.notification_setting,
    )
    if td.parent_team_id is not None:
        kwargs["parent_team_id"] = td.parent_team_id
    org.create_team(**kwargs)


def _execute_update(
    team,  # github.Team.Team
    td: TeamDef,
    changes: dict[str, tuple],
):
    """
    Update a single team's changed fields.

    :param team: PyGithub ``Team`` object to update
    :param td: the desired team definition
    :param changes: dict of ``{field: (old_value, new_value)}``
    """
    kwargs: dict[str, T.Any] = {}
    if "name" in changes:
        kwargs["name"] = td.name
    if "description" in changes:
        kwargs["description"] = td.description
    if "privacy" in changes:
        kwargs["privacy"] = td.privacy
    if "notification_setting" in changes:
        kwargs["notification_setting"] = td.notification_setting
    if "parent_team_id" in changes:
        kwargs["parent_team_id"] = td.parent_team_id if td.parent_team_id else ""
    if kwargs:
        team.edit(**kwargs)


def _execute_delete(
    team,  # github.Team.Team
):
    """
    Delete a single team.

    :param team: PyGithub ``Team`` object to delete
    """
    team.delete()


def plan_sync(
    desired: list[TeamDef],
    existing: list[ExistingTeamDef],
    delete_orphans: bool = False,
) -> TeamSyncResult:
    """
    Compare desired team definitions with existing teams and compute the delta.

    This function does NOT call any GitHub API. It is pure logic that can be
    tested without mocking.

    :param desired: the target state of teams
    :param existing: the current state of teams (fetched from GitHub)
    :param delete_orphans: if True, teams in ``existing`` but not in ``desired``
        will be marked for deletion
    :return: a :class:`TeamSyncResult` with create/update/delete lists
    """
    desired_by_slug = {td.slug: td for td in desired}
    existing_by_slug = {td.slug: td for td in existing}

    to_create: list[TeamDef] = []
    to_update: list[tuple[TeamDef, ExistingTeamDef, dict]] = []
    to_delete: list[ExistingTeamDef] = []

    for slug, td in desired_by_slug.items():
        if slug not in existing_by_slug:
            to_create.append(td)
        else:
            ex = existing_by_slug[slug]
            changes: dict[str, tuple] = {}
            for field in _SYNC_FIELDS:
                desired_val = getattr(td, field)
                existing_val = getattr(ex, field)
                if desired_val != existing_val:
                    changes[field] = (existing_val, desired_val)
            if changes:
                to_update.append((td, ex, changes))

    if delete_orphans:
        for slug, etd in existing_by_slug.items():
            if slug not in desired_by_slug:
                to_delete.append(etd)

    return TeamSyncResult(
        to_create=to_create,
        to_update=to_update,
        to_delete=to_delete,
    )


def fetch_existing_team_defs(
    org,  # github.Organization.Organization
) -> list[ExistingTeamDef]:
    """
    Fetch all existing teams from a GitHub org.

    :param org: PyGithub ``Organization`` object
    :return: list of :class:`ExistingTeamDef` with ``team_id`` populated
    """
    existing: list[ExistingTeamDef] = []
    for team in org.get_teams():
        existing.append(
            ExistingTeamDef(
                name=team.name,
                description=team.description or "",
                privacy=team.privacy or TeamPrivacyEnum.closed.value,
                notification_setting=(
                    getattr(
                        team,
                        "notification_setting",
                        TeamNotificationSettingEnum.notifications_enabled.value,
                    )
                    or TeamNotificationSettingEnum.notifications_enabled.value
                ),
                parent_team_id=team.parent.id if team.parent else None,
                team_id=team.id,
            )
        )
    return existing


def sync_teams(
    org,  # github.Organization.Organization
    desired: list[TeamDef],
    delete_orphans: bool = False,
    plan_mode: bool = True,
    delay: float = 0.1,
) -> TeamSyncResult:
    """
    Sync GitHub org teams to match the desired definitions.

    Workflow:

    1. Fetch all existing teams from the org (batch)
    2. Compare with desired definitions using :func:`plan_sync`
    3. If ``plan_mode`` is ``True``, only print the execution plan
    4. Otherwise, execute the plan via :meth:`TeamSyncResult.execute`

    .. note::

        GitHub REST API does not support batch team operations.
        Teams are created / updated / deleted one by one.

    :param org: PyGithub ``Organization`` object
    :param desired: list of desired :class:`TeamDef`
    :param delete_orphans: if ``True``, delete teams that exist on GitHub but
        not in the desired list.

        .. warning::

            Deleting a team **also removes all team-repo permission associations**.
            GitHub does NOT prevent deletion of teams associated with repos.
            The repos remain intact but lose the team-based permissions.

    :param plan_mode: if ``True``, only pretty-print the execution plan
        without making any API changes
    :param delay: seconds to wait between API calls to avoid rate limiting
    :return: a :class:`TeamSyncResult` describing what was (or would be) done
    """
    existing = fetch_existing_team_defs(org)
    result = plan_sync(desired, existing, delete_orphans=delete_orphans)
    result.pretty_print()
    if plan_mode is False:
        result.execute(org, delay=delay)
    return result
