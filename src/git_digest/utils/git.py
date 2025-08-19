import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from git import Repo

logger = logging.getLogger(__name__)


@dataclass
class GitCommit:
    """Git commit data container."""

    hash: str
    author: str
    email: str
    date: datetime
    message: str
    files_changed: list[str]
    repo_name: str = ""


def validate_repositories(repo_paths: list[str]) -> tuple[list[str], list[str]]:
    """Validate repository paths and return (valid_paths, error_messages)."""
    valid_paths: list[str] = []
    error_messages: list[str] = []

    for repo_path in repo_paths:
        repo_path_obj = Path(repo_path)
        if not repo_path_obj.exists():
            error_messages.append(f"Repository path '{repo_path}' does not exist")
        elif not (repo_path_obj / ".git").exists():
            error_messages.append(f"'{repo_path}' is not a git repository")
        else:
            valid_paths.append(repo_path)

    return valid_paths, error_messages


def get_commits(
    repo_path: str, since: str | None = None, until: str | None = None
) -> list[GitCommit]:
    """
    Retrieve git commits within a date range.

    Args:
        repo_path: Path to the git repository
        since: Start date (e.g., "2024-01-01", "1 week ago", "yesterday")
        until: End date (e.g., "2024-01-31", "today")

    Returns:
        List of GitCommit objects
    """
    repo = Repo(repo_path)
    repo_name = Path(repo_path).name

    kwargs: dict[str, Any] = {}
    if since:
        kwargs["since"] = since
    if until:
        kwargs["until"] = until

    commits: list[GitCommit] = []
    for commit in repo.iter_commits(**kwargs):
        # Get list of files changed in this commit
        files_changed: list[str] = []
        if commit.parents:
            # Compare with first parent to get changed files
            for diff in commit.diff(commit.parents[0]):
                if diff.a_path:
                    files_changed.append(diff.a_path)
                if diff.b_path and diff.b_path != diff.a_path:
                    files_changed.append(diff.b_path)
        else:
            # Initial commit - all files are "changed"
            for item in commit.tree.traverse():
                if (
                    hasattr(item, "type") and getattr(item, "type", None) == "blob"
                ):  # It's a file
                    item_path = getattr(item, "path", "")
                    if item_path:
                        files_changed.append(str(item_path))

        commits.append(
            GitCommit(
                hash=commit.hexsha,
                author=commit.author.name or "Unknown",
                email=commit.author.email or "unknown@example.com",
                date=datetime.fromtimestamp(commit.committed_date),
                message=commit.message.strip()
                if isinstance(commit.message, str)
                else commit.message.decode().strip(),
                files_changed=files_changed,
                repo_name=repo_name,
            )
        )

    return commits


def get_recent_commits(repo_path: str, days: int = 7) -> list[GitCommit]:
    """Get commits from the last N days."""
    return get_commits(repo_path, since=f"{days} days ago")


def get_recent_commits_by_count(repo_path: str, count: int) -> list[GitCommit]:
    """Get the last N commits regardless of date."""
    repo = Repo(repo_path)
    repo_name = Path(repo_path).name

    commits: list[GitCommit] = []
    for commit in repo.iter_commits(max_count=count):
        # Get list of files changed in this commit
        files_changed: list[str] = []
        if commit.parents:
            # Compare with first parent to get changed files
            for diff in commit.diff(commit.parents[0]):
                if diff.a_path:
                    files_changed.append(diff.a_path)
                if diff.b_path and diff.b_path != diff.a_path:
                    files_changed.append(diff.b_path)
        else:
            # Initial commit - all files are "changed"
            for item in commit.tree.traverse():
                if (
                    hasattr(item, "type") and getattr(item, "type", None) == "blob"
                ):  # It's a file
                    item_path = getattr(item, "path", "")
                    if item_path:
                        files_changed.append(str(item_path))

        commits.append(
            GitCommit(
                hash=commit.hexsha,
                author=commit.author.name or "Unknown",
                email=commit.author.email or "unknown@example.com",
                date=datetime.fromtimestamp(commit.committed_date),
                message=commit.message.strip()
                if isinstance(commit.message, str)
                else commit.message.decode().strip(),
                files_changed=files_changed,
                repo_name=repo_name,
            )
        )

    return commits


def process_single_repository(
    repo_path: str,
    since: str | None = None,
    until: str | None = None,
    days: int | None = None,
    count: int | None = None,
) -> list[GitCommit]:
    """Process a single repository and return commits based on filters."""
    logger.debug(f"Processing repository: {repo_path}")

    # Parameter precedence: count > days > since/until > default
    if count is not None:
        logger.debug(f"Getting last {count} commits from {Path(repo_path).name}")
        return get_recent_commits_by_count(repo_path, count)
    elif days is not None:
        logger.debug(
            f"Getting commits from last {days} days from {Path(repo_path).name}"
        )
        return get_recent_commits(repo_path, days)
    elif since or until:
        logger.debug(f"Getting commits with date filters from {Path(repo_path).name}")
        return get_commits(repo_path, since=since, until=until)
    else:
        logger.debug(f"Getting commits from last 7 days from {Path(repo_path).name}")
        return get_recent_commits(repo_path, 7)


def aggregate_commits_from_repos(
    repo_paths: list[str],
    since: str | None = None,
    until: str | None = None,
    days: int | None = None,
    count: int | None = None,
) -> list[GitCommit]:
    """Aggregate commits from multiple repositories."""
    all_commits: list[GitCommit] = []
    repo_stats: list[str] = []

    for repo_path in repo_paths:
        try:
            commits = process_single_repository(repo_path, since, until, days, count)
            all_commits.extend(commits)
            repo_name = Path(repo_path).name
            repo_stats.append(f"{repo_name}: {len(commits)} commits")
        except Exception as e:
            logger.error(f"Failed to process repository '{repo_path}': {str(e)}")
            continue

    if repo_stats:
        logger.info(f"Repository statistics: {', '.join(repo_stats)}")

    # Sort by date (newest first) for chronological consistency
    all_commits.sort(key=lambda c: c.date, reverse=True)

    return all_commits


def filter_commits_by_authors(
    commits: list[GitCommit], author_filters: list[str]
) -> tuple[list[GitCommit], dict[str, list[str]]]:
    """
    Filter commits by author names using partial matching.

    Returns:
        tuple[filtered_commits, {filter: [matched_authors]}]
    """
    if not author_filters:
        return commits, {}

    # Convert filters to lowercase for case-insensitive matching
    filters_lower = [f.lower() for f in author_filters]

    filtered_commits: list[GitCommit] = []
    matches_per_filter: dict[str, set[str]] = {f: set() for f in author_filters}

    for commit in commits:
        author_info = f"{commit.author} <{commit.email}>".lower()

        # Check if any filter matches this commit's author info
        for original_filter, filter_lower in zip(author_filters, filters_lower):
            if filter_lower in author_info:
                filtered_commits.append(commit)
                matches_per_filter[original_filter].add(
                    f"{commit.author} <{commit.email}>"
                )
                break  # Don't duplicate commits if multiple filters match

    # Convert sets to lists for return value
    matches_dict = {f: list(matches) for f, matches in matches_per_filter.items()}

    return filtered_commits, matches_dict


def group_commits_by_author(commits: list[GitCommit]) -> dict[str, list[GitCommit]]:
    """Group commits by author email."""
    author_commits: dict[str, list[GitCommit]] = defaultdict(list)
    for commit in commits:
        author_key = f"{commit.author} <{commit.email}>"
        author_commits[author_key].append(commit)
    return dict(author_commits)
