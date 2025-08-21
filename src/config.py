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

    HOME_ASSISTANT_AGENT_MODEL: str = "google/gemini-2.0-flash-001"
    HOME_ASSISTNAT_TOKEN: str = os.environ["HOME_ASSISTANT_TOKEN"]
    HOME_ASSISTANT_BASE_URL: str = os.environ["HOME_ASSISTANT_BASE_URL"]

    POSTGRES_DB_NAME: str = os.environ["POSTGRES_DB_NAME"]
    POSTGRES_DB_USER: str = os.environ["POSTGRES_DB_USER"]
    POSTGRES_DB_PASSWORD: str = os.environ["POSTGRES_DB_PASSWORD"]
    POSTGRES_DB_HOST: str = os.environ["POSTGRES_DB_HOST"]
    POSTGRES_DB_PORT: str = os.environ["POSTGRES_DB_PORT"]

    JOURNAL_REMINDER_TIME: str = os.environ["JOURNAL_REMINDER_TIME"]