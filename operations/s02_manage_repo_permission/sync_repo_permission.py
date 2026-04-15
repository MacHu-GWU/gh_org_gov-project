# -*- coding: utf-8 -*-

"""
Sync GitHub team-repo permissions from the local TSV file.

For each team with a ``repo_role`` defined, this script ensures
every repository in the organization has the correct team permission.

Usage::

    python operations/s02_manage_repo_permission/sync_repo_permission.py
"""

from pathlib import Path

from github import Github

from gh_org_gov.tests.config import Config
from gh_org_gov.team_def import load_team_defs_from_tsv
from gh_org_gov.repo import sync_repo_permissions

# --- Paths ---
dir_here = Path(__file__).absolute().parent
dir_s01 = dir_here.parent / "s01_manage_team_def"
path_team_def_tsv = dir_s01 / "team_def.tsv"

# --- Main ---
if __name__ == "__main__":
    # Load config (token + org name)
    config = Config.load()
    gh = Github(config.github_token)
    org = gh.get_organization(config.github_org_name)

    # Load desired team definitions from TSV
    desired = load_team_defs_from_tsv(path_team_def_tsv)
    teams_with_role = [td for td in desired if td.repo_role]

    print(f"Org: {config.github_org_name}")
    print(f"TSV: {path_team_def_tsv}")
    print(f"Teams with repo_role: {[(td.name, td.repo_role) for td in teams_with_role]}")
    print()

    # Sync — real_run=False by default for safety (dry run)
    result = sync_repo_permissions(
        gh_token=config.github_token,
        org=org,
        desired=desired,
        # real_run=False,
        real_run=True,
        add_limit=1,
        update_limit=1,
        remove_limit=1,
    )
