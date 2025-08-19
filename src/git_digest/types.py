from enum import Enum


class Provider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    COHERE = "cohere"
    ANTHROPIC = "anthropic"
