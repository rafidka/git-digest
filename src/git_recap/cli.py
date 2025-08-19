import logging
import os
from collections import defaultdict
from enum import Enum
from pathlib import Path

import typer
from openai import OpenAI

from .git_utils import GitCommit, GitCommitRetriever

logger = logging.getLogger(__name__)


class Provider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    COHERE = "cohere"
    ANTHROPIC = "anthropic"


# Provider configurations
PROVIDERS = {
    Provider.OPENAI: {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-5",
    },
    Provider.COHERE: {
        "base_url": "https://api.cohere.ai/compatibility/v1",
        "api_key_env": "COHERE_API_KEY",
        "default_model": "command-a-03-2025",
    },
    Provider.ANTHROPIC: {
        "base_url": "https://api.anthropic.com/v1/",
        "api_key_env": "ANTHROPIC_API_KEY",
        "default_model": "claude-opus-4-1-20250805",
    },
}

app = typer.Typer()


def setup_logging(debug: bool = False) -> None:
    """Configure logging based on debug flag."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_llm_client(provider: Provider) -> tuple[OpenAI, str]:
    """Initialize LLM client using OpenAI SDK for the specified provider."""
    config = PROVIDERS[provider]
    api_key_env = config["api_key_env"]

    api_key = os.getenv(api_key_env)
    if not api_key:
        logger.error(f"{api_key_env} environment variable not set")
        raise typer.Exit(1)

    logger.debug(f"Initializing {provider} client with OpenAI SDK")
    client = OpenAI(base_url=config["base_url"], api_key=api_key)
    model = config["default_model"]

    return client, model


def format_commits_for_llm(commits: list[GitCommit]) -> str:
    """Format git commits for LLM processing."""
    if not commits:
        return "No commits found in the specified date range."

    formatted: list[str] = []
    for commit in commits:
        files_str = (
            ", ".join(commit.files_changed)
            if commit.files_changed
            else "No files changed"
        )
        formatted.append(
            f"Commit: {commit.hash[:8]} ({commit.repo_name})\n"
            f"Author: {commit.author} <{commit.email}>\n"
            f"Date: {commit.date.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Message: {commit.message}\n"
            f"Files: {files_str}\n"
        )

    return "\n---\n".join(formatted)


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


def process_single_repository(
    repo_path: str, 
    since: str | None = None, 
    until: str | None = None, 
    days: int | None = None, 
    count: int | None = None
) -> list[GitCommit]:
    """Process a single repository and return commits based on filters."""
    logger.debug(f"Processing repository: {repo_path}")
    retriever = GitCommitRetriever(repo_path)
    
    # Parameter precedence: count > days > since/until > default
    if count is not None:
        logger.debug(f"Getting last {count} commits from {Path(repo_path).name}")
        return retriever.get_recent_commits_by_count(count)
    elif days is not None:
        logger.debug(f"Getting commits from last {days} days from {Path(repo_path).name}")
        return retriever.get_recent_commits(days)
    elif since or until:
        logger.debug(f"Getting commits with date filters from {Path(repo_path).name}")
        return retriever.get_commits(since=since, until=until)
    else:
        logger.debug(f"Getting commits from last 7 days from {Path(repo_path).name}")
        return retriever.get_recent_commits(7)


def aggregate_commits_from_repos(
    repo_paths: list[str],
    since: str | None = None,
    until: str | None = None, 
    days: int | None = None,
    count: int | None = None
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


def group_commits_by_author(commits: list[GitCommit]) -> dict[str, list[GitCommit]]:
    """Group commits by author email."""
    author_commits: dict[str, list[GitCommit]] = defaultdict(list)
    for commit in commits:
        author_key = f"{commit.author} <{commit.email}>"
        author_commits[author_key].append(commit)
    return dict(author_commits)


def summarize_with_llm(commits_text: str, provider: Provider, repo_names: list[str]) -> str:
    """Use LLM to summarize git commits from multiple repositories."""
    client, model = get_llm_client(provider)

    if len(repo_names) > 1:
        repo_context = f"from {len(repo_names)} repositories: {', '.join(repo_names)}"
        multi_repo_instruction = """

