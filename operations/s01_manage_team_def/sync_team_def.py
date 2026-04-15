# -*- coding: utf-8 -*-

"""
Sync GitHub org team definitions from the local TSV file.

Usage::

    python operations/s01_manage_team_def/sync_team_def.py
"""

from pathlib import Path

from github import Github

from gh_org_gov.tests.config import Config
from gh_org_gov.team_def import load_team_defs_from_tsv
from gh_org_gov.team import sync_teams

# --- Paths ---
dir_here = Path(__file__).absolute().parent
path_team_def_tsv = dir_here / "team_def.tsv"

# --- Main ---
if __name__ == "__main__":
    # Load config (token + org name)
    config = Config.load()
    gh = Github(config.github_token)
    org = gh.get_organization(config.github_org_name)

    # Load desired team definitions from TSV
    desired = load_team_defs_from_tsv(path_team_def_tsv)

    print(f"Org: {config.github_org_name}")
    print(f"TSV: {path_team_def_tsv}")
    print(f"Teams to sync: {[td.name for td in desired]}")
    print()

    # Sync — delete_orphans=False by default for safety
    result = sync_teams(
        org,
        desired,
        delete_orphans=False,
        plan_mode=True,
    )

    # # Report
    # if result.to_create:
    #     print(f"Created: {[td.name for td in result.to_create]}")
    # if result.to_update:
    #     for td, changes in result.to_update:
    #         print(f"Updated: {td.name} — {list(changes.keys())}")
    # if result.to_delete:
    #     print(f"Deleted: {result.to_delete}")
    # if not result.to_create and not result.to_update and not result.to_delete:
    #     print("Already in sync, nothing to do.")
