from git_recap.types import Provider

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
