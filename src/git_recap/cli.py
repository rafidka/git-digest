import logging
import os
from collections import defaultdict
from pathlib import Path

import typer
from openai import OpenAI

from .git_utils import GitCommit, GitCommitRetriever

logger = logging.getLogger(__name__)

app = typer.Typer()


def setup_logging(debug: bool = False) -> None:
    """Configure logging based on debug flag."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_cohere_client() -> OpenAI:
    """Initialize Cohere client using OpenAI SDK."""
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        logger.error("COHERE_API_KEY environment variable not set")
        raise typer.Exit(1)

    logger.debug("Initializing Cohere client with OpenAI SDK")
    return OpenAI(base_url="https://api.cohere.ai/compatibility/v1", api_key=api_key)


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
            f"Commit: {commit.hash[:8]}\n"
            f"Author: {commit.author} <{commit.email}>\n"
            f"Date: {commit.date.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Message: {commit.message}\n"
            f"Files: {files_str}\n"
        )

    return "\n---\n".join(formatted)


def group_commits_by_author(commits: list[GitCommit]) -> dict[str, list[GitCommit]]:
    """Group commits by author email."""
    author_commits: dict[str, list[GitCommit]] = defaultdict(list)
    for commit in commits:
        author_key = f"{commit.author} <{commit.email}>"
        author_commits[author_key].append(commit)
    return dict(author_commits)


def summarize_with_llm(commits_text: str) -> str:
    """Use Cohere to summarize git commits."""
    client = get_cohere_client()

    prompt = f"""Please provide a clear, human-readable summary of the following git commits. 
Focus on the key changes, features added, bugs fixed, and overall development progress.
Group related changes together and highlight the most important updates.

Git commits:
{commits_text}

Summary:"""

    try:
        response = client.chat.completions.create(
            model="command-r-plus",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.3,
        )

        content = response.choices[0].message.content
        return content.strip() if content else ""

    except Exception as e:
        logger.error(f"Error calling Cohere API: {str(e)}")
        raise typer.Exit(1)


def summarize_by_author(author_commits: dict[str, list[GitCommit]]) -> str:
    """Generate author-specific summaries using LLM."""
    client = get_cohere_client()
    
    summaries: list[str] = []
    
    for author, commits in author_commits.items():
        logger.debug(f"Generating summary for {author} ({len(commits)} commits)")
        
        commits_text = format_commits_for_llm(commits)
        
        prompt = f"""Please provide a concise summary of the contributions made by {author}.
Focus on the key changes, features, and improvements they implemented.
Be specific about what they accomplished.

Commits by {author}:
{commits_text}

Summary for {author}:"""
        
        try:
            response = client.chat.completions.create(
                model="command-r-plus",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3,
            )
            
            content = response.choices[0].message.content
            author_summary = content.strip() if content else ""
            
            commit_count = len(commits)
            commit_word = "commit" if commit_count == 1 else "commits"
            
            summaries.append(
                f"## {author} ({commit_count} {commit_word})\n\n{author_summary}"
            )
            
        except Exception as e:
            logger.error(f"Error generating summary for {author}: {str(e)}")
            summaries.append(
                f"## {author} ({len(commits)} commits)\n\nError generating summary for this author."
            )
    
    return "\n\n".join(summaries)


@app.command()
def recap(
    repo_path: str = typer.Argument(".", help="Path to the git repository"),
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
):
    """
    Generate a human-readable summary of recent git commits.
    """
    setup_logging(debug)
    if debug:
        logger.debug("Starting git-recap with debug logging enabled")
    
    logger.debug(f"Command arguments: repo_path={repo_path}, since={since}, until={until}, days={days}, by_author={by_author}")
    
    repo_path_obj = Path(repo_path)
    if not repo_path_obj.exists():
        logger.error(f"Repository path '{repo_path}' does not exist")
        raise typer.Exit(1)

    if not (repo_path_obj / ".git").exists():
        logger.error(f"'{repo_path}' is not a git repository")
        raise typer.Exit(1)

    logger.info(f"Analyzing git repository: {repo_path}")

    try:
        logger.debug(f"Initializing GitCommitRetriever for path: {repo_path_obj}")
        retriever = GitCommitRetriever(str(repo_path_obj))

        if days is not None:
            logger.info(f"Retrieving commits from the last {days} days...")
            commits = retriever.get_recent_commits(days)
        else:
            if since or until:
                date_info: list[str] = []
                if since:
                    date_info.append(f"since {since}")
                if until:
                    date_info.append(f"until {until}")
                logger.info(f"Retrieving commits {' '.join(date_info)}...")
            else:
                logger.info("Retrieving commits from the last 7 days...")
                commits = retriever.get_recent_commits(7)

            if since or until:
                commits = retriever.get_commits(since=since, until=until)
            else:
                commits = retriever.get_recent_commits(7)

        if not commits:
            logger.warning("No commits found in the specified date range.")
            return

        logger.info(f"Found {len(commits)} commits. Generating summary...")

        if by_author:
            logger.debug("Grouping commits by author")
            author_commits = group_commits_by_author(commits)
            logger.info(f"Found {len(author_commits)} unique authors")
            
            logger.debug("Generating author-specific summaries")
            summary = summarize_by_author(author_commits)
            
            print("\n" + "=" * 60)
            print("GIT RECAP SUMMARY - BY AUTHOR")
            print("=" * 60)
            print(summary)
            print("=" * 60)
        else:
            logger.debug("Formatting commits for LLM processing")
            commits_text = format_commits_for_llm(commits)
            logger.debug("Calling LLM for summary generation")
            summary = summarize_with_llm(commits_text)

            print("\n" + "=" * 50)
            print("GIT RECAP SUMMARY")
            print("=" * 50)
            print(summary)
            print("=" * 50)

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
