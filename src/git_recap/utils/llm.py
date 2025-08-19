import logging
import os

import typer
from openai import OpenAI

from git_recap.const import PROVIDERS
from git_recap.types import Provider
from git_recap.utils.git import GitCommit

logger = logging.getLogger(__name__)


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


def summarize_with_llm(
    commits_text: str, provider: Provider, repo_names: list[str]
) -> str:
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
This author worked across {repo_count} repositories: {", ".join(sorted(author_repos))}.
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
