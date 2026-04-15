# -*- coding: utf-8 -*-

"""
GitHub Repo Permission Sync Module

This module provides functionality to sync GitHub team-repo permissions
using a declarative approach. It compares desired team permissions (from
:class:`TeamDef` with ``repo_role`` set) against the actual GitHub state
and executes the delta.

Key classes:

- :class:`RepoPermChange`: A single team-repo permission change
- :class:`RepoPermSyncResult`: Delta between desired and existing permissions

Key functions:

- :func:`fetch_repo_team_permissions`: Batch-fetch all repos and team permissions via GraphQL
- :func:`plan_sync_repo_permissions`: Compute the delta (pure logic, no API)
- :func:`sync_repo_permissions`: Orchestrate fetch -> plan -> execute

Ref:

- Add or update team repository permissions: https://docs.github.com/en/rest/teams/teams?apiVersion=2022-11-28#add-or-update-team-repository-permissions
- Remove a repository from a team: https://docs.github.com/en/rest/teams/teams?apiVersion=2022-11-28#remove-a-repository-from-a-team
"""

import typing as T
import time
import dataclasses

from .team_def import TeamDef
from .client import graphql_request

# GraphQL permission values -> REST API permission values
_GRAPHQL_TO_REST_PERMISSION: dict[str, str] = {
    "ADMIN": "admin",
    "MAINTAIN": "maintain",
    "WRITE": "push",
    "READ": "pull",
    "TRIAGE": "triage",
}


@dataclasses.dataclass
class RepoPermChange:
    """
    A single team-repo permission change.

    :param team_slug: team slug (URL-friendly identifier)
    :param repo_full_name: full repo name (e.g. ``"org/repo"``)
    :param old_permission: current permission, ``None`` if team has no access
    :param new_permission: desired permission, ``None`` if removing access
    """

    team_slug: str = dataclasses.field()
    repo_full_name: str = dataclasses.field()
    old_permission: T.Optional[str] = dataclasses.field(default=None)
    new_permission: T.Optional[str] = dataclasses.field(default=None)


@dataclasses.dataclass
class RepoPermSyncResult:
    """
    Result of comparing desired team-repo permissions with existing state.

    :param to_add: teams that need permission added to a repo
    :param to_update: teams whose permission level needs to change
    :param to_remove: teams whose permission should be removed
    """

    to_add: list[RepoPermChange] = dataclasses.field(default_factory=list)
    to_update: list[RepoPermChange] = dataclasses.field(default_factory=list)
    to_remove: list[RepoPermChange] = dataclasses.field(default_factory=list)

    def pretty_print(self):
        """
        Pretty print the sync execution plan.
        """
        print(
            f"Summary: "
            f"🟢 Add {len(self.to_add)} | "
            f"🟡 Update {len(self.to_update)} | "
            f"🔴 Remove {len(self.to_remove)}"
        )

        if not self.to_add and not self.to_update and not self.to_remove:
            print("Already in sync, nothing to do.")
            return

        if self.to_add:
            print(f"🟢 Add ({len(self.to_add)}) ---")
            for ch in self.to_add:
                print(
                    f"  🟢 {ch.team_slug} -> {ch.repo_full_name}"
                    f" ({ch.new_permission})"
                )

        if self.to_update:
            print(f"🟡 Update ({len(self.to_update)}) ---")
            for ch in self.to_update:
                print(
                    f"  🟡 {ch.team_slug} -> {ch.repo_full_name}"
                    f" ({ch.old_permission!r} -> {ch.new_permission!r})"
                )

        if self.to_remove:
            print(f"🔴 Remove ({len(self.to_remove)}) ---")
            for ch in self.to_remove:
                print(
                    f"  🔴 {ch.team_slug} -> {ch.repo_full_name}"
                    f" (was {ch.old_permission!r})"
                )

    def execute(
        self,
        org,  # github.Organization.Organization
        delay: float = 0.1,
        add_limit: int | None = None,
        update_limit: int | None = None,
        remove_limit: int | None = None,
    ):
        """
        Execute the sync plan against the GitHub API.

        Uses PyGithub to add/update/remove team repository permissions.

        :param org: PyGithub ``Organization`` object
        :param delay: seconds to wait between API calls to avoid rate limiting
        :param add_limit: max number of add operations to execute,
            ``None`` means no limit
        :param update_limit: max number of update operations to execute,
            ``None`` means no limit
        :param remove_limit: max number of remove operations to execute,
            ``None`` means no limit
        """
        for ch in self.to_add[:add_limit]:
            team = org.get_team_by_slug(ch.team_slug)
            repo = org.get_repo(ch.repo_full_name.split("/", 1)[1])
            team.update_team_repository(repo, permission=ch.new_permission)
            time.sleep(delay)

        for ch in self.to_update[:update_limit]:
            team = org.get_team_by_slug(ch.team_slug)
            repo = org.get_repo(ch.repo_full_name.split("/", 1)[1])
            team.update_team_repository(repo, permission=ch.new_permission)
            time.sleep(delay)

        for ch in self.to_remove[:remove_limit]:
            team = org.get_team_by_slug(ch.team_slug)
            repo = org.get_repo(ch.repo_full_name.split("/", 1)[1])
            team.remove_from_repos(repo)
            time.sleep(delay)


