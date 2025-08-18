from dataclasses import dataclass
import os
from dotenv import load_dotenv
load_dotenv()


@dataclass
class Config:
    TELEGRAM_TOKEN: str = os.environ["TELEGRAM_TOKEN"]
    MY_CHAT_ID: int = int(os.environ["MY_CHAT_ID"])
    OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]