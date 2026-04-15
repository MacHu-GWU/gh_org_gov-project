# -*- coding: utf-8 -*-

import enum


class RepositoryRoleEnum(enum.StrEnum):
    admin = "admin"
    maintain = "maintain"
    push = "push"
    pull = "pull"
