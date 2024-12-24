import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
import sys
import time

bitbucket_baseurl = "https://coderepo.appslatam.com"

projects = [
    "XPCLOUD",
    "XPLIBRARIES",
    "XPACL",
    "XPDAT",
    "XPPOC",
    "XPBAC",
    "XPTC",
    "XPNDC",
    "XPMIC",
    "XPD2DEFFICIENTINFO",
    "XPBC",
    "XPOCORP",
    "XPST",
    "XPOEN",
    "XPMOBILE",
    "XPTES",
    "XPOFUL",
    "XPINFRA",
    "XPOOF",
    "XPUPC",
    "XPDPRE",
    "XPOOR",
    "XPOORC",
    "XPAF",
    "XPDINC",
    "XPEWAL",
    "XPOAWARDS",
    "XPCONFIG",
    "PRIN",
    "XPARQ",
    "SL",
]


def get_repositories(auth, project_key):
    repos = []
    url = f"{bitbucket_baseurl}/rest/api/1.0/projects/{project_key}/repos"
    while url:
        response = make_request(url, auth)
        data = response.json()
        repos.extend(data["values"])
        url = data.get("nextPageStart")
        if url:
            url = f"{bitbucket_baseurl}/rest/api/1.0/projects/{project_key}/repos?start={url}"
    return repos


def is_archived(auth, project_key, repo_slug):
    url = f"{bitbucket_baseurl}/rest/api/1.0/projects/{project_key}/repos/{repo_slug}"
    response = make_request(url, auth)
    return response.json().get("archived", False)


def has_gitlab_label(auth, project_key, repo_slug):
    url = f"{bitbucket_baseurl}/rest/api/1.0/projects/{project_key}/repos/{repo_slug}/labels"
    response = make_request(url, auth)
    labels = response.json()["values"]
    return any("gitlab" in label["name"].lower() for label in labels)


def make_request(url, auth, retries=5, backoff_factor=1):
    for retry in range(retries):
        try:
            response = requests.get(url, auth=auth)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                wait_time = backoff_factor * (2**retry)
                print(
                    f"Rate limit exceeded. Retrying in {wait_time} seconds...",
                    file=sys.stderr,
                )
                time.sleep(wait_time)
            else:
                raise
    raise requests.exceptions.HTTPError(
        f"Failed to get a successful response after {retries} retries."
    )


def process_repo(auth, project_key, repo):
    archived = is_archived(auth, project_key, repo["slug"])
    gitlab_label = False
    if archived:
        gitlab_label = has_gitlab_label(auth, project_key, repo["slug"])
    return archived, gitlab_label


def main():
    parser = argparse.ArgumentParser(description="Process some Bitbucket repositories.")
    parser.add_argument("username", type=str, help="The Bitbucket username")
    parser.add_argument("password", type=str, help="The Bitbucket password")

    args = parser.parse_args()

    auth = (args.username, args.password)

    total_repos = 0
    total_archived_with_gitlab_label = 0
    total_repository_by_project = {}

    for project in projects:
        repos = get_repositories(auth, project)
        repo_count = len(repos)
        total_repos += repo_count

        archived_with_gitlab_label = 0
        with ThreadPoolExecutor(max_workers=7) as executor:
            futures = [
                executor.submit(process_repo, auth, project, repo) for repo in repos
            ]
            for future in as_completed(futures):
                archived, gitlab_label = future.result()
                if archived and gitlab_label:
                    archived_with_gitlab_label += 1
                    total_archived_with_gitlab_label += 1

        total_repository_by_project[project] = {
            "total_repository": repo_count,
            "total_repository_migrated": archived_with_gitlab_label,
        }
        print(
            f'Project: {project}, Total Repositories: {repo_count}, Archived Repositories with "gitlab" label: {archived_with_gitlab_label}',
            file=sys.stderr,
        )

    output = {
        "total_repositories": total_repos,
        "total_archived_repositories_with_gitlab_label": total_archived_with_gitlab_label,
        "total_repository_by_project": total_repository_by_project,
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
