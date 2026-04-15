# -*- coding: utf-8 -*-

"""
GitHub client for API requests.
"""

import requests
from github import Github, Auth


def get_github(gh_token: str) -> Github:
    """
    Create an authenticated PyGithub client instance.

    :param gh_token: GitHub personal access token.
    :return: Authenticated Github client.
    """
    return Github(auth=Auth.Token(gh_token))


def graphql_request(
    gh_token: str,
    query: str,
    variables: dict | None = None,
) -> dict:
    """
    Send a GraphQL request to the GitHub API.

    :param gh_token: GitHub personal access token.
    :param query: GraphQL query string.
    :param variables: Optional dictionary of query variables.
    :return: JSON response as a dictionary.
    """
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables or {}},
        headers=headers,
    )
    response.raise_for_status()
    return response.json()
