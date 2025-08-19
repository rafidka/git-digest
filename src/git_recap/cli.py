import logging
from pathlib import Path

import typer

from git_recap.types import Provider
from git_recap.utils.git import (
    aggregate_commits_from_repos,
    filter_commits_by_authors,
    group_commits_by_author,
    validate_repositories,
)
from git_recap.utils.llm import (
    format_commits_for_llm,
    summarize,
    summarize_by_author,
)

logger = logging.getLogger(__name__)


# Provider configurations
app = typer.Typer()


def setup_logging(debug: bool = False) -> None:
    """Configure logging based on debug flag."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.command()
def recap(
    repo_paths: list[str] = typer.Argument(
        help="Paths to git repositories (defaults to current directory)"
    ),
    since: str | None = typer.Option(
        None,
        "--since",
        "-s",
        help="Start date (e.g., '2024-01-01', '1 week ago', 'yesterday')",
    ),
    until: str | None = typer.Option(
        None, "--until", "-u", help="End date (e.g., '2024-01-31', 'today')"
    ),
    days: int | None = typer.Option(
        None,
        "--days",
        "-d",
        help="Get commits from the last N days (overrides since/until)",
    ),
    count: int | None = typer.Option(
        None,
        "--count",
        "-c",
        help="Get the last N commits (overrides since/until/days)",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug logging",
    ),
    by_author: bool = typer.Option(
        False,
        "--by-author",
        help="Group summary by author instead of chronological overview",
    ),
    provider: Provider = typer.Option(
        Provider.COHERE,
        "--provider",
        help="LLM provider to use (openai, cohere, anthropic)",
    ),
    authors: list[str] = typer.Option(
        [],
        "--authors",
        help="Filter commits by author names (partial matching, case-insensitive). Supports comma-separated values: --authors 'Alice,Bob' or multiple flags: --authors Alice --authors Bob",
    ),
):
    """
    Generate a human-readable summary of recent git commits.
    """
    setup_logging(debug)
    if debug:
        logger.debug("Starting git-recap with debug logging enabled")

    # Default to current directory if no paths provided
    if not repo_paths:
        repo_paths = ["."]

    # Parse comma-separated author names and flatten the list
    parsed_authors: list[str] = []
    for author_arg in authors:
        # Split by comma and strip whitespace
        split_authors = [a.strip() for a in author_arg.split(",") if a.strip()]
        parsed_authors.extend(split_authors)

    logger.debug(
        f"Command arguments: repo_paths={repo_paths}, since={since}, until={until}, days={days}, count={count}, by_author={by_author}, provider={provider}, authors={parsed_authors}"
    )

    # Validate repositories
    valid_repos, error_messages = validate_repositories(repo_paths)

    if error_messages:
        for error in error_messages:
            logger.error(error)

    if not valid_repos:
        logger.error("No valid repositories found")
        raise typer.Exit(1)

    repo_names = [Path(repo).name for repo in valid_repos]
    if len(valid_repos) > 1:
        logger.info(
            f"Analyzing {len(valid_repos)} repositories: {', '.join(repo_names)}"
        )
    else:
        logger.info(f"Analyzing repository: {repo_names[0]}")

    try:
        # Aggregate commits from all repositories
        logger.debug("Aggregating commits from repositories")
        commits = aggregate_commits_from_repos(valid_repos, since, until, days, count)

        if not commits:
            if count is not None:
                logger.warning("No commits found in any repository.")
            else:
                logger.warning("No commits found in the specified date range.")
            return

        # Apply author filtering if specified
        original_commit_count = len(commits)
        if parsed_authors:
            logger.debug(f"Filtering commits by authors: {', '.join(parsed_authors)}")
            commits, author_matches = filter_commits_by_authors(commits, parsed_authors)

            # Log matching results
            matched_filters: list[str] = []
            unmatched_filters: list[str] = []
            for filter_name, matched_authors in author_matches.items():
                if matched_authors:
                    matched_filters.append(
                        f"{filter_name} ({len(set(matched_authors))} unique authors)"
                    )
                else:
                    unmatched_filters.append(filter_name)

            if matched_filters:
                logger.info(f"Author filter matches: {', '.join(matched_filters)}")
            if unmatched_filters:
                logger.warning(
                    f"No commits found for author filters: {', '.join(unmatched_filters)}"
                )

            logger.info(
                f"Filtered to {len(commits)} commits from {original_commit_count} total"
            )

        if not commits:
            if parsed_authors:
                logger.warning(
                    "No commits found matching the specified author filters."
                )
            elif count is not None:
                logger.warning("No commits found in any repository.")
            else:
                logger.warning("No commits found in the specified date range.")
            return

        logger.info(
            f"Found {len(commits)} commits across {len(valid_repos)} repositories. Generating summary..."
        )

        if by_author:
            logger.debug("Grouping commits by author")
            author_commits = group_commits_by_author(commits)
            logger.info(f"Found {len(author_commits)} unique authors")

            logger.debug("Generating author-specific summaries")
            summary = summarize_by_author(author_commits, provider)

            print("\n" + "=" * 60)
            header = "GIT RECAP SUMMARY - BY AUTHOR"
            if parsed_authors:
                header += " (FILTERED)"
            print(header)
            print("=" * 60)
            print(summary)
            print("=" * 60)
        else:
            logger.debug("Formatting commits for LLM processing")
            commits_text = format_commits_for_llm(commits)
            logger.debug("Calling LLM for summary generation")
            summary = summarize(commits_text, provider, repo_names)

            print("\n" + "=" * 50)
            if len(repo_names) > 1:
                header = f"GIT RECAP SUMMARY - {len(repo_names)} REPOSITORIES"
            else:
                header = "GIT RECAP SUMMARY"
            if parsed_authors:
                header += " (FILTERED)"
            print(header)
            print("=" * 50)
            print(summary)
            print("=" * 50)

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