# --- GraphQL fetch -------------------------------------------------------

_QUERY_REPOS = """\
query($org: String!, $cursor: String) {
  organization(login: $org) {
    repositories(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes { nameWithOwner }
    }
  }
}
"""

_QUERY_TEAM_REPOS = """\
query($org: String!, $teamCursor: String) {
  organization(login: $org) {
    teams(first: 100, after: $teamCursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        slug
        repositories(first: 100) {
          pageInfo { hasNextPage endCursor }
          edges {
            permission
            node { nameWithOwner }
          }
        }
      }
    }
  }
}
"""

_QUERY_TEAM_REPOS_INNER = """\
query($org: String!, $teamSlug: String!, $cursor: String) {
  organization(login: $org) {
    team(slug: $teamSlug) {
      repositories(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        edges {
          permission
          node { nameWithOwner }
        }
      }
    }
  }
}
"""


def fetch_repo_team_permissions(
    gh_token: str,
    org_name: str,
) -> tuple[list[str], dict[str, dict[str, str]]]:
    """
    Batch-fetch all repositories and team-repo permissions via GraphQL.

    This minimises API calls by using pagination rather than fetching
    per-team or per-repo via REST.

    :param gh_token: GitHub personal access token
    :param org_name: GitHub organization login name
    :return: tuple of:
        - list of all repo ``nameWithOwner`` strings
        - dict mapping ``{team_slug: {repo_full_name: permission}}``
          where permission uses REST values (admin/maintain/push/pull/triage)
    """
    # --- 1. Fetch all repos ---
    all_repos: list[str] = []
    cursor: T.Optional[str] = None
    while True:
        data = graphql_request(
            gh_token,
            _QUERY_REPOS,
            {"org": org_name, "cursor": cursor},
        )
        repos_data = data["data"]["organization"]["repositories"]
        for node in repos_data["nodes"]:
            all_repos.append(node["nameWithOwner"])
        if repos_data["pageInfo"]["hasNextPage"]:
            cursor = repos_data["pageInfo"]["endCursor"]
        else:
            break

    # --- 2. Fetch all teams and their repo permissions ---
    team_perms: dict[str, dict[str, str]] = {}
    team_cursor: T.Optional[str] = None
    teams_needing_pagination: list[str] = []

    while True:
        data = graphql_request(
            gh_token,
            _QUERY_TEAM_REPOS,
            {"org": org_name, "teamCursor": team_cursor},
        )
        teams_data = data["data"]["organization"]["teams"]
        for team_node in teams_data["nodes"]:
            slug = team_node["slug"]
            team_perms[slug] = {}
            repos_conn = team_node["repositories"]
            for edge in repos_conn["edges"]:
                perm = _GRAPHQL_TO_REST_PERMISSION.get(
                    edge["permission"], edge["permission"].lower()
                )
                team_perms[slug][edge["node"]["nameWithOwner"]] = perm
            if repos_conn["pageInfo"]["hasNextPage"]:
                teams_needing_pagination.append(slug)
        if teams_data["pageInfo"]["hasNextPage"]:
            team_cursor = teams_data["pageInfo"]["endCursor"]
        else:
            break

    # --- 3. Paginate remaining team-repo edges ---
    for slug in teams_needing_pagination:
        # We already have the first 100; fetch from the end cursor
        # Re-fetch from scratch for simplicity (first page is small overhead)
        team_perms[slug] = {}
        cursor = None
        while True:
            data = graphql_request(
                gh_token,
                _QUERY_TEAM_REPOS_INNER,
                {"org": org_name, "teamSlug": slug, "cursor": cursor},
            )
            repos_conn = data["data"]["organization"]["team"]["repositories"]
            for edge in repos_conn["edges"]:
                perm = _GRAPHQL_TO_REST_PERMISSION.get(
                    edge["permission"], edge["permission"].lower()
                )
                team_perms[slug][edge["node"]["nameWithOwner"]] = perm
            if repos_conn["pageInfo"]["hasNextPage"]:
                cursor = repos_conn["pageInfo"]["endCursor"]
            else:
                break

    return all_repos, team_perms


