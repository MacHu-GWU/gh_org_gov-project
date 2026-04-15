# -*- coding: utf-8 -*-

"""
GitHub Team Definition Data Types

Pure data type definitions for GitHub team management. No API logic.

Key classes:

- :class:`TeamPrivacyEnum`: Team visibility (visible / secret)
- :class:`TeamNotificationSettingEnum`: Team @mention notification setting
- :class:`TeamDef`: Dataclass representing all configurable team properties

Key functions:

- :func:`load_team_defs_from_tsv`: Load team definitions from a TSV file
"""

import typing as T
import csv
import enum
import dataclasses
from pathlib import Path

from .constants.constants import TeamDefTsvColEnum
from .constants.constants import RepositoryRoleEnum


class TeamPrivacyEnum(enum.StrEnum):
    """
    Team visibility setting.

    - ``closed``: Visible to all org members (recommended).
    - ``secret``: Only visible to team members, cannot be nested.
    """

    closed = "closed"
    secret = "secret"


class TeamNotificationSettingEnum(enum.StrEnum):
    """
    Team notification setting for @mentions.

    - ``notifications_enabled``: Everyone is notified when the team is @mentioned.
    - ``notifications_disabled``: No one receives notifications.
    """

    notifications_enabled = "notifications_enabled"
    notifications_disabled = "notifications_disabled"


@dataclasses.dataclass
class TeamDef:
    """
    Represents a GitHub team definition with all configurable properties.

    Maps to the fields available in the GitHub "Create new team" form:

    - Team name
    - Description
    - Parent team
    - Team visibility (visible / secret)
    - Team notifications (enabled / disabled)

    Ref: https://docs.github.com/en/rest/teams/teams?apiVersion=2022-11-28#create-a-team
    """

    # fmt: off
    name: str = dataclasses.field()
    description: str = dataclasses.field(default="")
    privacy: str = dataclasses.field(default=TeamPrivacyEnum.closed.value)
    notification_setting: str = dataclasses.field(default=TeamNotificationSettingEnum.notifications_enabled.value)
    parent_team_id: T.Optional[int] = dataclasses.field(default=None)
    repo_role: T.Optional[str] = dataclasses.field(default=None)
    # fmt: on

    @property
    def slug(self) -> str:
        """
        Generate URL-friendly team slug from the team name.

        Example: ``"Core Architects"`` -> ``"core-architects"``
        """
        return self.name.replace(" ", "-").lower()


@dataclasses.dataclass
class ExistingTeamDef(TeamDef):
    """
    A :class:`TeamDef` fetched from GitHub, with the remote ``team_id``.

    This subclass carries the extra metadata needed to update or delete
    a team without re-fetching it from the API.

    :param team_id: the GitHub-assigned integer ID of the team
    """

    # fmt: off
    team_id: T.Optional[int] = dataclasses.field(default=None)
    # fmt: on


def load_team_defs_from_tsv(path: T.Union[str, Path]) -> list[TeamDef]:
    """
    Load team definitions from a TSV file.

    Only columns defined in :mod:`gh_org_gov.constants.constants` as
    ``TEAM_DEF_COL_*`` are recognized. All other columns in the TSV are
    silently ignored (e.g. ``repo_role``, ``description_cn``, notes, etc.).

    If a recognized column is missing from the TSV or its cell is empty,
    the corresponding :class:`TeamDef` field keeps its default value —
    equivalent to leaving that field blank when creating a team via the
    GitHub API.

    Required column: ``team_name``

    Optional columns: ``description``, ``privacy``, ``notification_setting``,
    ``parent_team_id``

    :param path: path to the TSV file
    :return: list of TeamDef instances
    """
    Col = TeamDefTsvColEnum
    team_defs = []
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            # Required field
            kwargs: dict[str, T.Any] = dict(
                name=row[Col.TEAM_NAME],
            )
            # Optional string fields — use value only if column exists and is non-empty
            # For enum-backed fields, validate against allowed values
            _enum_validators: dict[str, type] = {
                "privacy": TeamPrivacyEnum,
                "notification_setting": TeamNotificationSettingEnum,
                "repo_role": RepositoryRoleEnum,
            }
            for col, field in [
                (Col.DESCRIPTION, "description"),
                (Col.PRIVACY, "privacy"),
                (Col.NOTIFICATION_SETTING, "notification_setting"),
                (Col.REPO_ROLE, "repo_role"),
            ]:
                val = row.get(col)
                if val:
                    if field in _enum_validators:
                        valid = {e.value for e in _enum_validators[field]}
                        if val not in valid:
                            raise ValueError(
                                f"Row {reader.line_num}: "
                                f"invalid {field}={val!r}, "
                                f"must be one of {sorted(valid)}"
                            )
                    kwargs[field] = val
            # Optional integer field
            val = row.get(Col.PARENT_TEAM_ID)
            if val:
                kwargs["parent_team_id"] = int(val)
            team_defs.append(TeamDef(**kwargs))
    return team_defs
