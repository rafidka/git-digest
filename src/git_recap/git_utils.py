from dataclasses import dataclass
from datetime import datetime
from typing import Any

from git import Repo


@dataclass
class GitCommit:
    """Git commit data container."""
    hash: str
    author: str
    email: str
    date: datetime
    message: str
    files_changed: list[str]


class GitCommitRetriever:
    """Utility to retrieve and parse git commits."""
    def __init__(self, repo_path: str = "."):
        self.repo = Repo(repo_path)

    def get_commits(
        self, since: str | None = None, until: str | None = None
    ) -> list[GitCommit]:
        """
        Retrieve git commits within a date range.

        Args:
            since: Start date (e.g., "2024-01-01", "1 week ago", "yesterday")
            until: End date (e.g., "2024-01-31", "today")

        Returns:
            List of GitCommit objects
        """
        kwargs: dict[str, Any] = {}
        if since:
            kwargs["since"] = since
        if until:
            kwargs["until"] = until

        commits: list[GitCommit] = []
        for commit in self.repo.iter_commits(**kwargs):
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
                    if hasattr(item, "type") and getattr(item, "type", None) == "blob":  # It's a file
                        item_path = getattr(item, "path", "")
                        if item_path:
                            files_changed.append(str(item_path))

            commits.append(
                GitCommit(
                    hash=commit.hexsha,
                    author=commit.author.name or "Unknown",
                    email=commit.author.email or "unknown@example.com",
                    date=datetime.fromtimestamp(commit.committed_date),
                    message=commit.message.strip() if isinstance(commit.message, str) else commit.message.decode().strip(),
                    files_changed=files_changed,
                )
            )

        return commits

    def get_recent_commits(self, days: int = 7) -> list[GitCommit]:
        """Get commits from the last N days."""
        return self.get_commits(since=f"{days} days ago")
