# git-recap

[![PyPI version](https://badge.fury.io/py/git-recap.svg)](https://badge.fury.io/py/git-recap)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

Summarize recent Git contributions into clear, human-readable updates using AI. Perfect
for standup meetings, progress reports, and understanding what happened in your
repositories.

## Features

- 🤖 **AI-Powered Summaries**: Uses Cohere, OpenAI or Anthropic to generate intelligent summaries
- 📁 **Multi-Repository Support**: Analyze multiple repositories simultaneously
- 👥 **Author Filtering**: Focus on specific contributors' work
- 📅 **Flexible Date Ranges**: Filter by date, days, or commit count
- 🎯 **Two Summary Modes**: Chronological overview or grouped by author
- 🔍 **Cross-Repository Analysis**: Identify related work across multiple projects
- 📊 **Detailed Logging**: Track what's being analyzed with debug mode

## Installation

### Using pip

```bash
pip install git-recap
```

### Using uv (recommended)

```bash
uv add git-recap
```

### From source

```bash
git clone https://github.com/your-username/git-recap.git
cd git-recap
uv sync
```

## Setup

You'll need an API key for one of the supported LLM providers:

### OpenAI

```bash
export OPENAI_API_KEY="your-api-key-here"
```

### Cohere (default)

```bash
export COHERE_API_KEY="your-api-key-here"
```

### Anthropic

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

## Quick Start

```bash
# Summarize the current repository (last 7 days)
git-recap .

# Summarize multiple repositories
git-recap /path/to/repo1 /path/to/repo2

# Use a specific LLM provider
git-recap . --provider openai

# Get commits from a specific time period
git-recap . --since "2024-01-01" --until "2024-01-31"

# Focus on specific authors
git-recap . --authors "alice,bob"

# Group summary by author instead of chronological
git-recap . --by-author
```

## Usage Examples

### Basic Usage

```bash
# Analyze current directory (default: last 7 days)
git-recap .

# Analyze specific repository
git-recap /path/to/my/project

# Multiple repositories
git-recap ~/projects/frontend ~/projects/backend ~/projects/mobile
```

### Time Filtering

```bash
# Last N days
git-recap . --days 14

# Last N commits
git-recap . --count 50

# Specific date range
git-recap . --since "2024-01-01" --until "2024-01-31"

# Natural language dates
git-recap . --since "last monday" --until "yesterday"
git-recap . --since "1 week ago"
```

### Author Filtering

```bash
# Single author (partial matching, case-insensitive)
git-recap . --authors alice

# Multiple authors
git-recap . --authors alice,bob,charlie

# Or using multiple flags
git-recap . --authors alice --authors bob
```

### Summary Modes

```bash
# Chronological overview (default)
git-recap .

# Group by author
git-recap . --by-author

# Author-focused analysis with time filter
git-recap . --by-author --days 30 --authors "alice,bob"
```

### Advanced Examples

```bash
# Debug mode with detailed logging
git-recap . --debug

# Multi-repo analysis for the last 2 weeks using OpenAI
git-recap ~/projects/* --days 14 --provider openai --debug

# Focus on recent work by specific team members
git-recap . --days 7 --authors "alice,bob,charlie" --by-author

# Last 25 commits across multiple repos
git-recap ~/frontend ~/backend --count 25
```

## Command Line Options

| Option        | Short | Description                                                      |
| ------------- | ----- | ---------------------------------------------------------------- |
| `repo_paths`  |       | Paths to git repositories to analyze (required)                  |
| `--since`     | `-s`  | Start date (e.g., '2024-01-01', '1 week ago', 'yesterday')       |
| `--until`     | `-u`  | End date (e.g., '2024-01-31', 'today')                           |
| `--days`      | `-d`  | Get commits from the last N days (overrides since/until)         |
| `--count`     | `-c`  | Get the last N commits (overrides since/until/days)              |
| `--authors`   |       | Filter commits by author names (supports comma-separated values) |
| `--by-author` |       | Group summary by author instead of chronological overview        |
| `--provider`  |       | LLM provider: openai, cohere (default), anthropic                |
| `--debug`     |       | Enable debug logging                                             |
| `--help`      |       | Show help message                                                |

## Supported LLM Providers

| Provider             | Default Model            | Environment Variable |
| -------------------- | ------------------------ | -------------------- |
| **Cohere** (default) | command-a-03-2025        | `COHERE_API_KEY`     |
| **OpenAI**           | gpt-5                    | `OPENAI_API_KEY`     |
| **Anthropic**        | claude-opus-4-1-20250805 | `ANTHROPIC_API_KEY`  |

## Sample Output

### Chronological Mode

```
==================================================
GIT RECAP SUMMARY
==================================================
Based on the recent commits from your repository, here's what's been happening:

## Key Development Activities

**Feature Development**
- Implemented user authentication system with JWT tokens
- Added password reset functionality with email verification
- Created user profile management interface

**Bug Fixes & Improvements**
- Fixed memory leak in data processing pipeline
- Improved error handling in API endpoints
- Enhanced logging for better debugging

**Infrastructure & Maintenance**
- Updated dependencies to latest stable versions
- Added comprehensive test coverage for auth module
- Set up automated deployment pipeline

The development focus has been on strengthening the authentication system while maintaining code quality through better testing and monitoring.
==================================================
```

### By-Author Mode

```
============================================================
GIT RECAP SUMMARY - BY AUTHOR
============================================================
## Alice Johnson <alice@company.com> (15 commits)

Alice focused on the authentication system overhaul, implementing JWT-based login, password reset functionality, and user profile management. She also enhanced the API security by adding proper input validation and rate limiting. Her work established a solid foundation for user management features.

## Bob Smith <bob@company.com> (8 commits)

Bob concentrated on infrastructure improvements, updating the CI/CD pipeline and adding comprehensive test coverage. He also fixed several critical bugs in the data processing module and improved overall system performance through caching optimizations.

## Charlie Brown <charlie@company.com> (5 commits)

Charlie worked on frontend enhancements, improving the user interface for the new authentication features and fixing responsive design issues. He also contributed to the documentation updates and helped with code review processes.
============================================================
```

## Environment Variables

All environment variables are optional but at least one LLM provider API key is required:

- `OPENAI_API_KEY` - OpenAI API key
- `COHERE_API_KEY` - Cohere API key
- `ANTHROPIC_API_KEY` - Anthropic API key

## Error Handling

git-recap provides helpful error messages for common issues:

- **Missing API keys**: Clear instructions on which environment variable to set
- **Invalid repositories**: Identifies which paths are not valid git repositories
- **Network issues**: Graceful handling of API connectivity problems
- **Empty results**: Informative messages when no commits match your criteria

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Install development dependencies: `uv sync --dev`
4. Install pre-commit hooks: `uv run pre-commit install`
5. Make your changes and add tests
6. Run the test suite: `uv run pytest`
7. Run linting: `uv run ruff check && uv run pyright`
8. Pre-commit hooks will automatically run on commit, or manually: `uv run pre-commit run --all-files`
9. Submit a pull request

## Development

```bash
# Clone and setup
git clone https://github.com/your-username/git-recap.git
cd git-recap
uv sync --dev

# Install pre-commit hooks
uv run pre-commit install

# Run from source
uv run git-recap . --help

# Run tests
uv run pytest

# Format and lint
uv run ruff format
uv run ruff check
uv run pyright

# Run all pre-commit checks
uv run pre-commit run --all-files
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