# --- Plan (pure logic) ---------------------------------------------------


def plan_sync_repo_permissions(
    desired: list[TeamDef],
    all_repos: list[str],
    current_perms: dict[str, dict[str, str]],
    remove_unlisted: bool = False,
) -> RepoPermSyncResult:
    """
    Compare desired team-repo permissions with current state and compute delta.

    This function does NOT call any GitHub API. It is pure logic that can be
    tested without mocking.

    Only teams in ``desired`` that have ``repo_role`` set are considered.
    For each such team, every repo in ``all_repos`` should have the
    team's ``repo_role`` permission.

    :param desired: list of :class:`TeamDef` (only those with ``repo_role``
        participate)
    :param all_repos: list of all repo ``nameWithOwner`` strings in the org
    :param current_perms: dict ``{team_slug: {repo_full_name: permission}}``
        representing current state on GitHub
    :param remove_unlisted: if ``True``, repos in ``current_perms`` for a
        desired team that are NOT in ``all_repos`` will be marked for removal.
        Default ``False`` for safety.
    :return: a :class:`RepoPermSyncResult` with add/update/remove lists
    """
    to_add: list[RepoPermChange] = []
    to_update: list[RepoPermChange] = []
    to_remove: list[RepoPermChange] = []

    all_repos_set = set(all_repos)

    for td in desired:
        if td.repo_role is None:
            continue

        slug = td.slug
        team_current = current_perms.get(slug, {})

        for repo in all_repos:
            current_perm = team_current.get(repo)
            if current_perm is None:
                # Team has no permission on this repo
                to_add.append(
                    RepoPermChange(
                        team_slug=slug,
                        repo_full_name=repo,
                        old_permission=None,
                        new_permission=td.repo_role,
                    )
                )
            elif current_perm != td.repo_role:
                # Team has wrong permission level
                to_update.append(
                    RepoPermChange(
                        team_slug=slug,
                        repo_full_name=repo,
                        old_permission=current_perm,
                        new_permission=td.repo_role,
                    )
                )
            # else: already correct, skip

        if remove_unlisted:
            for repo, perm in team_current.items():
                if repo not in all_repos_set:
                    to_remove.append(
                        RepoPermChange(
                            team_slug=slug,
                            repo_full_name=repo,
                            old_permission=perm,
                            new_permission=None,
                        )
                    )

    return RepoPermSyncResult(
        to_add=to_add,
        to_update=to_update,
        to_remove=to_remove,
    )


# --- Orchestrator ---------------------------------------------------------


def sync_repo_permissions(
    gh_token: str,
    org,  # github.Organization.Organization
    desired: list[TeamDef],
    plan_mode: bool = True,
    delay: float = 0.1,
    add_limit: int | None = None,
    update_limit: int | None = None,
    remove_limit: int | None = None,
) -> RepoPermSyncResult:
    """
    Sync GitHub team-repo permissions to match desired definitions.

    Workflow:

    1. Batch-fetch all repos and team permissions via GraphQL
    2. Compare with desired using :func:`plan_sync_repo_permissions`
    3. If ``plan_mode`` is ``True``, only print the execution plan
    4. Otherwise, execute the plan via :meth:`RepoPermSyncResult.execute`

    Only teams in ``desired`` that have ``repo_role`` set participate.

    :param gh_token: GitHub personal access token (needed for GraphQL)
    :param org: PyGithub ``Organization`` object (needed for REST writes)
    :param desired: list of desired :class:`TeamDef`
    :param plan_mode: if ``True``, only pretty-print the execution plan
        without making any API changes
    :param delay: seconds to wait between API calls to avoid rate limiting
    :param add_limit: max number of add operations to execute,
        ``None`` means no limit
    :param update_limit: max number of update operations to execute,
        ``None`` means no limit
    :param remove_limit: max number of remove operations to execute,
        ``None`` means no limit
    :return: a :class:`RepoPermSyncResult` describing what was (or would be) done
    """
    org_name = org.login
    all_repos, current_perms = fetch_repo_team_permissions(gh_token, org_name)
    result = plan_sync_repo_permissions(desired, all_repos, current_perms)
    result.pretty_print()
    if plan_mode is False:
        result.execute(
            org,
            delay=delay,
            add_limit=add_limit,
            update_limit=update_limit,
            remove_limit=remove_limit,
        )
    return result
