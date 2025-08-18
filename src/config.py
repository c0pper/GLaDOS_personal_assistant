from dataclasses import dataclass
import os
from dotenv import load_dotenv
load_dotenv()


@dataclass
class Config:
    TELEGRAM_TOKEN: str = os.environ["TELEGRAM_TOKEN"]
    MY_CHAT_ID: int = int(os.environ["MY_CHAT_ID"])
    OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
    OPENROUTER_API_KEY: str = os.environ["OPENROUTER_API_KEY"]
    SEARXNG_URL: str = os.environ["SEARXNG_URL"]

    ORCHESTRATOR_AGENT_MODEL: str = "mistralai/devstral-small"
    RESPONDER_AGENT_MODEL: str = "openai/gpt-4o-mini"

    VIKUNJA_BASE_URL: str = os.environ["VIKUNJA_BASE_URL"]
    VIKUNJA_TOKEN: str = os.environ["VIKUNJA_TOKEN"]
    VIKUNJA_AGENT_MODEL: str = "google/gemini-2.0-flash-001"