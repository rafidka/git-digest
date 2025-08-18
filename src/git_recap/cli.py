import os
from pathlib import Path

import typer
from openai import OpenAI

from .git_utils import GitCommitRetriever

app = typer.Typer()


def get_cohere_client() -> OpenAI:
    """Initialize Cohere client using OpenAI SDK."""
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        typer.echo("Error: COHERE_API_KEY environment variable not set", err=True)
        raise typer.Exit(1)

    return OpenAI(base_url="https://api.cohere.ai/compatibility/v1", api_key=api_key)


def format_commits_for_llm(commits) -> str:
    """Format git commits for LLM processing."""
    if not commits:
        return "No commits found in the specified date range."

    formatted = []
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

        return response.choices[0].message.content.strip()

    except Exception as e:
        typer.echo(f"Error calling Cohere API: {str(e)}", err=True)
        raise typer.Exit(1)


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
):
    """
    Generate a human-readable summary of recent git commits.
    """
    repo_path_obj = Path(repo_path)
    if not repo_path_obj.exists():
        typer.echo(f"Error: Repository path '{repo_path}' does not exist", err=True)
        raise typer.Exit(1)

    if not (repo_path_obj / ".git").exists():
        typer.echo(f"Error: '{repo_path}' is not a git repository", err=True)
        raise typer.Exit(1)

    typer.echo(f"Analyzing git repository: {repo_path}")

    try:
        retriever = GitCommitRetriever(str(repo_path_obj))

        if days is not None:
            typer.echo(f"Retrieving commits from the last {days} days...")
            commits = retriever.get_recent_commits(days)
        else:
            if since or until:
                date_info = []
                if since:
                    date_info.append(f"since {since}")
                if until:
                    date_info.append(f"until {until}")
                typer.echo(f"Retrieving commits {' '.join(date_info)}...")
            else:
                typer.echo("Retrieving commits from the last 7 days...")
                commits = retriever.get_recent_commits(7)

            if since or until:
                commits = retriever.get_commits(since=since, until=until)

        if not commits:
            typer.echo("No commits found in the specified date range.")
            return

        typer.echo(f"Found {len(commits)} commits. Generating summary...")

        commits_text = format_commits_for_llm(commits)
        summary = summarize_with_llm(commits_text)

        typer.echo("\n" + "=" * 50)
        typer.echo("GIT RECAP SUMMARY")
        typer.echo("=" * 50)
        typer.echo(summary)
        typer.echo("=" * 50)

    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
