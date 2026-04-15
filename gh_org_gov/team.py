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
    to_update: list[tuple[TeamDef, dict]] = dataclasses.field(default_factory=list)
    to_delete: list[str] = dataclasses.field(default_factory=list)


def plan_sync(
    desired: list[TeamDef],
    existing: list[TeamDef],
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
    to_update: list[tuple[TeamDef, dict]] = []
    to_delete: list[str] = []

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
                to_update.append((td, changes))

    if delete_orphans:
        for slug in existing_by_slug:
            if slug not in desired_by_slug:
                to_delete.append(slug)

    return TeamSyncResult(
        to_create=to_create,
        to_update=to_update,
        to_delete=to_delete,
    )


def sync_teams(
    org,  # github.Organization.Organization
    desired: list[TeamDef],
    delete_orphans: bool = False,
    delay: float = 0.1,
) -> TeamSyncResult:
    """
    Sync GitHub org teams to match the desired definitions.

    Workflow:

    1. Fetch all existing teams from the org (batch)
    2. Compare with desired definitions using :func:`plan_sync`
    3. Create / update / delete as needed

    :param org: PyGithub ``Organization`` object
    :param desired: list of desired :class:`TeamDef`
    :param delete_orphans: if ``True``, delete teams that exist on GitHub but
        not in the desired list.

        .. warning::

            Deleting a team **also removes all team-repo permission associations**.
            GitHub does NOT prevent deletion of teams associated with repos.
            The repos remain intact but lose the team-based permissions.

    :param delay: seconds to wait between API calls to avoid rate limiting
    :return: a :class:`TeamSyncResult` describing what was done
    """
    # --- 1. Fetch existing teams in batch ---
    existing: list[TeamDef] = []
    for team in org.get_teams():
        existing.append(
            TeamDef(
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
            )
        )

    # --- 2. Plan ---
    result = plan_sync(desired, existing, delete_orphans=delete_orphans)

    # --- 3. Execute ---
    # Build slug -> Team object mapping for updates and deletes
    team_mapping = {team.slug: team for team in org.get_teams()}

    for td in result.to_create:
        create_kwargs: dict[str, T.Any] = dict(
            name=td.name,
            description=td.description,
            privacy=td.privacy,
            notification_setting=td.notification_setting,
        )
        if td.parent_team_id is not None:
            create_kwargs["parent_team_id"] = td.parent_team_id
        org.create_team(**create_kwargs)
        time.sleep(delay)

    for td, changes in result.to_update:
        team = team_mapping[td.slug]
        edit_kwargs: dict[str, T.Any] = {}
        if "name" in changes:
            edit_kwargs["name"] = td.name
        if "description" in changes:
            edit_kwargs["description"] = td.description
        if "privacy" in changes:
            edit_kwargs["privacy"] = td.privacy
        if "notification_setting" in changes:
            edit_kwargs["notification_setting"] = td.notification_setting
        if "parent_team_id" in changes:
            edit_kwargs["parent_team_id"] = (
                td.parent_team_id if td.parent_team_id else ""
            )
        if edit_kwargs:
            team.edit(**edit_kwargs)
            time.sleep(delay)

    for slug in result.to_delete:
        if slug in team_mapping:
            team_mapping[slug].delete()
            time.sleep(delay)

    return result
