# -*- coding: utf-8 -*-

import enum


class RepositoryRoleEnum(enum.StrEnum):
    admin = "admin"
    maintain = "maintain"
    push = "push"
    pull = "pull"


class TeamDefTsvColEnum(enum.StrEnum):
    """
    Recognized TSV column names when loading :class:`TeamDef` from a TSV file.

    These correspond to the fields available when creating a team via the
    GitHub UI / API. Only these columns are read from the TSV; any other
    columns are silently ignored. If a column is missing or its cell is empty,
    the corresponding :class:`TeamDef` field keeps its default value —
    equivalent to leaving that field blank when creating a team.
    """

    # Required: the display name of the team
    TEAM_NAME = "team_name"
    # Optional: team description text
    DESCRIPTION = "description"
    # Optional: "closed" (visible, default) or "secret"
    PRIVACY = "privacy"
    # Optional: "notifications_enabled" (default) or "notifications_disabled"
    NOTIFICATION_SETTING = "notification_setting"
    # Optional: integer ID of the parent team, empty or absent means no parent
    PARENT_TEAM_ID = "parent_team_id"
