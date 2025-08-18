from dataclasses import dataclass
from datetime import datetime

from git import Repo


@dataclass
class GitCommit:
    hash: str
    author: str
    email: str
    date: datetime
    message: str
    files_changed: list[str]


class GitCommitRetriever:
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
        kwargs = {}
        if since:
            kwargs["since"] = since
        if until:
            kwargs["until"] = until

        commits = []
        for commit in self.repo.iter_commits(**kwargs):
            # Get list of files changed in this commit
            files_changed = []
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
                    if item.type == "blob":  # It's a file
                        files_changed.append(item.path)

            commits.append(
                GitCommit(
                    hash=commit.hexsha,
                    author=commit.author.name,
                    email=commit.author.email,
                    date=datetime.fromtimestamp(commit.committed_date),
                    message=commit.message.strip(),
                    files_changed=files_changed,
                )
            )

        return commits

    def get_recent_commits(self, days: int = 7) -> list[GitCommit]:
        """Get commits from the last N days."""
        return self.get_commits(since=f"{days} days ago")