Look for related work across repositories and identify:
1. Major features or initiatives that span multiple repositories
2. Coordinated changes and how they work together  
3. Cross-repository dependencies and integration work
4. Overall development themes and architectural decisions"""
    else:
        repo_context = f"from repository: {repo_names[0]}"
        multi_repo_instruction = ""

    prompt = f"""Analyze the following git commits {repo_context}.

Provide a clear, human-readable development summary that focuses on:
- Key changes, features added, and bugs fixed
- Overall development progress and milestones
- Important architectural or design decisions{multi_repo_instruction}

Git commits:
{commits_text}

Summary:"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.choices[0].message.content
        return content.strip() if content else ""

    except Exception as e:
        logger.error(f"Error calling {provider} API: {str(e)}")
        raise typer.Exit(1)


def summarize_by_author(
    author_commits: dict[str, list[GitCommit]], provider: Provider
) -> str:
    """Generate author-specific summaries using LLM."""
    client, model = get_llm_client(provider)

    summaries: list[str] = []
    
    # Collect repository info for context (not used in current implementation)
    all_repos: set[str] = set()
    for commits in author_commits.values():
        for commit in commits:
            if commit.repo_name:
                all_repos.add(commit.repo_name)

    for author, commits in author_commits.items():
        logger.debug(f"Generating summary for {author} ({len(commits)} commits)")

        commits_text = format_commits_for_llm(commits)
        
        # Count repositories this author worked in
        author_repos = set(commit.repo_name for commit in commits if commit.repo_name)
        repo_count = len(author_repos)
        
        if repo_count > 1:
            multi_repo_context = f"""
This author worked across {repo_count} repositories: {', '.join(sorted(author_repos))}.
Look for related work across repositories and explain how their changes work together.
Identify cross-repository coordination and the bigger picture of their contributions."""
        else:
            multi_repo_context = ""

        prompt = f"""Provide a comprehensive summary of contributions made by {author}.

Focus on the key changes, features, and improvements they implemented.
Be specific about what they accomplished and the impact of their work.{multi_repo_context}

Commits by {author}:
{commits_text}

Summary for {author}:"""

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.choices[0].message.content
            author_summary = content.strip() if content else ""

            commit_count = len(commits)
            commit_word = "commit" if commit_count == 1 else "commits"

            summaries.append(
                f"## {author} ({commit_count} {commit_word})\n\n{author_summary}"
            )

        except Exception as e:
            logger.error(
                f"Error generating summary for {author} using {provider}: {str(e)}"
            )
            summaries.append(
                f"## {author} ({len(commits)} commits)\n\nError generating summary for this author."
            )

    return "\n\n".join(summaries)


@app.command()
def recap(
    repo_paths: list[str] = typer.Argument(help="Paths to git repositories (defaults to current directory)"),
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
        Provider.OPENAI,
        "--provider",
        help="LLM provider to use (openai, cohere, anthropic)",
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
    
    logger.debug(
        f"Command arguments: repo_paths={repo_paths}, since={since}, until={until}, days={days}, count={count}, by_author={by_author}, provider={provider}"
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
        logger.info(f"Analyzing {len(valid_repos)} repositories: {', '.join(repo_names)}")
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

        logger.info(f"Found {len(commits)} total commits across {len(valid_repos)} repositories. Generating summary...")

        if by_author:
            logger.debug("Grouping commits by author")
            author_commits = group_commits_by_author(commits)
            logger.info(f"Found {len(author_commits)} unique authors")

            logger.debug("Generating author-specific summaries")
            summary = summarize_by_author(author_commits, provider)

            print("\n" + "=" * 60)
            print("GIT RECAP SUMMARY - BY AUTHOR")
            print("=" * 60)
            print(summary)
            print("=" * 60)
        else:
            logger.debug("Formatting commits for LLM processing")
            commits_text = format_commits_for_llm(commits)
            logger.debug("Calling LLM for summary generation")
            summary = summarize_with_llm(commits_text, provider, repo_names)

            print("\n" + "=" * 50)
            if len(repo_names) > 1:
                print(f"GIT RECAP SUMMARY - {len(repo_names)} REPOSITORIES")
            else:
                print("GIT RECAP SUMMARY")
            print("=" * 50)
            print(summary)
            print("=" * 50)

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
