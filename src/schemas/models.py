import os

from pydantic import BaseModel, Field


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


class LLMParameters(BaseModel):

    llm_model: str = Field(default_factory=lambda: _env("LLM_MODEL", "gpt-4o-mini"))
    llm_base_url: str = Field(
        default_factory=lambda: _env("LLM_BASE_URL", "https://api.openai.com/v1")
    )
    llm_api_key: str = Field(default_factory=lambda: _env("LLM_API_KEY", ""))
    llm_app_id: str = Field(default_factory=lambda: _env("LLM_APP_ID", ""))
